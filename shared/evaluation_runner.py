"""Deterministic contracts are independent of optional model-judge scores."""
import time
import json

import requests
from shared.evidence import cited_sources, retrieval_metrics


def score_dimensions(case, response):
    """Keep retrieval and citation validity distinct from answer correctness."""
    sources = {item['source_id'] for item in response.get('sources', [])}
    citations = set(cited_sources(response.get('answer', '')))
    result = {'citation_validity': not bool(citations - sources),
              'citation_present': bool(citations)}
    if 'expected_source_ids' in case:
        result['retrieval'] = retrieval_metrics(case['expected_source_ids'], sources)
    if 'expected_citation_ids' in case:
        result['citations'] = retrieval_metrics(case['expected_citation_ids'], citations)
    return result


def score_case(case, response):
    checks = []
    if 'expected_rows' in case:
        actual, expected = response.get('sql_rows'), case['expected_rows']
        if not isinstance(actual, list) or not isinstance(expected, list):
            checks.append(False)
        else:
            actual = [json.dumps(row, sort_keys=True, allow_nan=False) for row in actual]
            expected = [json.dumps(row, sort_keys=True, allow_nan=False) for row in expected]
            checks.append(actual == expected if case.get('ordered', True) else sorted(actual) == sorted(expected))
    if 'expected_sql_result' in case:
        checks.append(response.get('sql_result') == case['expected_sql_result'])
    if 'expected_answer' in case:
        checks.append(response.get('answer') == case['expected_answer'])
    if not checks:
        return 'unscored', 'missing_deterministic_expectation'
    if 'expected_intent' in case:
        checks.append(response.get('intent') == case['expected_intent'])
    dimensions = score_dimensions(case, response)
    checks.append(dimensions['citation_validity'])
    for dimension in ('retrieval', 'citations'):
        if dimension in dimensions:
            checks.append(dimensions[dimension]['precision'] == 1 and dimensions[dimension]['recall'] == 1)
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
                evidence = {key: response.get(key) for key in ('answer', 'context', 'sources', 'sql', 'sql_result', 'sql_rows', 'intent', 'metadata')}
                evidence['dimensions'] = score_dimensions(case, response)
            except Exception:
                status, reason, evidence = 'error', 'request_failed', {}
            store.record(run_id, case['id'], status, clock() - started, evidence, reason)
        store.finish(run_id)
    except Exception:
        store.finish(run_id, 'runner_failed')
        raise
