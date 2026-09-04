"""Initial ARES core security domain.

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04
"""
from alembic import op

from app import models  # noqa: F401
from app.database import Base

revision = "20260904_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
