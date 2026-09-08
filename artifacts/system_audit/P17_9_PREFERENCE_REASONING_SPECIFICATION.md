# Phase 17.9: Preference Consistency Reasoning Specification

## 1. Objective
Define deterministic reasoning over user preferences (`PREFERENCE`, `LANGUAGE_PREFERENCE`, `FORMAT_PREFERENCE`) to resolve conflicts, precedence, and temporal changes without query-frequency bias.

---

## 2. Preference Hierarchy & Precedence Rules
When multiple preference memories apply to a context, the engine resolves precedence according to:
1. **Explicit vs Inferred**: `creation_source="explicit_user_request"` strictly overrides `assistant_inferred` or `system_derived`.
2. **Specific Purpose vs General**: A preference scoped to a specific workflow overrides a general profile preference.
3. **Temporal Recency**: A newer explicit preference supersedes an older conflicting explicit preference.
4. **Anti-Inflation Rule (G4)**: Retrieval frequency does NOT increase preference strength.

---

## 3. Preference Packet Structure
```python
@dataclass(frozen=True)
class PreferenceResolution:
    resolved_preferences: dict[str, Any]      # Key -> value mapping (e.g. "language": "Tamil")
    superseded_preferences: list[str]         # Opaque IDs of overridden past preferences
    preference_warnings: list[str]            # Warnings if unresolvable conflict detected
    provenance_citations: dict[str, str]      # Preference key -> memory public ID
```
