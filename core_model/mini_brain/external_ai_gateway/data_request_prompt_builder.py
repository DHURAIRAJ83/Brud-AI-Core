"""MB-21: Data Acquisition Prompt Builder -- pure. Only ever invoked
after an admin has explicitly stated what data is missing (validated
upstream by `request_policy.validate_authorization()`) -- this module
builds the structured request prompt, it never decides what data is
needed.
"""

from __future__ import annotations

from typing import Any

REQUESTED_ARTIFACT_TYPES = (
    "candidate_facts", "candidate_explanations", "candidate_examples", "candidate_qa_pairs",
    "candidate_references",
)


def build_data_request_prompt(*, admin_stated_need: str, topic: str = "") -> dict[str, Any]:
    need = admin_stated_need.strip()
    topic_line = f" The topic area is: {topic.strip()}." if topic.strip() else ""
    prompt = (
        f"An administrator has identified a specific gap in an internal knowledge base: {need}."
        f"{topic_line} Please provide, clearly labeled and separated: (1) candidate facts, "
        "(2) candidate explanations, (3) candidate examples, (4) candidate question-answer pairs, "
        "(5) candidate references or sources if known. Do not fabricate a source citation if you "
        "are not certain one exists -- say so explicitly instead. Everything you provide will be "
        "treated as an unverified draft for human review, never inserted automatically anywhere."
    )
    return {
        "prompt": prompt, "admin_stated_need": need, "requested_artifact_types": list(REQUESTED_ARTIFACT_TYPES),
        "disclosure": (
            "only ever built after an explicit admin-stated need -- this module never originates a "
            "data request on its own, and every artifact type requested is disclosed to the provider "
            "itself as an unverified draft, never inserted automatically anywhere"
        ),
    }
