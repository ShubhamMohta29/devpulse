"""Unit tests for tools/bq_tools.py.

All tests run in MOCK_MODE so they need no real GCP project.
"""

import os

import pytest


def setup_module():
    os.environ["MOCK_MODE"]       = "true"
    os.environ["GCP_PROJECT_ID"]  = "test-project"
    os.environ["BQ_DATASET"]      = "devpulse"
    # Reset the BQ client singleton before each module
    from tools.bq_client import reset_client
    reset_client()


def teardown_module():
    for key in ("MOCK_MODE", "GCP_PROJECT_ID", "BQ_DATASET"):
        os.environ.pop(key, None)
    from tools.bq_client import reset_client
    reset_client()


class TestQueryOpenPRs:
    def test_returns_list(self):
        from tools.bq_tools import query_open_prs
        result = query_open_prs(min_age_days=0)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_age_filter(self):
        from tools.bq_tools import query_open_prs
        all_prs    = query_open_prs(min_age_days=0)
        stale_prs  = query_open_prs(min_age_days=5)
        assert len(stale_prs) <= len(all_prs)
        for pr in stale_prs:
            assert pr["age_days"] >= 5

    def test_result_has_required_keys(self):
        from tools.bq_tools import query_open_prs
        for pr in query_open_prs(min_age_days=0):
            assert "pr_number"    in pr
            assert "title"        in pr
            assert "author_login" in pr
            assert "age_days"     in pr


class TestQueryCommitVelocity:
    def test_returns_list(self):
        from tools.bq_tools import query_commit_velocity
        result = query_commit_velocity(days=7)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_result_has_required_keys(self):
        from tools.bq_tools import query_commit_velocity
        for row in query_commit_velocity(days=7):
            assert "commit_date"   in row
            assert "repo_name"     in row
            assert "commit_count"  in row

    def test_14d_returns_more_than_7d(self):
        from tools.bq_tools import query_commit_velocity
        rows_7  = query_commit_velocity(days=7)
        rows_14 = query_commit_velocity(days=14)
        assert len(rows_14) >= len(rows_7)


class TestQueryStaleTickets:
    def test_in_progress_tickets(self):
        from tools.bq_tools import query_stale_tickets
        result = query_stale_tickets(status="In Progress", min_age_days=0)
        assert isinstance(result, list)
        for ticket in result:
            assert ticket["status"] == "In Progress"

    def test_age_filter_applied(self):
        from tools.bq_tools import query_stale_tickets
        long_stale = query_stale_tickets(status="In Progress", min_age_days=20)
        for t in long_stale:
            assert t["age_days"] >= 20

    def test_empty_for_unknown_status(self):
        from tools.bq_tools import query_stale_tickets
        result = query_stale_tickets(status="NonExistentStatus", min_age_days=0)
        assert result == []


class TestQuerySprintHealth:
    def test_returns_dict(self):
        from tools.bq_tools import query_sprint_health
        result = query_sprint_health()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        from tools.bq_tools import query_sprint_health
        sprint = query_sprint_health()
        for key in ("sprint_name", "points_completed", "points_remaining", "is_on_track"):
            assert key in sprint


class TestDetectAnomalies:
    def test_returns_list(self):
        from tools.bq_tools import detect_anomalies
        result = detect_anomalies()
        assert isinstance(result, list)

    def test_anomaly_has_z_score(self):
        from tools.bq_tools import detect_anomalies
        for anomaly in detect_anomalies():
            assert "z_score"    in anomaly
            assert "severity"   in anomaly
            assert "metric_name" in anomaly


class TestWriteDigest:
    def test_returns_string_id(self):
        from tools.bq_tools import write_digest
        digest_id = write_digest({
            "digest_date": "2026-05-27",
            "open_pr_count": 4,
            "stale_pr_count": 2,
            "commit_count_7d": 42,
            "commit_count_prev_7d": 38,
            "anomaly_count": 1,
            "sprint_on_track": False,
            "narrative": "Test digest narrative.",
        })
        assert isinstance(digest_id, str)
        assert len(digest_id) == 36  # UUID length
