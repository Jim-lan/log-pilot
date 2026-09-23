"""Deterministic provider/budget contracts; no network or model loading."""
import unittest
from pathlib import Path
import importlib.util
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch


class BudgetContracts(unittest.TestCase):
    def test_deadline_prevents_new_calls(self):
        from shared.execution import RequestBudget, DeadlineExceeded
        clock = [10.0]
        budget = RequestBudget(timeout=5, max_llm_calls=2, clock=lambda: clock[0])
        clock[0] = 15.0
        with self.assertRaises(DeadlineExceeded):
            budget.begin_call("llm", 30)
        self.assertEqual(budget.calls["llm"], 0)

    def test_timeout_is_capped_by_remaining_time(self):
        from shared.execution import RequestBudget
        clock = [10.0]
        budget = RequestBudget(timeout=5, max_llm_calls=2, clock=lambda: clock[0])
        clock[0] = 13.0
        self.assertEqual(budget.begin_call("llm", 30), 2)

    def test_call_budget_exhaustion_is_sticky(self):
        from shared.execution import RequestBudget, CallBudgetExceeded
        budget = RequestBudget(timeout=5, max_llm_calls=1)
        budget.begin_call("llm", 2)
        with self.assertRaises(CallBudgetExceeded):
            budget.begin_call("llm", 2)
        with self.assertRaises(CallBudgetExceeded):
            budget.check()

    def test_cancellation_rejects_late_success(self):
        from shared.execution import RequestBudget, DeadlineExceeded
        budget = RequestBudget(timeout=5, max_llm_calls=2)
        budget.cancel()
        with self.assertRaises(DeadlineExceeded):
            budget.check()

    def test_request_contexts_are_separate(self):
        from shared.execution import RequestBudget, use_budget, current_budget
        a = RequestBudget(timeout=5, max_llm_calls=2)
        b = RequestBudget(timeout=5, max_llm_calls=2)
        with use_budget(a):
            a.begin_call("llm", 1)
            with use_budget(b):
                self.assertIs(current_budget(), b)
                self.assertEqual(b.calls["llm"], 0)
            self.assertIs(current_budget(), a)
        self.assertIsNone(current_budget())

    def test_late_provider_result_is_rejected(self):
        from shared.execution import RequestBudget, use_budget, invoke_provider, ProviderTimeout
        clock = [0.0]
        budget = RequestBudget(timeout=100, max_llm_calls=2, clock=lambda: clock[0])
        def late(timeout):
            clock[0] += timeout + 1
            return "late result"
        with use_budget(budget), self.assertRaises(ProviderTimeout):
            invoke_provider("llm", late)

    def test_search_budget_is_separate(self):
        from shared.execution import RequestBudget, CallBudgetExceeded
        budget = RequestBudget(timeout=10, max_llm_calls=1)
        budget.begin_call("llm", 2)
        budget.begin_call("search", 2)
        with self.assertRaises(CallBudgetExceeded):
            budget.begin_call("search", 2)


class ProviderContracts(unittest.TestCase):
    def setUp(self):
        from shared.execution import RequestBudget
        # SDK initialization time must not consume the simulated request budget.
        self.clock = [100.0]
        self.budget = RequestBudget(timeout=5, max_llm_calls=2, clock=lambda: self.clock[0])
        registry = ModuleType("services.pilot_orchestrator.src.model_registry")
        registry.registry = SimpleNamespace(get=lambda kind: SimpleNamespace(
            model_name="fixture", api_base="https://fixture.invalid/v1", api_key_env=None, temperature=0))
        tokens = ModuleType("services.pilot_orchestrator.src.token_counter")
        tokens.token_counter = None
        patches = patch.dict(sys.modules, {registry.__name__: registry, tokens.__name__: tokens})
        patches.start()
        self.addCleanup(patches.stop)
        self.module = self.load("budget_llm", "shared/llm/client.py")
        self.client = self.module.LLMClient()

    def load(self, name, path):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(name, root / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def sdk(self, handler):
        import httpx
        import openai
        client = openai.OpenAI(api_key="fixture", base_url="https://fixture.invalid/v1",
                               http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(client.close)
        self.client._get_client = lambda *args: client
        return client

    def test_real_sdk_receives_remaining_timeout(self):
        import httpx
        from shared.execution import use_budget
        seen = []
        def response(request):
            seen.append(request)
            return httpx.Response(200, json={"id": "fixture", "object": "chat.completion", "created": 0,
                "model": "fixture", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "fixture answer"}}]})
        self.sdk(response)
        self.clock[0] += 2
        with use_budget(self.budget):
            self.assertEqual(self.client.generate("question password=hunter2 learner@example.com"), "fixture answer")
        self.assertEqual(len(seen), 1)
        self.assertNotIn(b"hunter2", seen[0].content)
        self.assertNotIn(b"learner@example.com", seen[0].content)
        self.assertTrue(all(t == 3 for t in seen[0].extensions["timeout"].values()))
        self.assertEqual(self.budget.calls["llm"], 1)
        provenance = self.budget.provenance['model_calls']
        self.assertEqual(len(provenance), 1)
        self.assertEqual(provenance[0]['returned_model'], 'fixture')
        self.assertNotIn('hunter2', str(provenance))

    def test_sdk_timeout_has_no_hidden_retries(self):
        import httpx
        from shared.execution import use_budget, ProviderTimeout
        seen = []
        def timeout(request):
            seen.append(request)
            raise httpx.ReadTimeout("secret upstream URL", request=request)
        self.sdk(timeout)
        with use_budget(self.budget), self.assertRaises(ProviderTimeout) as error:
            self.client.generate("question")
        self.assertEqual(len(seen), 1)
        self.assertNotIn("secret", str(error.exception))

    def test_legacy_provider_errors_are_typed(self):
        import httpx
        from shared.execution import ExecutionFailure, use_budget
        self.module.registry = None
        self.client.config = {"llm": {"default_provider": "local", "providers": {"local": {
            "api_base": "https://fixture.invalid/v1", "default_model": "fixture"}}}}
        seen = []
        def unavailable(request):
            seen.append(request)
            return httpx.Response(503, json={"error": {"message": "private upstream diagnostics"}})
        self.sdk(unavailable)
        with use_budget(self.budget), self.assertRaises(ExecutionFailure) as error:
            self.client.generate("question")
        self.assertEqual(len(seen), 1)
        self.assertNotIn("private", str(error.exception))

    def test_search_client_timeout_and_cleanup(self):
        from shared.execution import use_budget
        factory = Mock()
        handle = factory.return_value.__enter__ = Mock(return_value=SimpleNamespace(
            text=Mock(return_value=[{"title": "fixture", "href": "https://fixture.invalid", "body": "evidence"}])))
        factory.return_value.__exit__ = Mock(return_value=False)
        dependency = ModuleType("duckduckgo_search")
        dependency.DDGS = factory
        with patch.dict(sys.modules, {"duckduckgo_search": dependency}):
            module = self.load("budget_search", "services/pilot_orchestrator/src/tools/web_search.py")
        with use_budget(self.budget):
            result = module.WebSearchTool().search("fixture password=hunter2 learner@example.com")
        self.assertIn("evidence", result)
        query = handle.return_value.text.call_args.args[0]
        self.assertNotIn("hunter2", query)
        self.assertNotIn("learner@example.com", query)
        self.assertTrue(0 < factory.call_args.kwargs["timeout"] <= 5)
        factory.return_value.__exit__.assert_called_once()
        self.assertEqual(self.budget.calls["search"], 1)
