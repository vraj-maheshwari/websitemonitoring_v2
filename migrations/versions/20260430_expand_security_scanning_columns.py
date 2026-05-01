"""Expand security scanning columns in seo_logs

Revision ID: 20260430_expand_security_scanning_columns
Revises: 20260430_add_hybrid_fetch_columns
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260430_expand_security_scanning_columns"
down_revision = "20260430_add_hybrid_fetch_columns"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.add_column(sa.Column("security_grade",       sa.String(2),  nullable=True))
        batch_op.add_column(sa.Column("security_categories",  sa.JSON(),     nullable=True))
        batch_op.add_column(sa.Column("cors_issues",          sa.JSON(),     nullable=True))
        batch_op.add_column(sa.Column("csp_issues",           sa.JSON(),     nullable=True))
        batch_op.add_column(sa.Column("mixed_content_detail", sa.JSON(),     nullable=True))


def downgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.drop_column("mixed_content_detail")
        batch_op.drop_column("csp_issues")
        batch_op.drop_column("cors_issues")
        batch_op.drop_column("security_categories")
        batch_op.drop_column("security_grade")
