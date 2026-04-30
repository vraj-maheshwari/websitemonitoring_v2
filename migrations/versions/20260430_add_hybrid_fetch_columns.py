"""Add render_mode, used_fallback, fallback_reason to seo_logs

Revision ID: 20260430_add_hybrid_fetch_columns
Revises: 20260430_add_incident_rca_and_security
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260430_add_hybrid_fetch_columns"
down_revision = "20260430_add_incident_rca_and_security"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.add_column(sa.Column("render_mode",     sa.String(32), nullable=True,  server_default="HTTP"))
        batch_op.add_column(sa.Column("used_fallback",   sa.Boolean(),  nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("fallback_reason", sa.Text(),     nullable=True))


def downgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.drop_column("fallback_reason")
        batch_op.drop_column("used_fallback")
        batch_op.drop_column("render_mode")
