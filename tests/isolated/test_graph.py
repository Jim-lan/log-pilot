"""Real LangGraph, node functions, templates and DuckDB; external services stubbed."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]


class GraphContracts(unittest.TestCase):
    def setUp(self):
        if "LOGPILOT_TEST_SCRATCH" not in os.environ:
            raise RuntimeError("Use the isolated runner")
        previous = Path.cwd()
        scratch = tempfile.TemporaryDirectory(dir=os.environ["LOGPILOT_TEST_SCRATCH"])
        self.addCleanup(scratch.cleanup)
        self.addCleanup(os.chdir, previous)
        os.chdir(scratch.name)
        from shared.db.duckdb_client import DuckDBConnector
        from datetime import datetime
        self.db = DuckDBConnector()
        self.db.insert_batch([dict(timestamp=datetime(2026, 9, 11), severity="ERROR",
                                   service_name="fixture", body="synthetic error", context={"template_id": "1"})])
        self.responses = {"intent_classifier": "sql", "sql_generator": "SELECT count(*) FROM logs",
                          "synthesize_answer": "One error.", "validate_answer": '{"valid":true}',
                          "verify_context": '{"valid":true}', "query_rewriter": "fixture revised query",
                          "fix_sql": "SELECT count(*) FROM logs"}
        self.calls = []
        search_policy = patch.dict(os.environ, {"LOGPILOT_ALLOW_WEB_SEARCH": "true"})
        search_policy.start()
        self.addCleanup(search_policy.stop)

        def generate(prompt, model_type="fast"):
            task = prompt.splitlines()[0].removeprefix("TASK:")
            if not prompt.startswith("TASK:"):
                task = "fix_sql"
            self.calls.append((task, prompt))
            response = self.responses[task]
            if callable(response):
                response = response()
            if isinstance(response, Exception):
                raise response
            return response

        from shared.execution import current_budget, invoke_provider
        self.llm = SimpleNamespace(generate=lambda prompt, model_type="fast":
            invoke_provider("llm", lambda timeout: generate(prompt, model_type))
            if current_budget() is not None else generate(prompt, model_type))
        self.kb = Mock()
        self.kb.retrieve.return_value = [SimpleNamespace(metadata={"type": "runbook_card", "topic": "fixture"},
                                                        get_content=lambda: "Runbook fixture evidence")]
        self.web = Mock()
        self.web.search.return_value = "External fixture evidence"
        dependencies = {}
        for name, attr, value in [
            ("shared.llm.client", "LLMClient", lambda: self.llm),
            ("services.knowledge_base.src.store", "KnowledgeStore", lambda: self.kb),
            ("services.pilot_orchestrator.src.tools.web_search", "WebSearchTool", lambda: self.web),
        ]:
            module = ModuleType(name)
            setattr(module, attr, value)
            dependencies[name] = module
        patched = patch.dict(sys.modules, dependencies)
        patched.start()
        self.addCleanup(patched.stop)
        from shared.llm.prompt_factory import PromptFactory
        original = PromptFactory.create_prompt
        tagged = patch.object(PromptFactory, "create_prompt", lambda obj, agent, task, **kw:
                              "TASK:" + task + "\n" + original(obj, agent, task, **kw))
        tagged.start()
        self.addCleanup(tagged.stop)
        self.nodes = self.load("services.pilot_orchestrator.src.nodes", "nodes.py")
        self.graph = self.load("services.pilot_orchestrator.src.graph", "graph.py")

    def load(self, name, file):
        spec = importlib.util.spec_from_file_location(name, ROOT / "services/pilot_orchestrator/src" / file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def invoke(self):
        return self.graph.pilot_graph.invoke({"query": "fixture question", "messages": []},
                                             config={"recursion_limit": 60})

    def count(self, task):
        return sum(name == task for name, _ in self.calls)

    def test_versioned_quality_fixtures_execute_real_graph_and_database(self):
        import json
        from datetime import datetime
        from shared.evaluation_runner import score_case
        fixture = json.loads((Path(__file__).parent / "quality_cases_v1.json").read_text())
        self.db.query("DELETE FROM logs")
        self.db.insert_batch([{**row, "timestamp": datetime.fromisoformat(row["timestamp"])} for row in fixture["logs"]])
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.responses["sql_generator"] = case["sql"]
                result = self.graph.pilot_graph.invoke({"query": case["question"], "messages": []})
                self.assertEqual(score_case(case, result)[0], "passed")

    def test_heldout_sql_fixtures_use_real_graph_and_disposable_rows(self):
        import json
        from datetime import datetime
        from shared.evaluation_runner import score_case
        fixture = json.loads((Path(__file__).parent / 'quality_holdout_v2.json').read_text())
        self.db.query('DELETE FROM logs')
        self.db.insert_batch([{**row, 'timestamp': datetime.fromisoformat(row['timestamp'])} for row in fixture['logs']])
        for case in fixture['cases']:
            if 'sql' not in case:
                continue
            with self.subTest(case=case['id']):
                self.responses['sql_generator'] = case['sql']
                result = self.graph.pilot_graph.invoke({'query': case['question'], 'messages': []})
                self.assertEqual(score_case(case, result)[0], 'passed')
                self.assertEqual(score_case(case, {**result, 'sql_rows': None})[0], 'failed')
                self.assertEqual(score_case(case, {**result, 'sql_rows': [['incorrect']]})[0], 'failed')
        self.assertEqual(self.db.query('SELECT count(*) FROM logs'), [(4,)])

    def test_followup_context_reaches_rewrite_and_answer_in_real_graph(self):
        messages = [{'role': 'user', 'content': 'Count errors for fixture service'},
                    {'role': 'assistant', 'content': 'One error for fixture service'}]
        result = self.graph.pilot_graph.invoke({'query': 'Explain that result', 'messages': messages})
        self.assertEqual(result['final_answer'], 'One error.')
        for task in ('query_rewriter', 'synthesize_answer'):
            prompt = next(prompt for name, prompt in self.calls if name == task)
            self.assertIn('Count errors for fixture service', prompt)
            self.assertIn('One error for fixture service', prompt)

    def test_template_provenance_is_request_local(self):
        from shared.execution import RequestBudget, use_budget
        first, second = RequestBudget(60, 16), RequestBudget(60, 16)
        with use_budget(first):
            self.invoke()
        self.assertTrue(first.provenance["templates"])
        self.assertTrue(all(len(value) == 64 for value in first.provenance["templates"].values()))
        self.assertEqual(second.provenance["templates"], {})

    def test_sql_happy_path_uses_real_database(self):
        result = self.invoke()
        self.assertEqual(result["sql_result"], "[(1,)]")
        self.assertEqual(result["final_answer"], "One error.")
        self.assertEqual(self.count("synthesize_answer"), 1)

    def test_execution_rejection_cannot_be_synthesized_as_success(self):
        from shared.execution import SQLExecutionFailure
        from shared.sql_policy import SQLPolicyError
        def execute(sql, params=None, *, explain=False):
            if explain:
                return []
            raise SQLPolicyError('row limit exceeded')
        with patch.object(self.nodes.DuckDBConnector, 'query_analytics', side_effect=execute):
            with self.assertRaises(SQLExecutionFailure):
                self.invoke()
        self.assertEqual(self.count('synthesize_answer'), 0)

    def test_execution_preserves_request_deadline_failure(self):
        from shared.execution import DeadlineExceeded
        with patch.object(self.nodes.DuckDBConnector, 'query_analytics', side_effect=DeadlineExceeded()):
            with self.assertRaises(DeadlineExceeded):
                self.nodes.execute_sql({'sql_query': 'SELECT count(*) FROM logs'})

    def test_rag_happy_path_uses_runbook(self):
        self.responses["intent_classifier"] = "rag"
        result = self.invoke()
        self.assertIn("Runbook fixture evidence", result["rag_context"])
        self.web.search.assert_not_called()
        self.assertEqual(len(result['sources']), 1)
        source = result['sources'][0]
        self.assertIn('[source:' + source['source_id'] + ']', result['rag_context'])
        self.assertEqual(len(source['content_sha256']), 64)

    def test_fabricated_citation_fails_without_trusting_model_judge(self):
        self.responses['intent_classifier'] = 'rag'
        self.responses['synthesize_answer'] = 'Invented answer [source:nonexistent]'
        result = self.invoke()
        self.assertEqual(result['outcome'], 'insufficient_evidence')
        self.assertEqual(self.count('synthesize_answer'), 3)
        self.assertEqual(self.count('validate_answer'), 0)
        self.assertNotIn('nonexistent', result['final_answer'])

    def test_cited_runbook_answer_keeps_matching_artifact_identity(self):
        from shared.evidence import source_record
        node = self.kb.retrieve.return_value[0]
        source = source_record(node, node.get_content())
        self.responses['intent_classifier'] = 'rag'
        self.responses['synthesize_answer'] = 'Use the runbook [source:' + source['source_id'] + ']'
        result = self.invoke()
        self.assertEqual(result['outcome'], 'validated')
        self.assertEqual(result['sources'][0], source)

    def test_rejected_context_terminates_with_used_fallback(self):
        self.responses["intent_classifier"] = "rag"
        self.responses["verify_context"] = '{"valid":false,"feedback":"need fixture specifics"}'
        result = self.invoke()
        self.assertEqual(self.kb.retrieve.call_count, 3)
        self.web.search.assert_called_once()
        synthesis = [p for name, p in self.calls if name == "synthesize_answer"]
        self.assertIn("External fixture evidence", synthesis[0])
        rewrites = [p for name, p in self.calls if name == "query_rewriter"]
        self.assertTrue(rewrites)
        self.assertIn("need fixture specifics", rewrites[0])
        self.assertEqual(result["context_retry_count"], 2)

    def test_rejected_answers_stop_and_abstain(self):
        self.responses["validate_answer"] = '{"valid":false,"feedback":"cite fixture evidence"}'
        result = self.invoke()
        self.assertEqual(self.count("synthesize_answer"), 3)
        self.assertEqual(result["outcome"], "insufficient_evidence")
        self.assertNotEqual(result["final_answer"], "One error.")
        synthesis = [p for name, p in self.calls if name == "synthesize_answer"]
        self.assertIn("cite fixture evidence", synthesis[1])

    def test_malformed_judge_fails_closed(self):
        self.responses["validate_answer"] = "not json"
        result = self.invoke()
        self.assertFalse(result["answer_valid"])
        self.assertEqual(self.count("synthesize_answer"), 3)
        self.assertNotEqual(result["final_answer"], "One error.")

    def test_string_true_is_not_validated(self):
        self.responses["validate_answer"] = '{"valid":"true"}'
        result = self.invoke()
        self.assertFalse(result["answer_valid"])
        self.assertNotEqual(result["final_answer"], "One error.")

    def test_sql_repairs_do_not_consume_answer_retries(self):
        self.responses["sql_generator"] = "SELECT absent FROM logs"
        fixes = iter(["SELECT absent FROM logs", "SELECT count(*) FROM logs"])
        self.responses["fix_sql"] = lambda: next(fixes)
        verdicts = iter(['{"valid":false,"feedback":"try evidence"}', '{"valid":true}'])
        self.responses["validate_answer"] = lambda: next(verdicts)
        result = self.invoke()
        self.assertEqual(self.count("fix_sql"), 2)
        self.assertEqual(self.count("synthesize_answer"), 2)
        self.assertTrue(result["answer_valid"])

    def test_empty_retrieval_has_bounded_attempts(self):
        self.responses["intent_classifier"] = "rag"
        self.kb.retrieve.return_value = []
        self.invoke()
        self.assertEqual(self.kb.retrieve.call_count, 3)
        self.assertEqual(self.count("verify_context"), 0)
        self.web.search.assert_called_once()

    def test_search_disabled_without_explicit_opt_in(self):
        self.responses["intent_classifier"] = "web_search"
        with patch.dict(os.environ, {"LOGPILOT_ALLOW_WEB_SEARCH": ""}):
            result = self.invoke()
        self.web.search.assert_not_called()
        self.assertEqual(self.count("synthesize_answer"), 0)
        self.assertEqual(result["outcome"], "insufficient_evidence")

    def test_search_outage_is_not_evidence(self):
        self.responses["intent_classifier"] = "web_search"
        self.web.search.side_effect = TimeoutError("synthetic outage")
        result = self.invoke()
        self.assertEqual(result["outcome"], "dependency_error")
        self.assertEqual(self.count("synthesize_answer"), 0)

    def test_search_adapter_error_text_is_not_evidence(self):
        self.responses["intent_classifier"] = "web_search"
        self.web.search.return_value = "Error performing web search: synthetic outage"
        result = self.invoke()
        self.assertEqual(result["outcome"], "dependency_error")
        self.assertEqual(self.count("synthesize_answer"), 0)

    def test_sql_repair_exhaustion_is_bounded(self):
        self.responses["sql_generator"] = "SELECT absent FROM logs"
        self.responses["fix_sql"] = "SELECT absent FROM logs"
        self.responses["validate_answer"] = '{"valid":false}'
        result = self.invoke()
        self.assertEqual(self.count("fix_sql"), 3)
        self.assertEqual(self.count("synthesize_answer"), 3)
        self.assertEqual(result["outcome"], "insufficient_evidence")

    def test_call_budget_propagates_through_real_graph(self):
        from shared.execution import RequestBudget, use_budget, CallBudgetExceeded
        budget = RequestBudget(timeout=5, max_llm_calls=2)
        with use_budget(budget), self.assertRaises(CallBudgetExceeded):
            self.invoke()
        self.assertEqual(budget.calls["llm"], 2)
        self.assertEqual(self.count("synthesize_answer"), 0)

    def test_caught_provider_failure_still_stops_graph(self):
        from shared.execution import RequestBudget, use_budget, ProviderTimeout
        self.responses["intent_classifier"] = TimeoutError("synthetic")
        budget = RequestBudget(timeout=5, max_llm_calls=5)
        with use_budget(budget), self.assertRaises(ProviderTimeout):
            self.invoke()
        self.assertEqual(self.count("synthesize_answer"), 0)
