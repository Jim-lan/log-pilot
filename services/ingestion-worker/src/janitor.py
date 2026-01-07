import time
from datetime import datetime, timedelta
from services.knowledge_base.src.store import KnowledgeStore

class Janitor:
    """
    Responsible for cleaning up old data from the Vector Store.
    """
    def __init__(self, kb: KnowledgeStore):
        self.kb = kb

    def run_cleanup(self, retention_days: int = 30):
        """
        Deletes vectors older than retention_days.
        """
        print(f"🧹 Janitor starting cleanup (Retention: {retention_days} days)...")
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.timestamp()
        
        print(f"   Cutoff Date: {cutoff_date} (Timestamp: {cutoff_timestamp})")
        
        try:
            self.kb.delete_older_than(cutoff_timestamp)
            print("✅ Cleanup complete.")
        except Exception as e:
            print(f"❌ Janitor failed: {e}")
