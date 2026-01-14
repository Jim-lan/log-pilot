import sys
import os
import uuid
import time
sys.path.append(os.getcwd())
from shared.db.duckdb_client import DuckDBConnector

def test_alert_persistence():
    print("🧪 Testing Alert Persistence...")
    db = DuckDBConnector()
    
    # 1. Create Fake Alert
    alert_id = str(uuid.uuid4())
    print(f"📝 Creating Alert {alert_id}...")
    conn = db._get_history_connection()
    conn.execute(f"INSERT INTO alerts (id, timestamp, severity, service, message, analysis, is_read) VALUES ('{alert_id}', current_timestamp, 'info', 'test', 'msg', 'analysis', FALSE)")
    conn.close()
    
    # 2. Verify it exists and is unread
    alerts = db.get_alerts(unread_only=True)
    found = any(a['id'] == alert_id for a in alerts)
    if not found:
        print("❌ Alert insert failed!")
        return
    print("✅ Alert inserted and visible.")
    
    # 3. Mark as Read
    print("actions: Marking as Read...")
    db.mark_alert_read(alert_id)
    
    # 4. Verify it is GONE from unread list
    alerts = db.get_alerts(unread_only=True)
    found = any(a['id'] == alert_id for a in alerts)
    if found:
        print("❌ Alert NOT marked as read! Still visible.")
    else:
        print("✅ Alert successfully marked as read.")

        # Double check it is actually read=true
        conn = db._get_history_connection()
        is_read = conn.execute(f"SELECT is_read FROM alerts WHERE id='{alert_id}'").fetchone()[0]
        print(f"   DB State: is_read={is_read}")
        conn.close()

if __name__ == "__main__":
    test_alert_persistence()
