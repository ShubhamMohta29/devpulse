# Product Requirements Document (PRD)

> DevPulse — Engineering Health Intelligence Agent
> Hackathon Track: Fivetran | Version 1.0 | May 2026

---

## 1.1 Product Overview

| Field | Detail |
| --- | --- |
| **Product name** | DevPulse |
| **Version** | 1.0 — Hackathon MVP |
| **Track** | Fivetran |
| **Owner** | Team (hackathon) |
| **Last updated** | May 2026 |

---

## 1.2 Problem Statement

Engineering teams generate enormous amounts of operational data — every pull request, every Jira ticket, every sprint, every code review — but almost none of it is analysed in a timely or systematic way. Managers rely on intuition, ad-hoc spreadsheets, or expensive BI tools to understand what is happening inside their engineering organisation. The lag between data and insight is typically days or weeks, by which time bottlenecks have already compounded into missed deadlines.

The core problems DevPulse solves:

- PR review bottlenecks go undetected until a sprint is already at risk
- Commit velocity drops are invisible until retrospectives surface them too late
- Jira tickets stuck in 'In Progress' for abnormal durations create hidden debt
- Sprint scope creep is identified manually by project managers, not automatically
- There is no unified, AI-readable surface that combines GitHub and Jira signals

---

## 1.3 Goals & Success Criteria

| Goal | Metric | Target |
| --- | --- | --- |
| Surface PR bottlenecks | Avg time-to-detection of stale PRs | < 24 hours |
| Detect velocity anomalies | Anomalies caught vs manual review | > 90% |
| Reduce triage time | Time spent in daily standups on status | -40% |
| Conversational access | Questions answered without dashboard navigation | 80%+ |
| Fivetran reliability | Sync success rate | > 99% |

---

## 1.4 Non-Goals

- DevPulse does not manage or assign Jira tickets — it only reads and analyses them
- It does not replace existing project management tools
- It does not write code or create PRs
- Performance reviews and individual developer scoring are explicitly out of scope

---

## 1.5 Target Users

| Persona | Role | Primary need |
| --- | --- | --- |
| Engineering Manager | Oversees team delivery | Weekly health digest, anomaly alerts |
| Tech Lead | Owns architecture & code quality | PR review lag, recurring blockers |
| Scrum Master | Facilitates sprints | Scope creep detection, ticket age analysis |
| Developer | Ships code | Self-service: 'where are my PRs sitting?' |

---

## 1.6 Feature List

### F-01 Daily Engineering Digest

Automated summary generated every morning at 08:00 covering: open PRs by age bucket, commit velocity vs prior week, tickets in abnormal states, sprint burn-down status. Delivered as a structured markdown report queryable by the agent.

### F-02 Anomaly Detection

The agent compares rolling 7-day and 30-day baselines for key metrics. When a metric deviates beyond a configurable threshold (default: 2 standard deviations), an anomaly record is written to BigQuery and surfaced to the user.

- Supported metrics: PR age, commit frequency, ticket age by status, review response time
- Anomaly severity: low / medium / high based on deviation magnitude

### F-03 Conversational Q&A

The agent accepts natural-language questions over the synced data. Examples:

- "Which PRs have been waiting more than 5 days for review?"
- "How many commits did we land this week vs last week?"
- "Which Jira tickets have been In Progress for more than 2 weeks?"
- "Is our current sprint on track?"

### F-04 Fivetran Sync Status Awareness

Before answering any data question, the agent queries the Fivetran MCP server to find the latest successful sync time for each connector.

### F-05 Trend Reports

On-demand and periodic (weekly / monthly depending on the user's choice) trend report generation covering a configurable time window. Output includes: PR merge rate, review cycle time, ticket completion rate, sprint velocity over time. Reports are written back to BigQuery for historical comparison.

---

## 1.7 Fivetran Track Alignment

| Requirement | How DevPulse satisfies it |
| --- | --- |
| Use Fivetran to move data | GitHub + Jira connectors sync to BigQuery on a 1-hour schedule |
| Leverage the Fivetran MCP server | Agent uses MCP tools to check connector status and trigger ad-hoc syncs |
| Build an agent on top of synced data | Gemini-powered agent queries BigQuery for all analysis |
| Demonstrate trust in the data foundation | Agent explicitly checks sync freshness before every answer |
| Use BigQuery as destination | All synced data and agent-generated insights land in BigQuery |