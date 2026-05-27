"""Realistic fixture data that matches the BigQuery schema exactly.

All tools check MOCK_MODE=true and return from here instead of hitting
real BigQuery / Fivetran. Gives the agent realistic data to reason over.
"""

from datetime import datetime, timedelta, timezone

_NOW = datetime.now(timezone.utc)
_DAY = timedelta(days=1)


# ── Fivetran connector status ──────────────────────────────────────────────

CONNECTOR_STATUS = {
    "github": {
        "connector_id": "mock-github-connector-001",
        "name": "GitHub — acme-corp",
        "service": "github",
        "status": "active",
        "last_successful_sync_at": (_NOW - timedelta(minutes=42)).isoformat(),
        "is_stale": False,
    },
    "jira": {
        "connector_id": "mock-jira-connector-001",
        "name": "Jira — ACME Engineering",
        "service": "jira",
        "status": "active",
        "last_successful_sync_at": (_NOW - timedelta(minutes=38)).isoformat(),
        "is_stale": False,
    },
}

CONNECTORS_LIST = list(CONNECTOR_STATUS.values())


# ── Open PRs ──────────────────────────────────────────────────────────────

OPEN_PRS = [
    {
        "pr_number": 247,
        "title": "feat: add GitHub OAuth flow",
        "author_login": "dev-alice",
        "repo_name": "acme-corp/backend",
        "age_days": 8,
        "age_bucket": ">7d",
        "last_reviewer": "dev-bob",
        "last_review_state": "CHANGES_REQUESTED",
        "last_reviewed_at": (_NOW - _DAY * 6).isoformat(),
        "created_at": (_NOW - _DAY * 8).isoformat(),
    },
    {
        "pr_number": 251,
        "title": "fix: race condition in cache invalidation",
        "author_login": "dev-charlie",
        "repo_name": "acme-corp/backend",
        "age_days": 5,
        "age_bucket": "3-7d",
        "last_reviewer": None,
        "last_review_state": None,
        "last_reviewed_at": None,
        "created_at": (_NOW - _DAY * 5).isoformat(),
    },
    {
        "pr_number": 254,
        "title": "chore: upgrade dependencies to latest",
        "author_login": "dev-alice",
        "repo_name": "acme-corp/frontend",
        "age_days": 3,
        "age_bucket": "3-7d",
        "last_reviewer": "dev-diana",
        "last_review_state": "COMMENTED",
        "last_reviewed_at": (_NOW - _DAY * 2).isoformat(),
        "created_at": (_NOW - _DAY * 3).isoformat(),
    },
    {
        "pr_number": 255,
        "title": "feat: dashboard redesign — phase 1",
        "author_login": "dev-diana",
        "repo_name": "acme-corp/frontend",
        "age_days": 1,
        "age_bucket": "1-3d",
        "last_reviewer": None,
        "last_review_state": None,
        "last_reviewed_at": None,
        "created_at": (_NOW - _DAY * 1).isoformat(),
    },
]


# ── Commit velocity ────────────────────────────────────────────────────────

def _commit_velocity(days: int = 7):
    rows = []
    repos = ["acme-corp/backend", "acme-corp/frontend"]
    counts = [4, 7, 3, 8, 5, 2, 9, 6, 4, 3, 7, 5, 2, 8]
    for i in range(days):
        for repo in repos:
            rows.append({
                "commit_date": ((_NOW - _DAY * (days - i)).date()).isoformat(),
                "repo_name": repo,
                "commit_count": counts[(i * 2 + repos.index(repo)) % len(counts)],
                "additions_sum": counts[(i * 2 + repos.index(repo)) % len(counts)] * 23,
                "deletions_sum": counts[(i * 2 + repos.index(repo)) % len(counts)] * 7,
            })
    return rows

COMMIT_VELOCITY_7D = _commit_velocity(7)
COMMIT_VELOCITY_14D = _commit_velocity(14)


# ── Stale Jira tickets ────────────────────────────────────────────────────

STALE_TICKETS = {
    "In Progress": [
        {
            "key": "ENG-412",
            "summary": "Migrate user service to microservices architecture",
            "status": "In Progress",
            "issue_type": "Story",
            "priority": "High",
            "assignee_id": "user-charlie",
            "sprint_id": "sprint-22",
            "story_points": 8.0,
            "age_days": 18,
            "days_since_update": 4,
        },
        {
            "key": "ENG-389",
            "summary": "Fix intermittent test failures in CI pipeline",
            "status": "In Progress",
            "issue_type": "Bug",
            "priority": "Medium",
            "assignee_id": "user-alice",
            "sprint_id": "sprint-22",
            "story_points": 3.0,
            "age_days": 22,
            "days_since_update": 7,
        },
    ],
    "In Review": [
        {
            "key": "ENG-441",
            "summary": "Add rate limiting to public API endpoints",
            "status": "In Review",
            "issue_type": "Task",
            "priority": "High",
            "assignee_id": "user-bob",
            "sprint_id": "sprint-22",
            "story_points": 5.0,
            "age_days": 14,
            "days_since_update": 2,
        },
    ],
    "Blocked": [
        {
            "key": "ENG-403",
            "summary": "Integrate payment provider v2 SDK",
            "status": "Blocked",
            "issue_type": "Story",
            "priority": "Highest",
            "assignee_id": "user-diana",
            "sprint_id": "sprint-22",
            "story_points": 13.0,
            "age_days": 12,
            "days_since_update": 5,
        },
    ],
}


# ── Sprint health ─────────────────────────────────────────────────────────

SPRINT_HEALTH = {
    "sprint_id": "sprint-22",
    "sprint_name": "Sprint 22",
    "sprint_state": "active",
    "start_date": (_NOW - _DAY * 7).date().isoformat(),
    "end_date": (_NOW + _DAY * 7).date().isoformat(),
    "total_tickets": 18,
    "total_points": 68.0,
    "points_completed": 29.0,
    "points_remaining": 39.0,
    "tickets_done": 7,
    "tickets_blocked": 1,
    "days_remaining": 7,
    "pct_complete": 42.6,
    "scope_change_pct": 8.3,
    "is_on_track": False,
}


# ── Anomalies ─────────────────────────────────────────────────────────────

ANOMALIES = [
    {
        "metric_name": "pr_age_days",
        "metric_value": 8.0,
        "baseline_mean": 3.2,
        "baseline_stddev": 1.8,
        "z_score": 2.67,
        "severity": "medium",
        "entity_type": "repo",
        "entity_id": "acme-corp/backend",
    },
    {
        "metric_name": "ticket_age_in_progress",
        "metric_value": 22.0,
        "baseline_mean": 7.5,
        "baseline_stddev": 4.1,
        "z_score": 3.54,
        "severity": "high",
        "entity_type": "ticket",
        "entity_id": "ENG-389",
    },
]
