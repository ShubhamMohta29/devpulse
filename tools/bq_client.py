"""Shared BigQuery client factory.

Returns a real bigquery.Client in normal mode, or a lightweight mock
object (duck-typed) when MOCK_MODE=true. All tool code imports from
here so the mock swap is in exactly one place.
"""

import os
from typing import Any

_client: Any = None


def get_client():
    global _client
    if _client is not None:
        return _client

    if os.getenv("MOCK_MODE", "false").lower() == "true":
        from mock.mock_client import MockBigQueryClient
        _client = MockBigQueryClient()
    else:
        from google.cloud import bigquery
        project = os.getenv("GCP_PROJECT_ID")
        if not project:
            raise EnvironmentError("GCP_PROJECT_ID is not set in the environment.")
        _client = bigquery.Client(project=project)

    return _client


def reset_client() -> None:
    """Force the singleton to be recreated (useful in tests)."""
    global _client
    _client = None
