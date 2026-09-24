"""Dry-run retention planning only; deletion requires separate operational gates."""
from datetime import datetime, timezone
import math


class Janitor:
    def __init__(self, kb):
        self.kb = kb

    def run_cleanup(self, retention_days=30):
        if isinstance(retention_days, bool) or not isinstance(retention_days, (int, float)) or not math.isfinite(retention_days) or retention_days <= 0:
            raise ValueError('Retention days must be positive and finite')
        cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86400
        return self.kb.retention_candidates(cutoff)
