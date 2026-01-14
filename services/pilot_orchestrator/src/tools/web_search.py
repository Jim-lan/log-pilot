try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    
import logging

class WebSearchTool:
    """
    Wrapper for DuckDuckGo Search.
    """
    def __init__(self):
        if HAS_DDGS:
            self.ddgs = DDGS()
        else:
            self.ddgs = None
            logging.warning("duckduckgo_search not installed. Web Search disabled.")
        
    def search(self, query: str, max_results: int = 5) -> str:
        """
        Performs a web search and returns formatted results.
        """
        if not self.ddgs:
            return "Web Search is unavailable (duckduckgo_search package not installed)."
            
        try:
            results = self.ddgs.text(query, max_results=max_results)
            if not results:
                return "No web search results found."
            
            summary = ""
            for i, r in enumerate(results):
                summary += f"{i+1}. {r.get('title', 'No Title')}\n"
                summary += f"   Source: {r.get('href', 'N/A')}\n"
                summary += f"   Snippet: {r.get('body', r.get('snippet', ''))}\n\n"
                
            return summary.strip()
            
        except Exception as e:
            logging.error(f"Web Search Failed: {e}")
            return f"Error performing web search: {str(e)}"
