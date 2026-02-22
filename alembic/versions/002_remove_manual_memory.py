"""移除 manual_memories 表

手动记忆功能已被自动记忆提取（MongoDB）取代。
manual_memories 表不再使用。

Revision ID: 002
Revises: 001
Create Date: 2026-02-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_manual_memories_importance", table_name="manual_memories")
    op.drop_index("idx_manual_memories_created_at", table_name="manual_memories")
    op.drop_index("idx_manual_memories_status", table_name="manual_memories")
    op.drop_index("idx_manual_memories_user_id", table_name="manual_memories")
    op.drop_table("manual_memories")


def downgrade() -> None:
    op.create_table(
        "manual_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "memory_type",
            sa.String(50),
            server_default="'general'",
            nullable=False,
        ),
        sa.Column(
            "importance_score",
            sa.Integer(),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(100),
            server_default="'user_instruction'",
            nullable=False,
        ),
        sa.Column("source_message_id", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="'active'",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "importance_score BETWEEN 1 AND 10",
            name="check_importance_score",
        ),
    )
    op.create_index("idx_manual_memories_user_id", "manual_memories", ["user_id"])
    op.create_index("idx_manual_memories_status", "manual_memories", ["status"])
    op.create_index(
        "idx_manual_memories_created_at", "manual_memories", ["created_at"]
    )
    op.create_index(
        "idx_manual_memories_importance", "manual_memories", ["importance_score"]
    )
