from core.duckdb_runner import execute_on_source, format_df
from core.redshift_runner import execute_on_redshift
from core.validators import validate_select_only
from config import IS_PROD, MAX_SQL_LEN


def query_source(
    sql:      str,
    username: str = None,
    password: str = None,
) -> str:
    if len(sql) > MAX_SQL_LEN:
        return f"Query too long (max {MAX_SQL_LEN} chars)."

    is_valid, reason = validate_select_only(sql)
    if not is_valid:
        return f"Query rejected: {reason}"

    try:
        if IS_PROD:
            df = execute_on_redshift(sql, username, password)
        else:
            df = execute_on_source(sql)
        return format_df(df)
    except Exception as e:
        return f"Error: {str(e)}"
