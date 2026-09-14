"""Deterministic contracts are independent of optional model-judge scores."""
import time

import requests


def score_case(case, response):
    checks = []
    if 'expected_sql_result' in case:
        checks.append(response.get('sql_result') == case['expected_sql_result'])
    if 'expected_answer' in case:
        checks.append(response.get('answer') == case['expected_answer'])
    if not checks:
        return 'unscored', 'missing_deterministic_expectation'
    if 'expected_intent' in case:
        checks.append(response.get('intent') == case['expected_intent'])
    return ('passed', None) if all(checks) else ('failed', 'incorrect_result')


def run_cases(store, run_id, cases, api_url, post=requests.post, clock=time.monotonic):
    """Each case is stateless and retains failures and elapsed client latency."""
    try:
        for case in cases:
            started = clock()
            try:
                result = post(api_url + '/query', json={'query': case['question'], 'persist_history': False}, timeout=125)
                result.raise_for_status()
                response = result.json()
                status, reason = score_case(case, response)
                evidence = {key: response.get(key) for key in ('answer', 'context', 'sql', 'sql_result', 'intent', 'metadata')}
            except Exception:
                status, reason, evidence = 'error', 'request_failed', {}
            store.record(run_id, case['id'], status, clock() - started, evidence, reason)
        store.finish(run_id)
    except Exception:
        store.finish(run_id, 'runner_failed')
        raise
