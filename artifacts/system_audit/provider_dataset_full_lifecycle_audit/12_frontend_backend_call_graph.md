# 12 FRONTEND ↔ BACKEND CALL GRAPH

```text
PATH A (Admin Upload):
ChatPanel / DocumentsPage ──[POST /api/admin/assistant/upload]──> DocumentService ──> ImportService ──> DatasetAdminRepository ──> RagRepository [✓ LEVEL 5 PROVEN]

PATH B (Provider Generation):
MultimodalDatasetGeneratorTab ──[POST /admin/mini-brain/multimodal-dataset-generator/sessions]──> MiniBrainMultimodalDatasetGeneratorService ──> Draft Sessions/Records [✓ LEVEL 5 PROVEN ISOLATED]
```
