# 08 TAMIL BOOK ACQUISITION AUDIT

## Capabilities Inventory

| Subsystem | Status | Location | Evidence / Capability |
| :--- | :--- | :--- | :--- |
| PDF Extraction |  |  | PyPDF / pdfplumber text extraction |
| Scanned Book OCR |  |  | Text cleanup regexes present; external OCR engine (Tesseract/PaddleOCR) dependency required |
| Tamil Normalization |  |  | Preserves NFC Unicode combining marks, strips mojibake |
| URL / Book Registry |  | N/A | No dedicated URL registry table for digital library crawling |
| Autonomous Book Downloader |  | N/A | Downloading from external book repositories requires manual upload |
