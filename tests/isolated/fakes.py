"""Explicit scripted boundaries for later agent tests; never call a provider."""
class ScriptedLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, prompt, model_type="fast"):
        self.calls.append((prompt, model_type))
        try:
            response = next(self.responses)
        except StopIteration:
            raise AssertionError("Unexpected extra LLM call")
        if isinstance(response, Exception):
            raise response
        return response


class ScriptedSearch:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, query):
        self.calls.append(query)
        return self.results
