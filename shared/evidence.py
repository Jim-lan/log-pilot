"""Identifiers for retrieved artifacts; not proof of original source authenticity."""
import hashlib
import re

_CITATION = re.compile(r'\[source:([A-Za-z0-9_-]+)\]')


def source_record(node, content):
    digest = hashlib.sha256(content.encode()).hexdigest()
    identity = str(getattr(node, 'node_id', None) or getattr(node, 'id_', None) or digest)
    record = {'source_id': 'kb-' + hashlib.sha256(identity.encode()).hexdigest()[:24],
            'content_sha256': digest, 'kind': str(node.metadata.get('type', 'log_pattern')),
            'title': str(node.metadata.get('topic', 'Log pattern')),
            'provenance': 'retrieved_artifact'}
    origin = {key: node.metadata[key] for key in (
        'namespace', 'source_id', 'version_id', 'source_sha256', 'source_spans', 'span_scope',
        'derivation_version') if key in node.metadata}
    if origin:
        record['document_origin'] = origin
    return record


def cited_sources(answer):
    return sorted(set(_CITATION.findall(answer)))


def retrieval_metrics(expected_ids, actual_ids):
    expected, actual = set(expected_ids), set(actual_ids)
    matches = len(expected & actual)
    return {'precision': matches / len(actual) if actual else (1.0 if not expected else 0.0),
            'recall': matches / len(expected) if expected else (1.0 if not actual else 0.0)}


def valid_web_url(value):
    from urllib.parse import urlsplit
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        url = urlsplit(value)
        return bool(url.scheme in ('http', 'https') and url.hostname and not url.username
                    and not url.password and url.port != 0)
    except ValueError:
        return False


def web_evidence(results):
    """Attribute search snippets, without fetching or claiming to verify pages."""
    from datetime import datetime, timezone
    sources, context, seen = [], [], set()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for item in results:
        if not isinstance(item, dict):
            continue
        url, content = item.get('href'), item.get('body', item.get('snippet'))
        if not valid_web_url(url) or not isinstance(content, str) or not content.strip():
            continue
        digest = hashlib.sha256(content.encode()).hexdigest()
        identity = 'web-' + hashlib.sha256((url + '\n' + digest).encode()).hexdigest()[:24]
        if identity in seen:
            continue
        seen.add(identity)
        title = item.get('title') if isinstance(item.get('title'), str) else 'Web result'
        source = dict(source_id=identity, content_sha256=digest, kind='web_snippet',
                      title=title, url=url, retrieved_at=retrieved_at, provenance='search_snippet')
        sources.append(source)
        context.append(f"[source:{identity}] {title}\nSource: {url}\nSnippet: {content}")
    return {'sources': sources, 'context': '\n\n'.join(context)}


def citation_scores(claims, answer, sources):
    """Conservative reviewed-fixture scoring; never infer semantic entailment."""
    if claims is None:
        return {'citation_coverage': None, 'citation_support': None}
    expected = {claim['text']: claim['supports'] for claim in claims}
    records = {}
    for source in sources:
        records.setdefault(source['source_id'], []).append(source.get('content_sha256'))
    seen, covered, supported, links, unexpected = set(), 0, 0, 0, 0
    for line in answer.splitlines():
        if not line.strip():
            continue
        text = _CITATION.sub('', line).strip()
        citations = cited_sources(line)
        known = text in expected and text not in seen
        if not known:
            unexpected += 1
        seen.add(text)
        covered += int(known and bool(citations))
        allowed = {(s['source_id'], s['content_sha256']) for s in expected.get(text, [])}
        for identity in citations:
            links += 1
            hashes = records.get(identity, [])
            supported += int(known and len(hashes) == 1 and (identity, hashes[0]) in allowed)
    denominator = len(expected) + unexpected
    return {'citation_coverage': covered / denominator if denominator else None,
            'citation_support': supported / links if links else (0.0 if claims else None)}


def web_attribution(sources, citations):
    from datetime import datetime
    cited = [s for s in sources if s.get('kind') == 'web_snippet' and s['source_id'] in citations]
    if not cited:
        return None
    def valid(source):
        try:
            return bool(valid_web_url(source.get('url')) and source.get('provenance') == 'search_snippet'
                        and re.fullmatch(r'[0-9a-f]{64}', source.get('content_sha256', ''))
                        and datetime.fromisoformat(source.get('retrieved_at', '')).utcoffset() is not None)
        except (ValueError, TypeError):
            return False
    return sum(valid(s) for s in cited) / len(cited)
