"""Web scraping tool for competitor and product research.

Wraps the ScrapeWebsiteTool from crewai-tools to extract content
from competitor websites, product pages, and technical documentation.
"""

from crewai_tools import ScrapeWebsiteTool


def create_scrape_tool() -> ScrapeWebsiteTool:
    """Create a web scraping tool for extracting website content.

    Returns an un-scoped instance so the agent can scrape any URL
    it discovers during research.
    """
    return ScrapeWebsiteTool()
