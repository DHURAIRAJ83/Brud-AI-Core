"""MB-09: Local Draft Planner -- pure. Prepares STRUCTURE only: an
outline, required topics, and sample format templates. Never invents
a fact, never fills in real content, and never claims the result is
verified -- every draft this module returns carries
`"verified": False` and an explicit disclosure string, structurally
impossible to omit since it is hard-coded into the return value, not
left to the caller to remember to add.
"""

from __future__ import annotations

from typing import Any

_FORMAT_TEMPLATES = {
    "QA pairs": {"instruction": "<question about {topic}, to be written by a human or an approved source>", "output_text": "<answer -- never invented here>"},
    "Documentation": {"section_heading": "<{topic} reference section title>", "body": "<factual content -- never invented here>"},
    "PDFs": {"note": "structure only -- point to a real, approved PDF source for {topic}, never fabricate one"},
    "Conversations": {"turns": [{"role": "user", "text": "<a realistic question about {topic}>"}, {"role": "assistant", "text": "<a grounded answer -- never invented here>"}]},
    "Books": {"note": "structure only -- point to a real, approved reference work for {topic}, never fabricate one"},
}


def build_draft_outline(*, topic: str, suggested_formats: list[str]) -> dict[str, Any]:
    structure = [
        f"Introduction to {topic}",
        f"Core concepts of {topic}",
        f"Common questions about {topic}",
        f"Worked examples in {topic}",
    ]
    required_topics = [topic]

    sample_formats = []
    for fmt in suggested_formats:
        template = _FORMAT_TEMPLATES.get(fmt)
        if template is None:
            continue
        sample_formats.append({"format": fmt, "template": template})

    return {
        "topic": topic,
        "structure": structure,
        "required_topics": required_topics,
        "sample_formats": sample_formats,
        "verified": False,
        "disclosure": (
            "structure only -- this draft contains no real facts and has not been verified; "
            "content must be written and independently verified before use"
        ),
    }
