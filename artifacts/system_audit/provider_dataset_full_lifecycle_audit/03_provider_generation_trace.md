# 03 PATH B: PROVIDER DATA GENERATION TRACE

- Generator Engine: `MiniBrainMultimodalDatasetGeneratorService` (MB-16) at `/admin/mini-brain/multimodal-dataset-generator`.
- UI Entry Point: `MultimodalDatasetGeneratorTab.jsx` on Admin Dashboard (`propose -> preview -> confirm -> execute` pipeline).
- Storage Scope: Writes to MB-16's own tables (`mini_brain_multimodal_dataset_sessions`, `_records`, `_events`).
- Isolation Invariant: No MB-16 route automatically writes to Dataset Studio, imports documents, starts training, or deploys models (`LEVEL 5 - PROVEN ISOLATED`).
