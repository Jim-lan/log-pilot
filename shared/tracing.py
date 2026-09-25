"""Bounded execution metadata only; no model/user content or exception text."""
from contextlib import contextmanager
from contextvars import ContextVar
import threading
import uuid

_ACTIVE_STAGE = ContextVar('logpilot_trace_stage', default=None)
FAILURE_CODES = frozenset({
    'dependency_error', 'deadline_exceeded', 'call_budget_exceeded', 'provider_timeout',
    'sql_execution_failed', 'query_capacity_exhausted', 'internal_error',
    'validation_rejected', 'retrieval_unavailable', 'web_search_disabled',
    'web_search_unavailable', 'insufficient_evidence',
})


class RequestTrace:
    version = 2

    def __init__(self, clock, max_spans=256):
        self.clock = clock
        self.started = clock()
        self.request_id = uuid.uuid4().hex
        self.max_spans = max(1, max_spans)
        self.lock = threading.RLock()
        self.events = []
        self.attempts = {}
        self.dropped = 0
        self.root = self.begin('request', 'query')

    def begin(self, kind, name):
        with self.lock:
            if len(self.events) >= self.max_spans:
                self.dropped += 1
                return None
            key = (kind, name)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            parent = _ACTIVE_STAGE.get()
            if parent is None or parent[0] != self.request_id:
                parent_id = self.events[0]['stage_id'] if self.events else None
            else:
                parent_id = parent[1]
            event = dict(request_id=self.request_id, stage_id=f'{self.request_id}:{len(self.events) + 1}',
                         parent_stage_id=parent_id, kind=kind, stage=name, attempt=self.attempts[key],
                         start_ms=max(0, (self.clock() - self.started) * 1000), duration_ms=None,
                         outcome='running', failure_code=None)
            self.events.append(event)
            return event

    def finish(self, event, outcome='succeeded', failure_code=None):
        if event is None:
            return
        with self.lock:
            if event['outcome'] != 'running':
                return
            event['duration_ms'] = max(0, (self.clock() - self.started) * 1000 - event['start_ms'])
            event['outcome'] = outcome if outcome in ('succeeded', 'failed', 'rejected', 'abstained', 'skipped') else 'failed'
            event['failure_code'] = failure_code if isinstance(failure_code, str) and failure_code in FAILURE_CODES else ('internal_error' if failure_code else None)

    @contextmanager
    def span(self, kind, name):
        event = self.begin(kind, name)
        token = _ACTIVE_STAGE.set((self.request_id, event['stage_id'])) if event else None
        try:
            yield event
        except BaseException as error:
            self.finish(event, 'failed', getattr(error, 'code', 'internal_error'))
            raise
        else:
            self.finish(event)
        finally:
            if token is not None:
                _ACTIVE_STAGE.reset(token)

    def snapshot(self):
        with self.lock:
            return [dict(event) for event in self.events]

    def metadata(self):
        with self.lock:
            return dict(request_id=self.request_id, trace_version=self.version, trace_dropped=self.dropped)

    def node_result(self, event, name, result):
        if not isinstance(result, dict):
            return
        validation = {'validate_sql': 'sql_valid', 'verify_context': 'context_valid', 'validate_answer': 'answer_valid'}
        if name in validation and result.get(validation[name]) is not True:
            self.finish(event, 'rejected', 'validation_rejected')
        elif name == 'perform_web_search' and result.get('failure_reason'):
            self.finish(event, 'failed', result['failure_reason'])
        elif name == 'retrieve_context' and str(result.get('rag_context', '')).startswith('Error retrieving context:'):
            self.finish(event, 'failed', 'retrieval_unavailable')
        elif name == 'finish_unverified':
            self.finish(event, 'abstained', result.get('failure_reason') or 'insufficient_evidence')
