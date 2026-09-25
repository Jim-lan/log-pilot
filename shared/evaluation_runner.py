"""Deterministic contracts are independent of optional model-judge scores."""
import time
import json

import requests
from shared.tracing import FAILURE_CODES
from shared.evaluation_context import EvaluationContext, validate_cases
from shared.evidence import cited_sources, retrieval_metrics, citation_scores, web_attribution


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
    result.update(citation_scores(case.get('citation_claims'), response.get('answer', ''), response.get('sources', [])))
    result['web_attribution'] = web_attribution(response.get('sources', []), citations)
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
    if 'expected_outcome' in case:
        checks.append((response.get('metadata') or {}).get('outcome') == case['expected_outcome'])
    dimensions = score_dimensions(case, response)
    checks.append(dimensions['citation_validity'])
    if 'citation_claims' in case:
        checks.extend(dimensions[name] == 1 for name in ('citation_coverage', 'citation_support'))
    if dimensions['web_attribution'] is not None:
        checks.append(dimensions['web_attribution'] == 1)
    for dimension in ('retrieval', 'citations'):
        if dimension in dimensions:
            checks.append(dimensions[dimension]['precision'] == 1 and dimensions[dimension]['recall'] == 1)
    return ('passed', None) if all(checks) else ('failed', 'incorrect_result')


def run_cases(store, run_id, cases, api_url, post=requests.post, clock=time.monotonic):
    """Context belongs only to this run and the explicitly named conversation."""
    conversations, blocked = {}, set()
    try:
        validate_cases(cases)
        for case in cases:
            conversation = case.get('conversation_id')
            if conversation is not None and conversation in blocked:
                store.record(run_id, case['id'], 'error', None, {}, 'prior_turn_failed')
                continue
            started = clock()
            result = None
            try:
                payload = {'query': case['question'], 'persist_history': False}
                if conversation is not None:
                    payload['evaluation_context'] = EvaluationContext.model_validate(
                        conversations.get(conversation, [])).model_dump()
                result = post(api_url + '/query', json=payload, timeout=125)
                result.raise_for_status()
                response = result.json()
                status, reason = score_case(case, response)
                evidence = {key: response.get(key) for key in ('answer', 'context', 'sources', 'sql', 'sql_result', 'sql_rows', 'intent', 'metadata', 'trace')}
                evidence['dimensions'] = score_dimensions(case, response)
                if conversation is not None:
                    context = (conversations.get(conversation, []) + [
                        {'role': 'user', 'content': case['question']},
                        {'role': 'assistant', 'content': response.get('answer')}])[-10:]
                    conversations[conversation] = EvaluationContext.model_validate(context).model_dump()
                    evidence['conversation_id'] = conversation
                    evidence['turn_index'] = case['turn_index']
            except Exception:
                status, reason, evidence = 'error', 'request_failed', {}
                if result is not None:
                    try:
                        detail = result.json().get('detail', {})
                        if (detail.get('trace_version') == 2 and isinstance(detail.get('trace'), list)
                                and len(detail['trace']) <= 256 and detail.get('code') in FAILURE_CODES):
                            reason = detail['code']
                            evidence = {'trace': detail['trace'], 'metadata': {
                                key: detail.get(key) for key in ('request_id', 'trace_version', 'trace_dropped', 'provenance')}}
                    except (ValueError, TypeError, AttributeError):
                        pass
                if conversation is not None:
                    blocked.add(conversation)
            store.record(run_id, case['id'], status, clock() - started, evidence, reason)
        store.finish(run_id)
    except Exception:
        store.finish(run_id, 'runner_failed')
        raise
