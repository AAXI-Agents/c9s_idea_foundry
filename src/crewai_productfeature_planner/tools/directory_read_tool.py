"""Directory read tool for listing project and output structures.

Wraps the DirectoryReadTool from crewai-tools so agents can inspect
directory contents — useful for checking existing PRD versions,
knowledge files, and project layout.
"""

from crewai_tools import DirectoryReadTool


def create_directory_read_tool(directory: str = "") -> DirectoryReadTool:
    """Create a directory read tool.

    Args:
        directory: Optional path to restrict reading to a specific directory.
                   If empty, the agent can read any directory it discovers.

    Returns:
        Configured DirectoryReadTool instance.
    """
    if directory:
        return DirectoryReadTool(directory=directory)
    return DirectoryReadTool()
