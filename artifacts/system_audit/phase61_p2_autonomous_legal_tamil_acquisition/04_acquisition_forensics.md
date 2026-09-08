# 04 ACQUISITION FORENSICS

- Engine: `core_model/corpus/autonomous_book_acquisition.py`.
- State Machine: `DISCOVERED -> SOURCE_VALIDATED -> RIGHTS_PENDING -> RIGHTS_VERIFIED -> ACQUISITION_APPROVED -> DOWNLOADED -> INTEGRITY_VERIFIED -> EXTRACTION_PENDING -> EXTRACTED`.
- Isolated Storage: All downloads saved exclusively in `data/candidate_acquisitions/`. Zero production database or model mutation.
