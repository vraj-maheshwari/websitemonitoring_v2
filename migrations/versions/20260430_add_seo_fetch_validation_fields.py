"""add seo fetch validation fields"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260430_add_seo_fetch_validation_fields"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.add_column(sa.Column("fetch_valid", sa.Boolean(), server_default=sa.true()))
        batch_op.add_column(sa.Column("fetch_html_preview", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("fetch_page_size_kb", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("fetch_status", sa.String(length=20), server_default="ok"))
        batch_op.add_column(sa.Column("invalidation_reason", sa.Text(), nullable=True))
        batch_op.alter_column("score", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("sites") as batch_op:
        batch_op.add_column(sa.Column("last_seo_fetch_valid", sa.Boolean(), server_default=sa.true()))
        batch_op.add_column(sa.Column("last_downtime_ended_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("sites") as batch_op:
        batch_op.drop_column("last_downtime_ended_at")
        batch_op.drop_column("last_seo_fetch_valid")

    with op.batch_alter_table("seo_logs") as batch_op:
        batch_op.alter_column("score", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("invalidation_reason")
        batch_op.drop_column("fetch_status")
        batch_op.drop_column("fetch_page_size_kb")
        batch_op.drop_column("fetch_html_preview")
        batch_op.drop_column("fetch_valid")
