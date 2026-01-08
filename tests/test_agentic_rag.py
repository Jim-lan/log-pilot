import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from services.pilot_orchestrator.src.graph import pilot_graph
from services.pilot_orchestrator.src.state import AgentState

class TestAgenticRAG(unittest.TestCase):
    
    @patch('services.pilot_orchestrator.src.nodes.DuckDBConnector')
    @patch('services.pilot_orchestrator.src.nodes.llm_client')
    @patch('services.pilot_orchestrator.src.nodes.get_kb_store')
    def test_rag_flow_success(self, mock_kb, mock_llm, mock_db):
        """
        Test the happy path: Rewrite -> Classify(RAG) -> Retrieve -> Verify(Valid) -> Synthesize -> Validate(Valid) -> END
        """
        # Mock LLM Responses
        mock_llm.generate.side_effect = [
            "rewritten query", # rewrite_query
            "rag",             # classify_intent
            '{"valid": true, "feedback": "Context is good"}', # verify_context
            "Final Answer",    # synthesize_answer
            '{"valid": true, "feedback": "Answer is good"}'   # validate_answer
        ]
        
        # Mock KB Retrieval
        mock_kb_instance = MagicMock()
        mock_node = MagicMock()
        mock_node.get_content.return_value = "User bob failed to login"
        mock_node.metadata = {"cluster_id": "101"}
        mock_kb_instance.retrieve.return_value = [MagicMock(node=mock_node)] 
        mock_kb.return_value = mock_kb_instance

        # Initial State
        state = AgentState(
            query="test query",
            messages=[{"role": "user", "content": "hello"}], # Add history to trigger rewrite
            history=[],
            retry_count=0
        )
        
        # Run Graph
        result = pilot_graph.invoke(state)
        
        # Assertions
        self.assertTrue(result.get("context_valid"))
        self.assertTrue(result.get("answer_valid"))
        self.assertEqual(result.get("final_answer"), "Final Answer")
        print("✅ Happy Path Verified")

    @patch('services.pilot_orchestrator.src.nodes.DuckDBConnector')
    @patch('services.pilot_orchestrator.src.nodes.llm_client')
    @patch('services.pilot_orchestrator.src.nodes.get_kb_store')
    def test_rag_context_retry(self, mock_kb, mock_llm, mock_db):
        """
        Test context retry: ... -> Verify(Invalid) -> Rewrite -> ...
        """
        # Mock LLM Responses
        mock_llm.generate.side_effect = [
            "rewritten query 1", # rewrite_query (1st)
            "rag",               # classify_intent
            '{"valid": false, "feedback": "Bad context"}', # verify_context (Invalid)
            "rewritten query 2", # rewrite_query (2nd - Retry)
            "rag",               # classify_intent (2nd)
            '{"valid": true, "feedback": "Good context"}', # verify_context (Valid)
            "Final Answer",      # synthesize_answer
            '{"valid": true, "feedback": "Answer is good"}' # validate_answer
        ]
        
        mock_kb_instance = MagicMock()
        mock_node = MagicMock()
        mock_node.get_content.return_value = "User bob failed to login"
        mock_node.metadata = {"cluster_id": "101"}
        mock_kb_instance.retrieve.return_value = [MagicMock(node=mock_node)]
        mock_kb.return_value = mock_kb_instance

        # Mock DuckDB
        mock_db_instance = MagicMock()
        mock_db_instance.query.return_value = [("2024-01-01", "auth", "ERROR", "User bob failed")]
        mock_db.return_value = mock_db_instance

        state = AgentState(
            query="test query",
            messages=[{"role": "user", "content": "hello"}], # Add history
            history=[],
            retry_count=0
        )
        
        result = pilot_graph.invoke(state)
        
        self.assertTrue(result.get("context_valid"))
        print("✅ Context Retry Verified")

if __name__ == "__main__":
    unittest.main()
