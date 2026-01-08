import json
import re
import sys
import time
import duckdb
import uuid
import os
from datetime import datetime
from typing import List, Dict, Any

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from services.pilot_orchestrator.src.graph import pilot_graph
from services.pilot_orchestrator.src.state import AgentState

# Configuration
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

    def invoke_agent(self, query: str) -> Dict:
        try:
            start_time = time.time()
            state = AgentState(
                query=query,
                messages=[],
                history=[],
                retry_count=0
            )
            result = pilot_graph.invoke(state)
            latency = time.time() - start_time
            
            return {
                "intent": result.get("intent"),
                "sql": result.get("sql_query"),
                "answer": result.get("final_answer"),
                "latency": latency
            }
        except Exception as e:
            print(f"❌ Agent Invoke Failed: {e}")
            return {"error": str(e)}

    def evaluate_sql(self, expected_pattern: str, actual_sql: str) -> bool:
        if not actual_sql:
            return False
        actual_norm = re.sub(r'\s+', ' ', actual_sql).strip()
        return bool(re.search(expected_pattern, actual_norm, re.IGNORECASE))

    def evaluate_rag(self, expected_keywords: List[str], actual_answer: str) -> bool:
        if not actual_answer:
            return False
        actual_lower = actual_answer.lower()
        return any(k.lower() in actual_lower for k in expected_keywords)

    def run(self):
        print(f"🚀 Starting Direct Evaluation...")
        dataset = self.load_dataset()
        
        passed = 0
        target_cases = dataset # Run all
        total = len(target_cases)
        
        print(f"{'ID':<10} {'Type':<10} {'Intent':<10} {'Result':<10} {'Latency':<10}")
        print("-" * 60)
        
        self.db.execute("INSERT INTO eval_runs VALUES (?, ?, ?, ?, ?)", 
                        (self.run_id, datetime.now(), total, 0, 0.0))

        for case in target_cases:
            # print(f"Running case {case['id']}...") # Reduce noise
            result = self.invoke_agent(case["question"])
            
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
            
            if not is_pass:
                # Print details for failures
                pass 

            if is_pass:
                passed += 1
                
            print(f"{case['id']:<10} {case['type']:<10} {result.get('intent', 'N/A'):<10} {result_status:<10} {result.get('latency', 0):.2f}s")
            
            self._log_result(case, result_status, result.get("latency", 0), 
                             sql=result.get("sql"), answer=result.get("answer"))

        print("-" * 60)
        pass_rate = (passed / total) * 100 if total > 0 else 0
        print(f"📊 Summary: {passed}/{total} Passed ({pass_rate:.1f}%)")
        
        self.db.execute("""
            UPDATE eval_runs 
            SET passed_cases = ?, pass_rate = ?
            WHERE run_id = ?
        """, (passed, pass_rate, self.run_id))

    def _log_result(self, case, status, latency, sql=None, answer=None, error=None):
        self.db.execute("""
            INSERT INTO eval_results (run_id, case_id, case_type, status, latency, actual_sql, actual_answer, error_details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (self.run_id, case["id"], case["type"], status, latency, sql, answer, error))

if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.run()
