import sys
import os
import time
import uuid
from datetime import datetime
import json

# Add project root to path to reuse shared modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from shared.db.duckdb_client import DuckDBConnector
from shared.llm.client import LLMClient

class SentryService:
    def __init__(self):
        self.db = DuckDBConnector()
        # Initialize alerts schema just in case
        self.db._init_alerts_schema()
        self.check_interval = 10 # Check every 10s for demo purposes (usually 60m)
        self.threshold_ratio = 1.15 # 15% increase
        self.running = True
        
    def run(self):
        print(f"🛡️ Sentry Service started. Monitoring for error spikes every {self.check_interval}s...")
        while self.running:
            try:
                self.check_anomalies()
            except Exception as e:
                print(f"❌ Sentry Error: {e}")
            
            time.sleep(self.check_interval)

    def check_anomalies(self):
        conn = self.db._get_connection()
        
        # 1. Get error count for last window (e.g., last 1 minute for demo)
        now_query = """
            SELECT COUNT(*) 
            FROM logs 
            WHERE 
                timestamp > (NOW() - INTERVAL 1 MINUTE)
                AND severity IN ('ERROR', 'CRITICAL', 'FATAL')
        """
        current_errors = conn.execute(now_query).fetchone()[0]
        
        # 2. Get baseline (previous 5 minutes avg)
        baseline_query = """
            SELECT COUNT(*) / 5.0
            FROM logs 
            WHERE 
                timestamp > (NOW() - INTERVAL 6 MINUTE)
                AND timestamp <= (NOW() - INTERVAL 1 MINUTE)
                AND severity IN ('ERROR', 'CRITICAL', 'FATAL')
        """
        avg_errors = conn.execute(baseline_query).fetchone()[0]
        conn.close()
        
        # Avoid division by zero
        if avg_errors == 0:
            avg_errors = 0.5 # Minimum baseline
            
        ratio = current_errors / avg_errors
        
        print(f"🔍 Scan: Current={current_errors} | Avg={avg_errors:.2f} | Ratio={ratio:.2f}")
        
        if ratio > self.threshold_ratio and current_errors > 5:
            self.trigger_alert(current_errors, avg_errors)

    def trigger_alert(self, current, avg):
        print("🚨 ANOMALY DETECTED! Triggering Alert...")
        
        alert_id = str(uuid.uuid4())
        message = f"Error spike detected (Rate: {current}/min, Avg: {avg:.1f}/min)"
        service = "system" # Ideally we breakdown by service in the SQL
        
        # 3. Simple Analysis (could call Pilot in future)
        analysis = "Potential service degradation. Immediate investigation recommended."
        
        # 4. Save to DB
        conn = self.db._get_history_connection()
        conn.execute("""
            INSERT INTO alerts (id, timestamp, severity, service, message, analysis, is_read)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (alert_id, datetime.now(), 'critical', service, message, analysis, False))
        conn.close()
        
        print(f"✅ Alert {alert_id} saved.")

if __name__ == "__main__":
    sentry = SentryService()
    sentry.run()
