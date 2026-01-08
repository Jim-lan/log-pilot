import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.pilot_orchestrator.src.graph import pilot_graph
from services.pilot_orchestrator.src.state import AgentState

class TestAgenticScenarios(unittest.TestCase):
    """
    Gold Test Cases for Agentic RAG.
    Simulates specific scenarios to verify agentic behaviors (Loops, Self-Correction).
    """

    def setUp(self):
        print("\n" + "="*50)

    @patch('services.pilot_orchestrator.src.nodes.DuckDBConnector')
    @patch('services.pilot_orchestrator.src.nodes.llm_client')
    @patch('services.pilot_orchestrator.src.nodes.get_kb_store')
    def test_scenario_bad_context_recovery(self, mock_kb, mock_llm, mock_db):
        """
        🏆 Gold Case: "The Confused Retriever"
        Scenario: User asks about "Auth". 
        1. Retriever fetches "Database" logs (Irrelevant).
        2. Context Verifier rejects it.
        3. Agent rewrites query to be more specific.
        4. Retriever fetches "Auth" logs (Relevant).
        5. Context Verifier approves.
        6. Agent answers.
        """
        print("🧪 Scenario: Bad Context Recovery (Self-Correction)")
        
        # --- Mocks ---
        # 1. KB: Returns [Bad Node] then [Good Node]
        bad_node = MagicMock()
        bad_node.get_content.return_value = "Database connection lost"
        bad_node.metadata = {"cluster_id": "999"}
        
        good_node = MagicMock()
        good_node.get_content.return_value = "User failed to login (Auth Error)"
        good_node.metadata = {"cluster_id": "101"}
        
        mock_kb_instance = MagicMock()
        mock_kb_instance.retrieve.side_effect = [
            [MagicMock(node=bad_node)], # 1st try (Bad)
            [MagicMock(node=good_node)] # 2nd try (Good)
        ]
        mock_kb.return_value = mock_kb_instance

        # 2. LLM Sequence
        mock_llm.generate.side_effect = [
            "auth issues",                                  # 1. Rewrite (Initial)
            "rag",                                          # 2. Classify
            '{"valid": false, "feedback": "Logs are about DB, not Auth"}', # 3. Verify Context (FAIL)
            "auth error logs specific",                     # 4. Rewrite (Retry)
            "rag",                                          # 5. Classify (Retry)
            '{"valid": true, "feedback": "Logs are about Auth"}', # 6. Verify Context (PASS)
            "There are auth errors.",                       # 7. Synthesize
            '{"valid": true, "feedback": "Good answer"}'    # 8. Validate Answer
        ]
        
        # 3. DB (Just needs to return something to avoid crash)
        mock_db_instance = MagicMock()
        mock_db_instance.query.return_value = [("2024-01-01", "auth", "ERROR", "Login failed")]
        mock_db.return_value = mock_db_instance

        # --- Execution ---
        state = AgentState(
            query="check auth",
            messages=[{"role": "user", "content": "check auth"}],
            history=[],
            retry_count=0
        )
        result = pilot_graph.invoke(state)

        # --- Verification ---
        self.assertTrue(result["context_valid"], "Final context should be valid")
        print("✅ Agent successfully rejected bad context and retried!")

    @patch('services.pilot_orchestrator.src.nodes.DuckDBConnector')
    @patch('services.pilot_orchestrator.src.nodes.llm_client')
    @patch('services.pilot_orchestrator.src.nodes.get_kb_store')
    def test_scenario_lazy_answer_correction(self, mock_kb, mock_llm, mock_db):
        """
        🏆 Gold Case: "The Lazy LLM"
        Scenario: User asks for a summary.
        1. Agent retrieves good logs.
        2. Agent answers "I don't know" (Lazy).
        3. Answer Validator rejects it.
        4. Agent retries and gives a full summary.
        """
        print("🧪 Scenario: Lazy Answer Correction")
        
        # --- Mocks ---
        # 1. KB: Good logs immediately
        node = MagicMock()
        node.get_content.return_value = "Error 500 in API"
        node.metadata = {"cluster_id": "500"}
        mock_kb_instance = MagicMock()
        mock_kb_instance.retrieve.return_value = [MagicMock(node=node)]
        mock_kb.return_value = mock_kb_instance

        # 2. LLM Sequence
        mock_llm.generate.side_effect = [
            "api errors",                                   # 1. Rewrite
            "rag",                                          # 2. Classify
            '{"valid": true, "feedback": "Relevant logs"}', # 3. Verify Context (PASS)
            "I don't know.",                                # 4. Synthesize (LAZY!)
            '{"valid": false, "feedback": "You have logs, answer the question!"}', # 5. Validate (FAIL)
            "The API is throwing Error 500.",               # 6. Synthesize (Retry)
            '{"valid": true, "feedback": "Much better."}'   # 7. Validate (PASS)
        ]
        
        mock_db_instance = MagicMock()
        mock_db_instance.query.return_value = [("2024-01-01", "api", "ERROR", "Error 500")]
        mock_db.return_value = mock_db_instance

        # --- Execution ---
        state = AgentState(
            query="what is wrong",
            messages=[{"role": "user", "content": "what is wrong"}],
            history=[],
            retry_count=0
        )
        result = pilot_graph.invoke(state)

        # --- Verification ---
        self.assertTrue(result["answer_valid"], "Final answer should be valid")
        self.assertEqual(result["final_answer"], "The API is throwing Error 500.")
        print("✅ Agent successfully corrected a lazy answer!")

if __name__ == "__main__":
    unittest.main()
