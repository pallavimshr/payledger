"""Create ledger tables: accounts, journal_entries, postings.

Revision ID: 0001
Revises:
Create Date: 2026-11-27
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('asset','liability','equity','revenue','expense')", name="ck_account_type"
        ),
    )
    op.create_index("ix_accounts_code", "accounts", ["code"], unique=True)

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "postings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("direction", sa.String(6), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount_paise > 0", name="ck_posting_amount_positive"),
        sa.CheckConstraint("direction IN ('debit','credit')", name="ck_posting_direction"),
    )
    op.create_index("ix_postings_entry_id", "postings", ["entry_id"])
    op.create_index("ix_postings_account_id", "postings", ["account_id"])


def downgrade() -> None:
    op.drop_table("postings")
    op.drop_table("journal_entries")
    op.drop_table("accounts")
