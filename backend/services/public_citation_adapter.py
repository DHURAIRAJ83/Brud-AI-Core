"""Public-safe citation normalization (Step 11).

Phase 16 found two citation-construction implementations
(`rag_generation_service.py` -> `rag_answer_citations`,
`chat_orchestration_service.py` -> `chat_response_citations`); neither
is touched here. `chat_response_citations` is the canonical path (it's
what `ChatOrchestrationService` -- the service Phase 18 must reuse --
already writes to). Its own `public_row()` strips the internal
`rag_chunk_id`/`memory_item_id` integer FKs without first resolving
them to a title/URL, so this module adds exactly one new, read-only
query that runs the join *before* those IDs would otherwise be
dropped, producing the public-safe shape Step 11 requires. No existing
`record_citation()` call or table is modified.

Memory-item citations are deliberately excluded from this adapter's
output -- the `memory` route never exposes memory as an external
citation (Step 12); only `rag_chunk` evidence rows are normalized here.
"""

from __future__ import annotations

import sqlite3
from typing import Any

_QUERY = """
SELECT
    c.public_id AS citation_id,
    c.rank AS rank,
    c.validation_status AS validation_status,
    ks.title AS title,
    ks.source_type AS source_type,
    sv.created_at AS retrieved_at,
    ks.updated_at AS source_updated_at
FROM chat_response_citations c
JOIN chat_grounded_responses r ON c.grounded_response_id = r.id
JOIN rag_chunks rc ON c.rag_chunk_id = rc.id
JOIN rag_source_versions sv ON rc.source_version_id = sv.id
JOIN rag_knowledge_sources ks ON sv.knowledge_source_id = ks.id
WHERE r.public_id = ? AND c.evidence_type = 'rag_chunk'
ORDER BY c.rank
"""

_SUPPORT_STATUS_BY_VALIDATION = {
    "valid": "supported",
    "valid_with_warning": "partially_supported",
    "invalid": "unsupported",
    "not_present": "unsupported",
}


def public_citations_for_response(
    connection: sqlite3.Connection, grounded_response_public_id: str
) -> list[dict[str, Any]]:
    rows = connection.execute(_QUERY, (grounded_response_public_id,)).fetchall()
    citations: list[dict[str, Any]] = []
    for row in rows:
        citations.append(
            {
                "citation_id": row["citation_id"],
                "source_type": "rag",
                "title": row["title"],
                "document_or_site_name": row["title"],
                "page_or_section": None,
                # Genuine document publish dates are not tracked at the
                # data-model level -- never fabricated as a value here.
                "published_at": None,
                "updated_at": row["source_updated_at"],
                "retrieved_at": row["retrieved_at"],
                "verification_status": row["validation_status"],
                "support_status": _SUPPORT_STATUS_BY_VALIDATION.get(
                    row["validation_status"], "unsupported"
                ),
                "url": None,
            }
        )
    return citations


__all__ = ["public_citations_for_response"]
