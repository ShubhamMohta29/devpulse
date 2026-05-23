# Technical Requirements Document (TRD)

> DevPulse — Engineering Health Intelligence Agent
> Hackathon Track: Fivetran | Version 1.0 | May 2026

---

## 2.1 System Architecture Summary

DevPulse is composed of four layers: the data ingestion layer (Fivetran), the data warehouse (BigQuery), the agent runtime (Google ADK + Gemini), and the interface layer (CLI / Slack webhook). Each layer is independently replaceable.

---

## 2.2 Tech Stack

| Layer | Technology | Justification |
| --- | --- | --- |
| Data pipeline | Fivetran (GitHub + Jira connectors) | Managed, reliable, no-code ELT |
| Data warehouse | Google BigQuery | Native Fivetran destination, SQL at scale |
| Agent framework | Google ADK (Agent Development Kit) | First-class Gemini support, tool use |
| LLM | Gemini 1.5 Pro / Flash | Instruction-following, function calling |
| Pipeline control | Fivetran MCP server | Agent-native connector introspection |
| BQ access | google-cloud-bigquery Python SDK | Direct SQL over synced tables |
| Interface | GUI + optional Slack webhook | Better user experience |
| Config | YAML + env vars | Portable, no secrets in code |

---

## 2.3 Agent Design

### 2.3.1 Agent Runtime

The agent is built with Google ADK. It runs as a Python process that accepts user queries via stdin (CLI mode) or HTTP POST (Slack mode). The agent maintains a short in-memory conversation history (last 10 turns) and calls tools as needed to answer each query.

### 2.3.2 Tool Definitions

| Tool name | Source | Description |
| --- | --- | --- |
| check_connector_status | Fivetran MCP | Returns last sync time and status for GitHub and Jira connectors |
| trigger_sync | Fivetran MCP | Triggers an ad-hoc sync for a given connector ID |
| list_connectors | Fivetran MCP | Lists all connectors in the Fivetran account |
| query_open_prs | BigQuery SDK | Returns open PRs older than N days with author and reviewer info |
| query_commit_velocity | BigQuery SDK | Returns daily commit counts for the last N days |
| query_stale_tickets | BigQuery SDK | Returns Jira tickets in a given status older than N days |
| query_sprint_health | BigQuery SDK | Returns sprint burn-down and scope change metrics |
| detect_anomalies | BigQuery SDK | Computes z-score deviations vs rolling baselines, returns anomalies |
| write_digest | BigQuery SDK | Writes a daily digest record to the agent_digests table |
| generate_trend_report | BigQuery SDK | Aggregates multi-week trend data and returns structured report |

### 2.3.3 System Prompt

The agent's system prompt defines its persona, constraints, and decision logic. Key rules encoded in the prompt:

- Always call `check_connector_status` before answering any data question
- If any connector is stale (>4 hours), prepend a staleness warning to the answer
- Never present individual developer performance metrics — aggregate only
- When anomalies are detected, include severity and recommended next action
- All SQL queries must include a time filter to avoid full-table scans

---

## 2.4 Data Flow

1. Fivetran syncs GitHub and Jira data to BigQuery on a 1-hour cadence.
2. A scheduled Cloud Run job runs the daily digest generator at 08:00.
3. User sends a query via GUI or Slack.
4. Agent calls `check_connector_status` via Fivetran MCP.
5. Agent routes the query to one or more BigQuery tools.
6. BigQuery executes parameterised SQL queries.
7. Agent synthesises the results and returns a natural-language answer.
8. If the answer contains a new insight, `write_digest` is called to persist it.

---

## 2.5 Infrastructure Requirements

| Component | Requirement |
| --- | --- |
| Fivetran account | Free trial (14 days); GitHub + Jira connectors enabled |
| BigQuery project | Google Cloud project with BigQuery API enabled; Fivetran service account with BQ write permissions |
| Fivetran MCP server | Node.js 18+; run via `npx fivetran-mcp`; `FIVETRAN_API_KEY` env var set |
| Agent runtime | Python 3.11+; `google-adk`, `google-cloud-bigquery`, `python-dotenv` installed |
| Cloud Run (optional) | For scheduled digest job and Slack webhook endpoint |
| Gemini API | `GOOGLE_API_KEY` or Vertex AI credentials |

---

## 2.6 Security

- All API keys stored in environment variables, never in source code
- Fivetran API key scoped to read + trigger-sync only
- BigQuery service account scoped to the `devpulse` dataset only
- No PII stored — GitHub usernames are hashed in the `agent_digests` table
- Slack webhook URL stored in Secret Manager if deployed to Cloud Run

---

## 2.7 Observability

- Agent logs all tool calls with timestamp, tool name, and latency to stdout
- BigQuery query costs are logged per query for budget tracking
- Fivetran sync failures trigger an alert via the Fivetran MCP status response
- A `devpulse_agent_logs` BigQuery table stores every agent interaction for audit