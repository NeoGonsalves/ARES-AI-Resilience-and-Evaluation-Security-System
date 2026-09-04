"""Add short-lived encrypted execution payloads.

Revision ID: 20260904_0002
Revises: 20260904_0001
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260904_0002"
down_revision = "20260904_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("test_runs")}
    if "encrypted_execution_payload" not in existing:
        op.add_column("test_runs", sa.Column("encrypted_execution_payload", sa.Text(), nullable=True))
    if "payload_expires_at" not in existing:
        op.add_column("test_runs", sa.Column("payload_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("test_runs")}
    if "payload_expires_at" in existing:
        op.drop_column("test_runs", "payload_expires_at")
    if "encrypted_execution_payload" in existing:
        op.drop_column("test_runs", "encrypted_execution_payload")
