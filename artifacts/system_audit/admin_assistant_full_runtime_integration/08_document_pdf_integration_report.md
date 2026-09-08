# 08 DOCUMENT / PDF INTEGRATION REPORT

- File Upload via Chat: Uploading PDF/dataset files in `ChatPanel.jsx` calls `assistantUpload()` -> `POST /api/admin/assistant/upload` -> parses document text, computes SHA-256 checksums, and stages documents (`END_TO_END_WORKING`).
- Documents Page: `DocumentsPage.jsx` connects to `GET /api/admin/documents` (`END_TO_END_WORKING`).
