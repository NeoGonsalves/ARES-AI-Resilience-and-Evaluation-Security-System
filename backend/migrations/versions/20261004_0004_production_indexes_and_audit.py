"""Production database indexes and audit logging table.

Revision ID: 20261004_0004
Revises: 20260904_0003
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0004"
down_revision = "20260904_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # 1. Composite indexes for high-throughput query patterns
    if "test_runs" in existing_tables:
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("test_runs")}
        if "ix_test_runs_project_status" not in existing_indexes:
            op.create_index("ix_test_runs_project_status", "test_runs", ["project_id", "status"])
        if "ix_test_runs_org_created" not in existing_indexes:
            op.create_index("ix_test_runs_org_created", "test_runs", ["organization_id", "created_at"])

    if "findings" in existing_tables:
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("findings")}
        if "ix_findings_test_severity" not in existing_indexes:
            op.create_index("ix_findings_test_severity", "findings", ["test_run_id", "severity"])
        if "ix_findings_category_risk" not in existing_indexes:
            op.create_index("ix_findings_category_risk", "findings", ["category", "risk_score"])

    if "evidence" in existing_tables:
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("evidence")}
        if "ix_evidence_test_sim" not in existing_indexes:
            op.create_index("ix_evidence_test_sim", "evidence", ["test_run_id", "similarity"])

    # 2. Production Audit Log Table
    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), nullable=True),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("action", sa.String(80), nullable=False, index=True),
            sa.Column("resource_type", sa.String(50), nullable=False, index=True),
            sa.Column("resource_id", sa.String(80), nullable=False, index=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        )
        op.create_index("ix_audit_logs_org_timestamp", "audit_logs", ["organization_id", "timestamp"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "audit_logs" in existing_tables:
        op.drop_table("audit_logs")

    if "evidence" in existing_tables:
        op.drop_index("ix_evidence_test_sim", table_name="evidence")

    if "findings" in existing_tables:
        op.drop_index("ix_findings_category_risk", table_name="findings")
        op.drop_index("ix_findings_test_severity", table_name="findings")

    if "test_runs" in existing_tables:
        op.drop_index("ix_test_runs_org_created", table_name="test_runs")
        op.drop_index("ix_test_runs_project_status", table_name="test_runs")
