# 07 OCR FORENSICS

- Adapter: `core_model/corpus/ocr_adapter.py`.
- Integration: Optional Tesseract/PaddleOCR connectors with pure Python regex fallback.
- OCR Confidence Threshold: Flags `review_required = True` if confidence < 0.70 or garbled script mixing detected.
