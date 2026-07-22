# OCR processing

OCR is local and optional. Capability detection reports PyMuPDF, Tesseract, and installed `tam`/`eng` language packs without exposing executable paths. Pages render one at a time with bounded DPI/pixels, page count, and timeout. Raw OCR and cleaned text are separate, with duration and low-confidence warnings. Missing dependencies and OCR failures are controlled errors; no automatic spelling correction is performed.
