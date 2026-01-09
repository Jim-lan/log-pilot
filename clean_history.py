import duckdb
import os

db_path = "data/target/history.duckdb"
try:
    if os.path.exists(db_path):
        conn = duckdb.connect(db_path)
        conn.execute("DELETE FROM chat_history")
        count = conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
        print(f"✅ History cleaned. Row count: {count}")
        conn.close()
    else:
        print("⚠️ No history DB found.")
except Exception as e:
    print(f"❌ Error: {e}")
