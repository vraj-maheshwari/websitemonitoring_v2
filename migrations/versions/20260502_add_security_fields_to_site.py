"""Add security fields to site

Revision ID: 20260502_add_security_fields_to_site
Revises: 20260501_add_playwright_cwv_columns
Create Date: 2026-05-02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260502_add_security_fields_to_site"
down_revision = "20260501_add_playwright_cwv_columns"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(sa.Column("security_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("security_grade", sa.String(2), nullable=True))
        batch_op.add_column(sa.Column("security_last_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("security_check_interval", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("last_security_check_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("next_security_check_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("security_status", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("security_started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("security_started_at")
        batch_op.drop_column("security_status")
        batch_op.drop_column("next_security_check_at")
        batch_op.drop_column("last_security_check_at")
        batch_op.drop_column("security_check_interval")
        batch_op.drop_column("security_last_error")
        batch_op.drop_column("security_grade")
        batch_op.drop_column("security_score")