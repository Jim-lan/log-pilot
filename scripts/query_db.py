import duckdb
import argparse
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

def query_db(query: str = None):
    db_path = "data/target/logs.duckdb"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = duckdb.connect(db_path)
    
    if query:
        print(f"🔍 Executing: {query}")
        try:
            results = conn.execute(query).fetchall()
            # Get column names
            cols = [desc[0] for desc in conn.description]
            print(f"{' | '.join(cols)}")
            print("-" * 40)
            for row in results:
                print(row)
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        # Default Summary
        print("📊 Data Summary:")
        
        print("\n1. Total Logs:")
        print(conn.execute("SELECT count(*) FROM logs").fetchone()[0])
        
        print("\n2. Logs by Service:")
        results = conn.execute("SELECT service_name, count(*) FROM logs GROUP BY 1 ORDER BY 2 DESC").fetchall()
        for row in results:
            print(f"   - {row[0]}: {row[1]}")

        print("\n3. Logs by Source File (Format Check):")
        # We extract the source file from the context JSON
        try:
            results = conn.execute("""
                SELECT context->>'source_file' as file, count(*) 
                FROM logs 
                GROUP BY 1 
                ORDER BY 2 DESC
            """).fetchall()
            for row in results:
                print(f"   - {row[0]}: {row[1]}")
        except:
            print("   (Could not extract source_file from context)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query LogPilot DuckDB.")
    parser.add_argument("query", nargs="?", help="SQL query to execute (optional)")
    args = parser.parse_args()
    
    query_db(args.query)
