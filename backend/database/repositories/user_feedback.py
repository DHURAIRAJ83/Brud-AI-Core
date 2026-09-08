"""User feedback repository for chat evaluations and telemetry."""

from __future__ import annotations

from uuid import uuid4

from backend.database.repositories.base import BaseRepository, NotFoundError
from backend.models.domain import UserFeedbackCreate, UserFeedbackPublic


class FeedbackRepository(BaseRepository):
    def create(self, item: UserFeedbackCreate) -> UserFeedbackPublic:
        public_id = str(uuid4())
        with self.transaction() as connection:
            chat_message_id = None
            if item.chat_message_public_id:
                row = connection.execute(
                    "SELECT id FROM chat_messages WHERE public_id=?",
                    (item.chat_message_public_id,),
                ).fetchone()
                if not row:
                    raise NotFoundError("chat message not found")
                chat_message_id = row[0]
            connection.execute(
                """INSERT INTO user_feedback(public_id,chat_message_id,feedback_type,rating,
                comment,suggested_answer,status) VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    chat_message_id,
                    item.feedback_type.value,
                    item.rating,
                    item.comment,
                    item.suggested_answer,
                    item.status.value,
                ),
            )
        return self.get_by_public_id(public_id)

    def get_by_public_id(self, public_id: str) -> UserFeedbackPublic:
        with self.transaction() as connection:
            row = connection.execute(
                """SELECT f.*, m.public_id AS chat_message_public_id FROM user_feedback f
                LEFT JOIN chat_messages m ON m.id=f.chat_message_id WHERE f.public_id=?""",
                (public_id,),
            ).fetchone()
        if not row:
            raise NotFoundError("feedback not found")
        return UserFeedbackPublic(
            public_id=row["public_id"],
            chat_message_public_id=row["chat_message_public_id"],
            feedback_type=row["feedback_type"],
            rating=row["rating"],
            comment=row["comment"],
            suggested_answer=row["suggested_answer"],
            status=row["status"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
        )
