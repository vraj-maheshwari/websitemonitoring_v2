"""Add CWV estimates, tech profiler, and broken link columns to seo_logs

Revision ID: 20260430_add_cwv_tech_broken_links
Revises: 20260430_add_seo_fetch_validation_fields
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260430_add_cwv_tech_broken_links"
down_revision = "20260430_add_seo_fetch_validation_fields"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        # Core Web Vitals proxy estimates
        batch_op.add_column(sa.Column("cwv_lcp_estimate_s",  sa.Float(),   nullable=True))
        batch_op.add_column(sa.Column("cwv_lcp_rating",      sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("cwv_fid_estimate_ms", sa.Float(),   nullable=True))
        batch_op.add_column(sa.Column("cwv_fid_rating",      sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("cwv_cls_estimate",    sa.Float(),   nullable=True))
        batch_op.add_column(sa.Column("cwv_cls_rating",      sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("cwv_data",            sa.JSON(),    nullable=True))
        # Technology profiler
        batch_op.add_column(sa.Column("tech_stack",          sa.JSON(),    nullable=True))
        batch_op.add_column(sa.Column("tech_flat",           sa.JSON(),    nullable=True))
        batch_op.add_column(sa.Column("tech_diff",           sa.JSON(),    nullable=True))
        # Broken link checker
        batch_op.add_column(sa.Column("broken_links",        sa.JSON(),    nullable=True))
        batch_op.add_column(sa.Column("broken_link_count",   sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("links_checked",       sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.drop_column("links_checked")
        batch_op.drop_column("broken_link_count")
        batch_op.drop_column("broken_links")
        batch_op.drop_column("tech_diff")
        batch_op.drop_column("tech_flat")
        batch_op.drop_column("tech_stack")
        batch_op.drop_column("cwv_data")
        batch_op.drop_column("cwv_cls_rating")
        batch_op.drop_column("cwv_cls_estimate")
        batch_op.drop_column("cwv_fid_rating")
        batch_op.drop_column("cwv_fid_estimate_ms")
        batch_op.drop_column("cwv_lcp_rating")
        batch_op.drop_column("cwv_lcp_estimate_s")
