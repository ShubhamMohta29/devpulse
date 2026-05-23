# Application Flow

> DevPulse — Engineering Health Intelligence Agent
> Hackathon Track: Fivetran | Version 1.0 | May 2026

---

## 3.1 Primary Flow: User Query

The following describes the step-by-step execution path when a user sends a question to DevPulse.

| Step | Actor | Action | Output |
| --- | --- | --- | --- |
| 1 | User | Types query in CLI or sends Slack message | Raw text query |
| 2 | Agent | Receives query, initialises conversation turn | Query in context window |
| 3 | Agent → MCP | Calls `check_connector_status` for GitHub connector | Last sync time, status |
| 4 | Agent → MCP | Calls `check_connector_status` for Jira connector | Last sync time, status |
| 5 | Agent | Evaluates staleness; prepends warning if >4 hours | Staleness flag |
| 6 | Agent | Routes query to appropriate BigQuery tool(s) | Tool call(s) |
| 7 | BigQuery | Executes parameterised SQL, returns rows | Structured result set |
| 8 | Agent | Synthesises result into natural-language answer | Draft answer |
| 9 | Agent | If new insight detected, calls `write_digest` | Digest record in BQ |
| 10 | Agent | Returns final answer to user | Formatted response |
| 11 | Logger | Writes interaction record to `agent_logs` table | Audit trail entry |

---

## 3.2 Secondary Flow: Daily Digest

A Cloud Run job (or local cron) runs at 08:00 daily and produces the engineering health digest without any user query.

1. Job starts, authenticates to Fivetran MCP and BigQuery
2. Calls `list_connectors` to confirm all sources are active
3. Calls `detect_anomalies` across all metric categories
4. Calls `query_open_prs` with a 3-day threshold
5. Calls `query_commit_velocity` for the past 7 days
6. Calls `query_sprint_health` for the active sprint
7. Synthesises all results into a structured digest
8. Calls `write_digest` to persist the record
9. Optionally posts digest to Slack via webhook

---

## 3.3 Tertiary Flow: Ad-hoc Sync Trigger

When a user asks a time-sensitive question and the connector is stale, the agent offers to trigger a fresh sync.

1. Agent detects staleness (>4 hours) from `check_connector_status`
2. Agent informs user: *"GitHub data is 6 hours old. Shall I trigger a fresh sync?"*
3. User confirms
4. Agent calls `trigger_sync` with the GitHub connector ID
5. Agent polls `check_connector_status` every 30 seconds until sync completes or times out (5 min)
6. Agent proceeds with the original query once fresh data is available

---

## 3.4 Error Handling

| Error condition | Agent behaviour |
| --- | --- |
| Fivetran MCP unreachable | Agent answers from cached BQ data; warns user that sync status is unavailable |
| BigQuery query timeout | Agent returns partial results with a note; logs the failed query |
| Gemini API rate limit | Exponential backoff up to 3 retries; then returns a graceful error message |
| No data found for query | Agent explicitly states no matching records rather than hallucinating |
| Connector sync failure | Agent surfaces the Fivetran error code and suggests manual investigation |