"""Placeholder BigQuery client for mock mode.

All tool functions in bq_tools.py short-circuit before calling this
when MOCK_MODE=true. This stub raises clearly if something reaches it
unexpectedly, so bugs are obvious rather than silent.
"""


class MockBigQueryClient:
    def query(self, sql: str, job_config=None):
        raise RuntimeError(
            "MockBigQueryClient.query() was called directly. "
            "All bq_tools.py functions must have an early-return mock path. "
            "Check that MOCK_MODE=true is set and the function handles it."
        )

    def insert_rows_json(self, table, rows):
        raise RuntimeError("MockBigQueryClient.insert_rows_json() called unexpectedly.")
