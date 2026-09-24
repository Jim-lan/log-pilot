"""Pure dry-run reconciliation over copied ledger/vector metadata. Never writes stores."""
import hashlib
import json


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def reconcile_records(vectors, claims, cards, max_records=100000):
    if type(max_records) is not int or not 1 <= max_records <= 100000:
        raise ValueError('Record limit must be from 1 to 100000')
    if any(len(rows) > max_records for rows in (vectors, claims, cards)):
        raise ValueError('Snapshot exceeds reconciliation record limit')
    seen = set()
    groups = {}
    actual_cards = {}
    unknown = []
    legacy_runbooks = []
    for record in vectors:
        node_id = record['id']
        if not isinstance(node_id, str) or not node_id or node_id in seen:
            raise ValueError('Missing or duplicate vector identity')
        seen.add(node_id)
        metadata = record.get('metadata') or {}
        text = record.get('document')
        if not isinstance(metadata, dict) or not isinstance(text, str):
            raise ValueError('Vector evidence is incomplete')
        reference = {'id_sha256': digest(node_id), 'text_sha256': digest(text)}
        if node_id.startswith('card-'):
            actual_cards[node_id] = reference
        elif metadata.get('type') == 'runbook_card':
            legacy_runbooks.append(reference)
        elif isinstance(metadata.get('service_name'), str) and metadata['service_name'] and metadata.get('cluster_id') is not None:
            # Match the existing protocol-2 algorithm exactly; do not rewrite runtime IDs.
            identity = json.dumps([metadata['service_name'], str(metadata['cluster_id'])])
            target = 'pattern-' + hashlib.sha256(identity.encode()).hexdigest()
            groups.setdefault(target, []).append({**reference, 'already_stable': node_id == target})
        else:
            unknown.append(reference)
    pattern_groups = []
    for target, records in sorted(groups.items()):
        status = ('conflicting_text' if len({r['text_sha256'] for r in records}) > 1 else
                  'duplicate_text_candidate' if len(records) > 1 else
                  'stable' if records[0]['already_stable'] else 'legacy_mapping_candidate')
        pattern_groups.append({'candidate_id': target, 'status': status,
                               'records': sorted(records, key=lambda r: r['id_sha256'])})
    expected = {}
    for card in cards:
        node_id = card['node_id']
        if node_id in expected or not isinstance(card['text'], str):
            raise ValueError('Invalid or duplicate journal card identity')
        expected[node_id] = card
    comparisons = []
    for node_id, card in sorted(expected.items()):
        found = actual_cards.pop(node_id, None)
        status = ('missing' if found is None else
                  'text_mismatch' if digest(card['text']) != found['text_sha256'] else 'text_match')
        comparisons.append({'id_sha256': digest(node_id), 'status': status,
                            'journal_done': bool(card['done'])})
    comparisons.extend({'id_sha256': value['id_sha256'], 'status': 'no_journal', 'journal_done': False}
                       for _, value in sorted(actual_cards.items()))
    claim_summary = []
    for claim in claims:
        claim_summary.append({'fingerprint': claim['fingerprint'], 'state': claim['state'],
                              'protocol': claim['protocol'],
                              'review_required': claim['protocol'] == 1 or claim['state'] != 'indexed'})
    return {'schema_version': 1, 'mode': 'dry_run', 'mutations': 0,
            'counts': {'vectors': len(vectors), 'claims': len(claims), 'journal_cards': len(cards)},
            'claims': sorted(claim_summary, key=lambda c: c['fingerprint']),
            'pattern_groups': pattern_groups, 'document_cards': comparisons,
            'legacy_runbooks': sorted(legacy_runbooks, key=lambda r: r['id_sha256']),
            'unknown_vectors': sorted(unknown, key=lambda r: r['id_sha256']),
            'review_required': True}
