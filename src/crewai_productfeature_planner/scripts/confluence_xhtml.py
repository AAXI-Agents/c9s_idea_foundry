"""Convert Markdown PRD content to Confluence-compatible XHTML.

The output is a valid XHTML fragment suitable for submission to the
Confluence REST API ``/rest/api/content`` endpoint (``storage`` format).

Usage::

    from crewai_productfeature_planner.confluence_xhtml import md_to_confluence_xhtml

    xhtml = md_to_confluence_xhtml("# Hello\\nSome **bold** text.")
"""

import re

import markdown

from crewai_productfeature_planner.scripts.logging_config import get_logger

logger = get_logger(__name__)

# Markdown extensions that improve Confluence compatibility.
_EXTENSIONS = [
    "tables",        # pipe-style tables → <table>
    "fenced_code",   # ```lang blocks → <pre><code>
    "toc",           # [TOC] support
    "nl2br",         # single newlines → <br />
    "sane_lists",    # stricter list parsing
]

_EXTENSION_CONFIGS: dict = {}


def md_to_confluence_xhtml(md_text: str) -> str:
    """Convert a Markdown string to Confluence storage-format XHTML.

    Args:
        md_text: Raw Markdown content.

    Returns:
        An XHTML string ready for the Confluence API ``storage`` representation.
    """
    md = markdown.Markdown(
        extensions=_EXTENSIONS,
        extension_configs=_EXTENSION_CONFIGS,
        output_format="xhtml",
    )
    xhtml = md.convert(md_text)

    # Wrap fenced code blocks in Confluence <ac:structured-macro> for
    # better rendering in the Confluence editor.
    xhtml = _wrap_code_blocks(xhtml)

    logger.debug(
        "Converted Markdown to Confluence XHTML (%d chars → %d chars)",
        len(md_text),
        len(xhtml),
    )
    return xhtml


def _wrap_code_blocks(xhtml: str) -> str:
    """Replace ``<pre>`` code blocks with Confluence code macro markup.

    Confluence uses ``ac:structured-macro`` with ``name="code"`` for
    syntax-highlighted code blocks.  This transforms standard HTML
    ``<pre>`` blocks into the Confluence storage format equivalent.
    """
    # Pattern: <pre ...><code class="language-xxx">...</code></pre>
    pattern = re.compile(
        r'<pre[^>]*><code\s+class="[^"]*language-(\w+)[^"]*">(.*?)</code></pre>',
        re.DOTALL,
    )

    def _replace(match: re.Match) -> str:
        lang = match.group(1)
        code = match.group(2)
        return (
            '<ac:structured-macro ac:name="code">'
            f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
            f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
            "</ac:structured-macro>"
        )

    result = pattern.sub(_replace, xhtml)

    # Also handle <pre> blocks without a language class
    plain_pattern = re.compile(
        r"<pre[^>]*><code>(.*?)</code></pre>",
        re.DOTALL,
    )

    def _replace_plain(match: re.Match) -> str:
        code = match.group(1)
        return (
            '<ac:structured-macro ac:name="code">'
            f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
            "</ac:structured-macro>"
        )

    return plain_pattern.sub(_replace_plain, result)
