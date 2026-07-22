# Phase 9 Report

## Baseline

- Baseline commit: `30b1181 feat: add Brud AI phase 8 core model architecture`
- Migration: `009_phase9_core_pretraining`
- Schema version: `9`

## Backup and migration

- Pre-migration schema: `8`
- Pre-migration checksum: `d7e04ffc32fba3c0a92b3fe3e0ccc8413773fae06e49745239d3bc9eced498c4`
- Backup: `brud_ai_before_v9_20260722_100217_707871.db`
- Backup checksum: `ed987401468af4099b8fcad75786260e0b259f4f44775b204fa81cebb129bb14`
- Post-migration checksum: `0915ffd562de1b539440e2b07c8f893251baa343082801efd305d5d681011523`
- Integrity check: `ok`
- Foreign-key check: no violations

## Capability results

- NumPy: `2.5.1`
- PyTorch: `2.13.0+cpu`
- NumPy/PyTorch interop: `torch.from_numpy(np.array([1,2,3]))` returned `tensor([1, 2, 3])`
- CUDA: unavailable; CPU-first behavior preserved

Port 8000 ownership could not be inspected because the sandbox returned `Cannot open netlink socket: Operation not permitted`. No process was killed. API verification used ASGI and alternate-port startup was attempted on `8001`, but loopback HTTP was blocked by sandbox policy.

## Implementation summary

Phase 9 adds:

- bounded pretraining schema tables;
- pretraining config validation;
- deterministic token-block packing;
- AdamW optimizer and schedulers;
- CPU training loop with metrics;
- validation-loss evaluation;
- optimizer-aware checkpoint manager;
- pause/resume checkpoint restoration;
- local worker command;
- authenticated pretraining APIs;
- pretraining CLI;
- Admin Dashboard Training page.

## Training evidence

Isolated temp-DB bounded run:

- Initial loss: `4.127198696136475`
- Final loss: `3.0928852558135986`
- Validation loss: `3.211236039797465`
- Processed tokens: `140`
- Final checkpoint checksum: `edd99df559384278e74c09cf1c66124244bdadc6c4d70cc0671c1e08999532ad`

Pause/resume temp-DB proof:

- Pause requested: `true`
- Paused at step: `2`
- Processed tokens at pause: `14`
- Resume completed at step: `6`
- Final processed tokens: `42`
- Checkpoint kinds: `final`, `pause`
- Latest checkpoint checksum: `be7532a8284ae36d8cde339ccd4d54a8a6f5919b7af01ec35b821490a4f4198f`

## API verification

ASGI verification:

- `GET /api/health`: `200`
- `GET /api/version`: `200`
- `POST /api/chat`: `200`
- unauthenticated `GET /api/admin/pretraining/capabilities`: `401`
- `POST /api/admin/auth/login`: `200`
- `GET /api/admin/auth/me`: `200`
- `GET /api/admin/overview`: `200`
- authenticated `GET /api/admin/pretraining/capabilities`: `200`
- authenticated `GET /api/admin/pretraining/jobs`: `200`
- missing CSRF mutation: `403`
- invalid estimate: `422`
- logout: `200`

Full job, worker, checkpoint, validation, promotion, CSRF, and safe-response coverage is implemented in temporary-database tests.

## Verification

- `python -m pytest -q`: `125 passed in 165.61s`
- `python -m ruff check .`: passed
- `git diff --check`: passed
- Chatbot build: passed
- Admin Dashboard build: passed
- SQLite `PRAGMA integrity_check`: `ok`
- SQLite `PRAGMA foreign_key_check`: no rows
- SQLite `PRAGMA user_version`: `9`

## Known limitations

- The development database currently has a ready dataset version but no registered verified tokenizer or architecture-verified model, so a real dev pretraining job was not queued against development data.
- Local HTTP loopback curl was blocked by sandbox policy; ASGI verification was used.
- The Phase 9 tiny stream is deterministic and bounded, but production-grade tokenizer-backed streaming and richer recovery tooling should be hardened in Phase 10.
- A short CPU run is not evidence of Tamil understanding or chat readiness.

## Phase 10 readiness

Phase 10 can build on v9 by hardening tokenizer-backed streaming, improving worker recovery/lease maintenance, adding richer checkpoint comparison, and beginning carefully bounded training-quality evaluation.

## Final verdict

PHASE_9_COMPLETE_WITH_WARNINGS
