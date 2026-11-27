"""Create reconciliation_runs and reconciliation_items.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

JSON_T = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("rows_in_report", sa.Integer(), nullable=False),
        sa.Column("ai_model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reconciliation_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("reconciliation_runs.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("report_amount_paise", sa.BigInteger(), nullable=True),
        sa.Column("ledger_amount_paise", sa.BigInteger(), nullable=True),
        sa.Column("report_fee_paise", sa.BigInteger(), nullable=True),
        sa.Column("ledger_fee_paise", sa.BigInteger(), nullable=True),
        sa.Column("report_row", JSON_T, nullable=True),
        sa.Column("journal_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("ai_cause", sa.String(50), nullable=True),
        sa.Column("ai_confidence", sa.String(10), nullable=True),
        sa.Column("ai_suggestion", JSON_T, nullable=True),
        sa.Column("ai_error", sa.Text(), nullable=True),
        sa.Column("resolution", sa.String(20), nullable=False),
        sa.Column("resolved_entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=True),
    )
    op.create_index("ix_reconciliation_items_run_id", "reconciliation_items", ["run_id"])
    op.create_index("ix_reconciliation_items_entity_id", "reconciliation_items", ["entity_id"])
    op.create_index("ix_reconciliation_items_status", "reconciliation_items", ["status"])


def downgrade() -> None:
    op.drop_table("reconciliation_items")
    op.drop_table("reconciliation_runs")
