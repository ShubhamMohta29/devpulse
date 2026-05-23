# Data Structure & Schema

> DevPulse — Engineering Health Intelligence Agent
> Hackathon Track: Fivetran | Version 1.0 | May 2026

---

## 4.1 BigQuery Dataset Layout

All tables live in a single BigQuery dataset: `devpulse`. Tables prefixed with `github_` and `jira_` are written by Fivetran and should never be modified by the agent. Tables prefixed with `agent_` are written by the agent itself.

---

## 4.2 Fivetran-managed Tables (read-only)

### github_pull_requests

| Column | Type | Description |
| --- | --- | --- |
| id | STRING | GitHub PR ID (primary key) |
| repo_name | STRING | Repository full name (org/repo) |
| number | INTEGER | PR number within the repo |
| title | STRING | PR title |
| state | STRING | open │ closed │ merged |
| author_login | STRING | GitHub username of the author |
| created_at | TIMESTAMP | When the PR was opened |
| updated_at | TIMESTAMP | Last activity on the PR |
| merged_at | TIMESTAMP | When merged (null if not merged) |
| closed_at | TIMESTAMP | When closed (null if open) |
| review_requested_at | TIMESTAMP | When first review was requested |
| _fivetran_synced | TIMESTAMP | Last time Fivetran synced this row |

### github_commits

| Column | Type | Description |
| --- | --- | --- |
| sha | STRING | Commit SHA (primary key) |
| repo_name | STRING | Repository full name |
| author_login | STRING | GitHub username of committer |
| committed_at | TIMESTAMP | Commit timestamp |
| additions | INTEGER | Lines added |
| deletions | INTEGER | Lines deleted |
| message_summary | STRING | First line of commit message |
| _fivetran_synced | TIMESTAMP | Last Fivetran sync timestamp |

### github_reviews

| Column | Type | Description |
| --- | --- | --- |
| id | STRING | Review ID |
| pull_request_id | STRING | FK to github_pull_requests.id |
| reviewer_login | STRING | GitHub username of reviewer |
| state | STRING | APPROVED │ CHANGES_REQUESTED │ COMMENTED |
| submitted_at | TIMESTAMP | When the review was submitted |
| _fivetran_synced | TIMESTAMP | Last Fivetran sync timestamp |

### jira_issues

| Column | Type | Description |
| --- | --- | --- |
| id | STRING | Jira issue ID (primary key) |
| key | STRING | Issue key e.g. ENG-123 |
| project_key | STRING | Jira project identifier |
| summary | STRING | Issue title |
| issue_type | STRING | Story │ Bug │ Task │ Epic │ Sub-task |
| status | STRING | To Do │ In Progress │ In Review │ Done │ Blocked |
| priority | STRING | Highest │ High │ Medium │ Low │ Lowest |
| assignee_id | STRING | Jira account ID of assignee |
| reporter_id | STRING | Jira account ID of reporter |
| created_at | TIMESTAMP | Issue creation time |
| updated_at | TIMESTAMP | Last status change or update |
| resolved_at | TIMESTAMP | Resolution time (null if unresolved) |
| sprint_id | STRING | FK to jira_sprints.id (null if backlog) |
| story_points | FLOAT | Estimate in story points |
| _fivetran_synced | TIMESTAMP | Last Fivetran sync timestamp |

### jira_sprints

| Column | Type | Description |
| --- | --- | --- |
| id | STRING | Sprint ID (primary key) |
| name | STRING | Sprint name e.g. 'Sprint 42' |
| board_id | STRING | FK to the Jira board |
| state | STRING | active │ closed │ future |
| start_date | DATE | Sprint start date |
| end_date | DATE | Sprint planned end date |
| completed_date | DATE | Actual completion date (null if ongoing) |
| _fivetran_synced | TIMESTAMP | Last Fivetran sync timestamp |

---

## 4.3 Agent-managed Tables (read-write)

### agent_digests

| Column | Type | Description |
| --- | --- | --- |
| digest_id | STRING | UUID (primary key) |
| generated_at | TIMESTAMP | When this digest was produced |
| digest_date | DATE | The business day this digest covers |
| open_pr_count | INTEGER | Total open PRs at digest time |
| stale_pr_count | INTEGER | PRs open > 3 days without activity |
| commit_count_7d | INTEGER | Commits in the past 7 days |
| commit_count_prev_7d | INTEGER | Commits in the 7 days before that |
| anomaly_count | INTEGER | Number of anomalies detected |
| anomaly_summary | STRING | JSON array of top anomalies |
| sprint_on_track | BOOLEAN | Whether the active sprint is on track |
| narrative | STRING | Agent-generated natural-language summary |
| model_used | STRING | Gemini model version used for generation |

### agent_anomalies

| Column | Type | Description |
| --- | --- | --- |
| anomaly_id | STRING | UUID (primary key) |
| detected_at | TIMESTAMP | When the anomaly was flagged |
| metric_name | STRING | e.g. pr_age_days, commit_count, ticket_age_in_progress |
| metric_value | FLOAT | Observed value at detection time |
| baseline_mean | FLOAT | Rolling 30-day mean for this metric |
| baseline_stddev | FLOAT | Rolling 30-day standard deviation |
| z_score | FLOAT | Deviation magnitude (│z│ > 2 = anomaly) |
| severity | STRING | low │ medium │ high |
| entity_type | STRING | repo │ ticket │ sprint |
| entity_id | STRING | The specific repo/ticket/sprint affected |
| resolved_at | TIMESTAMP | When metric returned to normal (null if ongoing) |

### agent_logs

| Column | Type | Description |
| --- | --- | --- |
| log_id | STRING | UUID (primary key) |
| session_id | STRING | Groups all turns in one conversation |
| logged_at | TIMESTAMP | Timestamp of the interaction |
| user_query | STRING | Raw user input |
| tools_called | STRING | JSON array of tool names invoked |
| bq_bytes_processed | INTEGER | Total BigQuery bytes billed for this turn |
| latency_ms | INTEGER | Total wall-clock time in milliseconds |
| model_used | STRING | Gemini model version |
| response_preview | STRING | First 500 chars of agent response |

---

## 4.4 Key BigQuery Views

The agent uses parameterised views to avoid writing raw SQL in tool code. The following views are pre-deployed as part of the setup script.

| View name | Purpose | Underlying tables |
| --- | --- | --- |
| v_open_prs_aged | Open PRs with age in days, bucketed | github_pull_requests, github_reviews |
| v_commit_velocity_daily | Daily commit counts per repo | github_commits |
| v_ticket_age_by_status | Ticket age grouped by current status | jira_issues |
| v_sprint_burndown | Story points completed vs remaining by day | jira_issues, jira_sprints |
| v_metric_baselines | Rolling 30-day mean + stddev per metric | agent_anomalies, github_commits, jira_issues |

---

## 4.5 Fivetran Connector Configuration

| Connector | Fivetran schema | Sync frequency | Tables used |
| --- | --- | --- | --- |
| GitHub | github | 1 hour | pull_requests, commits, reviews, repositories |
| Jira | jira | 1 hour | issues, sprints, boards, users, issue_transitions |