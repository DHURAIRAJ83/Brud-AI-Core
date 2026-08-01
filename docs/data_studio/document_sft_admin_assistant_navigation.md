# Document SFT — Admin Assistant Navigation (Production Closure)

## Contract reused, not invented

`AdminAssistantChatService.send_message()` already returned a
`navigation_target` field (`{page_id, nav_key}`, sometimes with extra keys --
see the pre-existing `dataset_discovery`/`dataset_verification`/
`sample_import`/`rag_sandbox` cases) before this pass. This pass adds new
cases to that same field rather than introducing a parallel `navigation`
object. For the 9 tab-key cases the extra keys are `tab_key`,
`document_public_id`, and (where applicable) `documents_tab` or
`wizard_step` -- exactly what `resolve_document_navigation()` returns. For
"open resulting dataset version" the extra key is `dataset_version_public_id`.

## Document context

`send_message()` already accepted `entity_type`/`entity_public_id` params
(threaded from the API request payload, previously stored only in the
context snapshot, never used to drive navigation). This pass is the first
to read them: when `entity_type == "document"`, `entity_public_id` becomes
the document a navigation reply is scoped to. No new parameter was added,
and no document is ever guessed from message text -- if the frontend
doesn't pass an entity, the reply says so honestly ("Open a document first
so I can show its real status here.") rather than fabricating one.

## Matching

`AdminAssistantChatService._DOCUMENT_NAV_KEYWORDS` (English + Tamil phrases)
maps a message to one of the 9 registered `tab_key`s;
`_DATASET_VERSION_RESULT_KEYWORDS` is a separate, single-purpose matcher for
"open resulting dataset version". Both are pure substring checks on the
lowercased message, same style as every other `_match_*_intent()` in this
file. `security-review` is checked first in the dict so its own keywords
("security findings", "block export") aren't shadowed by the more generic
"export" keyword.

## Real data, never fabricated

Where a document is known, the reply calls exactly one existing read-only
tool (the same 8 tools built in the prior pass -- `get_document_sft_generator_
eligibility`, `get_document_sft_handoff_summary`, `get_document_security_
review_summary`, `get_document_media_content_summary`,
`get_document_dataset_version_status`) via the same `_run_tool_logged()` path
every other tool call in this service already uses, and folds one real
number from the result into the reply (`_summarize_document_nav_tool_result()`).
Two cases (`critical-pages`, `tamil-quality`) have no matching existing
per-document tool -- rather than build a new one just to have a number,
these two return real navigation with honest guidance and no count,
disclosed here rather than silently faked.

## Cases supported

Open Critical Pages, Open Tamil Quality, Open SFT Generation, Open Candidate
Review, Open Export, Open Dataset Handoff, Open Security Review, Open Media
& Tables, Open Training Readiness, Open resulting Dataset Version -- all 10
required by the task, verified with real fixture documents in
`tests/backend/test_admin_assistant_document_navigation.py` (9 tests), plus
the exact two Tamil example questions from the task text
(`எந்த security findings exportஐ block செய்கின்றன?`,
`உருவாக்கப்பட்ட dataset versionஐ திறக்கவும்.`) and two more of the five
listed examples reused verbatim as test messages.

## Authority boundary

Every new code path in this pass only ever calls `_run_tool_logged()`,
which only ever calls `run_tool()`, which is hard-restricted to
`READ_ONLY_TOOLS` -- there is no code path from any of the 10 new
navigation cases to `AdminAssistantService.propose()`/`execute()`, so the
Assistant structurally cannot approve a candidate, approve a correction
rule, confirm a dataset-version build, or start training through
navigation. Verified directly: `TestAuthorityBoundary::
test_navigation_never_mutates_anything` sends all 4 distinct navigation
message types against a real fixture document and then asserts
`training_jobs`, `admin_approvals`, and `document_sft_dataset_handoffs`
row counts are all `0` afterward.

## Registry parity

11 new tests in `tests/core_model/test_admin_assistant_registries.py`
enforce: no duplicate/fabricated navigation keys, every `nav_key` points at
a real registered page, every `documents_tab` is a real
`DocumentsPage.jsx` tab, every `wizard_step` is in `1..14`, the JS mirror
matches the Python registry exactly, the chat service's keyword dict only
ever references registered keys, and `documents`' `PageEntry.tabs` now
matches the real frontend tab list exactly (previously stale -- see the
closure audit).
