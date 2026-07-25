# Feedback API and CLI

## API

54 routes under `/api/admin/feedback`, every mutating route behind
`require_admin` + CSRF:

- **Policies**: `GET/POST /policies`, `GET/PATCH /policies/{id}`,
  `POST /policies/{id}/{validate,activate}`.
- **Feedback events**: `GET/POST /events`, `GET /events/{id}`,
  `POST /events/{id}/{triage,delete}`,
  `GET/POST /events/{id}/classifications`, `GET /events/{id}/findings`.
- **Review queues**: `GET/POST /review-queues`, `GET /review-queues/{id}`,
  `POST /review-queues/{id}/assign`, `GET /review-queues/{id}/items`.
- **Reviews**: `POST/GET /events/{id}/reviews`,
  `GET /events/{id}/review-summary`.
- **Corrected responses**: `POST/GET /events/{id}/corrected-responses`,
  `GET /corrected-responses/{id}`,
  `POST /corrected-responses/{id}/{validate,reject}`.
- **Dataset candidates**: `GET /dataset-candidates`,
  `POST /events/{id}/dataset-candidates`, `GET /dataset-candidates/{id}`,
  `POST /dataset-candidates/{id}/{validate,approve,reject,quarantine,export}`,
  `GET /dataset-candidates/{id}/{versions,issues}`.
- **Regression suites/runs**: `GET/POST /regression-suites`,
  `GET /regression-suites/{id}`, `POST /regression-suites/{id}/fixtures`,
  `POST /regression-suites/{id}/{validate,activate}`,
  `POST /regression-suites/{id}/runs`,
  `POST /regression-runs/{id}/execute`, `GET /regression-runs/{id}`,
  `GET /regression-runs/{id}/{results,metrics}`.
- **Comparisons and reports**: `POST /regression-runs/compare`,
  `GET /comparisons/{id}`, `POST/GET /improvement-reports[/{id}]`.
- **Manifest**: `GET /policies/{id}/manifest`,
  `POST /policies/{id}/manifest/verify`.

Every response exposes public IDs only — no absolute filesystem paths,
no internal integer database IDs, no secrets, no raw hidden system
prompts.

## CLI

`backend/feedback_cli.py`, 18 subcommands: `policies`, `create-policy`,
`events`, `inspect-event`, `triage`, `assign-review`, `review`,
`add-correction`, `validate-correction`, `create-candidate`,
`validate-candidate`, `approve-candidate`, `export-candidate`,
`create-regression-suite`, `execute-regression`, `compare-runs`,
`create-report`, `verify-manifest`. Mirrors the typed-confirmation
pattern used by every prior phase's operator CLI (e.g.
`backend/rag_cli.py`, `backend/conversation_memory_cli.py`).
