"""Conservative UTC activity metadata and dry-run retention decisions, never deletion."""
from datetime import datetime, timezone
import math


def epoch(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite UTC timestamp')
    return float(value)


def pattern_activity(previous, event_time, indexed_at):
    event, indexed = epoch(event_time), epoch(indexed_at)
    first, last, last_indexed, hold = event, event, indexed, False
    if previous is not None:
        try:
            if not isinstance(previous, dict):
                raise ValueError('Invalid prior activity metadata')
            if 'retention_schema' in previous:
                if type(previous['retention_schema']) is not int or previous['retention_schema'] != 1:
                    raise ValueError('Unknown retention schema')
                old_first = epoch(previous['first_seen_at_unix'])
                old_last = epoch(previous['last_seen_at_unix'])
                old_indexed = epoch(previous['last_indexed_at_unix'])
                if old_first > old_last:
                    raise ValueError('Invalid pattern activity interval')
                first, last = min(old_first, event), max(old_last, event)
                last_indexed = max(old_indexed, indexed)
            else:
                old_event = epoch(previous['timestamp'])
                first, last = min(old_event, event), max(old_event, event)
            hold = bool(previous.get('retention_hold', False))
        except (KeyError, TypeError, ValueError, OverflowError):
            # Unknown legacy activity must not become a deletion candidate after an update.
            hold = True
    return {'retention_schema': 1, 'first_seen_at_unix': first, 'last_seen_at_unix': last,
            'last_indexed_at_unix': last_indexed, 'retention_hold': hold}


def retention_candidate(metadata, cutoff):
    cutoff = epoch(cutoff)
    if (not isinstance(metadata, dict) or metadata.get('type') != 'log_pattern' or
            type(metadata.get('retention_schema')) is not int or metadata.get('retention_schema') != 1 or metadata.get('retention_hold', True) is not False):
        return False
    try:
        first = epoch(metadata['first_seen_at_unix'])
        last = epoch(metadata['last_seen_at_unix'])
        indexed = epoch(metadata['last_indexed_at_unix'])
        return first <= last and last < cutoff and indexed < cutoff
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def retention_report(collection, cutoff, max_records=100000):
    """Read a stable/offline collection; return review candidates, never invoke delete."""
    cutoff = epoch(cutoff)
    if type(max_records) is not int or not 1 <= max_records <= 100000:
        raise ValueError('Invalid retention inventory limit')
    count = collection.count()
    if count > max_records:
        raise ValueError('Retention inventory exceeds record limit')
    import hashlib
    seen = set()
    candidates = []
    for offset in range(0, count, 500):
        batch = collection.get(limit=500, offset=offset, include=['metadatas'])
        if len(batch['ids']) != len(batch['metadatas']):
            raise ValueError('Incomplete retention inventory')
        for node_id, metadata in zip(batch['ids'], batch['metadatas']):
            if node_id in seen:
                raise ValueError('Unstable retention inventory')
            seen.add(node_id)
            if retention_candidate(metadata, cutoff):
                candidates.append(hashlib.sha256(node_id.encode()).hexdigest())
    if len(seen) != count or collection.count() != count:
        raise ValueError('Unstable retention inventory')
    return {'mode': 'dry_run', 'cutoff_unix': cutoff, 'scanned': count,
            'candidate_id_hashes': sorted(candidates), 'mutations': 0, 'review_required': True}
