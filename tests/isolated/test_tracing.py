"""Structured traces report execution state without raw request/provider data."""
import unittest
from shared.execution import RequestBudget, use_budget, guarded_node, invoke_provider, ExecutionFailure
from shared.tracing import RequestTrace


class TraceContracts(unittest.TestCase):
    def test_nested_provider_parent_attempts_and_monotonic_timing(self):
        now = [10.0]
        budget = RequestBudget(30, 4, clock=lambda: now[0])
        @guarded_node
        def validate_answer(state):
            invoke_provider('llm', lambda timeout: 'private model output')
            now[0] += .25
            return {'answer_valid': False, 'answer_feedback': 'password=private'}
        with use_budget(budget):
            validate_answer({})
            validate_answer({})
        events = budget.trace.snapshot()
        nodes = [e for e in events if e['kind'] == 'node']
        providers = [e for e in events if e['kind'] == 'provider']
        self.assertEqual([e['attempt'] for e in nodes], [1, 2])
        self.assertEqual([e['attempt'] for e in providers], [1, 2])
        self.assertEqual([e['parent_stage_id'] for e in providers], [e['stage_id'] for e in nodes])
        self.assertEqual([e['duration_ms'] for e in nodes], [250, 250])
        self.assertTrue(all(e['outcome'] == 'rejected' for e in nodes))
        self.assertNotIn('private', str(events))
        self.assertEqual(len({e['stage_id'] for e in events}), len(events))

    def test_caught_failure_remains_failed_and_budget_denial_has_own_event(self):
        budget = RequestBudget(30, 1)
        @guarded_node
        def synthesize_answer(state):
            try:
                invoke_provider('llm', lambda timeout: (_ for _ in ()).throw(RuntimeError('secret upstream body')))
            except ExecutionFailure:
                pass
            return {'final_answer': 'false success'}
        with use_budget(budget), self.assertRaises(ExecutionFailure):
            synthesize_answer({})
        events = budget.trace.snapshot()[1:]
        self.assertTrue(all(e['outcome'] == 'failed' for e in events))
        self.assertTrue(all(e['failure_code'] == 'dependency_error' for e in events))
        self.assertNotIn('secret', str(events))
        budget = RequestBudget(30, 1)
        with use_budget(budget):
            invoke_provider('llm', lambda timeout: 'ok')
            with self.assertRaises(ExecutionFailure):
                invoke_provider('llm', lambda timeout: self.fail('denied provider executed'))
        self.assertEqual(budget.calls['llm'], 1)
        self.assertEqual(budget.trace.snapshot()[-1]['failure_code'], 'call_budget_exceeded')
        self.assertEqual(budget.trace.snapshot()[-1]['attempt'], 2)

    def test_bounded_snapshot_timeout_and_terminal_root_are_not_rewritten(self):
        trace = RequestTrace(lambda: 1.0, max_spans=2)
        event = trace.begin('node', 'blocked')
        trace.finish(trace.root, 'failed', 'deadline_exceeded')
        snapshot = trace.snapshot()
        self.assertEqual(snapshot[1]['outcome'], 'running')
        self.assertIsNone(snapshot[1]['duration_ms'])
        trace.finish(event)
        trace.finish(trace.root)
        for i in range(100):
            with trace.span('node', 'overflow'):
                pass
        self.assertEqual(len(trace.snapshot()), 2)
        self.assertEqual(trace.metadata()['trace_dropped'], 100)
        self.assertEqual(snapshot[1]['outcome'], 'running')
        self.assertEqual(trace.snapshot()[0]['outcome'], 'failed')
        snapshot[0]['outcome'] = 'altered'
        self.assertEqual(trace.snapshot()[0]['outcome'], 'failed')

    def test_parallel_requests_keep_ids_and_parents_isolated(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        barrier = threading.Barrier(2)
        def request(_):
            budget = RequestBudget(30, 2)
            @guarded_node
            def execute_sql(state):
                barrier.wait(timeout=5)
                invoke_provider('llm', lambda timeout: 'private')
                return state
            with use_budget(budget):
                execute_sql({})
            return budget.trace.snapshot()
        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = list(executor.map(request, range(2)))
        self.assertNotEqual(first[0]['request_id'], second[0]['request_id'])
        for events in (first, second):
            self.assertEqual({e['request_id'] for e in events}, {events[0]['request_id']})
            self.assertEqual(events[2]['parent_stage_id'], events[1]['stage_id'])

    def test_unexpected_exception_and_unknown_failure_code_are_sanitized(self):
        trace = RequestTrace(lambda: 0)
        with self.assertRaises(RuntimeError):
            with trace.span('node', 'stage'):
                raise RuntimeError('api_key=private')
        self.assertEqual(trace.snapshot()[-1]['failure_code'], 'internal_error')
        trace.finish(trace.root, 'failed', 'private custom code')
        self.assertNotIn('private', str(trace.snapshot()))

    def test_evaluator_retains_failure_events_without_raw_error_message(self):
        from unittest.mock import Mock
        from shared.evaluation_runner import run_cases
        trace = RequestTrace(lambda: 0)
        trace.finish(trace.root, 'failed', 'dependency_error')
        response, store = Mock(), Mock()
        response.raise_for_status.side_effect = RuntimeError('upstream private error')
        response.json.return_value = {'detail': {'code': 'dependency_error',
            'message': 'private upstream response', **trace.metadata(), 'trace': trace.snapshot()}}
        run_cases(store, 'run', [{'id': 'one', 'question': 'q', 'expected_answer': 'a'}],
                  'http://fixture', post=Mock(return_value=response))
        recorded = store.record.call_args.args
        self.assertEqual(recorded[2], 'error')
        self.assertEqual(recorded[-1], 'dependency_error')
        self.assertEqual(recorded[4]['trace'], trace.snapshot())
        self.assertNotIn('private', str(recorded))
