from shared.evidence import web_evidence
from shared.privacy import redact_outbound
try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    
import logging
from shared.execution import invoke_provider, ExecutionFailure, ProviderTimeout

class WebSearchTool:
    """
    Wrapper for DuckDuckGo Search.
    """
    def __init__(self):
        pass
        
    def search(self, query: str, max_results: int = 5) -> dict:
        """
        Performs a web search and returns attributed snippet evidence.
        """
        def request(timeout):
            if not HAS_DDGS:
                raise ExecutionFailure()
            # Client is per call: concurrent requests cannot share mutable timeout
            # settings, and transport resources close before releasing capacity.
            transport_timeout = int(timeout)
            if transport_timeout < 1:
                raise ProviderTimeout()
            with DDGS(timeout=transport_timeout) as client:
                results = list(client.text(redact_outbound(query), max_results=max_results))
            return web_evidence(results)

        return invoke_provider("search", request)
