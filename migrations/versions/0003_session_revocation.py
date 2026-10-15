"""Persistent session revocation without an additional session store."""

from alembic import op
import sqlalchemy as sa

revision = "0003_session_revocation"
down_revision = "0002_operations"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("users", "admins"):
        op.add_column(table, sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    for table in ("users", "admins"):
        op.drop_column(table, "token_version")
