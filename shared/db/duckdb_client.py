import duckdb
import json
from typing import List, Dict, Any
import os

class DuckDBConnector:
    def __init__(self, db_path: str = "data/target/logs.duckdb", read_only: bool = False):
        self.db_path = db_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        if read_only:
             # Disable locking for read-only connections to avoid Docker bind-mount issues
            self.conn = duckdb.connect(self.db_path, read_only=True, config={'access_mode': 'READ_ONLY'})
        else:
            self.conn = duckdb.connect(self.db_path)
            self._init_schema()
        # Auto-load catalog if present
        if os.path.exists("data/system_catalog.csv"):
            self.load_catalog("data/system_catalog.csv")

    def load_catalog(self, csv_path: str):
        """Loads the system catalog CSV into a table."""
        print(f"📖 Loading System Catalog from {csv_path}...")
        try:
            # Create or Replace the table directly from CSV
            self.conn.execute(f"CREATE OR REPLACE TABLE system_catalog AS SELECT * FROM read_csv_auto('{csv_path}')")
            print("✅ System Catalog loaded.")
        except Exception as e:
            print(f"❌ Failed to load catalog: {e}")

    def _init_schema(self):
        """Initializes the logs table with the Golden Standard schema."""
        # Note: We use a JSON type for the 'context' column
        # DuckDB supports JSON natively.
        schema_sql = """
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
            context JSON
        );
        """
        self.conn.execute(schema_sql)

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
