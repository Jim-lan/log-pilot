import duckdb
import json
from typing import List, Dict, Any
import os
import time

class DuckDBConnector:
    def __init__(self, db_path: str = "data/target/logs.duckdb", read_only: bool = False):
        self.db_path = db_path
        self.history_path = "data/target/history.duckdb"
        self.read_only = read_only
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Init schemas if not read only (or check existence)
        if not self.read_only:
             self._init_schema()
             
        self._init_history_schema()
        
        # Auto-load catalog if present
        if os.path.exists("data/system_catalog.csv"):
            self.load_catalog("data/system_catalog.csv")

    def _get_connection(self):
        """Creates a transient connection to the DB."""
        # Wait for DB file to exist if read-only
        if self.read_only:
            start_wait = time.time()
            while not os.path.exists(self.db_path):
                if time.time() - start_wait > 60:
                     raise TimeoutError(f"Timed out waiting for {self.db_path}")
                time.sleep(1)
                
        max_retries = 30
        for i in range(max_retries):
            try:
                if self.read_only:
                    return duckdb.connect(self.db_path, read_only=True, config={'access_mode': 'READ_ONLY'})
                else:
                    return duckdb.connect(self.db_path)
            except Exception as e:
                # If locked, wait and retry
                if "lock" in str(e).lower() or "read-only" in str(e).lower():
                    if i < max_retries - 1:
                        time.sleep(0.5) 
                    else:
                        raise e
                else:
                    raise e

    def _get_history_connection(self):
         """Creates a transient connection to the History DB."""
         return duckdb.connect(self.history_path)

    def _init_schema(self):
        """Initializes the logs table."""
        try:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    timestamp TIMESTAMP,
                    severity VARCHAR,
                    service_name VARCHAR,
                    trace_id VARCHAR,
                    body VARCHAR,
                    environment VARCHAR,
                    app_id VARCHAR,
                    department VARCHAR,
                    host VARCHAR,
                    region VARCHAR,
                    context VARCHAR
                );
            """)
            conn.close()
        except Exception as e:
            print(f"⚠️ Failed to init schema: {e}")

    def _init_history_schema(self):
        """Initializes the history table in the separate DB."""
        try:
            conn = self._get_history_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id UUID DEFAULT uuid(),
                    timestamp TIMESTAMP DEFAULT current_timestamp,
                    session_id VARCHAR,
                    role VARCHAR,
                    content VARCHAR
                );
            """)
            conn.close()
        except Exception as e:
            print(f"⚠️ Failed to init history schema: {e}")
            
    def save_message(self, session_id: str, role: str, content: str):
        """Saves a chat message to history DB."""
        conn = None
        try:
            conn = self._get_history_connection()
            conn.execute(
                "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                [session_id, role, content]
            )
        except Exception as e:
            print(f"❌ Failed to save message: {e}")
        finally:
            if conn: conn.close()

    def get_history(self, session_id: str = "default"):
        """Retrieves chat history from history DB."""
        conn = None
        try:
            conn = self._get_history_connection()
            rows = conn.execute(
                "SELECT role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY timestamp ASC",
                [session_id]
            ).fetchall()
            return rows
        except Exception as e:
            print(f"❌ Failed to get history: {e}")
            return []
        finally:
            if conn: conn.close()

    def insert_batch(self, logs: List[Dict[str, Any]]):
        """
        Inserts a batch of log records using a transient connection.
        """
        if not logs:
            return

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

        insert_sql = """
        INSERT INTO logs (timestamp, severity, service_name, trace_id, body, environment, app_id, department, host, region, context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        conn = None
        try:
            conn = self._get_connection()
            conn.executemany(insert_sql, values)
        except Exception as e:
            print(f"❌ Failed to insert batch: {e}")
            raise e
        finally:
            if conn: conn.close()

    def query(self, sql: str, params: List[Any] = None) -> List[Any]:
        """Executes a raw SQL query using a transient connection."""
        conn = None
        try:
            conn = self._get_connection()
            if params:
                return conn.execute(sql, params).fetchall()
            return conn.execute(sql).fetchall()
        finally:
            if conn: conn.close()
            
    def load_catalog(self, csv_path: str):
         # Simplistic pass for now
         pass

    def close(self):
        pass
