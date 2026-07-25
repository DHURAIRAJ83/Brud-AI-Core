# Conversation Memory API and CLI

## API

58 routes under `/api/admin/conversation-memory`, every mutating
route behind `require_admin` + CSRF:

- **Policies**: `GET/POST /policies`, `GET/PATCH /policies/{id}`,
  `POST /policies/{id}/validate`, `POST /policies/{id}/activate`.
- **Sessions**: `GET/POST /sessions`, `GET /sessions/{id}`,
  `POST /sessions/{id}/{pause,resume,close,expire}`,
  `GET /sessions/{id}/turns`.
- **Messages / orchestration**: `POST /sessions/{id}/messages`,
  `GET /orchestration-runs/{id}`,
  `GET /orchestration-runs/{id}/{context,response,issues}`.
- **Summaries**: `POST/GET /sessions/{id}/summaries`,
  `GET /summaries/{id}`,
  `POST /summaries/{id}/{validate,accept,reject}`.
- **Consent**: `GET/POST /consents`, `GET /consents/{id}`,
  `POST /consents/{id}/{revoke,expire}`.
- **Memory items**: `GET/POST /memory-items` (`GET` accepts an
  optional `participant_scope_key` filter), `GET /memory-items/{id}`,
  `POST /memory-items/{id}/{confirm,reject,correct,expire,delete}`,
  `GET /memory-items/{id}/{versions,events}`.
- **Retrieval profiles / retrieval**: `GET/POST /retrieval-profiles`,
  `GET/PATCH /retrieval-profiles/{id}`,
  `POST /retrieval-profiles/{id}/{validate,activate}`,
  `POST /retrieve`, `GET /retrieval-runs/{id}`,
  `GET /retrieval-runs/{id}/results`.
- **Evaluation**: `GET/POST /evaluation-suites`,
  `POST /evaluation-suites/{id}/fixtures`,
  `POST /evaluation-suites/{id}/runs`,
  `POST /evaluation-runs/{id}/execute`,
  `GET /evaluation-runs/{id}`, `GET /evaluation-runs/{id}/metrics`.
- **Manifest**: `POST /policies/{id}/manifest`,
  `GET /policies/{id}/manifest/verify`.

Every response exposes public IDs only — no absolute filesystem paths,
no internal integer database IDs, no secrets, no raw tensors.

## CLI

`backend/conversation_memory_cli.py`, 15 subcommands: `policies`,
`create-policy`, `create-session`, `inspect-session`, `send-message`,
`create-summary`, `grant-consent`, `revoke-consent`,
`propose-memory`, `confirm-memory`, `correct-memory`,
`delete-memory`, `retrieve-memory`, `evaluate`, `verify-manifest`.
Mirrors the typed-confirmation pattern used by every prior phase's
operator CLI (e.g. `backend/rag_cli.py`).
