"""Evaluation API: explicit initialization, durable runs, optional judge."""
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field
from shared.evaluation import EvaluationStore
from shared.evaluation_runner import run_cases
from shared.evaluation_dataset import load_dataset

app = FastAPI(title="LogPilot Evaluation Service")
PILOT_API_URL = os.getenv("PILOT_API_URL", "http://pilot-orchestrator:8000")
METRICS_DB_PATH = os.getenv("METRICS_DB_PATH", "/app/data/target/metrics.duckdb")
DATASET_PATH = os.getenv("EVALUATION_DATASET_PATH", "/app/tests/evaluation/golden_dataset.json")


class EvaluateRequest(BaseModel):
    query: str
    rewritten_query: str
    rag_context: str
    final_answer: str


class BatchEvaluateRequest(BaseModel):
    dataset_path: Optional[str] = None
    limit: Optional[int] = Field(default=None, gt=0, le=1000)


@app.get("/health")
def health():
    return {"status": "ok", "schema_version": 1, "ragas": "on_demand"}


@app.post("/evaluate")
def evaluate_single(req: EvaluateRequest):
    # A judge is supplementary; it does not determine deterministic pass rates.
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy
        from datasets import Dataset
        from langchain_community.chat_models import ChatOllama
        from langchain_community.embeddings import OllamaEmbeddings
        host = os.getenv("LLM_BASE_URL", "http://log-pilot-llm:11434/v1").removesuffix("/v1")
        model = os.getenv("EVALUATION_JUDGE_MODEL", "gemma4:e4b")
        scores = evaluate(Dataset.from_dict({"question": [req.query], "answer": [req.final_answer],
            "contexts": [[req.rag_context]]}), metrics=[faithfulness, answer_relevancy],
            llm=ChatOllama(model=model, base_url=host), embeddings=OllamaEmbeddings(model=model, base_url=host))
        return scores.to_pandas().to_dict(orient="records")[0]
    except Exception:
        raise HTTPException(status_code=503, detail="Evaluation judge unavailable")


@app.post("/evaluate/batch")
def trigger_batch_eval(req: BatchEvaluateRequest, background_tasks: BackgroundTasks):
    # Restrict file access to the server-configured dataset, never an arbitrary client path.
    if req.dataset_path is not None and req.dataset_path != DATASET_PATH:
        raise HTTPException(status_code=400, detail="Use the configured evaluation dataset")
    try:
        raw = Path(DATASET_PATH).read_bytes()
        cases, dataset_provenance = load_dataset(json.loads(raw))
        cases = cases[:req.limit] if req.limit else cases
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unavailable evaluation dataset")
    run_id = str(uuid.uuid4())
    store = EvaluationStore(METRICS_DB_PATH)
    store.start(run_id, [c['id'] for c in cases], {
        **dataset_provenance, "dataset_sha256": hashlib.sha256(raw).hexdigest(), "limit": req.limit,
        "contract_version": 3, "scorer": "exact_result_citation_v2",
        "model_identity": "unrecorded", "prompt_version": "unrecorded"})
    background_tasks.add_task(run_cases, store, run_id, cases, PILOT_API_URL)
    return {"status": "started", "run_id": run_id, "schema_version": 1}
