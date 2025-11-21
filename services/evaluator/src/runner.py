import json
import os
import sys
import pandas as pd
from tqdm import tqdm
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from services.evaluator.src.scorer import EvalScorer
from services.schema_discovery.src.agent import DiscoveryAgent
from services.pilot_orchestrator.src.tools.sql_tool import SQLGenerator
# from services.pilot_orchestrator.src.nodes import retrieve_context # Harder to isolate RAG node without full graph

class EvalRunner:
    """
    Runs evaluations for specific agents.
    """
    
    def __init__(self, dataset_dir: str = "services/evaluator/datasets"):
        self.dataset_dir = dataset_dir
        self.scorer = EvalScorer()

    def load_dataset(self, name: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.dataset_dir, f"{name}.json")
        with open(path, "r") as f:
            return json.load(f)

    def evaluate_schema_discovery(self) -> pd.DataFrame:
        print("🧪 Evaluating Schema Discovery Agent...")
        data = self.load_dataset("schema_discovery")
        agent = DiscoveryAgent(max_retries=1) # Fast fail for eval
        
        results = []
        for item in tqdm(data):
            logs = item["logs"]
            expected = item["expected_regex"]
            
            predicted = agent.discover_schema(logs)
            score = self.scorer.score_regex(predicted, expected, logs)
            
            results.append({
                "id": item["id"],
                "score": score,
                "predicted": predicted,
                "expected": expected
            })
            
        return pd.DataFrame(results)

    def evaluate_sql_gen(self) -> pd.DataFrame:
        print("🧪 Evaluating SQL Generator...")
        data = self.load_dataset("sql_gen")
        agent = SQLGenerator()
        
        results = []
        for item in tqdm(data):
            query = item["query"]
            expected = item["expected_sql"]
            
            try:
                predicted = agent.generate_sql(query)
            except Exception as e:
                predicted = str(e)
                
            score = self.scorer.score_sql(predicted, expected)
            
            results.append({
                "id": item["id"],
                "score": score,
                "predicted": predicted,
                "expected": expected
            })
            
        return pd.DataFrame(results)

    # RAG evaluation would go here (omitted for brevity as it requires full KB setup)
