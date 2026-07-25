# Conversation Memory Settings

21 `BRUD_MEMORY_*` settings in `backend/core/config.py`, plus 2 derived
list properties (`memory_allowed_categories_list`,
`memory_forbidden_categories_list`).

| Setting | Default | Purpose |
|---|---|---|
| `BRUD_MEMORY_ENABLED` | `true` | master feature flag |
| `BRUD_MEMORY_DEFAULT_SESSION_MODE` | `private_no_persist` | default mode for new sessions |
| `BRUD_MEMORY_MAX_SESSION_TURNS` | 20 | per-session turn cap |
| `BRUD_MEMORY_MAX_SESSION_AGE_SECONDS` | 3600 | session TTL |
| `BRUD_MEMORY_MAX_TURN_CHARACTERS` | 4000 | per-turn content length cap |
| `BRUD_MEMORY_MAX_SHORT_TERM_TOKENS` | 800 | short-term context token budget |
| `BRUD_MEMORY_MAX_SUMMARY_TOKENS` | 200 | summary token budget |
| `BRUD_MEMORY_MAX_LONG_TERM_ITEMS` | 50 | per-participant active memory item cap |
| `BRUD_MEMORY_DEFAULT_TTL_SECONDS` | 7,776,000 (90 days) | default memory item expiry |
| `BRUD_MEMORY_MAX_RETRIEVAL_RESULTS` | 5 | default retrieval result cap |
| `BRUD_MEMORY_MAX_CONTEXT_TOKENS` | 200 | memory-evidence context budget |
| `BRUD_MEMORY_REQUIRE_EXPLICIT_CONSENT` | `true` | gate long-term memory behind consent |
| `BRUD_MEMORY_ALLOW_ASSISTANT_PROPOSALS` | `true` | allow assistant-inferred proposals at all |
| `BRUD_MEMORY_AUTO_ACTIVATE_USER_CONFIRMED` | `false` | never auto-activate without the consent/confirmation gate |
| `BRUD_MEMORY_BLOCK_SENSITIVE_CONTENT` | `true` | enforce the safety scan as blocking, not just warning |
| `BRUD_MEMORY_PRIVATE_SESSION_RETENTION_SECONDS` | 0 | private-mode content retention (0 = none) |
| `BRUD_MEMORY_MAX_ACTIVE_SESSIONS` | 5 | per-participant concurrent session cap |
| `BRUD_MEMORY_MAX_ACTIVE_EVALUATION_RUNS` | 1 | concurrent evaluation run cap |
| `BRUD_MEMORY_ALLOWED_CATEGORIES` | the 8 `MEMORY_CATEGORIES`, comma-separated | policy-layer allow-list |
| `BRUD_MEMORY_FORBIDDEN_CATEGORIES` | the 14 `FORBIDDEN_MEMORY_CATEGORIES`, comma-separated | documents the structural deny-list at the settings layer too |
| `BRUD_MEMORY_REQUIRE_DELETION_CACHE_INVALIDATION` | `true` | asserts the "no stale cache" retrieval design is in effect |

`BRUD_MEMORY_DEFAULT_SESSION_MODE=private_no_persist` is the single
setting that most directly encodes this phase's core privacy
guarantee: a session started with no other configuration retains
nothing after it ends.
