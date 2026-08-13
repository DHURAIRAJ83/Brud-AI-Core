"""MB-01: Brud Mini Brain API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class MiniBrainSettingsPatch(DomainModel):
    config: dict[str, Any] = Field(default_factory=dict)
