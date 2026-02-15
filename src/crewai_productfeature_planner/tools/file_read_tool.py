"""File read tool for reading reference documents and knowledge files.

Wraps the FileReadTool from crewai-tools to let agents read
existing PRDs, knowledge files, technical specs, and other documents.
"""

from crewai_tools import FileReadTool


def create_file_read_tool(file_path: str = "") -> FileReadTool:
    """Create a file read tool.

    Args:
        file_path: Optional path to restrict reading to a single file.
                   If empty, the agent can read any file it discovers.

    Returns:
        Configured FileReadTool instance.
    """
    if file_path:
        return FileReadTool(file_path=file_path)
    return FileReadTool()
