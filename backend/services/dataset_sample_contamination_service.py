"""Phase 12 Step 20 evaluation contamination checks.

Calls `core_model.corpus.contamination.check_contamination()` directly
-- never a second checksum-comparison implementation. The caller
supplies the comparison checksum sets (pulled from existing
validation/test/evaluation-fixture/regression-fixture/holdout/hidden-
prompt tables); this service never queries those tables itself.

Confirmed contamination (an exact normalized-checksum match) is never
ambiguous, so it is always `confirmed_overlap`, never `possible_
overlap` -- `possible_overlap` is reserved for a future near-duplicate-
style fuzzy comparison this phase does not implement (an honest,
disclosed gap, not silently promised).
"""

from __future__ import annotations

from typing import Any

from core_model.corpus import BLOCKING_CONTAMINATION_ISSUES
from core_model.corpus.contamination import check_contamination


class ExternalDatasetContaminationService:
    def check(
        self,
        text: str,
        *,
        training_checksums: frozenset[str] = frozenset(),
        validation_checksums: frozenset[str] = frozenset(),
        test_checksums: frozenset[str] = frozenset(),
        evaluation_fixture_checksums: frozenset[str] = frozenset(),
        regression_fixture_checksums: frozenset[str] = frozenset(),
        holdout_checksums: frozenset[str] = frozenset(),
        hidden_prompt_checksums: frozenset[str] = frozenset(),
    ) -> dict[str, Any]:
        any_comparison_set_supplied = any(
            (
                training_checksums, validation_checksums, test_checksums,
                evaluation_fixture_checksums, regression_fixture_checksums,
                holdout_checksums, hidden_prompt_checksums,
            )
        )
        result = check_contamination(
            segment_text=text,
            training_checksums=training_checksums,
            validation_checksums=validation_checksums,
            test_checksums=test_checksums,
            evaluation_fixture_checksums=evaluation_fixture_checksums,
            regression_fixture_checksums=regression_fixture_checksums,
            holdout_checksums=holdout_checksums,
            hidden_prompt_checksums=hidden_prompt_checksums,
        )
        if not any_comparison_set_supplied:
            status = "unknown"
        elif result["issues"]:
            status = "confirmed_overlap"
        else:
            status = "clear"

        blocks_training = bool(set(result["issues"]) & BLOCKING_CONTAMINATION_ISSUES)
        return {
            "status": status,
            "checksum": result["checksum"],
            "issues": result["issues"],
            "blocks_training": blocks_training,
        }
