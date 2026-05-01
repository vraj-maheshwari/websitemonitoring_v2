"""Add Playwright Core Web Vitals columns

Revision ID: 20260501_add_playwright_cwv_columns
Revises: 20260430_expand_security_scanning_columns
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260501_add_playwright_cwv_columns"
down_revision = "20260430_expand_security_scanning_columns"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.add_column(sa.Column("lh_lcp_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_fcp_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_tbt_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_cls", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_ttfb_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_tti_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_si_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_page_load_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_performance_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lh_lcp_rating", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("lh_fcp_rating", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("lh_tbt_rating", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("lh_cls_rating", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("lh_ttfb_rating", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("lh_audit_method", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("lh_audited_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("lh_error", sa.Text(), nullable=True))

    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(sa.Column("lh_performance_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lh_lcp_ms", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lh_cls", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("lh_cls")
        batch_op.drop_column("lh_lcp_ms")
        batch_op.drop_column("lh_performance_score")

    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.drop_column("lh_error")
        batch_op.drop_column("lh_audited_at")
        batch_op.drop_column("lh_audit_method")
        batch_op.drop_column("lh_ttfb_rating")
        batch_op.drop_column("lh_cls_rating")
        batch_op.drop_column("lh_tbt_rating")
        batch_op.drop_column("lh_fcp_rating")
        batch_op.drop_column("lh_lcp_rating")
        batch_op.drop_column("lh_performance_score")
        batch_op.drop_column("lh_page_load_ms")
        batch_op.drop_column("lh_si_ms")
        batch_op.drop_column("lh_tti_ms")
        batch_op.drop_column("lh_ttfb_ms")
        batch_op.drop_column("lh_cls")
        batch_op.drop_column("lh_tbt_ms")
        batch_op.drop_column("lh_fcp_ms")
        batch_op.drop_column("lh_lcp_ms")
