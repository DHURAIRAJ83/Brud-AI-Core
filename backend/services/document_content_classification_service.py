"""Text-data-only content classification for document pages (Task
Finalization §16/§17). No vision model is used or implied -- classification
is derived entirely from extraction metadata already computed by the
existing pipeline (`document_pages.image_count`/`text_length`) plus a
conservative, table-likelihood text heuristic. A page whose meaning cannot
be recovered from its extracted text is marked `vision_required` and is
never eligible for text-only SFT generation.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.documents import DocumentRepository, decode

_CLASSIFICATION_JSON = {"table_data_json"}

_MIN_USABLE_TEXT_CHARS = 40
_MIN_SUBSTANTIAL_TEXT_CHARS = 200
# A conservative, text-only table-likelihood signal: several consecutive
# lines that each contain multiple wide-gap/tab/pipe-separated fields. Real
# structured extraction (e.g. PyMuPDF's table finder) was not wired in this
# pass -- disclosed as a known limitation, not fabricated as full support.
_COLUMN_SEPARATOR = re.compile(r"(?:\t| {3,}|\s\|\s)")


def _looks_like_table(text: str) -> bool:
    matching_lines = 0
    for line in text.split("\n"):
        if len(_COLUMN_SEPARATOR.split(line.strip())) >= 3:
            matching_lines += 1
    return matching_lines >= 3


class DocumentContentClassificationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)

    def _classify(self, page) -> tuple[str, bool]:
        image_count = page["image_count"] or 0
        text = page["cleaned_text"] or ""
        text_length = len(text.strip())

        if image_count == 0:
            if _looks_like_table(text):
                return "table", False
            return "text_only", False

        if text_length < _MIN_USABLE_TEXT_CHARS:
            return "image_without_usable_text", True
        if text_length < _MIN_SUBSTANTIAL_TEXT_CHARS:
            return "image_with_caption", False
        if _looks_like_table(text):
            return "mixed_content", False
        return "image_with_explanation", False

    def classify_page(
        self, document_public_id: str, page_number: int, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            page = self.repository.page(connection, document["id"], page_number)
            content_type, vision_required = self._classify(page)
            text = page["cleaned_text"] or ""
            existing = connection.execute(
                "SELECT id FROM document_content_classifications WHERE document_source_id=? "
                "AND page_number=?",
                (document["id"], page_number),
            ).fetchone()
            caption_text = text[:_MIN_SUBSTANTIAL_TEXT_CHARS] if content_type in (
                "image_with_caption", "image_with_explanation", "mixed_content"
            ) else ""
            if existing:
                connection.execute(
                    "UPDATE document_content_classifications SET content_type=?,"
                    "caption_text=?,vision_required=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (content_type, caption_text, 1 if vision_required else 0, existing["id"]),
                )
                public_id_row = connection.execute(
                    "SELECT public_id FROM document_content_classifications WHERE id=?",
                    (existing["id"],),
                ).fetchone()
                classification_public_id = public_id_row["public_id"]
            else:
                classification_public_id = str(uuid4())
                connection.execute(
                    """INSERT INTO document_content_classifications(
                        public_id,document_source_id,page_number,content_type,caption_text,
                        vision_required
                    ) VALUES (?,?,?,?,?,?)""",
                    (
                        classification_public_id, document["id"], page_number, content_type,
                        caption_text, 1 if vision_required else 0,
                    ),
                )
        return self.get_classification(document_public_id, page_number)

    def get_classification(self, document_public_id: str, page_number: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            row = connection.execute(
                "SELECT * FROM document_content_classifications WHERE document_source_id=? "
                "AND page_number=?",
                (document["id"], page_number),
            ).fetchone()
        if row is None:
            raise ValidationError("this page has not been classified yet")
        return decode(row, _CLASSIFICATION_JSON)

    def classify_document(self, document_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            pages = connection.execute(
                "SELECT page_number FROM document_pages WHERE document_source_id=? "
                "ORDER BY page_number LIMIT ?",
                (document["id"], self.settings.document_classification_max_pages_per_job),
            ).fetchall()
        for page in pages:
            self.classify_page(document_public_id, page["page_number"], admin_id)
        return self.summary(document_public_id)

    def summary(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            rows = connection.execute(
                "SELECT content_type,COUNT(*) count FROM document_content_classifications "
                "WHERE document_source_id=? GROUP BY content_type",
                (document["id"],),
            ).fetchall()
            vision_required_count = connection.execute(
                "SELECT COUNT(*) FROM document_content_classifications WHERE "
                "document_source_id=? AND vision_required=1",
                (document["id"],),
            ).fetchone()[0]
        return {
            "document_public_id": document_public_id,
            "by_content_type": {row["content_type"]: row["count"] for row in rows},
            "vision_required_count": vision_required_count,
        }
