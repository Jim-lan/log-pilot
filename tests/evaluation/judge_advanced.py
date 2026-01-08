import json
import sys
import time
import duckdb
import uuid
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Set Env Var for Local Testing
os.environ["LLM_BASE_URL"] = "http://localhost:11434/v1"

from services.pilot_orchestrator.src.graph import pilot_graph
from services.pilot_orchestrator.src.state import AgentState

# Ragas Imports
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy
    from datasets import Dataset
    from langchain_community.chat_models import ChatOllama
    from langchain_community.embeddings import OllamaEmbeddings
    # Ragas Wrappers (if needed, but Ragas v0.2+ often accepts LangChain objects directly)
    # We will pass the langchain objects to the 'llm' and 'embeddings' args of evaluate/metrics
except ImportError as e:
    print(f"❌ Ragas Import Error: {e}")
    sys.exit(1)

# Configuration
DATASET_PATH = "tests/evaluation/golden_dataset.json"
METRICS_DB_PATH = "data/target/metrics.duckdb"

class AdvancedEvaluator:
    def __init__(self):
        self.run_id = str(uuid.uuid4())
        self.db = duckdb.connect(METRICS_DB_PATH)
        self._init_db()
        
        # Initialize LLM & Embeddings for Ragas
        print("🤖 Initializing Ragas with Ollama (llama3)...")
        self.llm = ChatOllama(model="llama3", base_url="http://localhost:11434")
        self.embeddings = OllamaEmbeddings(model="llama3", base_url="http://localhost:11434")

    def _init_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs_advanced (
                run_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP,
                total_cases INTEGER,
                avg_faithfulness DOUBLE,
                avg_answer_relevancy DOUBLE,
                avg_latency DOUBLE
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS eval_results_advanced (
                run_id VARCHAR,
                case_id VARCHAR,
                case_type VARCHAR,
                query VARCHAR,
                rewritten_query VARCHAR,
                final_answer VARCHAR,
                contexts VARCHAR,
                faithfulness DOUBLE,
                answer_relevancy DOUBLE,
                latency DOUBLE,
                FOREIGN KEY (run_id) REFERENCES eval_runs_advanced(run_id)
            )
        """)

    def load_dataset(self) -> List[Dict]:
        with open(DATASET_PATH, "r") as f:
            return json.load(f)

    def invoke_agent(self, query: str) -> Dict:
        start_time = time.time()
        state = AgentState(
            query=query,
            messages=[],
            history=[],
            retry_count=0
        )
        try:
            result = pilot_graph.invoke(state)
            latency = time.time() - start_time
            return {
                "rewritten_query": result.get("rewritten_query", query),
                "rag_context": result.get("rag_context", ""),
                "final_answer": result.get("final_answer", ""),
                "latency": latency,
                "error": None
            }
        except Exception as e:
            return {"error": str(e), "latency": time.time() - start_time}

    def run(self):
        print(f"🚀 Starting Advanced Evaluation...")
        dataset = self.load_dataset()
        
        # Filter for RAG cases only (RAGAS is for RAG)
        rag_cases = [c for c in dataset if c["type"] == "rag"]
        print(f"ℹ️ Found {len(rag_cases)} RAG cases. Running first 1 for test.")
        rag_cases = rag_cases[:1] # LIMIT TO 1 FOR TEST
        
        results_data = []
        
        for case in rag_cases:
            print(f"Running case {case['id']}...")
            agent_output = self.invoke_agent(case["question"])
            
            if agent_output.get("error"):
                print(f"❌ Error in {case['id']}: {agent_output['error']}")
                continue
                
            # Prepare data for Ragas
            # Ragas expects: question, answer, contexts (list), ground_truth (optional)
            results_data.append({
                "case_id": case["id"],
                "case_type": case["type"],
                "question": case["question"],
                "answer": agent_output["final_answer"],
                "contexts": [agent_output["rag_context"]], # Treat as single chunk
                "rewritten_query": agent_output["rewritten_query"],
                "latency": agent_output["latency"]
                # "ground_truth": ... (We don't have full text GT, skipping for now)
            })

        if not results_data:
            print("⚠️ No results to evaluate.")
            return

        # Convert to HuggingFace Dataset
        hf_dataset = Dataset.from_pandas(pd.DataFrame(results_data))
        
        print("📊 Running Ragas Metrics (Faithfulness, Answer Relevancy)...")
        # Note: Ragas might be slow locally
        try:
            # We pass the llm and embeddings explicitly
            # Note: Ragas API might vary, but usually 'evaluate' takes llm/embeddings
            # If this fails, we might need to wrap them or configure globally.
            # For ragas v0.4, we might need to set `ragas.llm` and `ragas.embeddings`?
            # Or pass them to `evaluate`.
            
            # Let's try passing them in the `llm` and `embeddings` arguments
            scores = evaluate(
                hf_dataset,
                metrics=[faithfulness, answer_relevancy],
                llm=self.llm,
                embeddings=self.embeddings
            )
            
            print("\n📈 Evaluation Results:")
            print(scores)
            
            # Save to DB
            df_scores = scores.to_pandas()
            # Merge back with original data (if needed, but scores usually preserves order/index)
            # Actually scores.to_pandas() returns the dataset with score columns appended.
            
            avg_faith = df_scores["faithfulness"].mean()
            avg_rel = df_scores["answer_relevancy"].mean()
            avg_lat = df_scores["latency"].mean()
            
            self.db.execute("INSERT INTO eval_runs_advanced VALUES (?, ?, ?, ?, ?, ?)", 
                            (self.run_id, datetime.now(), len(results_data), avg_faith, avg_rel, avg_lat))
            
            for _, row in df_scores.iterrows():
                self.db.execute("""
                    INSERT INTO eval_results_advanced 
                    (run_id, case_id, case_type, query, rewritten_query, final_answer, contexts, faithfulness, answer_relevancy, latency)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.run_id, 
                    row["case_id"], 
                    row["case_type"], 
                    row["question"], 
                    row["rewritten_query"], 
                    row["answer"], 
                    str(row["contexts"]), 
                    row["faithfulness"], 
                    row["answer_relevancy"], 
                    row["latency"]
                ))
                
            print(f"✅ Results saved to {METRICS_DB_PATH}")
            
        except Exception as e:
            print(f"❌ Ragas Evaluation Failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    evaluator = AdvancedEvaluator()
    evaluator.run()
