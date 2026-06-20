import duckdb
from core.duckdb_runner import get_schema, get_full_schema
from core.redshift_runner import get_redshift_schema
from core.pathguard import safe_path, list_available
from config import IS_PROD, SOURCE_FOLDER


def inspect_source_schema(
    schema:   str = None,
    filename: str = None,
    username: str = None,
    password: str = None,
) -> str:
    try:
        if IS_PROD:
            return get_redshift_schema(username, password)

        # No args — list everything
        if not schema and not filename:
            return get_full_schema()

        # Schema only — list tables in that schema
        if schema and not filename:
            schema_dir = SOURCE_FOLDER / schema
            if not schema_dir.exists():
                return list_available(SOURCE_FOLDER)
            lines = [f"Schema: {schema}\n"]
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
                lines.append(f"  SQL name : {schema}.{table_name}")
                lines.append(f"  Rows     : {row_count:,}")
                lines.append(f"  Columns  :")
                lines.append(col_schema)
                lines.append("")
            return "\n".join(lines)

        # Schema + filename — specific table
        if schema and filename:
            csv_path, err = safe_path(SOURCE_FOLDER, schema, filename)
            if csv_path is None:
                return err
            table_name = csv_path.stem
            col_schema = get_schema(str(csv_path))
            row_count  = duckdb.execute(
                f"SELECT COUNT(*) FROM read_csv_auto('{csv_path}', header=True)"
            ).fetchone()[0]
            return (
                f"Schema   : {schema}\n"
                f"Table    : {table_name}\n"
                f"SQL name : {schema}.{table_name}\n"
                f"Rows     : {row_count:,}\n"
                f"Columns  :\n{col_schema}"
            )

    except Exception as e:
        return f"Error: {str(e)}"
