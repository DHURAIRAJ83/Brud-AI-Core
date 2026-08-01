# Phase 12 — Approved Sample Import, Quarantine, File Safety, PII & Data Quality Validation — Plan

Baseline: Phase 11 complete (`PHASE_11_COMPLETE_WITH_LIMITATIONS`), schema version 34. This
document is written before any Phase 12 implementation code, per Step 1.

## 1. Existing systems reused (baseline inspection findings)

Inspected directly (file + exact identifier) rather than assumed:

| Need | Existing component | Reuse strategy |
|---|---|---|
| Streaming bounded write + checksum + magic-byte prefix check | `backend/services/document_service.py::DocumentService.upload()` (`target.open("xb")`, `os.chmod(0o600)`, 64KB chunk loop, `hashlib.sha256()` streamed, delete-on-exception) | Mirror the exact pattern for the sample-download writer; no new dependency (repo has no `python-magic`/`filetype` — hand-rolled signature table is the house style) |
| Filename safety | `document_service.py::safe_filename()` | Reuse directly |
| SSRF / domain allow-list / redirect caps | `backend/services/dataset_verification_transport.py` (`is_domain_allowed()`, `default_resolver()`, private/loopback/link-local rejection) | Extend into a new streaming transport (Phase 11's fetch is whole-body-in-memory bounded to 2MB; Phase 12 needs genuine streaming with a larger, approval-bound byte cap) — same protections, new function, not a duplicate module |
| PDF embedded-text extraction | `corpus_processing_service.py` (`fitz`/PyMuPDF), mirrored already once in `dataset_verification_transport.py::_extract_pdf_embedded_text()` | Mirror again (third copy) — consistent with the codebase's existing stance of not cross-importing this private-style method |
| PII detection | `core_model/corpus/pii_detection.py::detect_pii()/redact_pii()/decide_pii_action()` (email, phone, aadhaar_like, pan_like, passport_like, precise_address, personal_medical_record) | Reuse directly as the base layer; extend with API-key/token/private-key/card categories via `secret_detection.py` (below) rather than re-implementing |
| Secret/credential detection | `core_model/corpus/secret_detection.py::detect_secrets()` → `core_model/conversation/memory_safety.py::detect_safety_signals()` (password, api_key, access_token, private_key, payment_card, bank_account, cookie, absolute_path, env_dump) | Reuse directly for the "secrets" half of Step 16 |
| Harmful-content classification | `core_model/corpus/safety_filter.py::assess_safety()` (explicit_violence, self_harm, illegal_instructions, weapon_construction, malware_instructions, credential_theft, hate_harassment, sexual_content, exploitative_content, high_risk_medical, high_risk_financial + descriptive/educational/historical/preventive/operational_harmful behavior classing) | Reuse directly for Step 17 |
| Prompt/instruction-injection signals | `core_model/rag/injection_filter.py::detect_injection_signals()` (ignore_previous_instructions, reveal_system_prompt, act_as_system, execute_commands, change_policies, exfiltrate_secrets, encoded_payload, etc.) | Reuse directly for Step 21's instruction/prompt-injection detection |
| Contamination checksum comparison | `core_model/corpus/contamination.py::check_contamination()` + `core_model/corpus/exact_deduplication.py::tamil_safe_normalized_checksum()` + `core_model.corpus.BLOCKING_CONTAMINATION_ISSUES` | Call directly, supplying sample-record text and comparison checksum sets pulled from existing fixture/eval tables |
| Unicode/Tamil integrity | `core_model/corpus/unicode_normalization.py` (`assess_unicode_integrity`, `detect_replacement_characters`, `detect_mojibake`, `tamil_combining_marks_preserved`), `core_model/corpus/tamil_normalization.py` (`normalize_tamil_text`, `apply_tamil_ocr_substitutions`, `remove_stray_zero_width_characters`) | Reuse directly for Step 15 |
| Language/script classification | `core_model/corpus/language_detection.py::assess_language()` (Tamil/Latin/mixed ratios, Tanglish lexicon hits, numeric/code detection) | Reuse directly |
| Stale-approval-check registry | `backend/services/admin_assistant_service.py::STALE_CHECK_FINGERPRINTS` dict + fingerprint-fn pattern, checked at both `review()` and `execute()` | Register one fingerprint fn per Phase 12 mutating action into the *same* dict — this is exactly the mechanism Step 5's "reject as stale if any bound field changes" requires |
| Audit | `backend/database/repositories/phase2.py::AuditLogRepository.append()` (auto-redacts via `redact_secrets()`) | Reuse directly; action strings follow the existing short-verb convention (`"collect_evidence"`, `"finalize"`, etc.) |
| Migration conventions | `backend/database/schema.py` (`SCHEMA_VERSION`, `PHASE33_SCHEMA` executescript pattern, `PHASE34_COLUMNS` ALTER-TABLE pattern), `backend/database/migrations.py` (`_apply_v33`/`_apply_v34`, idempotent via `schema_migrations` guard) | Byte-for-byte same pattern for migration 035 |
| Storage-directory convention | `backend/core/config.py::Settings` — one `Path` field per subsystem (`import_dir`, `document_dir`, `pretraining_dir`, ...), each in a validation allowlist | Add one new `quarantine_dir` field to the same allowlist |
| Admin Assistant registries | `core_model/admin_assistant/action_registry.py::ActionDefinition`, `backend/services/admin_assistant_tools.py::ToolDefinition`, `core_model/admin_assistant/dashboard_registry.py::PageEntry`, `core_model/admin_assistant/dataset_verification_help.py` (FAQ template) | Structurally identical new entries, no schema changes |
| Governance eligibility signal to read | `core_model/data_verification/__init__.py::PERMISSION_TYPES` (`rag_use`, `training_use`, `evaluation_use`, `commercial_use`, ...), `backend/database/repositories/dataset_verification.py` case fields (`verification_expiry_status`, `locked_at`, `declared_licence`, `normalized_licence_identifier`, `next_reverification_at`) | Eligibility gate reads these directly (read-only), never writes Phase 11 tables |
| Provider status | `backend/database/repositories/external_data_providers.py::ExternalDataProviderRepository` (`enabled`, `lifecycle_status`, `trust_status`) | Eligibility gate queries this directly — no separate `core_model/data_providers` policy module exists (that package is empty) |

### Deliberately NOT reused (name collision to avoid)

`import_service.py:897` and `document_service.py:1221` already move failed-validation files into a
flat `data/imports/quarantine/` / `data/documents/quarantine/` folder — a narrow, pre-existing,
unrelated use of the word "quarantine" (uuid-named files, no manifest, no per-item directory).
Phase 12's quarantine is a much richer, isolated concept and **must never write into those
directories** — it uses its own root, `data/quarantine/external-samples/<sample_import_id>/`.

### Built from scratch (no reusable component existed)

Bounded record-level CSV/JSON/JSONL parsers for raw external-sample inspection (existing parsers
in `import_service.py` assume admin-mapped-field imports, not raw inspection); archive safety
(zip/tar/tar.gz) handling — nothing exists anywhere in the repo; deterministic
executable/script/macro signature scanner — nothing exists; record-level duplicate/conflict
service (the existing `ExternalDatasetDeduplicationService` operates at dataset-candidate
granularity, not sample-record granularity).

## 2. Architecture decision: table count

Step 3 recommends 12 tables. All 12 are used as named — no collapsing or splitting was justified
during baseline inspection (each maps to a genuinely distinct entity with its own lifecycle:
import, approval, file, download event, extraction event, scan result, record, record issue,
review, report, event/audit-trail, deletion request). No 13th table is added.

## 3. Sample-import lifecycle

18 statuses (Step 4) stored in `external_dataset_sample_imports.status`, transitions logged to
`external_dataset_sample_events` (mirrors Phase 11's events-table-as-audit-trail pattern — no
separate "current stage" boolean anywhere; `current_stage` is a plain enum column, one of the 13
Step 4 stages, updated alongside status but never conflated with it — satisfying "a single boolean
must not represent the lifecycle").

## 4. Sample approval model

A distinct `external_dataset_sample_import_approvals` row, immutable once `status='approved'`
(delete-blocked + update-blocked table, same trigger pattern as Phase 11's `_verification_reviews`).
Binds exactly the 21 fields listed in Step 5. Staleness is enforced two ways:

1. **At propose/approve time** via a new `_fingerprint_dataset_sample_import_state` function
   registered into `admin_assistant_service.STALE_CHECK_FINGERPRINTS`, following the identical
   mechanism Phase 11 uses — re-read `dataset_version`/`revision`/`source_checksum` from the live
   Phase 11 case at review-time and reject on mismatch.
2. **At download time** (defense in depth, since download can happen after the Admin Assistant
   step): `ExternalDatasetSampleDownloadService` re-derives a `target_fingerprint` from current
   case state and compares it against the approval's stored `target_fingerprint` before allowing
   any byte to be fetched — a stale approval is rejected even if somehow invoked outside the
   Assistant pipeline.

Purposes are restricted to the 6 listed in Step 5; `production_rag`/`training`/`model_release` are
rejected by application-level validation (not just by omission from a dropdown) so a crafted API
request cannot bypass the restriction.

## 5. Sample-selection model

`selection_method` enum (Step 7) + recorded parameters (`selection_seed`, `source_split`,
`source_file`, `row_start`, `row_end`, `requested_count`, `actual_count`) on the sample-import row.
"Deterministic seeded sample" uses Python's `random.Random(seed)` seeded exclusively from the
stored `selection_seed`, applied only to an already-bounded candidate list (never an unbounded
population) — this satisfies "no unbounded random sampling" while still being reproducible.

## 6. Safe download design

New `backend/services/dataset_sample_download_service.py` (or similarly named) streams via
`httpx` using a `stream=True` GET, re-using Phase 11's domain-allowlist/SSRF/DNS-resolution
protections, adding: content-length precheck against `approved_byte_limit`, byte-counter enforced
per chunk during streaming (abort the instant the counter exceeds the cap, not just after
completion), a temp filename inside the target quarantine directory, SHA-256 computed
incrementally per chunk (mirroring `document_service.py::upload()`), atomic `os.replace()` into
`original/` only after the stream completes cleanly and checksum is recorded, zero-or-one retry,
no credentials ever embedded in the request URL, and full secret redaction in any logged error.
On any byte-limit/timeout/error: delete the partial temp file, record a `failed` download event
with a machine-readable reason, and leave the sample-import in a state that surfaces the failure
(never silently downgrade to a partial success).

## 7. Quarantine storage layout

```
data/quarantine/external-samples/<sample_import_id>/
  original/        # immutable byte-for-byte copies as downloaded, 0o600, never executable
  derived/          # extraction output, normalized text, redacted-candidate copies
  reports/          # rendered report snapshot(s) for this import
  manifest.json     # file list + checksums + source metadata, updated as files are added
```

Added as `Settings.quarantine_dir` in `backend/core/config.py`'s existing storage-allowlist
pattern (default `data/quarantine`). Never reachable via any static-file route or public URL — the
file-content API endpoints return metadata + (for supported text types only) a bounded safe-text
preview rendered server-side, never a raw file stream to an unauthenticated caller. A storage quota
(`Settings.quarantine_max_bytes_per_import` and a total-quarantine soft cap) is checked before
download and enforced during streaming.

## 8. Archive safety

Only `zip`, `tar`, `tar.gz` (Step 11) via Python's stdlib `zipfile`/`tarfile`, opened in
inspect-then-extract-member-by-member mode (never `extractall()`), enforcing before extracting
each member: path-traversal rejection (resolved path must stay under the derived directory),
absolute-path rejection, symlink/hardlink/device-file rejection (`tarfile.TarInfo.issym()` /
`.islnk()` / `.isdev()`; zip has no native symlink concept on this platform but external-attribute
Unix-mode bits are checked defensively), encrypted-entry rejection (`zipfile` `is_encrypted`
per-entry check / non-zero-flag detection), a running expanded-byte counter compared against a
compression-ratio threshold and an absolute cap, a max member count, and a max nested-archive
depth (an archive-inside-an-archive is opened only up to a configured depth, then flagged
`unsupported`/`blocked` rather than recursed further). All extraction happens under a wall-clock
timeout; on any violation or timeout, extraction aborts and any partial output is deleted.

## 9. Supported formats / modality strategy

Text: TXT, Markdown, CSV, JSON, JSONL, PDF — fully supported per Step 2/13, each with its own
bounded parser (new, since no bounded record-level parser existed for raw external inspection).
Image/audio/video: file-safety validation (signature check, size, MIME) plus bounded metadata
extraction only — explicitly no semantic evaluation, matching Step 2's "do not claim semantic ...
evaluation exists yet." Multimodal: manifest + cross-reference validation only (e.g. an
image-caption pair's referenced file IDs both exist and are individually validated) — no alignment
scoring.

## 10. PII and sensitive-data strategy

Layered per Step 16: (1) deterministic patterns — `pii_detection.detect_pii()` +
`secret_detection.detect_secrets()`; (2) contextual heuristic — confidence downgraded/upgraded
based on surrounding tokens (e.g. a 10-digit number near "call" vs. near "invoice #"); (3) human
review — anything not cleanly `not_detected` or `confirmed`-with-high-confidence becomes a
`external_dataset_sample_record_issues` row requiring a reviewer decision. The **original**
quarantined record is never modified; `redact_pii()`'s output is stored as a separate
`derived/`-directory candidate linked to (not overwriting) the original, exactly satisfying "do
not silently alter source meaning" and "store original + redacted derived candidate."

## 11. Quality and contamination strategy

Quality: bounded structural/statistical checks (empty/too-short/too-long/malformed/encoding
issues) modeled on `dataset_quality.py`'s scoring approach but operating on quarantine records, not
`dataset_records`. Duplicate: new record-level service (exact checksum, normalized checksum via
`tamil_safe_normalized_checksum()`, cross-file, cross-existing-approved-dataset) creating review
groups, never auto-merging. Contamination: `check_contamination()` called per record against
checksum sets pulled from existing validation/test/eval-fixture tables; a `blocks_training` result
sets `training_assessment_status` to `blocked` but never touches `rag_sandbox_eligible` directly
(contamination against training/eval sets doesn't automatically disqualify RAG-sandbox use, per the
spec's own "may still be retained as evaluation-only data" carve-out).

## 12. Human-review workflow

Mirrors Phase 11's `_verification_reviews` append-only pattern: every review decision (Step 22) is
inserted, never updated, into `external_dataset_sample_reviews`, referencing the specific
file/record/issue/duplicate-group/conflict it resolves. `edit_derived_copy`/`redact_derived_copy`
decisions create a new versioned row in the derived-content table (never overwrite); the original
stays byte-identical and immutable for the life of the import.

## 13. Phase 13 handoff

The finalized report's `rag_sandbox_eligible` boolean is the only signal Phase 13 may read. Phase
12 performs zero writes to any RAG table, creates no index, and the frontend report view is
required (Step 31) to never render the words "Training Approved" or "Production RAG Approved."
`training_assessment_status` is explicitly advisory (Step 25) and structurally cannot be upgraded
to `training_approved` by any Phase 12 code path — there is no such status value in the enum at
all.

## 14. Phase 11 known-limitation handling

Phase 11's `refreshSelected()` issues ~10 sequential (non-`Promise.all`) GET requests, causing a
visible UI lag after mutations. Per Step 40, Phase 12 will **not** copy this pattern in its own
frontend refresh logic (new fetches will be batched via `Promise.all` where they're independent).
The existing Phase 11 code will be left as-is unless a small, directly-shared, regression-tested
fix is possible without a broader rewrite; if not, it remains a recorded deferred item — consistent
with Step 40's explicit instruction not to perform an unrelated rewrite.
