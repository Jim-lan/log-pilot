# Restricted SQL execution

## Decision and scope

Model-generated SQL and MCP `query_logs` now use `DuckDBConnector.query_analytics`. Trusted application-owned queries retain the internal `query` interface for ingestion and schema operations. Syntax validation uses the same analytics policy before EXPLAIN, since binding an external reader can itself access a file. MCP recent logs also uses the restricted executor; fixed schema introspection remains internal.

SQLGlot 26.33.0 parses exactly one SELECT/set-operation statement. The policy permits only the documented `logs` and `system_catalog` columns and explicitly approved scalar/aggregate functions. It resolves CTE scopes, rejects database-qualified names and external table functions, expands stars against approved columns and checks column references. Unknown functions fail closed. This intentionally narrows accepted SQL; add supported analytics through policy review and regression fixtures, not a bypass flag.

Execution opens a read-only DuckDB connection with external access and extension autoload/autoinstall disabled. It sets 256 MB engine memory, one execution thread, no temporary spill directory, then locks configuration. It permits at most 1000 returned rows and interrupts execution after five seconds or the remaining request budget, whichever is shorter. Excess rows produce an error rather than a silently truncated answer. Timers are cancelled/joined before closing the connection; a subsequent query can run after cancellation.

Engine controls follow [DuckDB's security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview) and [extension controls](https://duckdb.org/docs/current/operations_manual/securing_duckdb/securing_extensions). Every selected setting was also executed against this project's pinned DuckDB 1.1.3; current documentation alone is not proof of compatibility with that version.

SQL execution failure stops graph synthesis and returns HTTP 422 with code `sql_execution_failed`. Existing request-budget failures retain their typed status. Validation failures still participate in bounded SQL repair; a failed execution is never supplied as successful empty evidence.

## Evidence and limits

Tests retain count, grouping, joins, JSON extraction, time filtering, CTEs and empty-result analytics. They reject file readers, attached databases, system tables, unknown columns, extension loading, configuration changes, mutation, multiple statements and misleading nested CTE scope. A test bypasses the parser deliberately and verifies DuckDB still refuses an external file. A real billion-combination aggregate is interrupted, then the same database answers a small query. MCP entry points and the graph's failure path are covered.

This is not complete Phase 3.2 or an OS sandbox. The database is assumed to have a trusted schema; approved names must not be replaced by attacker-controlled views/macros. All allowed columns remain visible to the local developer profile. Tenant row scope, authentication, process/filesystem isolation, response byte limits and bounded connection acquisition are not implemented here. DuckDB's memory setting does not bound all Python/process memory, and interrupt is cooperative rather than a forced process kill. Concurrent connection ownership/configuration and embedded-storage locks remain Phase 5 work. Those gates must pass before shared deployment.

## Rollout and learning

No schema migration, data rewrite or application restart is performed. Rebuild orchestrator and MCP images to install the pinned parser before deployment. Test a disposable deployment first. A newly rejected legitimate query should receive a reviewed allowlist extension and regression test; never restore raw model SQL execution as a rollback shortcut.

The learning point is the distinction between syntax validity, operation authorization and resource containment. A read-only database alone cannot prevent external reads, and a parsed allowlist alone cannot provide operating-system isolation.
