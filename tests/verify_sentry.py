import sys
import os
import time
import threading
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.sentry.src.main import SentryService
from shared.db.duckdb_client import DuckDBConnector
from scripts.demo_trigger_sentry import trigger_sentry

def test_sentry_flow():
    print("\n🛡️ Testing Sentry End-to-End Flow...")
    
    # 1. Setup - Ensure DBs are ready
    print("   Initializing DBs...")
    db = DuckDBConnector(read_only=False)
    # Ensure logs table exists (since we inject directly)
    db._init_schema()
    db._init_alerts_schema()
    
    # Clear alerts for clean test
    conn = db._get_history_connection()
    conn.execute("DELETE FROM alerts")
    conn.close()
    
    # 2. Start Sentry Service in a thread
    print("   Starting Sentry Service...")
    sentry = SentryService()
    sentry.check_interval = 2 # Fast check for test
    
    stop_sentry = False
    def run_sentry():
        while not stop_sentry:
            try:
                sentry.check_anomalies()
            except Exception as e:
                print(f"Sentry Error: {e}")
            time.sleep(2)
            
    sentry_thread = threading.Thread(target=run_sentry)
    sentry_thread.daemon = True
    sentry_thread.start()
    
    time.sleep(2) # Warm up
    
    # 3. Simulate Spike
    print("   Property Triggering Spike...")
    trigger_sentry("test-service", 10) # 10 errors should trigger baseline 0.5 -> 20x ratio
    
    # 4. Wait for detection
    print("   Waiting for detection...")
    time.sleep(5)
    
    stop_sentry = True
    
    # 5. Check Alert in DB
    print("   Verifying Alert...")
    conn = db._get_history_connection()
    alerts = conn.execute("SELECT * FROM alerts WHERE service='system'").fetchall() # trigger_sentry sets service='system' in alert creation? No, Sentry main.py sets service='system' currently.
    conn.close()
    
    if len(alerts) > 0:
        print(f"   ✅ Alert found: {alerts[0]}")
        return True
    else:
        print("   ❌ No alert found in DB!")
        return False

if __name__ == "__main__":
    if test_sentry_flow():
        print("\n🎉 SENTRY VERIFICATION PASSED")
        sys.exit(0)
    else:
        print("\n💥 SENTRY VERIFICATION FAILED")
        sys.exit(1)
