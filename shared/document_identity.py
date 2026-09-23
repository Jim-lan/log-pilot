"""Versioned source identities and byte spans; no storage or provider side effects."""
import hashlib
import json
import re


def _digest(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def document_manifest(namespace, source_key, raw):
    if not isinstance(namespace, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', namespace):
        raise ValueError('Invalid document namespace')
    if (not isinstance(source_key, str) or not source_key or len(source_key) > 1024 or
            '\\' in source_key or any(ord(c) < 32 or ord(c) == 127 for c in source_key) or
            any(part in ('', '.', '..') for part in source_key.split('/')) or
            re.match(r'^[A-Za-z]:', source_key)):
        raise ValueError('Expected a stable relative document key')
    if not isinstance(raw, bytes) or not raw or len(raw) > 8 * 1024 * 1024:
        raise ValueError('Expected nonempty document bytes up to 8 MiB')
    raw.decode('utf-8')
    source_id = 'source-' + _digest(['source-v1', namespace, source_key])
    content_hash = hashlib.sha256(raw).hexdigest()
    return {'schema_version': 1, 'namespace': namespace, 'source_key': source_key,
            'source_id': source_id, 'content_sha256': content_hash, 'byte_length': len(raw),
            'version_id': 'document-' + _digest(['document-v1', source_id, content_hash])}


def document_span(raw, start, end):
    if (not isinstance(raw, bytes) or type(start) is not int or type(end) is not int or
            not 0 <= start < end <= len(raw)):
        raise ValueError('Invalid source byte range')
    # Check both boundaries against the exact original, including multibyte characters.
    raw[:start].decode('utf-8')
    raw[start:end].decode('utf-8')
    raw[end:].decode('utf-8')
    return {'start_byte': start, 'end_byte': end,
            'content_sha256': hashlib.sha256(raw[start:end]).hexdigest()}


def card_identity(version_id, ordinal):
    if (not isinstance(version_id, str) or not re.fullmatch(r'document-[0-9a-f]{64}', version_id)
            or type(ordinal) is not int or not 0 <= ordinal < 32):
        raise ValueError('Invalid document card identity')
    return 'card-' + _digest(['card-v1', version_id, ordinal])
