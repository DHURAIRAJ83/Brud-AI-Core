# Phase 20 — Deterministic Tool Contract

## 1. Pipeline

```
Phase 17 classification (intent=ask_calculation)
  -> select_tool_for_request() (deterministic regex sub-classification,
     never a user-supplied tool name)
  -> extract_tool_input() (bounded regex extraction, returns None on
     any ambiguity -- never guesses a value)
  -> DeterministicToolExecutionService.execute()
       tool lookup (closed registry, unknown name -> "unsupported")
       -> external_mcp source check (unconditional refuse)
       -> public/admin-enabled check
       -> rate limit check (tool_exec)
       -> input schema validation (required fields)
       -> deterministic execution (real arithmetic code, never eval)
       -> output normalization
       -> audit (deterministic_tool_execution_events, always written)
  -> format_tool_result_text() (template, never the model, wraps the
     already-final structured result)
```

## 2. Tool selection

`core_model/tool_gateway/tool_selection.py::select_tool_for_request()`
is a pure function over Phase 17's own `intent` field — only
`ask_calculation` (one of Phase 17's existing `_TOOL_INTENTS`) ever
selects a tool; `ask_code` (the other member) has no matching tool and
always returns `None`. Never modifies Phase 17's classification to
accommodate this. Within `ask_calculation`, a bounded regex decides
`unit_conversion` (unit-keyword + `to`/`in` pattern) vs.
`date_time_arithmetic` (ISO date + day/week-delta hint) vs. the
`calculator` default — always exactly one of three fixed strings, or
`None`.

## 3. Calculator (`core_model/tool_gateway/calculator.py`)

AST-allowlist evaluator over `decimal.Decimal` — **never** `eval`,
`exec`, or `compile` with anything but the one pre-validated
`mode="eval"` parse call (proven structurally: a test walks the
module's own AST and asserts no `eval`/`exec` call exists in the
source). Allowed: `Add`, `Sub`, `Mult`, `Div`, `Pow`, unary `+`/`-`,
numeric constants, parentheses, percentages (regex-normalized to
`(N/100)` before parsing). Everything else — `Call`, `Attribute`,
`Name`, `Import`, `Lambda`, comprehensions, assignments, boolean/
comparison/bitwise operators, f-strings, collection literals — falls
through to `unsupported_expression`/`unsupported_operator` (an
allowlist, not a denylist, so a novel Python syntax feature is
rejected by default).

Bounds: `MAX_EXPRESSION_LENGTH=200`, `MAX_PAREN_DEPTH=20` (checked on
the raw string *before* parsing — CPython's own parser recursion limit
can be hit by paren count regardless of the post-parse AST-depth
check), `MAX_AST_DEPTH=20`, `MAX_EXPONENT=12`,
`MAX_RESULT_EXPONENT=100` (rejects a result whose magnitude exceeds
10^100). Division/modulo by zero raise a clean `CalculatorError`, never
a raw Python exception.

**Real bug found and fixed**: `%` was originally both a percentage
suffix *and* a modulo binary operator, but the percentage-normalizing
regex runs before parsing and cannot distinguish `"50% * 200"` from
`"10 % 3"` — the latter was silently corrupted into invalid syntax
(`"(10/100) 3"`). Since Step 18 requires percentage support but never
mentions modulo, `Mod` was removed from the allowed binary operators;
`%` is now unconditionally percentage-only, documented in the module's
own docstring.

19 real security-focused parametrized test cases proven blocked:
`__import__('os')`, `open(...)`, `(1).__class__`/`__mro__`/`__bases__`
attribute-chain sandbox-escape attempts, `lambda`, comprehensions,
`exec`/`eval`/`compile` calls, `import` statements, `globals()`/
`locals()`/`vars()`/`getattr`, boolean/comparison/bitwise operators,
string/collection literals, f-strings — all rejected.

## 4. Unit conversion (`core_model/tool_gateway/unit_conversion.py`)

Explicit unit allowlists only across `length`/`mass`/`volume`/`time`/
`area`/`speed`/`data_size`/`temperature` (special-cased, non-linear).
An unrecognized unit is `invalid_unit`, never guessed.
`ton`/`gallon`/`cup` (bare) are rejected as `ambiguous_unit` — their
common definitions differ 10-20%+ across locales/standards; the
qualified forms (`metric_ton`/`us_ton`/`uk_ton`,
`gallon_us`/`gallon_uk`, `cup_us`/`cup_metric`) work. `mile` is treated
as the international statute mile (a documented, deliberate judgment
call — virtually every general-purpose conversion tool does this, and
no common "mile" definition differs enough to warrant a clarification
prompt the way `ton`/`gallon`/`cup` do). `MAX_CONVERSION_MAGNITUDE=1e15`
bounds extreme values. Mismatched categories (`kg` → `metres`) are
rejected, never silently coerced.

## 5. Date/time arithmetic (`core_model/tool_gateway/date_time_arithmetic.py`)

ISO-8601 (`YYYY-MM-DD`) dates only — a locale-ambiguous form like
`01/02/2026` is rejected as `ambiguous_date_format`, never guessed.
Calendar-date-only operations never need a timezone; a datetime with a
time-of-day component requires an explicit UTC offset/`Z` suffix or is
rejected as `timezone_required`. No live "current time" is ever
returned — every operation is anchored to caller-supplied dates only.
`MAX_DAY_DELTA=366,000` (~1000 years) bounds huge-range abuse for
`add_days`/`add_weeks`/`date_difference`. Leap years handled correctly
via Python's own `datetime.date` arithmetic (verified:
2028-02-28 + 1 day = 2028-02-29; 2026-02-28 + 1 day = 2026-03-01).

## 6. Tool result integration

`PublicChatResponse` for a successful tool answer:
`route_used="tool"`, `tool_name`, `tool_version`, `tool_status`,
`source_types=["tool"]`, `citations=[]`, `evidence_status=
"deterministic"` (a new, distinct taxonomy value — never conflated
with `"grounded"`). The reply text is built by
`format_tool_result_text()` — a bilingual template function, not an
LLM call, wrapping the already-final structured `output_payload`; the
model never sees or can alter the numeric result. Live-verified:
`987654 * 12345 = 12192588630` rendered exactly in the running
chatbot UI, `5.0 kilometres = 5000.0 metres`, `Difference: 30 days.`

## 7. Registry (`backend/services/deterministic_tool_registry.py`)

Exactly three hand-written `ToolDescriptor` entries, no reflection-
based dynamic import, no plugin auto-loading from any location.
`get_tool_descriptor()` only ever returns one of these three fixed
descriptors or `None` — never a caller-supplied arbitrary name.
