# PDF security

Uploads are bounded, streamed, hashed, assigned server-generated names, and stored privately with restrictive permissions. Filenames are sanitized; traversal and null-byte names are rejected. The `%PDF-` signature and PyMuPDF parse are required. Encrypted, malformed, empty, oversized, and over-limit documents are rejected. PDFs are never executed, publicly served, or sent to external providers. Duplicate checksums return the existing public ID without storing a second copy.
