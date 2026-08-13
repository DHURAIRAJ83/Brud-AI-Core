"""MB-14: Image Caption -- pure. Audited finding: no image-captioning
model exists anywhere in this codebase. Captions are only ever
populated from an admin-supplied caption via Stage 7 Admin Annotation
-- never generated automatically. Always `verified: false`.
"""

from __future__ import annotations

from typing import Any

SHORT_CAPTION_CHARS = 80


def generate_captions(*, admin_caption: str | None = None) -> dict[str, Any]:
    if admin_caption:
        return {
            "short_caption": admin_caption[:SHORT_CAPTION_CHARS], "detailed_caption": admin_caption,
            "educational_caption": None, "dataset_caption": admin_caption,
            "source": "admin_supplied", "verified": False,
        }
    return {
        "short_caption": None, "detailed_caption": None, "educational_caption": None, "dataset_caption": None,
        "source": "unavailable", "verified": False,
        "disclosure": (
            "no image captioning model exists anywhere in this codebase (confirmed by audit) -- "
            "captions are only ever populated from an admin-supplied caption via Stage 7 Admin "
            "Annotation, never generated automatically"
        ),
    }
