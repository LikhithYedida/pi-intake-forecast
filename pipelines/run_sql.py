"""
Run the warehouse SQL against BigQuery, in file-number order.

  python pipelines/run_sql.py            # build clean (1x), mart (2x) and dashboard views (3x)
  python pipelines/run_sql.py --checks   # run sql/checks/mart_checks.sql and show results
  python pipelines/run_sql.py sql/21_*.sql   # run specific files only

Each file holds one CREATE OR REPLACE TABLE statement, so every run rebuilds
the tables from scratch. Re-running is always safe.
"""
import re
import sys
import time
from pathlib import Path

from google.cloud import bigquery

PROJECT = "pi-intake-forecast"
DEFAULT_PATTERNS = ["sql/1*.sql", "sql/2*.sql", "sql/3*.sql"]
CHECKS_FILE = Path("sql/checks/mart_checks.sql")


def build(client: bigquery.Client, patterns: list[str]) -> None:
    files = sorted({f for p in patterns for f in Path().glob(p)})
    if not files:
        raise SystemExit(f"No SQL files match {patterns}. Run from the project root.")
    for f in files:
        start = time.time()
        job = client.query(f.read_text(encoding="utf-8"))
        job.result()
        target = job.ddl_target_table
        name = f"{target.dataset_id}.{target.table_id}" if target else ""
        table = client.get_table(target) if target else None
        size = "view" if table is not None and table.table_type == "VIEW" else \
            f"{table.num_rows:,} rows" if table is not None else "-"
        print(f"  {f.name:40s} -> {name:34s} {size:>13s}  ({time.time() - start:.1f}s)")


def checks(client: bigquery.Client) -> None:
    text = CHECKS_FILE.read_text(encoding="utf-8")
    # statements end with ";" at the end of a line (comments never do)
    for block in [b.strip() for b in re.split(r";[ \t]*(?:--[^\n]*)?\n", text + "\n") if b.strip()]:
        lines = block.splitlines()
        title = next((l[3:].strip() for l in lines if re.match(r"-- Check \d", l)), "")
        expect = next((l[3:].strip() for l in lines if l.startswith("-- Expect")), "")
        sql = "\n".join(l for l in lines if not l.startswith("--")).strip()
        if not sql:
            continue
        row = list(client.query(sql).result())[0]
        print(f"\n{title}\n  {expect}\n  Got: {dict(row.items())}")


def main() -> None:
    client = bigquery.Client(project=PROJECT)
    args = sys.argv[1:]
    if args == ["--checks"]:
        checks(client)
    else:
        print("Building warehouse tables:")
        build(client, args or DEFAULT_PATTERNS)
        print("\nDone. Next: python pipelines/run_sql.py --checks")


if __name__ == "__main__":
    main()
