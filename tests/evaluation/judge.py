import json
import requests
import re
import sys
import time
import duckdb
import uuid
from datetime import datetime
from typing import List, Dict, Any

# Configuration
API_URL = "http://127.0.0.1:8000/query"
DATASET_PATH = "tests/evaluation/golden_dataset.json"
METRICS_DB_PATH = "data/target/metrics.duckdb"

class Evaluator:
    def __init__(self):
        self.results = []
        self.run_id = str(uuid.uuid4())
        self.db = duckdb.connect(METRICS_DB_PATH)
        self._init_db()

    def _init_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                run_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP,
                total_cases INTEGER,
                passed_cases INTEGER,
                pass_rate DOUBLE
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS eval_results (
                run_id VARCHAR,
                case_id VARCHAR,
                case_type VARCHAR,
                status VARCHAR,
                latency DOUBLE,
                actual_sql VARCHAR,
                actual_answer VARCHAR,
                error_details VARCHAR,
                FOREIGN KEY (run_id) REFERENCES eval_runs(run_id)
            )
        """)

    def load_dataset(self) -> List[Dict]:
        with open(DATASET_PATH, "r") as f:
            return json.load(f)

    def call_api(self, query: str) -> Dict:
        try:
            start_time = time.time()
            # Increase timeout for LLM inference (initial load can be slow)
            response = requests.post(API_URL, json={"query": query}, timeout=300)
            response.raise_for_status()
            data = response.json()
            data["latency"] = time.time() - start_time
            return data
        except Exception as e:
            print(f"❌ API Call Failed: {e}")
            return {"error": str(e)}

    def evaluate_sql(self, expected_pattern: str, actual_sql: str) -> bool:
        if not actual_sql:
            return False
        # Normalize whitespace
        actual_norm = re.sub(r'\s+', ' ', actual_sql).strip()
        # Check regex
        return bool(re.search(expected_pattern, actual_norm, re.IGNORECASE))

    def evaluate_rag(self, expected_keywords: List[str], actual_answer: str) -> bool:
        if not actual_answer:
            return False
        # Simple keyword check (Placeholder for LLM Judge)
        actual_lower = actual_answer.lower()
        return any(k.lower() in actual_lower for k in expected_keywords)

    def run(self):
        print(f"🚀 Starting Evaluation against {API_URL}...")
        dataset = self.load_dataset()
        
        passed = 0
        total = len(dataset) # Run all for metrics, or subset if debugging
        
        # For this specific run, we might be filtering in the loop, but let's assume full run for metrics
        # If filtering, 'total' should reflect that.
        # Let's stick to the loop logic for now.
        
        print(f"{'ID':<10} {'Type':<10} {'Intent':<10} {'Result':<10} {'Latency':<10}")
        print("-" * 60)
        
        # Insert Run Record (Placeholder stats, updated later)
        self.db.execute("INSERT INTO eval_runs VALUES (?, ?, ?, ?, ?)", 
                        (self.run_id, datetime.now(), total, 0, 0.0))

        # Run sql_1 to sql_6 (indices 0 to 6) as per previous config
        target_cases = dataset[0:6]
        total = len(target_cases)

        for case in target_cases:
            print(f"Running case {case['id']}...")
            result = self.call_api(case["question"])
            
            if "error" in result:
                print(f"{case['id']:<10} {case['type']:<10} ERROR      FAIL       -")
                self._log_result(case, "FAIL", 0, error=result["error"])
                continue
            
            # 1. Check Intent
            intent_pass = result["intent"] == case["expected_intent"]
            
            # 2. Check Content
            content_pass = False
            if case["type"] == "sql":
                content_pass = self.evaluate_sql(case["expected_sql_pattern"], result.get("sql"))
            elif case["type"] == "rag":
                content_pass = self.evaluate_rag(case["expected_keywords"], result.get("answer"))
            elif case["type"] == "ambiguous":
                content_pass = True
            
            # Final Verdict
            is_pass = intent_pass and content_pass
            result_status = "PASS" if is_pass else "FAIL"
            
            # Log details if failed
            if not is_pass:
                print(f"\n[FAIL] ID: {case['id']}")
                print(f"  Expected Intent: {case['expected_intent']}, Got: {result.get('intent')}")
                if case['type'] == 'sql':
                    print(f"  Expected SQL: {case['expected_sql_pattern']}")
                    print(f"  Actual SQL:   {result.get('sql')}")

            if is_pass:
                passed += 1
                
            print(f"{case['id']:<10} {case['type']:<10} {result.get('intent', 'N/A'):<10} {result_status:<10} {result.get('latency', 0):.2f}s")
            
            self._log_result(case, result_status, result.get("latency", 0), 
                             sql=result.get("sql"), answer=result.get("answer"))

        print("-" * 60)
        pass_rate = (passed / total) * 100 if total > 0 else 0
        print(f"📊 Summary: {passed}/{total} Passed ({pass_rate:.1f}%)")
        
        # Update Run Summary
        self.db.execute("""
            UPDATE eval_runs 
            SET passed_cases = ?, pass_rate = ?
            WHERE run_id = ?
        """, (passed, pass_rate, self.run_id))
        
        if passed < total:
            sys.exit(1)

    def _log_result(self, case, status, latency, sql=None, answer=None, error=None):
        self.db.execute("""
            INSERT INTO eval_results (run_id, case_id, case_type, status, latency, actual_sql, actual_answer, error_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.run_id, case["id"], case["type"], status, latency, sql, answer, error))

if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.run()
