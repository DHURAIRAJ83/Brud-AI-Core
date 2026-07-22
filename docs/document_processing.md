# Document processing

PDFs are streamed into private project storage, signature-checked, opened with PyMuPDF, and rejected when encrypted, malformed, empty, or over configured size/page limits. Pages are analysed independently: embedded text is extracted directly and image-only pages use local OCR when available. Failed pages remain visible.

Cleaned text is derived from raw text and can be edited without changing raw evidence. Deterministic paragraph/page/window segmentation creates candidates with page provenance. Candidates are validated, duplicate-checked, reviewed, and imported transactionally as draft records only. Cancellation is checked between pages and archive is soft-delete.

Phase 6 quality and versioning can later assess PDF-derived draft records, approve eligible records through admin review, and include approved records in immutable dataset versions. Document processing itself never approves records or trains a model.
