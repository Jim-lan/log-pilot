"""Persisted comparisons with fixed validators and explicit acceptance gates."""
import json
import math
import statistics
import uuid
from pathlib import Path
from typing import List, Optional
import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.evaluation import CASE_STATUSES
from shared.evaluation_runner import run_cases
from shared.evaluation_provenance import scorer_identity


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profiles: List[str] = Field(min_length=2, max_length=4)
    repeats: int = Field(default=3, strict=True, ge=1, le=5)
    limit: Optional[int] = Field(default=None, strict=True, ge=1, le=1000)
    data_revision: str = Field(min_length=1, max_length=128)
    min_pass_rate: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    max_error_rate: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    max_p95_seconds: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def unique(self):
        if len(set(self.profiles)) != len(self.profiles):
            raise ValueError('Profiles must be unique')
        return self


def plan_comparison(request, catalog, cases, dataset_provenance):
    if len(cases) * len(request.profiles) * request.repeats > 5000:
        raise ValueError('Comparison exceeds 5000 case executions')
    manifests = {name: catalog.resolve(name)[1] for name in request.profiles}
    validators = {json.dumps(m['validation'], sort_keys=True) for m in manifests.values()}
    if len(validators) != 1:
        raise ValueError('Comparison requires identical validation settings')
    comparison_id = str(uuid.uuid4())
    scorer = scorer_identity()
    runs = []
    for repetition in range(request.repeats):
        order = request.profiles[repetition % len(request.profiles):] + request.profiles[:repetition % len(request.profiles)]
        for name in order:
            provenance = {**dataset_provenance, **scorer, 'comparison_id': comparison_id,
                'comparison_plan': request.model_dump(), 'model_profile': manifests[name],
                'repetition': repetition + 1, 'execution_order': len(runs) + 1,
                'case_order': [c['id'] for c in cases], 'execution': {'coverage': 'pending'}}
            runs.append((str(uuid.uuid4()), [c['id'] for c in cases], provenance))
    return comparison_id, runs


def run_comparison(store, runs, cases, api_url, runner=run_cases):
    try:
        for run_id, _, provenance in runs:
            profile = provenance['model_profile']
            runner(store, run_id, cases, api_url, model_profile=profile['profile_id'],
                   expected_profile_sha256=profile['profile_sha256'],
                   data_revision=provenance['comparison_plan']['data_revision'])
    except Exception:
        # Terminal results are immutable; unstarted/unfinished runs remain explicit errors.
        for run_id, _, _ in runs:
            store.finish(run_id, 'comparison_runner_failed')
        raise


def _percentile(values, percentile):
    return sorted(values)[max(0, math.ceil(len(values) * percentile) - 1)] if values else None


def comparison_report(path, comparison_id):
    if not Path(path).exists():
        return None
    with duckdb.connect(path, read_only=True) as conn:
        conn.execute('BEGIN')
        if not {'evaluation_runs_v1', 'evaluation_cases_v1'} <= {r[0] for r in conn.execute('SHOW TABLES').fetchall()}:
            return None
        rows = conn.execute("""SELECT run_id,status,provenance FROM evaluation_runs_v1
            WHERE json_extract_string(provenance, '$.comparison_id')=?""", [comparison_id]).fetchall()
        if not rows:
            return None
        cases = conn.execute("""SELECT c.run_id,c.case_id,c.status,c.latency,c.evidence,c.failure_code
            FROM evaluation_cases_v1 c JOIN evaluation_runs_v1 r USING(run_id)
            WHERE json_extract_string(r.provenance, '$.comparison_id')=? ORDER BY c.case_id""", [comparison_id]).fetchall()
    runs = [{'run_id': r[0], 'status': r[1], 'provenance': json.loads(r[2])} for r in rows]
    runs.sort(key=lambda r: r['provenance']['execution_order'])
    plan = runs[0]['provenance']['comparison_plan']
    complete = (len(runs) == len(plan['profiles']) * plan['repeats']
                and all(r['status'] in ('completed', 'completed_with_errors') for r in runs))
    templates, identities, candidates, details = {}, {}, [], []
    expected_scorer = runs[0]['provenance']['scorer_sha256']
    global_consistent = all(r['provenance']['scorer_sha256'] == expected_scorer
                            and r['provenance']['comparison_plan'] == plan for r in runs)
    reference = runs[0]['provenance']
    global_consistent &= all(all(r['provenance'].get(key) == reference.get(key)
                                for key in ('dataset_sha256', 'limit', 'case_order')) for r in runs)
    for name in plan['profiles']:
        selected = [r for r in runs if r['provenance']['model_profile']['profile_id'] == name]
        counts = dict.fromkeys(CASE_STATUSES, 0)
        latencies, valid, verified = [], 0, True
        observed_tokens, calls, measured_calls = 0, 0, 0
        dimensions = {}
        rates = []
        expected_profile = selected[0]['provenance']['model_profile']['profile_sha256'] if selected else None
        for run in selected:
            run_cases_rows = [c for c in cases if c[0] == run['run_id']]
            expected_ids = run['provenance']['case_order']
            verified &= sorted(c[1] for c in run_cases_rows) == sorted(expected_ids)
            rates.append(sum(c[2] == 'passed' for c in run_cases_rows) / len(expected_ids))
            for _, case_id, status, latency, raw, failure in run_cases_rows:
                counts[status] += 1
                if latency is not None:
                    latencies.append(latency)
                evidence = json.loads(raw) if raw else {}
                metadata = evidence.get('metadata') or {}
                actual = metadata.get('provenance') or {}
                profile = actual.get('model_profile') or {}
                verified &= (profile.get('profile_sha256') == expected_profile
                             and profile.get('profile_id') == name
                             and actual.get('evaluation_data_revision') == plan['data_revision'])
                actual_templates = actual.get('templates') or {}
                verified &= bool(actual_templates)
                for template, digest in actual_templates.items():
                    templates.setdefault(template, set()).add(digest)
                valid += metadata.get('outcome') == 'validated'
                for call in actual.get('model_calls', []):
                    role = call.get('role')
                    expected_settings = run['provenance']['model_profile'].get(role, {}) if role in ('generation', 'validation') else {}
                    verified &= (bool(expected_settings) and call.get('requested_model') == expected_settings.get('model')
                                 and call.get('settings') == {k: v for k, v in expected_settings.items() if k != 'model' and v is not None})
                    if call.get('returned_model') is not None:
                        identities.setdefault((name, role), set()).add((call['returned_model'], call.get('system_fingerprint')))
                    calls += 1
                    usage = call.get('usage') or {}
                    tokens = usage.get('total_tokens')
                    if type(tokens) is int and tokens >= 0:
                        measured_calls += 1
                        observed_tokens += tokens
                for dimension in ('citation_coverage', 'citation_support', 'web_attribution', 'citation_validity'):
                    value = (evidence.get('dimensions') or {}).get(dimension)
                    if isinstance(value, (int, float)):
                        dimensions.setdefault(dimension, []).append(float(value))
                details.append({'run_id': run['run_id'], 'profile_id': name, 'repetition': run['provenance']['repetition'],
                    'case_id': case_id, 'status': status, 'latency_seconds': latency, 'failure_code': failure,
                    'request_id': metadata.get('request_id'), 'dimensions': evidence.get('dimensions')})
        total = sum(counts.values())
        candidates.append({'profile_id': name, 'profile_sha256': expected_profile, 'case_counts': counts,
            'total_cases': total, 'pass_rate': counts['passed'] / total if total else None,
            'error_rate': counts['error'] / total if total else None,
            'runtime_validated_rate': valid / total if total else None,
            'latency_p50_seconds': statistics.median(latencies) if latencies else None,
            'latency_p95_seconds': _percentile(latencies, .95), 'latency_samples': len(latencies),
            'repetition_pass_rates': rates,
            'dimensions': {k: {'mean': statistics.mean(v), 'scored_cases': len(v)} for k, v in dimensions.items()},
            'observed_total_tokens': observed_tokens if measured_calls else None,
            'total_tokens': observed_tokens if calls and calls == measured_calls else None,
            'usage_calls': measured_calls, 'total_model_calls': calls, 'cost': None,
            'provenance_verified': bool(verified and selected)})
    global_consistent &= all(len(values) == 1 for values in templates.values())
    global_consistent &= all(len(values) == 1 for values in identities.values())
    gates_defined = all(plan.get(k) is not None for k in ('min_pass_rate', 'max_error_rate', 'max_p95_seconds'))
    for candidate in candidates:
        candidate['eligible'] = bool(complete and global_consistent and gates_defined
            and candidate['provenance_verified'] and candidate['case_counts']['unscored'] == 0
            and candidate['pass_rate'] is not None and candidate['pass_rate'] >= plan['min_pass_rate']
            and candidate['error_rate'] <= plan['max_error_rate'] and candidate['latency_p95_seconds'] is not None
            and candidate['latency_p95_seconds'] <= plan['max_p95_seconds'])
    eligible = sorted((c for c in candidates if c['eligible']), key=lambda c: (-c['pass_rate'], c['latency_p95_seconds']))
    tied = len(eligible) > 1 and (eligible[0]['pass_rate'], eligible[0]['latency_p95_seconds']) == (eligible[1]['pass_rate'], eligible[1]['latency_p95_seconds'])
    return {'schema_version': 1, 'reporter_sha256': scorer_identity()['scorer_sha256'], 'comparison_id': comparison_id, 'complete': complete,
            'plan': plan, 'runs': runs, 'candidates': candidates, 'cases': details,
            'template_scorer_consistent': bool(global_consistent),
            'recommendation': eligible[0]['profile_id'] if eligible and not tied else None,
            'decision': 'incomplete' if not complete else 'gates_not_set' if not gates_defined else
                        'provenance_changed' if not global_consistent else 'tie' if tied else
                        'eligible_candidate' if eligible else 'no_eligible_candidate',
            'selection_rule': 'highest deterministic pass rate, then lowest p95 latency; no automatic promotion',
            'data_revision_verification': 'operator_asserted', 'weight_identity': 'provider_names_only'}
