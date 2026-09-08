# 16 ADMIN DATA VS PROVIDER GENERATED DATA MATRIX

| Capability | Admin Upload (Path A) | Provider Generated (Path B) |
|---|---|---|
| Frontend UI | `DocumentsPage.jsx` / `ChatPanel.jsx` | `MultimodalDatasetGeneratorTab.jsx` |
| API Route | `POST /api/admin/assistant/upload` | `POST /admin/mini-brain/multimodal-dataset-generator/*` |
| Backend Service | `DocumentService` / `ImportService` | `MiniBrainMultimodalDatasetGeneratorService` |
| Data Validation | `data_cleaner.py` / `DatasetService` | MB-16 `quality_analysis` / `duplicate_detection` |
| Quality Scoring | YES — PROVEN | YES — PROVEN |
| Duplicate Check | YES — PROVEN | YES — PROVEN |
| Human Review | YES — PROVEN | YES — PROVEN (Mandatory Admin Certification) |
| Dataset Versioning | YES — PROVEN | YES — PROVEN (Exports Draft on certification) |
| RAG Ingestion | YES — PROVEN | YES — PROVEN (Post-certification) |
| Training Eligibility | YES — PROVEN | YES — PROVEN (Post-certification & Token check) |
| Chat Direct Invoc | YES — PROVEN | PARTIAL (Prompting guidance; generation via Dashboard tab) |
| Runtime Verified | YES — PROVEN | YES — PROVEN |
