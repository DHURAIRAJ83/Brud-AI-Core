# Stage D Audit Report — 02: Executable Architecture Discovery

## Executive Summary
| Component | Primary File | Class / Module | Runtime Status | Implementation Quality |
|---|---|---|---|---|
| **Canonical Model** | `core_model/architecture/brud_small_v2.py` | `BrudSmallV2Model` & `BrudSmallScaledModel` | REAL | ✅ Production Consolidated |
| **Canonical Training Engine** | `core_model/training/brud_training_engine.py` | `BrudTrainingEngine` | REAL | ✅ Governed & Refusing |
| **Safe Checkpoint Loader** | `core_model/training/brud_training_engine.py` | `load_checkpoint_safely` | REAL | ✅ PE-Filtered & Fail-Closed |
| **Inference Runtime** | `backend/services/inference_runtime_service.py` | `InferenceRuntimeService` | REAL | ⚠️ Needs Default $\\theta=1.25$ Wiring |
| **Admin Mini Brain** | `backend/services/admin_mini_brain_service.py` | `AdminMiniBrainService` | REAL | ✅ Governed Proposal Assistant |
