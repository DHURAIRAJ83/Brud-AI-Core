"""MB-05.1: Curriculum Analyzer -- Good Sequence / Missing Prerequisite
/ Broken Sequence per covered subtopic. Built entirely by composing
Coverage Analyzer's and Difficulty Analyzer's already-computed outputs
(which subtopic each record matched, and each record's difficulty
level) -- never re-scans record text a second time.
"""

from __future__ import annotations

from typing import Any

_BASIC_LEVELS = {"Easy", "Medium"}
_ADVANCED_LEVELS = {"Hard", "Very Hard"}


def analyze_curriculum(*, coverage: dict[str, Any], difficulty_by_id: dict[str, str]) -> dict[str, Any]:
    topics: list[dict[str, Any]] = []

    for domain, data in coverage.items():
        for subtopic, info in data["subtopics"].items():
            if info["status"] == "Missing":
                continue

            levels_present = {difficulty_by_id.get(record_id) for record_id in info["matched_record_ids"]}
            levels_present.discard(None)
            has_basic = bool(levels_present & _BASIC_LEVELS)
            has_advanced = bool(levels_present & _ADVANCED_LEVELS)

            if has_advanced and not has_basic:
                verdict = "Missing Prerequisite"
                reason = f"{subtopic} has {info['record_hits']} record(s) at Hard/Very Hard level but none at Easy/Medium"
            elif has_basic and has_advanced:
                verdict = "Good Sequence"
                reason = f"{subtopic} has both foundational (Easy/Medium) and advanced (Hard/Very Hard) records"
            elif has_basic:
                verdict = "Good Sequence"
                reason = f"{subtopic} has foundational records only -- no advanced content yet, not a broken sequence"
            else:
                verdict = "Broken Sequence"
                reason = f"{subtopic} has matching records but no determinable difficulty level"

            topics.append({"domain": domain, "subtopic": subtopic, "verdict": verdict, "reason": reason})

    verdict_counts = {"Good Sequence": 0, "Missing Prerequisite": 0, "Broken Sequence": 0}
    for topic in topics:
        verdict_counts[topic["verdict"]] += 1

    return {"topics": topics, "verdict_counts": verdict_counts}
