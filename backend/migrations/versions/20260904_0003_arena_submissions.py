"""Persist Arena challenge submissions.

Revision ID: 20260904_0003
Revises: 20260904_0002
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260904_0003"
down_revision = "20260904_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "arena_submissions" not in inspector.get_table_names():
        op.create_table(
            "arena_submissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("challenge_id", sa.String(40), nullable=False),
            sa.Column("test_run_id", sa.String(36), sa.ForeignKey("test_runs.id"), nullable=False),
            sa.Column("score", sa.JSON(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "challenge_id", "test_run_id", name="uq_arena_submission_attempt"),
        )
        op.create_index("ix_arena_submissions_user_id", "arena_submissions", ["user_id"])
        op.create_index("ix_arena_submissions_challenge_id", "arena_submissions", ["challenge_id"])


def downgrade() -> None:
    op.drop_table("arena_submissions")
