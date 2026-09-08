# 04 MODULE INVENTORY

## High-Level Subsystems and Component Mapping

### 1. Admin Assistant & Mini Brain Subsystem
- **Path**: , , 
- **Key Modules**:
  - : Formulates tool invocation plans.
  - : Manages short-term conversation context.
  - : Rule/heuristic-based intent parser.
  - : Structured prompt formulation engine.
  - : Post-action feedback validator.
  - : Main state machine for Mini Brain.

### 2. Corpus & Dataset Subsystem
- **Path**: , 
- **Key Modules**:
  - : Main JSONL/text ingestion stream.
  -  & : SHA256 & Jaccard token n-gram dedup.
  -  & : Dataset rights verification.
  -  & : Tamil text cleaning & OCR artifact removal.
  - : Heuristic domain tagger.

### 3. Sovereign Training Subsystem
- **Path**: 
- **Key Modules**:
  - : Core PyTorch training loop.
  - : Multi-epoch execution engine.
  -  & : Token accounting ledgers.
  - : Validation loss and gradient checks.
