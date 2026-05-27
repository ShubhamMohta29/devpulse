-- DevPulse: Agent-managed table DDL
-- Run via: python schema/deploy_schema.py
-- These tables are WRITTEN by the agent. GitHub/Jira tables are managed by Fivetran.

-- ── agent_digests ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.agent_digests` (
  digest_id       STRING    NOT NULL,
  generated_at    TIMESTAMP NOT NULL,
  digest_date     DATE      NOT NULL,
  open_pr_count   INT64,
  stale_pr_count  INT64,
  commit_count_7d      INT64,
  commit_count_prev_7d INT64,
  anomaly_count   INT64,
  anomaly_summary STRING,   -- JSON array of top anomaly dicts
  sprint_on_track BOOL,
  narrative       STRING,   -- agent-generated markdown summary
  model_used      STRING
);

-- ── agent_anomalies ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.agent_anomalies` (
  anomaly_id      STRING    NOT NULL,
  detected_at     TIMESTAMP NOT NULL,
  metric_name     STRING    NOT NULL,  -- e.g. pr_age_days, commit_count
  metric_value    FLOAT64,
  baseline_mean   FLOAT64,
  baseline_stddev FLOAT64,
  z_score         FLOAT64,
  severity        STRING,   -- low | medium | high
  entity_type     STRING,   -- repo | ticket | sprint
  entity_id       STRING,
  resolved_at     TIMESTAMP           -- null if still active
);

-- ── agent_logs ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `{project}.{dataset}.agent_logs` (
  log_id              STRING    NOT NULL,
  session_id          STRING    NOT NULL,
  logged_at           TIMESTAMP NOT NULL,
  user_query          STRING,
  tools_called        STRING,   -- JSON array of tool names
  bq_bytes_processed  INT64,
  latency_ms          INT64,
  model_used          STRING,
  response_preview    STRING    -- first 500 chars of response
);
