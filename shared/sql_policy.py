"""Restricted local analytics execution; not a tenant or OS sandbox."""
import threading

import duckdb
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from shared.execution import current_budget

SCHEMA = {
    'logs': dict.fromkeys(['timestamp', 'severity', 'service_name', 'trace_id', 'body',
                          'environment', 'app_id', 'department', 'host', 'region', 'context'], 'UNKNOWN'),
    'system_catalog': dict.fromkeys(['system_name', 'department', 'owner_email', 'criticality'], 'UNKNOWN'),
}
FUNCTIONS = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'NULLIF', 'CAST', 'TRY_CAST',
             'LOWER', 'UPPER', 'LENGTH', 'ABS', 'ROUND', 'CEIL', 'FLOOR', 'SUBSTRING',
             'TRIM', 'CONCAT', 'CONCAT_WS', 'JSON_EXTRACT', 'JSON_EXTRACT_SCALAR',
             'DATE_TRUNC', 'TIMESTAMP_TRUNC', 'DATE_DIFF', 'TIMESTAMP_DIFF', 'EXTRACT',
             'CURRENT_TIMESTAMP', 'CURRENT_DATE', 'NOW', 'TODAY', 'ROW_NUMBER', 'RANK',
             'DENSE_RANK', 'LAG', 'LEAD', 'IF', 'CASE'}


class SQLPolicyError(ValueError):
    pass


def validate_query(sql):
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 20000:
        raise SQLPolicyError('SQL must be nonempty and at most 20000 characters')
    try:
        statements = sqlglot.parse(sql, read='duckdb')
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            raise SQLPolicyError('Only one SELECT analytics statement is allowed')
        tree = statements[0]
        if any(node.args.get('recursive') for node in tree.find_all(exp.With)) or tree.find(exp.Into):
            raise SQLPolicyError('Recursive queries and SELECT INTO are not allowed')
        ctes = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
        for table in tree.find_all(exp.Table):
            if (not isinstance(table.this, exp.Identifier) or table.db or table.catalog or
                    table.name.lower() not in set(SCHEMA) | ctes):
                raise SQLPolicyError('Only approved local tables are allowed')
        # Resolve each scope: a CTE name in an unrelated nested scope must not
        # authorize an actual table with that name elsewhere in the statement.
        for scope in traverse_scope(tree):
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table) and source.name.lower() not in SCHEMA:
                    raise SQLPolicyError('Only approved local tables are allowed')
        for function in tree.find_all(exp.Func):
            name = function.name.upper() if isinstance(function, exp.Anonymous) else function.sql_name()
            if name not in FUNCTIONS:
                raise SQLPolicyError('SQL function is not approved: ' + name)
        # Expand stars against approved columns and validate references through CTEs/aliases.
        tree = qualify(tree, dialect='duckdb', schema=SCHEMA, infer_schema=False)
        return tree.sql(dialect='duckdb')
    except SQLPolicyError:
        raise
    except Exception:
        raise SQLPolicyError('SQL could not be validated against approved tables and columns')


def execute_query(path, sql, params=None, *, explain=False, max_rows=1000, timeout=5.0):
    statement = validate_query(sql)
    if not 1 <= max_rows <= 10000 or not 0 < timeout <= 30:
        raise SQLPolicyError('Invalid executor limits')
    budget = current_budget()
    if budget is not None:
        timeout = min(timeout, budget.remaining())
    conn = duckdb.connect(path, read_only=True, config={'enable_external_access': False,
        'autoinstall_known_extensions': False, 'autoload_known_extensions': False})
    timer = None
    expired = threading.Event()
    try:
        conn.execute("SET memory_limit='256MB'")
        conn.execute("SET temp_directory=''")
        conn.execute('SET threads=1')
        conn.execute('SET lock_configuration=true')
        def interrupt():
            expired.set()
            conn.interrupt()
        timer = threading.Timer(timeout, interrupt)
        timer.daemon = True
        timer.start()
        query = 'EXPLAIN ' + statement if explain else f'SELECT * FROM ({statement}) AS bounded_result LIMIT {max_rows + 1}'
        rows = conn.execute(query, params or []).fetchmany(max_rows + 1)
        if expired.is_set():
            raise SQLPolicyError('SQL execution deadline exceeded')
        if len(rows) > max_rows:
            raise SQLPolicyError('SQL result exceeds the allowed row limit; narrow the query')
        if budget is not None:
            budget.check()
        return rows
    except duckdb.InterruptException:
        raise SQLPolicyError('SQL execution deadline exceeded')
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        conn.close()
