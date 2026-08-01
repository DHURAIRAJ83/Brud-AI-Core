# Phase 18 — Public Chat Request/Response Schema Reference

Source of truth: `backend/models/public_chat.py`. All models are
`DomainModel` subclasses with `extra="forbid"` (repo-wide convention)
-- an unknown field is a 422, never silently dropped.

## Request: `PublicChatRequest`

| Field | Type | Constraints |
|---|---|---|
| `message` | `str` | 1-4000 chars, stripped, non-blank |
| `conversation_id` | `str \| None` | validated public-id format |
| `language_override` | `"auto" \| "ta" \| "en"` | default `"auto"` -- **never** `"tanglish"` |
| `memory_consent` | `bool` | default `false` |
| `client_request_id` | `str \| None` | max 128 chars |

No field selects a model assignment, RAG space, provider, or
checkpoint. There is no field to request Tanglish output. Sending any
unrecognized field (e.g. an attempted `model_assignment_id`) fails
validation with a 422, never silently ignored.

## Response: `PublicChatResponse`

| Field | Type | Notes |
|---|---|---|
| `reply` | `str` | Never fabricated; never Tanglish script |
| `detected_language` | `str` | Raw input classification (`ta\|en\|mixed\|tanglish\|unknown`) |
| `answer_language` | `str` | Always `"ta"` or `"en"` |
| `route_used` | `str` | One of `EXECUTABLE_ROUTES` -- never `trusted_web`/`tool` |
| `route_reason_codes` | `list[str]` | Phase 17 reason codes, explainability only |
| `evidence_status` | `str` | `grounded\|partially_grounded\|insufficient\|conflicting\|model_only\|none` |
| `confidence_band` | `str` | `high\|medium\|low\|unknown` -- never a fabricated percentage |
| `source_types` | `list[str]` | Subset of `("model","rag","memory")` |
| `citations` | `list[PublicCitation]` | `[]` for model-only/memory/clarify/refuse/insufficient |
| `memory_used` | `bool` | |
| `clarification_required` | `bool` | |
| `insufficient_evidence` | `bool` | |
| `safety_status` | `str` | `safe\|caution\|refused\|output_blocked\|review_flagged` |
| `fallbacks_attempted` | `list[str]` | Structured reason codes, see below |
| `request_id` | `str` | For feedback correlation |
| `conversation_id` | `str \| None` | Optional |
| `model_assignment_public_name` | `str \| None` | Public-safe name only, never an internal ID |
| `rag_space_public_name` | `str \| None` | Public-safe name only |
| `freshness_status` | `str \| None` | e.g. `current_information_requires_web` |
| `limitations` | `list[str]` | Optional free-form caveats |

### `PublicCitation`

`citation_id`, `source_type` (`rag\|memory`), `title`,
`document_or_site_name`, `page_or_section`, `published_at`,
`updated_at`, `retrieved_at`, `verification_status`, `support_status`,
`url`. **Never present**: internal integer FK, internal DB path,
private filesystem path, checkpoint path.

### `fallbacks_attempted` reason codes

`trusted_web_unavailable`, `tool_unavailable`, `rag_scope_unavailable`,
`rag_insufficient_evidence`, `model_assignment_unavailable`,
`memory_unavailable`, `memory_consent_required`,
`classification_failed`, `output_safety_blocked`,
`input_safety_refused`.

## What a public response is guaranteed to never contain

Verified by `test_public_chat_security.py::
test_response_never_exposes_internal_identifiers_or_paths` and the
citation-adapter design (Section 10 of the main doc):

- Internal numeric/model ID, checkpoint path, private provider name
- Private filesystem path (`/core_models/...`, `/database/...`)
- System prompt / hidden policy text / raw chain-of-thought
- Admin account IDs, internal audit IDs
- Private memory contents beyond what the requester's own conversation
  contributed
- A fabricated confidence percentage (only the four bands above)
- A fake citation for a model-only answer

## `GET /api/chat/capabilities`

`PublicChatCapabilities`: `core_model_available`, `approved_rag_available`,
`memory_available` (all computed live from real resolver state, never
hardcoded `true`), `trusted_web_available` (always `false`),
`tool_available` (always `false`), `supported_input_languages`
(`["ta","en","tanglish"]` -- Tanglish is accepted as *input*),
`public_output_policy` (`"tamil_first"`).

## `POST /api/chat/feedback`: `PublicChatFeedbackRequest`

`request_id`, `route_used`, `answer_hash` (client-computed SHA-256 of
the reply text -- the server never persists raw answer text, so this
is the only way to correlate feedback to an answer), `feedback_type`
(one of `PUBLIC_FEEDBACK_TYPES`: `thumbs_up|thumbs_down|
language_report|safety_report`), optional `comment` (max 1000 chars).

## Stable public error codes

`CHAT_INPUT_TOO_LARGE`, `CHAT_RATE_LIMITED`, `CHAT_MODEL_UNAVAILABLE`,
`CHAT_RAG_UNAVAILABLE`, `CHAT_RAG_INSUFFICIENT`,
`CHAT_MEMORY_CONSENT_REQUIRED`, `CHAT_CLARIFICATION_REQUIRED`,
`CHAT_WEB_NOT_AVAILABLE`, `CHAT_TOOL_NOT_AVAILABLE`,
`CHAT_SAFETY_REFUSAL`, `CHAT_OUTPUT_BLOCKED`, `CHAT_INTERNAL_ERROR`.
Every error body is `{"error": {"code": ..., "message": ...}}` --
localized (Tamil/English), never an internal stack trace.
