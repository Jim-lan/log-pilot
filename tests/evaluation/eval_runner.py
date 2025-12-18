import json
import requests
import re
import sys
import time
from typing import List, Dict, Any

# Configuration
API_URL = "http://127.0.0.1:8000/query"
DATASET_PATH = "tests/evaluation/golden_dataset.json"

class Evaluator:
    def __init__(self):
        self.results = []

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
        total = len(dataset)
        
        print(f"{'ID':<10} {'Type':<10} {'Intent':<10} {'Result':<10} {'Latency':<10}")
        print("-" * 60)
        
        for case in dataset:
            result = self.call_api(case["question"])
            
            if "error" in result:
                print(f"{case['id']:<10} {case['type']:<10} ERROR      FAIL       -")
                self.results.append({"id": case["id"], "status": "error", "details": result["error"]})
                continue
            
            # 1. Check Intent
            intent_pass = result["intent"] == case["expected_intent"]
            
            # 2. Check Content
            content_pass = False
            if case["type"] == "sql":
                content_pass = self.evaluate_sql(case["expected_sql_pattern"], result.get("sql"))
            elif case["type"] == "rag":
                content_pass = self.evaluate_rag(case["expected_keywords"], result.get("answer"))
            
            # Final Verdict
            is_pass = intent_pass and content_pass
            if is_pass:
                passed += 1
                status = "PASS"
            else:
                status = "FAIL"
                
            print(f"{case['id']:<10} {case['type']:<10} {result['intent']:<10} {status:<10} {result['latency']:.2f}s")
            self.results.append({
                "id": case["id"],
                "status": status,
                "actual_intent": result["intent"],
                "actual_sql": result.get("sql"),
                "actual_answer": result.get("answer")
            })

        print("-" * 60)
        print(f"📊 Summary: {passed}/{total} Passed ({passed/total*100:.1f}%)")
        
        if passed < total:
            sys.exit(1)

if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.run()
