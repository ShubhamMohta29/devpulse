-- DevPulse: BigQuery Views
-- All views use CREATE OR REPLACE so they are safe to re-run.
-- {project} and {dataset} are substituted at deploy time.

-- ── v_open_prs_aged ────────────────────────────────────────────────────────
-- Open PRs with age in days, bucketed. Joins in latest review state per PR.
CREATE OR REPLACE VIEW `{project}.{dataset}.v_open_prs_aged` AS
SELECT
  pr.id,
  pr.repo_name,
  pr.number                                              AS pr_number,
  pr.title,
  pr.author_login,
  pr.created_at,
  pr.updated_at,
  pr.review_requested_at,
  DATE_DIFF(CURRENT_DATE(), DATE(pr.created_at), DAY)   AS age_days,
  CASE
    WHEN DATE_DIFF(CURRENT_DATE(), DATE(pr.created_at), DAY) < 1  THEN '<1d'
    WHEN DATE_DIFF(CURRENT_DATE(), DATE(pr.created_at), DAY) < 3  THEN '1-3d'
    WHEN DATE_DIFF(CURRENT_DATE(), DATE(pr.created_at), DAY) < 7  THEN '3-7d'
    ELSE '>7d'
  END                                                    AS age_bucket,
  last_review.reviewer_login                             AS last_reviewer,
  last_review.state                                      AS last_review_state,
  last_review.submitted_at                               AS last_reviewed_at
FROM
  `{project}.{dataset}.github_pull_requests` pr
LEFT JOIN (
  SELECT
    pull_request_id,
    reviewer_login,
    state,
    submitted_at,
    ROW_NUMBER() OVER (PARTITION BY pull_request_id ORDER BY submitted_at DESC) AS rn
  FROM `{project}.{dataset}.github_reviews`
) last_review ON pr.id = last_review.pull_request_id AND last_review.rn = 1
WHERE
  pr.state = 'open';

-- ── v_commit_velocity_daily ────────────────────────────────────────────────
-- Daily commit count, additions, and deletions per repository.
CREATE OR REPLACE VIEW `{project}.{dataset}.v_commit_velocity_daily` AS
SELECT
  DATE(committed_at)      AS commit_date,
  repo_name,
  COUNT(*)                AS commit_count,
  SUM(additions)          AS additions_sum,
  SUM(deletions)          AS deletions_sum
FROM
  `{project}.{dataset}.github_commits`
WHERE
  committed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
GROUP BY
  1, 2;

-- ── v_ticket_age_by_status ─────────────────────────────────────────────────
-- Age of each open Jira ticket grouped by current status.
CREATE OR REPLACE VIEW `{project}.{dataset}.v_ticket_age_by_status` AS
SELECT
  id,
  key,
  project_key,
  summary,
  issue_type,
  status,
  priority,
  assignee_id,
  sprint_id,
  story_points,
  created_at,
  updated_at,
  DATE_DIFF(CURRENT_DATE(), DATE(created_at), DAY)  AS age_days,
  DATE_DIFF(CURRENT_DATE(), DATE(updated_at), DAY)  AS days_since_update
FROM
  `{project}.{dataset}.jira_issues`
WHERE
  resolved_at IS NULL;

-- ── v_sprint_burndown ──────────────────────────────────────────────────────
-- Story points completed vs remaining for the active sprint.
CREATE OR REPLACE VIEW `{project}.{dataset}.v_sprint_burndown` AS
SELECT
  s.id                  AS sprint_id,
  s.name                AS sprint_name,
  s.start_date,
  s.end_date,
  s.state               AS sprint_state,
  COUNT(i.id)           AS total_tickets,
  SUM(i.story_points)   AS total_points,
  SUM(CASE WHEN i.status = 'Done'  THEN COALESCE(i.story_points, 0) ELSE 0 END) AS points_completed,
  SUM(CASE WHEN i.status != 'Done' THEN COALESCE(i.story_points, 0) ELSE 0 END) AS points_remaining,
  COUNT(CASE WHEN i.status = 'Done'     THEN 1 END) AS tickets_done,
  COUNT(CASE WHEN i.status = 'Blocked'  THEN 1 END) AS tickets_blocked,
  DATE_DIFF(s.end_date, CURRENT_DATE(), DAY)         AS days_remaining,
  SAFE_DIVIDE(
    SUM(CASE WHEN i.status = 'Done' THEN COALESCE(i.story_points, 0) ELSE 0 END),
    NULLIF(SUM(i.story_points), 0)
  ) * 100                                            AS pct_complete
FROM
  `{project}.{dataset}.jira_sprints` s
LEFT JOIN
  `{project}.{dataset}.jira_issues` i ON i.sprint_id = s.id
WHERE
  s.state = 'active'
GROUP BY
  1, 2, 3, 4, 5;

-- ── v_metric_baselines ─────────────────────────────────────────────────────
-- Rolling 30-day mean and stddev per metric, used by detect_anomalies.
CREATE OR REPLACE VIEW `{project}.{dataset}.v_metric_baselines` AS
WITH commit_daily AS (
  SELECT
    'commit_count'      AS metric_name,
    CAST(commit_count AS FLOAT64) AS metric_value,
    commit_date
  FROM `{project}.{dataset}.v_commit_velocity_daily`
  WHERE commit_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
pr_age AS (
  SELECT
    'pr_age_days'       AS metric_name,
    CAST(age_days AS FLOAT64) AS metric_value,
    DATE(created_at)    AS commit_date
  FROM `{project}.{dataset}.v_open_prs_aged`
  WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
ticket_age AS (
  SELECT
    CONCAT('ticket_age_', LOWER(REPLACE(status, ' ', '_'))) AS metric_name,
    CAST(age_days AS FLOAT64) AS metric_value,
    DATE(created_at)          AS commit_date
  FROM `{project}.{dataset}.v_ticket_age_by_status`
  WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
),
all_metrics AS (
  SELECT * FROM commit_daily
  UNION ALL SELECT * FROM pr_age
  UNION ALL SELECT * FROM ticket_age
)
SELECT
  metric_name,
  AVG(metric_value)    AS baseline_mean,
  STDDEV(metric_value) AS baseline_stddev,
  MIN(metric_value)    AS min_value,
  MAX(metric_value)    AS max_value,
  COUNT(*)             AS sample_count
FROM all_metrics
GROUP BY metric_name;
