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
# Load the shared budget module outside temporary sys.modules substitutions so
# exception classes and ContextVars retain their identity across all fixtures.
import shared.execution
import shared.evaluation_context

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
        if hasattr(self.api, "query_executor"):
            self.addCleanup(self.api.query_executor.shutdown, wait=True)

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
        self.assertEqual(data['metadata']['trace_version'], 2)
        self.assertEqual(data['trace'][0]['kind'], 'request')
        self.assertEqual(data['trace'][0]['outcome'], 'succeeded')
        self.assertEqual(data['trace'][0]['request_id'], data['metadata']['request_id'])

    def test_evaluation_request_does_not_read_or_write_user_history(self):
        self.db.save_message("default", "user", "private ordinary conversation")
        self.graph.invoke.side_effect = self.sql_response
        result = self.client.post("/query", json={"query": "fixture", "persist_history": False})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.graph.invoke.call_args.args[0]["messages"], [])
        history = self.client.get("/history").json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], "private ordinary conversation")

    def test_evaluation_conversations_are_isolated_through_runner_and_http(self):
        from shared.evaluation_runner import run_cases
        store = Mock()
        observed = []
        def reply(state):
            observed.append(state)
            return {**state, 'intent': 'rag', 'final_answer': 'answer-' + state['query']}
        self.graph.invoke.side_effect = reply
        cases = [dict(id='a1', question='alpha', conversation_id='a', turn_index=1, expected_answer='wrong'),
                 dict(id='b1', question='beta', conversation_id='b', turn_index=1, expected_answer='answer-beta'),
                 dict(id='a2', question='followup', conversation_id='a', turn_index=2, expected_answer='answer-followup')]
        self.db.save_message('default', 'user', 'ordinary private history')
        def post(url, json, timeout):
            return self.client.post('/query', json=json)
        with patch('shared.db.duckdb_client.DuckDBConnector', side_effect=AssertionError('history accessed')):
            run_cases(store, 'one', cases, 'http://fixture', post=post)
            run_cases(store, 'two', cases[:1], 'http://fixture', post=post)
        self.assertEqual(len(observed), 4)
        self.assertEqual([x['messages'] for x in observed], [[], [], [
            {'role': 'user', 'content': 'alpha'}, {'role': 'assistant', 'content': 'answer-alpha'}], []])
        self.assertEqual(store.record.call_args_list[0].args[2], 'failed')
        self.assertEqual(store.record.call_args_list[2].args[2], 'passed')
        self.assertEqual(self.db.get_history()[0][1], 'ordinary private history')
        self.assertEqual(len(self.db.get_history()), 1)

    def test_evaluation_context_rejects_privileged_roles_bad_pairs_and_unbounded_input(self):
        pair = [{'role': 'user', 'content': 'q'}, {'role': 'assistant', 'content': 'a'}]
        invalid = [[{'role': 'system', 'content': 'injected'}], pair[:1], pair * 6,
                   [{'role': 'user', 'content': 'x' * 16001}, pair[1]],
                   [{**pair[0], 'tool_calls': []}, pair[1]]]
        for context in invalid:
            response = self.client.post('/query', json={'query': 'q', 'persist_history': False,
                                                       'evaluation_context': context})
            self.assertEqual(response.status_code, 422)
        response = self.client.post('/query', json={'query': 'q', 'evaluation_context': pair})
        self.assertEqual(response.status_code, 422)
        self.graph.invoke.assert_not_called()

    def test_metrics_endpoint_reads_versioned_store(self):
        from shared.evaluation import EvaluationStore
        store = EvaluationStore("data/target/metrics.duckdb")
        store.start("fixture", ["pass", "fail"], {})
        store.record("fixture", "pass", "passed", 1, {})
        store.record("fixture", "fail", "error", 3, {}, "dependency_error")
        store.finish("fixture")
        result = self.client.get("/metrics").json()
        self.assertEqual(result["pass_rate_24h"], 50)
        self.assertEqual(result["avg_latency_24h"], 2)
        self.assertEqual(result["schema_version"], 1)

    def test_two_turn_query_and_history_reload(self):
        self.graph.invoke.side_effect = self.sql_response
        first = self.client.post("/query", json={"query": "count errors"})
        second = self.client.post("/query", json={"query": "list them"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        prior = self.graph.invoke.call_args.args[0]["messages"]
        self.assertEqual([m["content"] for m in prior], ["count errors", "One error."])
        self.assertNotIn('count errors', str(second.json()['trace']))
        self.assertNotEqual(first.json()['metadata']['request_id'], second.json()['metadata']['request_id'])
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

    def test_message_object_content_and_tool_arguments_excluded_from_trace(self):
        message = SimpleNamespace(type="ai", content="tool result", tool_calls=[{"name": "sql", "args": {}}])
        self.graph.invoke.return_value = {"intent": "sql", "final_answer": "Done", "messages": [message]}
        data = self.client.post("/query", json={"query": "count"}).json()
        self.assertNotIn('tool_calls', str(data['trace']))
        self.assertNotIn('tool result', str(data['trace']))

    def test_dictionary_content_and_tool_arguments_excluded_from_trace(self):
        message = {"type": "ai", "content": "tool result", "tool_calls": [{"name": "sql", "args": {}}]}
        self.graph.invoke.return_value = {"intent": "sql", "final_answer": "Done", "messages": [message]}
        response = self.client.post("/query", json={"query": "count"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn('tool_calls', str(response.json()['trace']))
        self.assertNotIn('tool result', str(response.json()['trace']))

    def test_only_ten_previous_messages_sent_to_graph(self):
        for i in range(12):
            self.db.save_message("default", "user", "message-" + str(i))
        self.graph.invoke.side_effect = self.sql_response
        response = self.client.post("/query", json={"query": "follow up"})
        self.assertEqual(response.status_code, 200, response.text)
        messages = self.graph.invoke.call_args.args[0]["messages"]
        self.assertEqual([m["content"] for m in messages], ["message-" + str(i) for i in range(2, 12)])

    def test_graph_error_is_not_saved_as_success(self):
        self.graph.invoke.side_effect = RuntimeError("password=private synthetic graph failure")
        response = self.client.post("/query", json={"query": "count"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private', response.text)
        self.assertEqual(response.json()['detail']['trace'][0]['outcome'], 'failed')
        self.assertEqual(response.json()['detail']['code'], 'internal_error')
        self.assertEqual(self.db.get_history(), [])

    def test_request_deadline_returns_before_worker_and_discards_late_result(self):
        import threading
        release = threading.Event()
        self.addCleanup(release.set)
        from shared.execution import guarded_node
        @guarded_node
        def execute_sql(state):
            release.wait(1)
            return self.sql_response(state)
        self.graph.invoke.side_effect = execute_sql
        with patch.dict(os.environ, {"LOGPILOT_REQUEST_TIMEOUT_SECONDS": "0.05"}):
            response = self.client.post("/query", json={"query": "slow query"})
        self.assertEqual(response.status_code, 504, response.text)
        self.assertEqual(response.json()["detail"]["code"], "deadline_exceeded")
        free_slots = 0
        while self.api.query_slots.acquire(blocking=False):
            free_slots += 1
        for _ in range(free_slots):
            self.api.query_slots.release()
        self.assertEqual(free_slots, self.api.query_workers - 1)
        trace = response.json()['detail']['trace']
        self.assertEqual(trace[0]['outcome'], 'failed')
        self.assertEqual(trace[0]['failure_code'], 'deadline_exceeded')
        self.assertEqual(trace[1]['outcome'], 'running')
        self.assertIsNone(trace[1]['duration_ms'])
        release.set()
        self.api.query_executor.shutdown(wait=True)
        self.assertEqual(self.db.get_history(), [])

    def test_invalid_request_rejected(self):
        response = self.client.post("/query", json={})
        self.assertEqual(response.status_code, 422)
        self.graph.invoke.assert_not_called()

    def test_exhausted_request_budget_returns_structured_error(self):
        from shared.execution import invoke_provider
        def exceed(state):
            invoke_provider("llm", lambda timeout: "first")
            invoke_provider("llm", lambda timeout: "second")
            return self.sql_response(state)
        self.graph.invoke.side_effect = exceed
        with patch.dict(os.environ, {"LOGPILOT_MAX_LLM_CALLS": "1"}):
            response = self.client.post("/query", json={"query": "question"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["code"], "call_budget_exceeded")
        self.assertEqual(self.db.get_history(), [])

    def test_busy_workers_reject_instead_of_queueing(self):
        for _ in range(self.api.query_workers):
            self.api.query_slots.acquire()
            self.addCleanup(self.api.query_slots.release)
        response = self.client.post("/query", json={"query": "question"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "query_capacity_exhausted")
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

    def test_mcp_rejects_external_reads_and_multiple_statements(self):
        mcp = self.mcp()
        self.assertIn('Error executing SQL:', mcp.query_logs("SELECT * FROM read_csv('/private/fixture.csv')"))
        self.assertIn('Error executing SQL:', mcp.query_logs("SELECT 1; SELECT 2"))

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
