"""Reproducible scorer identity and explicit coverage of recorded execution metadata."""
import hashlib
import json
import re
from pathlib import Path

SCORER = 'exact_result_citation_v2'
CONTRACT_VERSION = 4


def scorer_identity():
    root = Path(__file__).parent
    names = ('evaluation_runner.py', 'evaluation_context.py', 'evaluation_dataset.py',
             'evidence.py', 'evaluation_provenance.py')
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    return {'scorer': SCORER, 'scorer_files': hashes,
            'scorer_sha256': hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            'contract_version': CONTRACT_VERSION}


def execution_summary(rows):
    models, templates, missing = {}, {}, []
    for case_id, raw in rows:
        try:
            evidence = json.loads(raw) if raw else {}
            provenance = (evidence.get('metadata') or {}).get('provenance')
        except (ValueError, TypeError, AttributeError):
            provenance = None
        if (not isinstance(provenance, dict) or not isinstance(provenance.get('model_calls'), list)
                or not isinstance(provenance.get('templates'), dict)):
            missing.append(case_id)
            continue
        for call in provenance['model_calls']:
            if not isinstance(call, dict):
                continue
            identity = {key: call.get(key) for key in ('requested_model', 'returned_model', 'temperature',
                                                       'system_fingerprint', 'outcome')}
            models[json.dumps(identity, sort_keys=True)] = identity
        for name, digest in provenance['templates'].items():
            if isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest):
                templates.setdefault(name, set()).add(digest)
    return {'coverage': 'complete' if not missing else ('unavailable' if len(missing) == len(rows) else 'partial'),
            'total_cases': len(rows), 'cases_with_provenance': len(rows) - len(missing),
            'missing_case_ids': sorted(missing), 'models': [models[key] for key in sorted(models)],
            'templates': {name: sorted(values) for name, values in sorted(templates.items())}}
