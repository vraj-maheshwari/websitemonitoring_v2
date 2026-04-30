"""Add incident RCA/timeline columns and SEOLog security columns

Revision ID: 20260430_add_incident_rca_and_security
Revises: 20260430_add_cwv_tech_broken_links
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = "20260430_add_incident_rca_and_security"
down_revision = "20260430_add_cwv_tech_broken_links"
branch_labels = None
depends_on = None


def upgrade():
    # Incident: root cause analysis + timeline
    with op.batch_alter_table("incidents") as batch_op:
        batch_op.add_column(sa.Column("root_cause", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("timeline",   sa.JSON(),     nullable=True))

    # SEOLog: security audit results
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.add_column(sa.Column("security_score",   sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("security_headers", sa.JSON(),    nullable=True))
        batch_op.add_column(sa.Column("security_issues",  sa.JSON(),    nullable=True))
        batch_op.add_column(sa.Column("malware_flags",    sa.JSON(),    nullable=True))


def downgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.drop_column("malware_flags")
        batch_op.drop_column("security_issues")
        batch_op.drop_column("security_headers")
        batch_op.drop_column("security_score")

    with op.batch_alter_table("incidents") as batch_op:
        batch_op.drop_column("timeline")
        batch_op.drop_column("root_cause")
