"""Tests for the Confluence XHTML converter module."""

import pytest

from crewai_productfeature_planner.scripts.confluence_xhtml import (
    _wrap_code_blocks,
    md_to_confluence_xhtml,
)


# ── md_to_confluence_xhtml ────────────────────────────────────


class TestMdToConfluenceXhtml:
    """Unit tests for md_to_confluence_xhtml."""

    def test_empty_input(self):
        assert md_to_confluence_xhtml("") == ""

    def test_heading_conversion(self):
        result = md_to_confluence_xhtml("# Title\n## Subtitle")
        assert "<h1" in result
        assert "Title" in result
        assert "<h2" in result
        assert "Subtitle" in result

    def test_bold_and_italic(self):
        result = md_to_confluence_xhtml("**bold** and *italic*")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_unordered_list(self):
        result = md_to_confluence_xhtml("- item one\n- item two")
        assert "<li>" in result
        assert "item one" in result

    def test_ordered_list(self):
        result = md_to_confluence_xhtml("1. first\n2. second")
        assert "<ol>" in result
        assert "<li>" in result

    def test_table_rendering(self):
        md = "| Col A | Col B |\n|-------|-------|\n| 1     | 2     |"
        result = md_to_confluence_xhtml(md)
        assert "<table>" in result
        assert "<th>" in result or "<td>" in result

    def test_inline_code(self):
        result = md_to_confluence_xhtml("Use `pip install`")
        assert "<code>" in result
        assert "pip install" in result

    def test_fenced_code_block_with_language(self):
        md = "```python\nprint('hello')\n```"
        result = md_to_confluence_xhtml(md)
        # Should be wrapped in Confluence macro
        assert "ac:structured-macro" in result
        assert 'ac:name="code"' in result
        assert "python" in result

    def test_fenced_code_block_without_language(self):
        md = "```\nsome code\n```"
        result = md_to_confluence_xhtml(md)
        assert "ac:structured-macro" in result

    def test_link(self):
        result = md_to_confluence_xhtml("[Click](https://example.com)")
        assert "https://example.com" in result
        assert "Click" in result

    def test_returns_xhtml_format(self):
        """XHTML output should use self-closing tags like <br />."""
        result = md_to_confluence_xhtml("line1\nline2")
        # nl2br extension converts single newlines to <br />
        assert "<br />" in result or "<br/>" in result

    def test_multiline_prd_content(self):
        """A realistic PRD snippet should convert without error."""
        md = (
            "# Feature: SSO\n\n"
            "## Overview\n"
            "Single sign-on for enterprise.\n\n"
            "## Requirements\n"
            "- SAML 2.0 support\n"
            "- OAuth 2.0 fallback\n\n"
            "```yaml\nauth:\n  provider: okta\n```\n"
        )
        result = md_to_confluence_xhtml(md)
        assert "<h1" in result
        assert "<h2" in result
        assert "<li>" in result
        assert "ac:structured-macro" in result


# ── _wrap_code_blocks ─────────────────────────────────────────


class TestWrapCodeBlocks:
    """Unit tests for _wrap_code_blocks helper."""

    def test_no_code_blocks_unchanged(self):
        html = "<p>Hello world</p>"
        assert _wrap_code_blocks(html) == html

    def test_language_class_wrapped(self):
        html = '<pre><code class="language-js">let x = 1;</code></pre>'
        result = _wrap_code_blocks(html)
        assert 'ac:name="code"' in result
        assert 'ac:name="language">js</ac:parameter>' in result
        assert "let x = 1;" in result

    def test_plain_code_wrapped(self):
        html = "<pre><code>plain code</code></pre>"
        result = _wrap_code_blocks(html)
        assert 'ac:name="code"' in result
        assert "plain code" in result

    def test_multiple_blocks(self):
        html = (
            '<pre><code class="language-py">a=1</code></pre>'
            "<p>text</p>"
            "<pre><code>b=2</code></pre>"
        )
        result = _wrap_code_blocks(html)
        assert result.count("ac:structured-macro") == 4  # 2 open + 2 close
