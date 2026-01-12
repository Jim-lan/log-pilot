import sys
import os
import time
import argparse
import random
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from shared.db.duckdb_client import DuckDBConnector

def trigger_sentry(service, count):
    print(f"🧨 Triggering Sentry Alert Simulation")
    print(f"   Target Service: {service}")
    print(f"   Error Count:    {count}")
    
    db = DuckDBConnector(read_only=False)
    conn = db._get_connection()
    
    # Generate bulk error logs
    logs = []
    
    # Errors for the simulation
    error_templates = [
        "Connection refused to database primary",
        "Timeout waiting for upstream service",
        "NullPointerException in Handler.process()",
        "Rate limit exceeded for API key"
    ]
    
    print("⚡ Injecting logs...")
    for i in range(count):
        timestamp = datetime.now()
        severity = "CRITICAL" if i % 2 == 0 else "ERROR"
        body = random.choice(error_templates)
        
        # Insert directly to SQL to suffice the query requirement in Sentry
        # Columns: timestamp, severity, service_name, trace_id, body, environment, app_id, department, host, region, context
        conn.execute("""
            INSERT INTO logs VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            timestamp, 
            severity, 
            service, 
            f"trace-{random.randint(1000,9999)}", 
            body, 
            "production", 
            "app-1", 
            "engineering", 
            "host-1", 
            "us-east-1", 
            "{}"
        ))
        
    conn.close()
    print(f"✅ Injected {count} error logs into DuckDB.")
    print("⏳ Sentry Service should detect this in < 10 seconds...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a Sentry alert by injecting errors.")
    parser.add_argument("--service", type=str, default="auth-service", help="Service name to target")
    parser.add_argument("--count", type=int, default=50, help="Number of errors to inject")
    parser.add_argument("--scenario", type=str, help="Optional scenario name (unused logic, just for demo consistency)")
    
    args = parser.parse_args()
    
    trigger_sentry(args.service, args.count)
