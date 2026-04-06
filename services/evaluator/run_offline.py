import json
import os
import sys
import requests
import statistics
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.evaluator.src.scorer import EvalScorer

API_URL = "http://localhost:8000/query"

def load_cases(path: str) -> List[Dict[str, Any]]:
    print(f"📂 Loading cases from {path}...")
    with open(path, "r") as f:
        # Handling both JSONL and JSON array for flexibility
        if path.endswith(".jsonl"):
            return [json.loads(line) for line in f]
        else:
            return json.load(f)

def run_trial(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Runs a single case against the Pilot API.
    """
    query = case.get("question") or case.get("query")
    print(f"   ▶️ Running: {query[:50]}...")
    
    try:
        resp = requests.post(API_URL, json={"query": query})
        resp.raise_for_status()
        data = resp.json()
        
        return {
            "case_id": case.get("id", "unknown"),
            "final": data.get("answer"),
            "sql": data.get("sql"),
            "trace": data.get("trace", []),
            "context": data.get("context"), # RAG context
            "meta": data.get("metadata", {})
        }
    except Exception as e:
        print(f"   ❌ Network/API Error: {e}")
        return {"error": str(e)}

def main():
    # Use the new benchmark dataset by default
    dataset_path = os.path.join(os.path.dirname(__file__), "datasets/benchmark_20.json")
    if not os.path.exists(dataset_path):
        # Fallback to golden if benchmark doesn't exist
        dataset_path = os.path.join(os.path.dirname(__file__), "../../tests/evaluation/golden_dataset.json")
        
    print(f"📂 Loading cases from {dataset_path}...")
    
    if not os.path.exists(dataset_path):
        print(f"❌ Dataset not found at {dataset_path}")
        return

    cases = load_cases(dataset_path)
    scorer = EvalScorer()
    
    # Metrics
    det_scores = []
    routing_scores = []
    latencies = {"sql": [], "rag": []}
    
    print(f"🚀 Starting Offline Eval for {len(cases)} cases...")
    
    for case in cases:
        # 1. Run Config
        trial = run_trial(case)
        
        if "error" in trial:
            continue
            
        # 2. Grade
        print(f"   ⚖️ Grading Case: {case.get('id')} ({case.get('type')})...")
        
        # A. Structured Output Check
        struct_res = scorer.grade_structured_output(trial["final"])
        
        # B. Evidence Check (only if context present)
        ev_score = 0.0
        if trial.get("context"):
            ev_score = scorer.grade_evidence_citation(trial["final"], trial["context"])
        else:
            ev_score = 1.0 # NA
            
        # C. Routing Check
        expected_tool = case.get("expected_tool")
        rout_score = 0.0
        if expected_tool:
            rout_score = scorer.grade_routing(trial["trace"], expected_tool)
            routing_scores.append(rout_score)
            print(f"      - Routing Score:   {rout_score} (Expected: {expected_tool})")
        else:
             print("      - Routing Score:   N/A")

        # D. SQL Check (New)
        sql_score = 0.0
        if case.get("type") == "sql" and case.get("expected_sql"):
            # Extract SQL from output or trace?
            # The API response puts sql in 'sql' field usually
            # But run_trial puts it in 'sql' (we need to update run_trial to parse it)
            # The API returns 'sql' field!
            
            # Note: run_trial implementation earlier didn't preserve the 'sql' field from API response properly?
            # Let's check: "final": data.get("answer")... "meta": data...
            # The API returns QueryResponse which has `sql` field.
            # We need to make sure run_trial returns it.
            # Assuming we fix run_trial below or assumed it's in `meta`...
            # Actually, let's fix run_trial in this block or blindly assume it's in the dict.
            
            # Wait, `run_offline.py` `run_trial` function:
            # return { "final": ..., "context": ..., "meta": ... }
            # I need to add 'sql' to run_trial return value first. 
            # But I can't edit distinct parts of the file easily without seeing it.
            # I will trust that I can fetch it from meta if I update run_trial now, 
            # Or I can just check if 'sql' is in the API response which `data` is.
            
            # Let's assume I fix run_trial to include 'sql'.
            generated_sql = trial.get("sql")
            expected_sql = case.get("expected_sql")
            
            sql_score = scorer.grade_sql(generated_sql, expected_sql)
            print(f"      - SQL Score:       {sql_score:.2f}")
            print(f"        (Exp: {expected_sql[:30]}...)")
            print(f"        (Got: {str(generated_sql)[:30]}...)")
            
        # E. Retrieval Check (New)
        retrieval_score = 0.0
        if case.get("type") == "rag" and case.get("expected_context_keywords"):
            context = trial.get("context", "")
            exp_kw = case.get("expected_context_keywords")
            
            retrieval_score = scorer.grade_retrieval(context, exp_kw)
            print(f"      - Retrieval Score: {retrieval_score:.2f}")
            print(f"        (Checking for: {exp_kw})")
        
        # Latency tracking
        lat = trial["meta"].get("latency", 0)
        ctype = case.get("type", "other")
        if ctype in latencies:
            latencies[ctype].append(lat)
            
        combined_score = (struct_res["score"] + ev_score) / 2
        det_scores.append(combined_score)
        
        print(f"      - Structure Score: {struct_res['score']:.2f}")
        print(f"      - Evidence Score:  {ev_score:.2f}")
        print(f"      - Latency:         {lat:.2f}s")
        print("-" * 40)

    # Reporting
    print("\n📊 Evaluation Report")
    print("=" * 40)
    
    if det_scores:
        print(f"✅ Avg Quality Score:   {statistics.mean(det_scores):.2f} (Structure + Evidence)")
        
    if routing_scores:
        print(f"🧭 Avg Routing Acc:     {statistics.mean(routing_scores)*100:.1f}%")
        
    for k, v in latencies.items():
        if v:
            print(f"⏱️  Avg Latency ({k.upper()}): {statistics.mean(v):.2f}s (n={len(v)})")
            
    print("=" * 40)

if __name__ == "__main__":
    main()
