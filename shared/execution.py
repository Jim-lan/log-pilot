"""Request-local execution limits shared by graph nodes and provider adapters."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import copy
import math
import os
import threading
import time
from shared.tracing import RequestTrace


class ExecutionFailure(Exception):
    code = "dependency_error"
    status = 502
    message = "A required provider could not complete the request."

    def __init__(self):
        super().__init__(self.message)


class DeadlineExceeded(ExecutionFailure):
    code, status = "deadline_exceeded", 504
    message = "The request deadline was exceeded. Narrow the query and try again."


class CallBudgetExceeded(ExecutionFailure):
    code, status = "call_budget_exceeded", 429
    message = "The request exhausted its provider-call budget. Narrow the query and try again."


class ProviderTimeout(ExecutionFailure):
    code, status = "provider_timeout", 504
    message = "A required provider timed out. Please try again."


class SQLExecutionFailure(ExecutionFailure):
    code, status = 'sql_execution_failed', 422
    message = 'The SQL query could not execute within the allowed policy and limits. Narrow the query and try again.'


def setting(name, default, cast=float):
    value = cast(os.getenv(name, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return value


class RequestBudget:
    def __init__(self, timeout, max_llm_calls, max_search_calls=1, clock=time.monotonic):
        self.clock = clock
        self.trace = RequestTrace(clock)
        self.deadline = clock() + timeout
        self.limits = {"llm": max_llm_calls, "search": max_search_calls}
        self.calls = {"llm": 0, "search": 0}
        self.provenance = {"model_calls": [], "templates": {}}
        self.failure = None
        self.lock = threading.RLock()

    def provenance_snapshot(self):
        with self.lock:
            return copy.deepcopy(self.provenance)

    @classmethod
    def from_env(cls):
        return cls(setting("LOGPILOT_REQUEST_TIMEOUT_SECONDS", 120),
                   setting("LOGPILOT_MAX_LLM_CALLS", 16, int),
                   setting("LOGPILOT_MAX_SEARCH_CALLS", 1, int))

    def check(self):
        with self.lock:
            if self.failure is not None:
                raise self.failure
            if self.clock() >= self.deadline:
                self.failure = DeadlineExceeded()
                raise self.failure

    def remaining(self):
        self.check()
        return max(0, self.deadline - self.clock())

    def fail(self, failure):
        with self.lock:
            if self.failure is None:
                self.failure = failure
            raise self.failure

    def cancel(self):
        with self.lock:
            if self.failure is None:
                self.failure = DeadlineExceeded()

    def begin_call(self, kind, timeout):
        with self.lock:
            self.check()
            if self.calls.get(kind, 0) >= self.limits.get(kind, 1):
                self.fail(CallBudgetExceeded())
            self.calls[kind] = self.calls.get(kind, 0) + 1
            return min(timeout, self.remaining())


_active_budget = ContextVar("logpilot_request_budget", default=None)


def current_budget():
    return _active_budget.get()


@contextmanager
def use_budget(budget):
    token = _active_budget.set(budget)
    try:
        yield budget
    finally:
        _active_budget.reset(token)


def check_budget():
    budget = current_budget()
    if budget is not None:
        budget.check()


def guarded_node(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        budget = current_budget()
        if budget is None:
            return fn(*args, **kwargs)
        with budget.trace.span('node', fn.__name__) as event:
            check_budget()
            result = fn(*args, **kwargs)
            # Caught provider failures must not become successful evidence.
            check_budget()
            budget.trace.node_result(event, fn.__name__, result)
            return result
    return run


def invoke_provider(kind, operation):
    budget = current_budget() or RequestBudget.from_env()
    with budget.trace.span('provider', kind):
        timeout = budget.begin_call(kind, setting(
            "LOGPILOT_SEARCH_TIMEOUT_SECONDS" if kind == "search" else "LOGPILOT_LLM_TIMEOUT_SECONDS",
            10 if kind == "search" else 30))
        started = budget.clock()
        try:
            result = operation(timeout)
        except ExecutionFailure as failure:
            budget.fail(failure)
        except Exception as error:
            budget.check()
            # Provider SDKs use different timeout exception types; preserve only a
            # sanitized category, never upstream bodies, URLs or credentials.
            failure = ProviderTimeout() if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.lower() else ExecutionFailure()
            budget.fail(failure)
        budget.check()
        if budget.clock() - started >= timeout:
            budget.fail(ProviderTimeout())
        return result
