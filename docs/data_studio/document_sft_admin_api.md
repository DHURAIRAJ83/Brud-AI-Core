# Document SFT — Admin REST API (Production Integration pass)

All routes require `require_admin`; all `POST` routes additionally require CSRF
(`X-CSRF-Token`, via `CsrfDependency`). Errors follow the repository-wide taxonomy:
`NotFoundError`→404, `ConflictError`→409, `ValidationError`→422 (see
`backend/core/exceptions.py`, unchanged).

## Document-scoped (`/api/admin/documents/{public_id}/...`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/overview` | Composite status: review summary, SFT summary, exports, handoffs, classification summary, security summary |
| GET | `/generator-eligibility` | Approved-chunk counts by type, classification summary, available vs. deferred generators with reasons |
| POST | `/sft-export/{export_public_id}/validate` | Re-derive checksum from disk, compare to stored manifest |
| POST | `/sft-export/{export_public_id}/handoff-preview` | Eligible/duplicate/lineage-missing counts before ingesting |
| POST | `/sft-export/{export_public_id}/handoff-ingest` | Ingest export into `dataset_records` (idempotent, checksum-conflict-detecting; `confirm: true` required) |
| GET | `/handoffs` | List handoffs for this document |
| GET | `/handoffs/{handoff_public_id}` | Single handoff detail |
| POST | `/handoffs/{handoff_public_id}/dataset-version-proposal` | Draft-only dataset-version build proposal |
| GET | `/handoffs/{handoff_public_id}/split-preview` | Train/validation/test split + leakage preview (422 if no build proposed yet) |
| POST | `/handoffs/{handoff_public_id}/confirm-build` | Explicit build confirmation (`confirm: true` required) |
| GET | `/dataset-version-status` | Current handoff/build/version status for this document |
| POST | `/content-classifications/scan` | Classify all pages (text-only, no vision model) |
| GET | `/content-classifications` | Paginated per-page classifications |
| POST | `/security/scan` | Detect prompt-injection/PII/secrets/paths in extracted text |
| GET | `/security-findings` | Paginated findings, optional `finding_type` filter |
| GET | `/pii-findings` | Findings filtered to `pii_*` types only |
| POST | `/security/{finding_public_id}/review` | Mark a finding `reviewed` or `dismissed` (the finding's own `action`, e.g. `block_export`, is never admin-overridable via this endpoint -- see Security note below) |

## Global (`/api/admin/document-tamil-correction-rules`)

| Method | Path | Purpose |
|---|---|---|
| GET | `` | List rules, optional `status` filter |
| POST | `` | Create a `draft` rule |
| GET | `/{rule_public_id}` | Single rule |
| GET | `/{rule_public_id}/history` | Append-only review history |
| POST | `/{rule_public_id}/review` | `submit_review` / `approve` / `activate` / `reject`, enforced by the existing state machine |

This is a global registry (no `document_source_id` column exists on
`document_tamil_correction_rules`), so it is not nested under `/documents/{id}`.

## Security note: review action set

`document_security_findings.review_status` is constrained to `pending`/`reviewed`/
`dismissed` (unchanged from the prior pass's schema). The finding's own `action`
column (`allow`/`mask_for_preview`/`exclude_from_sft`/`require_review`/
`block_export`) is system-computed at scan time and is **not** exposed as an
admin-settable field on the review endpoint -- an admin can mark a finding reviewed
or dismissed, but cannot flip a real secret's `block_export` action off through the
API. This is a deliberate simplification of the richer action set described in the
original task text (`Allow`/`Mask in preview`/`Block export` as distinct review
actions): allowing an admin action to silently downgrade `block_export` would weaken
the one safety gate the task itself calls mandatory ("Secrets and absolute paths must
remain export blockers until resolved"). Resolving a `block_export` finding requires
correcting the underlying document text and re-scanning, not overriding the finding.

## Pagination

List endpoints return `{items, total, page/offset, page_size/limit}` consistent with
every other document list endpoint in this router (`documentSftCandidates`,
`documentTamilQualityIssues`, etc.) -- no new pagination convention was introduced.
