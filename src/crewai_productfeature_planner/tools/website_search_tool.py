"""Website semantic search tool for deep research within specific sites.

Wraps the WebsiteSearchTool from crewai-tools, which uses RAG
(Retrieval-Augmented Generation) to semantically search within the
content of websites — useful for exploring competitor docs, API
references, and industry standard pages.
"""

from crewai_tools import WebsiteSearchTool


def create_website_search_tool(website: str = "") -> WebsiteSearchTool:
    """Create a website semantic search tool.

    Args:
        website: Optional URL to restrict searching to a specific site.
                 If empty, the agent can search within any site it discovers.

    Returns:
        Configured WebsiteSearchTool instance.
    """
    if website:
        return WebsiteSearchTool(website=website)
    return WebsiteSearchTool()
