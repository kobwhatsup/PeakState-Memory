"""创建记忆系统核心表: user_profiles 和 manual_memories

Revision ID: 001
Revises: None
Create Date: 2026-02-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── user_profiles 表 ──────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # 基本信息
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("age_range", sa.String(20), nullable=True),
        sa.Column("occupation", sa.String(200), nullable=True),
        sa.Column("family_role", postgresql.ARRAY(sa.String()), nullable=True),
        # JSONB 字段
        sa.Column(
            "core_goals",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column(
            "core_values",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column(
            "health_info",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column(
            "important_dates",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=True,
        ),
        sa.Column(
            "preferences",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        # 元数据
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
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        # 约束
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )
    op.create_index("idx_user_profiles_user_id", "user_profiles", ["user_id"])

    # ── manual_memories 表 ────────────────────────────────
    op.create_table(
        "manual_memories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # 记忆内容
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
        # 来源
        sa.Column(
            "source",
            sa.String(100),
            server_default="'user_instruction'",
            nullable=False,
        ),
        sa.Column("source_message_id", sa.String(100), nullable=True),
        # 状态
        sa.Column(
            "status",
            sa.String(20),
            server_default="'active'",
            nullable=False,
        ),
        # 元数据
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
        # 约束
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


def downgrade() -> None:
    op.drop_table("manual_memories")
    op.drop_table("user_profiles")
