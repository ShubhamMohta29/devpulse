"""Idempotent BigQuery schema deployer.

Usage:
    python schema/deploy_schema.py

Reads tables.sql and views.sql, substitutes {project} and {dataset},
then executes each statement. Uses CREATE TABLE IF NOT EXISTS and
CREATE OR REPLACE VIEW so it is safe to re-run at any time.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

_SCHEMA_DIR = Path(__file__).parent
_PROJECT    = os.getenv("GCP_PROJECT_ID", "")
_DATASET    = os.getenv("BQ_DATASET", "devpulse")


def _split_statements(sql: str) -> list[str]:
    """Split a SQL file into individual statements on semicolons."""
    # Strip comments, split on semicolons, discard blanks
    stripped = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in stripped.split(";") if s.strip()]


def deploy_schema(project_id: str, dataset_id: str) -> None:
    client = bigquery.Client(project=project_id)

    # Ensure dataset exists
    dataset_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
    dataset_ref.location = "US"
    try:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"[OK]  Dataset {project_id}.{dataset_id} ready")
    except Exception as exc:
        print(f"[ERR] Could not create dataset: {exc}", file=sys.stderr)
        raise

    for filename in ("tables.sql", "views.sql"):
        sql_path = _SCHEMA_DIR / filename
        raw_sql  = sql_path.read_text(encoding="utf-8")
        sql      = raw_sql.replace("{project}", project_id).replace("{dataset}", dataset_id)

        for statement in _split_statements(sql):
            # Extract a short label for the log line
            first_line = statement.splitlines()[0] if statement else ""
            label = first_line[:80].strip()
            try:
                client.query(statement).result()
                print(f"[OK]  {label}")
            except Exception as exc:
                print(f"[ERR] {label}\n      {exc}", file=sys.stderr)
                raise

    print("\nSchema deployment complete.")


if __name__ == "__main__":
    if not _PROJECT:
        sys.exit("ERROR: GCP_PROJECT_ID is not set. Add it to your .env file.")
    deploy_schema(_PROJECT, _DATASET)
