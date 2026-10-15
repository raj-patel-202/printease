"""Record captured provider amounts in minor units for accurate refund reconciliation."""

from alembic import op
import sqlalchemy as sa

revision = "0004_captured_amount"
down_revision = "0003_session_revocation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("captured_amount", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("payments", "captured_amount")
