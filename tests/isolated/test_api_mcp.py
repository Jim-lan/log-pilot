"""Real HTTP API + real temporary DuckDB; stub graph/provider/transport edges."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from shared.db.duckdb_client import DuckDBConnector

ROOT = Path(__file__).resolve().parents[2]


def load_source(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class APIAndMCPContracts(unittest.TestCase):
    def setUp(self):
        if "LOGPILOT_TEST_SCRATCH" not in os.environ:
            raise RuntimeError("Run scripts/run_isolated_tests.py")
        self.previous = Path.cwd()
        self.scratch = tempfile.TemporaryDirectory(dir=os.environ["LOGPILOT_TEST_SCRATCH"])
        os.chdir(self.scratch.name)
        self.addCleanup(self.restore)
        self.db = DuckDBConnector()
        from datetime import datetime
        self.db.insert_batch([dict(timestamp=datetime(2026, 9, 10, 12), severity="ERROR",
                                   service_name="fixture", body="synthetic error")])
        graph_module = ModuleType("services.pilot_orchestrator.src.graph")
        self.graph = Mock()
        graph_module.pilot_graph = self.graph
        # Patch before importing the API, so no embedding or provider initializes.
        with patch.dict(sys.modules, {graph_module.__name__: graph_module}):
            self.api = load_source("isolated_api", "services/pilot_orchestrator/src/api.py")
        self.client = TestClient(self.api.app)
        self.addCleanup(self.client.close)

    def restore(self):
        os.chdir(self.previous)
        self.scratch.cleanup()

    def sql_response(self, state):
        return {**state, "intent": "sql", "final_answer": "One error.",
                "sql_query": "SELECT count(*) FROM logs", "sql_result": "[(1,)]"}

    def test_first_query_preserves_response_contract(self):
        self.graph.invoke.side_effect = self.sql_response
        response = self.client.post("/query", json={"query": "count errors"})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data["answer"], data["sql_result"], data["intent"]), ("One error.", "[(1,)]", "sql"))
        self.assertGreaterEqual(data["metadata"]["latency"], 0)
        self.assertEqual(data["trace"], [])

    def test_two_turn_query_and_history_reload(self):
        self.graph.invoke.side_effect = self.sql_response
        first = self.client.post("/query", json={"query": "count errors"})
        second = self.client.post("/query", json={"query": "list them"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        prior = self.graph.invoke.call_args.args[0]["messages"]
        self.assertEqual([m["content"] for m in prior], ["count errors", "One error."])
        self.assertEqual(second.json()["trace"][0], {"type": "user", "content": "count errors"})
        history = self.client.get("/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual([m["content"] for m in history.json()], ["count errors", "One error.", "list them", "One error."])

    def test_rag_evidence_preserved(self):
        self.graph.invoke.return_value = {"intent": "rag", "final_answer": "Inspect configuration.",
                                          "rag_context": "Synthetic runbook evidence."}
        data = self.client.post("/query", json={"query": "why"}).json()
        self.assertEqual(data["context"], "Synthetic runbook evidence.")
        self.assertEqual(data["intent"], "rag")

    def test_web_fallback_returns_used_evidence_and_retry_metadata(self):
        self.graph.invoke.return_value = {"intent": "web_search", "final_answer": "External answer",
                                          "rag_context": "rejected local context", "web_results": "used web evidence",
                                          "outcome": "validated", "context_retry_count": 2}
        data = self.client.post("/query", json={"query": "why"}).json()
        self.assertEqual(data["context"], "used web evidence")
        self.assertEqual(data["metadata"]["outcome"], "validated")
        self.assertEqual(data["metadata"]["retry_counts"], {"sql": 0, "context": 2, "answer": 0})

    def test_message_object_tool_metadata_preserved(self):
        message = SimpleNamespace(type="ai", content="tool result", tool_calls=[{"name": "sql", "args": {}}])
        self.graph.invoke.return_value = {"intent": "sql", "final_answer": "Done", "messages": [message]}
        data = self.client.post("/query", json={"query": "count"}).json()
        self.assertEqual(data["trace"][0]["tool_calls"], message.tool_calls)

    def test_dictionary_tool_metadata_preserved(self):
        message = {"type": "ai", "content": "tool result", "tool_calls": [{"name": "sql", "args": {}}]}
        self.graph.invoke.return_value = {"intent": "sql", "final_answer": "Done", "messages": [message]}
        response = self.client.post("/query", json={"query": "count"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["trace"], [message])

    def test_only_ten_previous_messages_sent_to_graph(self):
        for i in range(12):
            self.db.save_message("default", "user", "message-" + str(i))
        self.graph.invoke.side_effect = self.sql_response
        response = self.client.post("/query", json={"query": "follow up"})
        self.assertEqual(response.status_code, 200, response.text)
        messages = self.graph.invoke.call_args.args[0]["messages"]
        self.assertEqual([m["content"] for m in messages], ["message-" + str(i) for i in range(2, 12)])

    def test_graph_error_is_not_saved_as_success(self):
        self.graph.invoke.side_effect = RuntimeError("synthetic graph failure")
        response = self.client.post("/query", json={"query": "count"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.db.get_history(), [])

    def test_invalid_request_rejected(self):
        response = self.client.post("/query", json={})
        self.assertEqual(response.status_code, 422)
        self.graph.invoke.assert_not_called()

    def test_health_contract_with_provider_stub(self):
        nodes = ModuleType("services.pilot_orchestrator.src.nodes")
        nodes.llm_client = SimpleNamespace(check_health=lambda: {"status": "ready", "model": "fixture"})
        with patch.dict(sys.modules, {nodes.__name__: nodes}):
            response = self.client.get("/health")
        self.assertEqual(response.json(), {"status": "ok", "llm": {"status": "ready", "model": "fixture"}})

    def mcp(self):
        module = ModuleType("fastmcp")
        module.FastMCP = lambda name: SimpleNamespace(tool=lambda: lambda fn: fn,
                                                     resource=lambda uri: lambda fn: fn)
        with patch.dict(sys.modules, {"fastmcp": module}):
            return load_source("isolated_mcp", "services/mcp_server/src/main.py")

    def test_mcp_query_uses_real_connector(self):
        self.assertEqual(self.mcp().query_logs("SELECT count(*) FROM logs"), "[(1,)]")

    def test_mcp_recent_logs_uses_real_connector(self):
        result = self.mcp().get_recent_logs()
        self.assertNotIn("Error fetching", result)
        self.assertIn("synthetic error", result)

    def test_mcp_schema_uses_real_connector(self):
        result = self.mcp().get_schema()
        self.assertNotIn("Error fetching", result)
        self.assertIn("service_name", result)

    def test_mcp_reports_query_error(self):
        self.assertIn("Error executing SQL:", self.mcp().query_logs("SELECT missing FROM logs"))

    def test_mcp_forwarding_and_timeout(self):
        mcp = self.mcp()
        response = Mock()
        response.json.return_value = {"answer": "fixture answer"}
        with patch.object(mcp.requests, "post", return_value=response) as post:
            self.assertEqual(mcp.ask_log_pilot("question"), "fixture answer")
            post.assert_called_once_with("http://pilot-orchestrator:8000/query", json={"query": "question"}, timeout=60)
            response.raise_for_status.assert_called_once()
        with patch.object(mcp.requests, "post", side_effect=mcp.requests.Timeout("synthetic")):
            self.assertIn("Error calling Pilot:", mcp.ask_log_pilot("question"))
