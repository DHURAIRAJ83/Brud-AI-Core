# 09 TRAINING PIPELINE TRACE

- Pipeline Scripts: `scripts/01_prepare_data.py`, `scripts/02_train_tokenizer.py`, `scripts/03_pretrain.py`, `scripts/04_finetune.py`, `scripts/05_quantize.py`, `scripts/06_test_inference.py`.
- Training Gate: All pretraining entry points strictly enforce `SignedTrainingGateEngine` fail-closed verification.
- UI Visibility: Rendered on `BaseTrainingPage.jsx` and `IncrementalTrainingPage.jsx` (`LEVEL 5 - E2E VERIFIED`).
