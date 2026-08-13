"""MB-27: Secret Masker -- pure, one-way only. A raw secret value (or
merely its presence) goes in; a fixed-width masked indicator and a
presence boolean come out. This module never returns anything that
could be used to reconstruct or infer the real value -- the masked
indicator is always the same fixed string regardless of the real
value's length or content, by design (a variable-length mask would
itself leak information).
"""

from __future__ import annotations

from typing import Any

MASKED_INDICATOR = "•" * 6  # "••••••"


def mask_secret(*, has_value: bool, updated_at: str | None = None) -> dict[str, Any]:
    return {
        "masked_indicator": MASKED_INDICATOR if has_value else "",
        "is_set": has_value,
        "updated_at": updated_at if has_value else None,
    }


def mask_secret_list(secret_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`secret_rows` here means already-fetched `{"secret_name", "updated_at"}`
    dicts -- this function never receives or touches `encrypted_value`."""

    return [
        {"secret_name": row["secret_name"], **mask_secret(has_value=True, updated_at=row.get("updated_at"))}
        for row in secret_rows
    ]
