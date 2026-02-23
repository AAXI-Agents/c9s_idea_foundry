"""Tests for the PRD file-write tool."""

from datetime import datetime

from crewai_productfeature_planner.tools.file_write_tool import PRDFileWriteTool


def _year_month_dir(base):
    """Return the expected YYYY/MM subdirectory under *base*."""
    now = datetime.now()
    return base / now.strftime("%Y") / now.strftime("%m")


def test_prd_file_write_creates_file(tmp_path):
    """Tool should create the file with the specified name and content."""
    tool = PRDFileWriteTool(output_dir=str(tmp_path))
    result = tool._run(content="# Test PRD", filename="test_prd.md", version=1)

    assert "test_prd.md" in result
    written = _year_month_dir(tmp_path) / "test_prd.md"
    assert written.exists()
    assert written.read_text() == "# Test PRD"


def test_prd_file_write_auto_generates_filename(tmp_path):
    """When no filename is given, one should be generated with version+timestamp."""
    tool = PRDFileWriteTool(output_dir=str(tmp_path))
    tool._run(content="# Auto PRD", version=2)

    ym = _year_month_dir(tmp_path)
    files = list(ym.glob("prd_v2_*.md"))
    assert len(files) == 1


def test_prd_file_write_creates_output_dir(tmp_path):
    """Tool should create nested output directories if they don't exist."""
    nested = tmp_path / "nested" / "dir"
    tool = PRDFileWriteTool(output_dir=str(nested))
    tool._run(content="# Nested PRD", filename="test.md")

    ym = _year_month_dir(nested)
    assert ym.exists()
    assert (ym / "test.md").exists()


def test_prd_file_write_adds_md_extension(tmp_path):
    """Tool should append .md when the filename lacks it."""
    tool = PRDFileWriteTool(output_dir=str(tmp_path))
    tool._run(content="# Ext Test", filename="my_prd")

    assert (_year_month_dir(tmp_path) / "my_prd.md").exists()


def test_prd_file_write_preserves_md_extension(tmp_path):
    """Tool should not double-append .md when the filename already has it."""
    tool = PRDFileWriteTool(output_dir=str(tmp_path))
    tool._run(content="# Ext Test", filename="my_prd.md")

    ym = _year_month_dir(tmp_path)
    assert (ym / "my_prd.md").exists()
    assert not (ym / "my_prd.md.md").exists()


def test_prd_file_write_year_month_subdir(tmp_path):
    """Output should land in a YYYY/MM subdirectory."""
    tool = PRDFileWriteTool(output_dir=str(tmp_path))
    result = tool._run(content="# PRD", filename="sub.md")

    now = datetime.now()
    expected = tmp_path / now.strftime("%Y") / now.strftime("%m") / "sub.md"
    assert expected.exists()
    assert str(now.strftime("%Y")) in result
    assert str(now.strftime("%m")) in result
