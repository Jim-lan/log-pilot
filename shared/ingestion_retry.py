"""Conservative retry classification; unknown failures require operator review."""
import sqlite3
from shared.execution import ExecutionFailure


def retryable_ingestion_failure(error):
    if isinstance(error, ExecutionFailure):
        return error.code in ('provider_timeout', 'dependency_error')
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    if isinstance(error, sqlite3.OperationalError):
        return any(word in str(error).lower() for word in ('locked', 'busy'))
    return False
