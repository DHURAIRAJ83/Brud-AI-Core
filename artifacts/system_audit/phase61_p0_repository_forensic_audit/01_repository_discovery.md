# 01 REPOSITORY DISCOVERY

## Executive Summary
This document records the foundational discovery metrics for the **Brud AI / Brud Admin Assistant Mini Brain** repository gathered during Phase 61 - P0 Forensic Audit.

## Baseline Metadata
- **Absolute Repository Path**: 
- **Git Branch**: 
- **Commit SHA**: 
- **Governance State**: 
- **Audit Timestamp**: 

## Repository Physical Metrics
- **Total Workspace Files**: 79,004 (excluding )
- **Total Workspace Directories**: 12,113 (excluding )
- **Total Disk Volume**: 9,333,389,773 bytes (~9.33 GB)

## Inventory by File Type / Extension
| Category | File Extension | Count | Description / Role |
| :--- | :--- | :--- | :--- |
| Source Code |  | 9,595 | Python backend, core_model, scripts, tests |
| Compiled Python |  | 9,598 | Bytecode cache files |
| Frontend | , , ,  | 6,432 | Next.js / Vite web applications |
| Datasets / Documents |  | 8,345 | Scanned and text books / document corpus |
| Datasets / Text | , ,  | 21,732 | Corpus records, manifests, configs |
| Model Checkpoints | , , ,  | 6,357 | PyTorch & GGUF model weights |
| Tokenizers | ,  | 201 | SentencePiece / BPE vocabulary files |
| Databases | ,  | 160 | SQLite database files (deploy, tests, audit) |
| Documentation |  | 2,492 | Architecture specs, phase reports, guides |
| C/C++ Headers/Source | , , ,  | 9,734 | Native extensions and embedded headers |

## Primary Subsystems Identified
1. : FastAPI REST endpoints, database ORM, runtime services, background tasks.
2. : Core LLM engine, Admin Assistant, Mini Brain, corpus pipelines, evaluation, training, provider integrations, RAG, tokenizer.
3. : Web dashboards (, ).
4. : Infrastructure, model configs, system environments.
5. : Staging & deployment scripts, isolated test database environments.
6. : Extensive test suites (, , , ).
