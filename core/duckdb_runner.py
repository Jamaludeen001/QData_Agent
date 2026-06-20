import duckdb
import pandas as pd
from pathlib import Path
from functools import lru_cache
from config import TEMP_FOLDER, SOURCE_FOLDER, MAX_DF_ROWS


def format_df(df: pd.DataFrame) -> str:
    if df.empty:
        return "Query returned no rows."
    truncated = len(df) > MAX_DF_ROWS
    return (
        f"Rows: {len(df)}{' (showing first 50)' if truncated else ''}\n\n"
        + df.head(MAX_DF_ROWS).to_string(index=False)
    )


@lru_cache(maxsize=64)
def get_schema(csv_path: str) -> str:
    conn = duckdb.connect(database=":memory:")
    try:
        df = conn.execute(
            f"DESCRIBE SELECT * FROM read_csv_auto('{csv_path}', header=True)"
        ).fetchdf()
        return "\n".join(
            f"    {row['column_name']} ({row['column_type']})"
            for _, row in df.iterrows()
        )
    finally:
        conn.close()


def _register_all_sources(conn: duckdb.DuckDBPyConnection):
    """
    Creates DuckDB schemas and registers CSV files as views.
    Enables natural dot notation: schema.table
    """
    for schema_dir in SOURCE_FOLDER.iterdir():
        if schema_dir.is_dir():
            schema_name = schema_dir.name
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            for csv_file in schema_dir.glob("*.csv"):
                table_name = csv_file.stem
                conn.execute(
                    f"CREATE VIEW {schema_name}.{table_name} AS "
                    f"SELECT * FROM read_csv_auto('{csv_file}', header=True)"
                )


def execute_on_source(sql: str) -> pd.DataFrame:
    conn = duckdb.connect(database=":memory:")
    try:
        _register_all_sources(conn)
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def get_full_schema() -> str:
    lines = []
    for schema_dir in sorted(SOURCE_FOLDER.iterdir()):
        if schema_dir.is_dir():
            schema_name = schema_dir.name
            lines.append(f"Schema: {schema_name}")
            for csv_file in sorted(schema_dir.glob("*.csv")):
                table_name = csv_file.stem
                col_schema = get_schema(str(csv_file))
                try:
                    row_count = duckdb.execute(
                        f"SELECT COUNT(*) FROM read_csv_auto('{csv_file}', header=True)"
                    ).fetchone()[0]
                except Exception:
                    row_count = "?"
                lines.append(f"  Table    : {table_name}")
                lines.append(f"  SQL name : {schema_name}.{table_name}")
                lines.append(f"  Rows     : {row_count:,}")
                lines.append(f"  Columns  :")
                lines.append(col_schema)
                lines.append("")
    return "\n".join(lines)


def execute_on_temp(sql: str, session_id: str) -> pd.DataFrame:
    db_path = TEMP_FOLDER / f"session_{session_id}.db"
    conn    = duckdb.connect(database=str(db_path))
    try:
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def load_into_temp(session_id: str, table_name: str, sql: str) -> int:
    source_conn = duckdb.connect(database=":memory:")
    try:
        _register_all_sources(source_conn)
        df = source_conn.execute(sql).fetchdf()
    finally:
        source_conn.close()

    db_path   = TEMP_FOLDER / f"session_{session_id}.db"
    temp_conn = duckdb.connect(database=str(db_path))
    try:
        temp_conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM df"
        )
        count = temp_conn.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
        return count
    finally:
        temp_conn.close()


def cleanup_session(session_id: str):
    db_path = TEMP_FOLDER / f"session_{session_id}.db"
    if db_path.exists():
        db_path.unlink()
