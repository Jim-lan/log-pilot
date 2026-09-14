"""Identifiers for retrieved artifacts; not proof of original source authenticity."""
import hashlib
import re

_CITATION = re.compile(r'\[source:([A-Za-z0-9_-]+)\]')


def source_record(node, content):
    digest = hashlib.sha256(content.encode()).hexdigest()
    identity = str(getattr(node, 'node_id', None) or getattr(node, 'id_', None) or digest)
    return {'source_id': 'kb-' + hashlib.sha256(identity.encode()).hexdigest()[:24],
            'content_sha256': digest, 'kind': str(node.metadata.get('type', 'log_pattern')),
            'title': str(node.metadata.get('topic', 'Log pattern')),
            'provenance': 'retrieved_artifact'}


def cited_sources(answer):
    return sorted(set(_CITATION.findall(answer)))


def retrieval_metrics(expected_ids, actual_ids):
    expected, actual = set(expected_ids), set(actual_ids)
    matches = len(expected & actual)
    return {'precision': matches / len(actual) if actual else (1.0 if not expected else 0.0),
            'recall': matches / len(expected) if expected else (1.0 if not actual else 0.0)}
