"""Phase 21A: production tokenizer and base-model pretraining
readiness -- pure functions only. All impure work (SentencePiece
training, corpus/dataset reads, PyTorch model construction, real
trainer execution) lives in `backend/services/`, which reuses Phase
7 (tokenizer), Phase 8 (architecture), Phase 9 (trainer/checkpoint),
and Phase 20 (corpus release) machinery unchanged."""
