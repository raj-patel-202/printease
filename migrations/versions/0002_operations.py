"""Admin audit trail, account suspension and case-insensitive identities."""

from alembic import op
import sqlalchemy as sa

revision = "0002_operations"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    # Unique index creation deliberately fails if legacy identities differ only by case.
    # Resolve those accounts with an operator before retrying; never silently merge them.
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_index("uq_admins_email_lower", "admins", [sa.text("lower(email)")], unique=True)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_id", sa.Integer()),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("actor_id", "action", "created_at"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_index("uq_admins_email_lower", table_name="admins")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_column("users", "is_active")
