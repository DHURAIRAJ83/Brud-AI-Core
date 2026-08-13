"""MB-28: Citation Formatter -- pure. Formats tool-result/report-derived
facts into inline citations, so the assistant never asserts a
tool-sourced fact without attribution back to the tool that produced it.
"""

from __future__ import annotations

from typing import Any


def format_citation(*, source_name: str, fact: str) -> str:
    return f"{fact} [source: {source_name}]"


def append_citations(*, text: str, tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return text
    citation_lines = [
        format_citation(source_name=result.get("tool_name", "unknown"), fact=result.get("summary", ""))
        for result in tool_results
        if result.get("summary")
    ]
    if not citation_lines:
        return text
    return text + "\n\nSources:\n" + "\n".join(f"- {line}" for line in citation_lines)
