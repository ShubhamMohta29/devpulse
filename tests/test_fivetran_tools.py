"""Unit tests for tools/fivetran_tools.py.

All tests run in MOCK_MODE so they need no real Fivetran account.
HTTP-path tests use pytest-mock to patch httpx.Client.
"""

import os

import pytest


# ── Mock mode tests (no credentials needed) ────────────────────────────────

class TestCheckConnectorStatusMock:
    def setup_method(self):
        os.environ["MOCK_MODE"] = "true"

    def teardown_method(self):
        os.environ.pop("MOCK_MODE", None)

    def test_returns_github_connector(self):
        from tools.fivetran_tools import check_connector_status
        result = check_connector_status("mock-github-connector-001")
        assert result["connector_id"] == "mock-github-connector-001"
        assert result["service"] == "github"
        assert "last_successful_sync_at" in result
        assert isinstance(result["is_stale"], bool)

    def test_returns_jira_connector(self):
        from tools.fivetran_tools import check_connector_status
        result = check_connector_status("mock-jira-connector-001")
        assert result["service"] == "jira"

    def test_unknown_connector_returns_stale(self):
        from tools.fivetran_tools import check_connector_status
        result = check_connector_status("nonexistent-connector")
        assert result["is_stale"] is True


class TestListConnectorsMock:
    def setup_method(self):
        os.environ["MOCK_MODE"] = "true"

    def teardown_method(self):
        os.environ.pop("MOCK_MODE", None)

    def test_returns_list(self):
        from tools.fivetran_tools import list_connectors
        result = list_connectors()
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_each_connector_has_required_keys(self):
        from tools.fivetran_tools import list_connectors
        for connector in list_connectors():
            assert "connector_id" in connector
            assert "status" in connector
            assert "is_stale" in connector


class TestTriggerSyncMock:
    def setup_method(self):
        os.environ["MOCK_MODE"] = "true"

    def teardown_method(self):
        os.environ.pop("MOCK_MODE", None)

    def test_returns_success(self):
        from tools.fivetran_tools import trigger_sync
        result = trigger_sync("any-connector-id")
        assert result["success"] is True
        assert "sync_completed_at" in result
        assert "Mock mode" in result.get("note", "")


# ── HTTP path tests (Fivetran REST API mocked with httpx) ──────────────────

class TestCheckConnectorStatusHTTP:
    def setup_method(self):
        os.environ.pop("MOCK_MODE", None)
        os.environ["FIVETRAN_API_KEY"]    = "test-key"
        os.environ["FIVETRAN_API_SECRET"] = "test-secret"

    def teardown_method(self):
        os.environ.pop("FIVETRAN_API_KEY", None)
        os.environ.pop("FIVETRAN_API_SECRET", None)

    def test_active_connector(self, mocker):
        from datetime import datetime, timezone, timedelta
        mock_resp = mocker.MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "service": "github",
                "schema":  "github_acme",
                "succeeded_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
                "status": {"sync_state": "scheduled"},
            }
        }
        mock_resp.raise_for_status = mocker.MagicMock()
        mocker.patch("httpx.Client.get", return_value=mock_resp)

        from tools.fivetran_tools import check_connector_status
        result = check_connector_status("conn-123")
        assert result["connector_id"] == "conn-123"
        assert result["is_stale"] is False

    def test_stale_connector(self, mocker):
        from datetime import datetime, timezone, timedelta
        mock_resp = mocker.MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "service": "jira",
                "schema":  "jira_acme",
                "succeeded_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
                "status": {"sync_state": "scheduled"},
            }
        }
        mock_resp.raise_for_status = mocker.MagicMock()
        mocker.patch("httpx.Client.get", return_value=mock_resp)

        from tools.fivetran_tools import check_connector_status
        result = check_connector_status("conn-456")
        assert result["is_stale"] is True

    def test_mcp_unreachable_returns_graceful_dict(self, mocker):
        import httpx as _httpx
        mocker.patch("httpx.Client.get", side_effect=_httpx.ConnectError("refused"))

        from tools.fivetran_tools import check_connector_status
        result = check_connector_status("conn-789")
        assert result["status"] == "unreachable"
        assert result["is_stale"] is True
        assert "error" in result
