"""Search tool for market and technical research.

Wraps the SerperDevTool from crewai-tools, which uses the
Serper.dev Google Search API. Requires SERPER_API_KEY in the environment.
"""

from crewai_tools import SerperDevTool


def create_search_tool(n_results: int = 10) -> SerperDevTool:
    """Create a configured search tool for competitor and standards research.

    Args:
        n_results: Number of search results to return (default: 10).

    Returns:
        Configured SerperDevTool instance.
    """
    return SerperDevTool(n_results=n_results)
