"""MB-26: Brud Mini Brain Voice & Speech Runtime -- pure policy/planning
helpers only. Every module here is deterministic and side-effect free,
except `audio_session_manager.py` (the one explicit local-file-I/O
module, the same class of exception `timeout_runner.py` establishes
for MB-25's package) and the two optional real-backend adapters
(`faster_whisper_backend.py`, `coqui_tts_backend.py`), which are
impure by the unavoidable nature of real model loading and inference
-- both are import-guarded and never a hard dependency.
"""
