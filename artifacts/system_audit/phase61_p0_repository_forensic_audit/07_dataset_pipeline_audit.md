# 07 DATASET PIPELINE AUDIT

## Input Workflows Audit

### Mode A — Admin Supplied Dataset Workflow
- **Status**: 
- **Execution Path**: File Upload -> Provenance () -> Rights Check () -> Deduplication (, ) -> Quality Score () -> Token Accounting () -> Candidate Approval Gate.

### Mode B — Admin Requested Dataset Preparation Workflow
- **Status**: 
- **Evidence**:
  - Format ingestion supports PDF, TXT, HTML, JSONL ().
  - Text extraction and OCR cleaning (, ) work on local files.
  - **Gap**: End-to-end autonomous discovery, web acquisition, and rights clearance requested via high-level natural language prompt is not fully wired.
