# Context Orchestration and Budgeting

`ChatOrchestrationService.send_message()` assembles one bounded,
priority-ordered context per message, recorded as an append-only
`chat_context_assemblies` row plus one `chat_context_items` row per
included/dropped item.

## Ordering and budget

`core_model.conversation.context_budget`:

- Mandatory items (fixed system instructions, the current user
  message) are placed first and must fit or the run fails closed with
  `mandatory_context_exceeds_budget` (see below) — the current user
  message is never silently dropped to make room for anything else.
- Optional items (conversation history, validated summary, memory
  results, RAG results) are then greedy-packed via
  `select_items_within_budget()` in priority order within whatever
  budget remains, `allocate_optional_budgets()` splitting the
  remainder across categories. An item is never split partway to fit —
  it is included whole or dropped whole.
- `reserved_output_tokens` is always subtracted from the model's
  `maximum_model_context` before any of the above, so the model always
  has room to actually answer.

## Fail-closed on tiny profiles

If the fixed system instructions plus the current request already
exceed `maximum_model_context` minus reserved output tokens, orchestration
reports `mandatory_context_exceeds_budget` as a critical
`chat_orchestration_issues` row and the response status becomes
`blocked_context` — no answer is fabricated, and no evidence is
silently omitted to force a fit. This was observed directly in manual
verification Path I under the small CPU-only test runtime profile
(`maximum_context_length=64`), the same honest limitation Phase 16
documented for its own tiny test profile in `rag_context_budget_and_prompt.md`.

## Memory and RAG stay separately cited

Memory retrieval (`MemoryService.retrieve()`) and RAG retrieval
(`RagRetrievalService.retrieve()`) are both called as separate,
fully self-committing operations *before* orchestration opens its own
transaction to assemble context — mirroring the cross-transaction
visibility lesson learned in Phase 15/16. Their results are tagged
with distinct `CONTEXT_ITEM_TYPES` (`memory_item` vs `rag_chunk`) all
the way through to `chat_response_citations`, so a generated answer's
citations always distinguish "this came from something you told me"
from "this came from the knowledge base" — never merged into one
undifferentiated evidence pool.
