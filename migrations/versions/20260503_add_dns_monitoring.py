"""Add DNS monitoring

Revision ID: 20260503_add_dns_monitoring
Revises: 20260502_add_security_fields_to_site
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = "20260503_add_dns_monitoring"
down_revision = "20260502_add_security_fields_to_site"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "dns_logs" not in inspector.get_table_names():
        op.create_table(
            "dns_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
            sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved", sa.Boolean(), nullable=True),
            sa.Column("resolution_time_ms", sa.Float(), nullable=True),
            sa.Column("ip_addresses", sa.JSON(), nullable=True),
            sa.Column("nameservers", sa.JSON(), nullable=True),
            sa.Column("mx_records", sa.JSON(), nullable=True),
            sa.Column("hijack_suspected", sa.Boolean(), nullable=True),
            sa.Column("new_ips", sa.JSON(), nullable=True),
            sa.Column("removed_ips", sa.JSON(), nullable=True),
            sa.Column("ns_changed", sa.Boolean(), nullable=True),
            sa.Column("added_ns", sa.JSON(), nullable=True),
            sa.Column("removed_ns", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    existing_site_columns = {column["name"] for column in inspector.get_columns("sites")}
    with op.batch_alter_table("sites") as batch_op:
        if "dns_resolved" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_resolved", sa.Boolean(), nullable=True))
        if "dns_resolution_time_ms" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_resolution_time_ms", sa.Float(), nullable=True))
        if "dns_last_ips" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_last_ips", sa.JSON(), nullable=True))
        if "dns_last_ns" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_last_ns", sa.JSON(), nullable=True))
        if "dns_hijack_suspected" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_hijack_suspected", sa.Boolean(), nullable=True))
        if "dns_ns_changed" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_ns_changed", sa.Boolean(), nullable=True))
        if "dns_last_error" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_last_error", sa.String(500), nullable=True))
        if "dns_status" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_status", sa.String(32), nullable=True))
        if "dns_started_at" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_started_at", sa.DateTime(timezone=True), nullable=True))
        if "last_dns_check_at" not in existing_site_columns:
            batch_op.add_column(sa.Column("last_dns_check_at", sa.DateTime(timezone=True), nullable=True))
        if "next_dns_check_at" not in existing_site_columns:
            batch_op.add_column(sa.Column("next_dns_check_at", sa.DateTime(timezone=True), nullable=True))
        if "dns_check_interval" not in existing_site_columns:
            batch_op.add_column(sa.Column("dns_check_interval", sa.Integer(), nullable=True))

    op.execute("UPDATE sites SET dns_status = 'pending' WHERE dns_status IS NULL")
    op.execute("UPDATE sites SET dns_check_interval = 3600 WHERE dns_check_interval IS NULL")
    op.execute("UPDATE sites SET next_dns_check_at = CURRENT_TIMESTAMP WHERE next_dns_check_at IS NULL")


def downgrade():
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("dns_check_interval")
        batch_op.drop_column("next_dns_check_at")
        batch_op.drop_column("last_dns_check_at")
        batch_op.drop_column("dns_started_at")
        batch_op.drop_column("dns_status")
        batch_op.drop_column("dns_last_error")
        batch_op.drop_column("dns_ns_changed")
        batch_op.drop_column("dns_hijack_suspected")
        batch_op.drop_column("dns_last_ns")
        batch_op.drop_column("dns_last_ips")
        batch_op.drop_column("dns_resolution_time_ms")
        batch_op.drop_column("dns_resolved")

    op.drop_table("dns_logs")
