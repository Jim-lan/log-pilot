import os
import json
import duckdb
import requests
import uuid
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

# Ragas Imports
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from datasets import Dataset
    from langchain_community.chat_models import ChatOllama
    from langchain_community.embeddings import OllamaEmbeddings
except ImportError:
    print("⚠️ Ragas not installed or import failed.")

app = FastAPI(title="LogPilot Evaluation Service")

# Configuration
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://log-pilot-llm:11434/v1")
PILOT_API_URL = os.getenv("PILOT_API_URL", "http://pilot-orchestrator:8000")
METRICS_DB_PATH = "/app/data/target/metrics.duckdb"
DATASET_PATH = "/app/tests/evaluation/golden_dataset.json"

# Initialize Ragas Components
print(f"🤖 Initializing Ragas with Ollama at {LLM_BASE_URL}...")
# Note: Ragas uses LangChain objects. We need to ensure they point to the right URL.
# The base_url for ChatOllama should be the Ollama server URL (e.g. http://log-pilot-llm:11434)
# LLM_BASE_URL usually has /v1 for OpenAI compat, but LangChain ChatOllama expects just the host.
OLLAMA_HOST = LLM_BASE_URL.replace("/v1", "")

llm = ChatOllama(model="llama3", base_url=OLLAMA_HOST)
embeddings = OllamaEmbeddings(model="llama3", base_url=OLLAMA_HOST)

class EvaluateRequest(BaseModel):
    query: str
    rewritten_query: str
    rag_context: str
    final_answer: str

class BatchEvaluateRequest(BaseModel):
    dataset_path: Optional[str] = DATASET_PATH
    limit: Optional[int] = None

def _init_db():
    conn = duckdb.connect(METRICS_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs_micro (
            run_id VARCHAR PRIMARY KEY,
            timestamp TIMESTAMP,
            total_cases INTEGER,
            avg_faithfulness DOUBLE,
            avg_answer_relevancy DOUBLE,
            avg_latency DOUBLE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results_micro (
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
            FOREIGN KEY (run_id) REFERENCES eval_runs_micro(run_id)
        )
    """)
    conn.close()

_init_db()

@app.get("/health")
def health():
    return {"status": "ok", "ragas": "ready"}

@app.post("/evaluate")
def evaluate_single(req: EvaluateRequest):
    """
    Evaluates a single RAG interaction.
    """
    try:
        # Create a mini dataset for Ragas
        data = {
            "question": [req.query],
            "answer": [req.final_answer],
            "contexts": [[req.rag_context]],
            # "ground_truth": ...
        }
        dataset = Dataset.from_dict(data)
        
        scores = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings
        )
        
        return scores.to_pandas().to_dict(orient="records")[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_batch_evaluation(run_id: str, limit: Optional[int]):
    print(f"🚀 Starting Batch Evaluation {run_id}...")
    conn = duckdb.connect(METRICS_DB_PATH)
    
    try:
        # 1. Load Dataset
        with open(DATASET_PATH, "r") as f:
            dataset = json.load(f)
        
        rag_cases = [c for c in dataset if c["type"] == "rag"]
        if limit:
            rag_cases = rag_cases[:limit]
            
        print(f"ℹ️ Processing {len(rag_cases)} cases...")
        
        results_data = []
        
        # 2. Invoke Pilot for each case
        for case in rag_cases:
            try:
                # Call Pilot Orchestrator API
                # We assume there's an endpoint or we use the graph directly?
                # Ideally we call the API.
                # POST /query
                resp = requests.post(f"{PILOT_API_URL}/query", json={
                    "query": case["question"]
                })
                resp.raise_for_status()
                data = resp.json()
                
                # Extract internals (Pilot API needs to return these or we infer)
                # If Pilot API doesn't return internals, we might need to update Pilot API 
                # OR use a special "debug" endpoint.
                # For now, let's assume Pilot returns standard response and we might miss 'rewritten_query'
                # unless we update Pilot to return metadata.
                # Let's assume data has 'metadata' field.
                
                metadata = data.get("metadata", {})
                
                results_data.append({
                    "case_id": case["id"],
                    "case_type": case["type"],
                    "question": case["question"],
                    "answer": data.get("answer", ""),
                    "contexts": [metadata.get("rag_context", "")],
                    "rewritten_query": metadata.get("rewritten_query", ""),
                    "latency": metadata.get("latency", 0)
                })
                
            except Exception as e:
                print(f"❌ Error invoking pilot for {case['id']}: {e}")
        
        if not results_data:
            print("⚠️ No results to evaluate.")
            return

        # 3. Run Ragas
        hf_dataset = Dataset.from_pandas(pd.DataFrame(results_data))
        scores = evaluate(
            hf_dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=llm,
            embeddings=embeddings
        )
        
        # 4. Save Results
        df_scores = scores.to_pandas()
        avg_faith = df_scores["faithfulness"].mean()
        avg_rel = df_scores["answer_relevancy"].mean()
        avg_lat = 0 # df_scores["latency"].mean() if available
        
        conn.execute("INSERT INTO eval_runs_micro VALUES (?, ?, ?, ?, ?, ?)", 
                        (run_id, datetime.now(), len(results_data), avg_faith, avg_rel, avg_lat))
        
        for _, row in df_scores.iterrows():
            conn.execute("""
                INSERT INTO eval_results_micro 
                (run_id, case_id, case_type, query, rewritten_query, final_answer, contexts, faithfulness, answer_relevancy, latency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, 
                row["case_id"], 
                row["case_type"], 
                row["question"], 
                row["rewritten_query"], 
                row["answer"], 
                str(row["contexts"]), 
                row["faithfulness"], 
                row["answer_relevancy"], 
                0 # latency
            ))
            
        print(f"✅ Batch Evaluation {run_id} Complete.")
        
    except Exception as e:
        print(f"❌ Batch Evaluation Failed: {e}")
    finally:
        conn.close()

@app.post("/evaluate/batch")
def trigger_batch_eval(req: BatchEvaluateRequest, background_tasks: BackgroundTasks):
    """
    Triggers a background batch evaluation run.
    """
    run_id = str(uuid.uuid4())
    background_tasks.add_task(run_batch_evaluation, run_id, req.limit)
    return {"status": "started", "run_id": run_id}
