import duckdb
import json
from typing import List, Dict, Any
import os

class DuckDBConnector:
    def __init__(self, db_path: str = "data/target/logs.duckdb", read_only: bool = False):
        self.db_path = db_path
        self.history_path = "data/target/history.duckdb"
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 1. Connect to Logs DB (Read-Only or Read-Write)
        if read_only:
             # Wait for DB file to exist
            import time
            print(f"⏳ Waiting for DB file at {self.db_path}...")
            while not os.path.exists(self.db_path):
                time.sleep(1)
            print("✅ DB file found.")
            
            # Disable locking for read-only connections
            max_retries = 30
            for i in range(max_retries):
                try:
                    self.conn = duckdb.connect(self.db_path, read_only=True, config={'access_mode': 'READ_ONLY'})
                    print("✅ Connected to Logs DB (Read-Only).")
                    break
                except Exception as e:
                    if "lock" in str(e).lower() and i < max_retries - 1:
                        print(f"🔒 DB locked, retrying in 2s... ({i+1}/{max_retries})")
                        time.sleep(2)
                    else:
                        raise e
        else:
            self.conn = duckdb.connect(self.db_path)
            self._init_schema() # Only inits logs table
            
        # 2. Connect to History DB (Always Read-Write)
        # We use a separate connection for history to avoid locking conflicts with logs
        try:
            self.history_conn = duckdb.connect(self.history_path)
            self._init_history_schema()
            print("✅ Connected to History DB.")
        except Exception as e:
            print(f"⚠️ Failed to connect to History DB: {e}")
            self.history_conn = None

        # Auto-load catalog if present
        if os.path.exists("data/system_catalog.csv"):
            self.load_catalog("data/system_catalog.csv")

    def _init_schema(self):
        """Initializes the logs table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                timestamp TIMESTAMP,
                level VARCHAR,
                service VARCHAR,
                message VARCHAR,
                template_id VARCHAR
            );
        """)

    def _init_history_schema(self):
        """Initializes the history table in the separate DB."""
        if self.history_conn:
            self.history_conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id UUID DEFAULT uuid(),
                    timestamp TIMESTAMP DEFAULT current_timestamp,
                    session_id VARCHAR,
                    role VARCHAR,
                    content VARCHAR
                );
            """)
            
    def save_message(self, session_id: str, role: str, content: str):
        """Saves a chat message to history DB."""
        if self.history_conn:
            try:
                self.history_conn.execute(
                    "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                    [session_id, role, content]
                )
                print(f"💾 Saved message to history: {role} - {content[:20]}...")
            except Exception as e:
                print(f"❌ Failed to save message: {e}")

    def get_history(self, session_id: str = "default"):
        """Retrieves chat history from history DB."""
        if self.history_conn:
            try:
                rows = self.history_conn.execute(
                    "SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY timestamp ASC",
                    [session_id]
                ).fetchall()
                print(f"📖 Retrieved {len(rows)} history items for session {session_id}")
                return rows
            except Exception as e:
                print(f"❌ Failed to get history: {e}")
                return []
        return []

    def insert_batch(self, logs: List[Dict[str, Any]]):
        """
        Inserts a batch of log records.
        Expects a list of dictionaries matching the LogEvent schema.
        """
        if not logs:
            return

        # Prepare data for insertion
        # We need to ensure 'context' is serialized to a JSON string if it's a dict
        # However, DuckDB's Python client handles dict -> JSON conversion automatically 
        # if we use the right appender or insert method. 
        # For simplicity and safety, we'll serialize explicitly for the SQL interface.
        
        values = []
        for log in logs:
            context_json = json.dumps(log.get("context", {}))
            values.append((
                log["timestamp"],
                log["severity"],
                log["service_name"],
                log.get("trace_id"),
                log["body"],
                log.get("environment"),
                log.get("app_id"),
                log.get("department"),
                log.get("host"),
                log.get("region"),
                context_json
            ))

        # Use executemany for batch insertion
        insert_sql = """
        INSERT INTO logs (timestamp, severity, service_name, trace_id, body, environment, app_id, department, host, region, context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.conn.executemany(insert_sql, values)

    def query(self, sql: str) -> List[Any]:
        """Executes a raw SQL query and returns the result."""
        return self.conn.execute(sql).fetchall()

    def close(self):
        self.conn.close()
