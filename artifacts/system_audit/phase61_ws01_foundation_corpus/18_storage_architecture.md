# Phase 61 WS01 Report — 18: Storage Format Architecture

## Storage Formats
- **Dataset Records:** Stored in UTF-8 `.jsonl` files (streamable, zero-RAM overhead).
- **Dataset Metadata & Lineage:** Stored in SQLite database (`data/database/brud_ai.db`).
