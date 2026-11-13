"""Export Oracle schema metadata (no table rows or credentials) to CSV and JSON.

Usage:
  export ORACLE_USER=...
  export ORACLE_PASSWORD=...
  export ORACLE_DSN=localhost:1521/FREEPDB1
  python export_schema.py --schemas HR CO OE SH BI PM
"""
import argparse
import csv
import json
import os
from pathlib import Path

import oracledb

SQL = {
    "tables": """
        SELECT owner, table_name, num_rows, last_analyzed
        FROM all_tables
        WHERE owner = :owner
        ORDER BY table_name
    """,
    "columns": """
        SELECT owner, table_name, column_id, column_name, data_type,
               data_length, data_precision, data_scale, nullable,
               data_default, char_length
        FROM all_tab_columns
        WHERE owner = :owner
        ORDER BY table_name, column_id
    """,
    "constraints": """
        SELECT owner, table_name, constraint_name, constraint_type,
               status, validated, search_condition_vc,
               r_owner, r_constraint_name, delete_rule
        FROM all_constraints
        WHERE owner = :owner AND constraint_type IN ('P','U','R','C')
        ORDER BY table_name, constraint_name
    """,
    "constraint_columns": """
        SELECT owner, table_name, constraint_name, column_name, position
        FROM all_cons_columns
        WHERE owner = :owner
        ORDER BY table_name, constraint_name, position
    """,
    "foreign_keys": """
        SELECT fk.owner, fk.table_name, fk.constraint_name,
               fkc.column_name, fkc.position,
               pk.owner AS referenced_owner, pk.table_name AS referenced_table,
               pkc.column_name AS referenced_column,
               fk.delete_rule
        FROM all_constraints fk
        JOIN all_cons_columns fkc
          ON fk.owner=fkc.owner AND fk.constraint_name=fkc.constraint_name
        JOIN all_constraints pk
          ON pk.owner=fk.r_owner AND pk.constraint_name=fk.r_constraint_name
        JOIN all_cons_columns pkc
          ON pk.owner=pkc.owner AND pk.constraint_name=pkc.constraint_name
         AND pkc.position=fkc.position
        WHERE fk.owner=:owner AND fk.constraint_type='R'
        ORDER BY fk.table_name, fk.constraint_name, fkc.position
    """,
}


def query_rows(connection, sql, owner):
    with connection.cursor() as cur:
        cur.execute(sql, owner=owner)
        headers = [col[0].lower() for col in cur.description]
        rows = []
        for record in cur:
            row = {}
            for key, value in zip(headers, record):
                if hasattr(value, "read"):
                    value = value.read()
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                row[key] = str(value) if value is not None else None
            rows.append(row)
        return headers, rows


def save_csv(path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Export Oracle schema metadata only")
    parser.add_argument("--schemas", nargs="+", required=True, help="Schema owners, e.g. HR CO")
    parser.add_argument("--out", default="schema", help="Output directory (default: schema)")
    args = parser.parse_args()

    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")
    if not all((user, password, dsn)):
        parser.error("Set ORACLE_USER, ORACLE_PASSWORD and ORACLE_DSN environment variables")

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    with oracledb.connect(user=user, password=password, dsn=dsn) as conn:
        for original in args.schemas:
            owner = original.strip().upper()
            if not owner or not all(c.isalnum() or c in "_$#" for c in owner):
                parser.error(f"Invalid schema name: {original!r}")
            target = out_root / owner
            target.mkdir(parents=True, exist_ok=True)
            payload = {"schema": owner}
            for name, sql in SQL.items():
                headers, rows = query_rows(conn, sql, owner)
                save_csv(target / f"{name}.csv", headers, rows)
                payload[name] = rows
                print(f"{owner}/{name}: {len(rows)} rows")
            (target / "metadata.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    print(f"Metadata export complete: {out_root.resolve()}")


if __name__ == "__main__":
    main()
