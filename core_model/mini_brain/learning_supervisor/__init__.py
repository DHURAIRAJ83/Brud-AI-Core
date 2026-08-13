"""MB-06: Learning Supervisor -- an orchestration layer, never a
Training Engine. Every module here decides, validates, compares, or
recommends -- none of them run a gradient step, write a checkpoint, or
touch model weights. The existing CPU Training Engine
(`backend/services/pretraining_service.py`, `core_model/training/`)
remains the only component permitted to actually train.

Reuse discipline (audited before writing anything): overfitting/
underfitting math reuses `core_model.training.diagnostics`
(`loss_improvement_ratio`, `train_validation_gap`, `is_diverging`,
`safe_perplexity`) UNCHANGED -- never a second loss-diagnostics
implementation. Everything that submits, monitors, or acts on real
training/RAG/benchmark state goes through the existing services'
public methods only, composed in `backend/services/
mini_brain_learning_supervisor_service.py`, never duplicated here.
"""
