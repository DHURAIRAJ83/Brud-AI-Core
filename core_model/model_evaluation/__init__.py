"""Phase 13 multilingual evaluation, safety validation, and chat-readiness
assessment: deterministic scoring only, reusing Phase 12's bounded greedy
generation and evaluation primitives rather than duplicating them.

Named ``model_evaluation`` (not ``evaluation``) to avoid colliding with the
pre-existing ``core_model.evaluation`` package, which holds unrelated Phase 8
core-model architecture smoke-test helpers (``architecture_checks.py``,
imported by ``backend/services/core_model_service.py``) — a different
concern (architecture validation) from this package's concern (behavioral
evaluation of a trained, instruction-tuned candidate).

Every function here is pure — no database access, no model loading, no
network access. Callers pass in already-generated text and fixture
metadata; nothing here claims comprehensive factual, safety, or
adversarial-robustness guarantees.
"""

FIXTURE_CATEGORIES = (
    "language_compliance",
    "instruction_following",
    "response_relevance",
    "format_compliance",
    "translation",
    "definition",
    "summarization",
    "classification",
    "transformation",
    "reasoning_basic",
    "code_switching",
    "tanglish_understanding",
    "safety_refusal",
    "unsafe_instruction_handling",
    "prompt_leakage",
    "role_leakage",
    "system_prompt_leakage",
    "repetition",
    "robustness",
    "unicode_handling",
)

LANGUAGES = ("ta", "en", "tgl", "mixed")
LANGUAGES_WITH_OVERALL = (*LANGUAGES, "overall")

SAFETY_CATEGORIES = (
    "self_harm",
    "violence",
    "illegal_activity",
    "weapons",
    "malware",
    "privacy",
    "credential_theft",
    "hate_or_harassment",
    "sexual_content",
    "medical_high_stakes",
    "financial_high_stakes",
)

PASS = "pass"
WARNING = "warning"
FAIL = "fail"
NOT_EVALUATED = "not_evaluated"
