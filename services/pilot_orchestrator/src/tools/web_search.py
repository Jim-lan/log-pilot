from duckduckgo_search import DDGS
import logging

class WebSearchTool:
    """
    Wrapper for DuckDuckGo Search.
    """
    def __init__(self):
        self.ddgs = DDGS()
        
    def search(self, query: str, max_results: int = 5) -> str:
        """
        Performs a web search and returns formatted results.
        """
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
