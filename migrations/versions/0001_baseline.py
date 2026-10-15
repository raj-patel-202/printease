"""Original schema baseline. Existing installations must verify before stamping."""

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(120), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(120), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(200), nullable=False),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("copies", sa.Integer(), nullable=False),
        sa.Column("orientation", sa.String(20), nullable=False),
        sa.Column("side_mode", sa.String(20), nullable=False),
        sa.Column("paper_size", sa.String(16), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("color_mode", sa.String(20), nullable=False),
        sa.Column("total_cost", sa.Integer(), nullable=False),
        sa.Column("date_ordered", sa.DateTime(timezone=True), nullable=False),
        sa.Column("print_status", sa.String(20), nullable=False),
    )
    for column in ("user_id", "date_ordered", "print_status"):
        op.create_index(f"ix_orders_{column}", "orders", [column])
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True
        ),
        sa.Column("payment_status", sa.String(20), nullable=False),
        sa.Column("receipt_token", sa.String(255), nullable=False, unique=True),
        sa.Column("razorpay_payment_id", sa.String(100), unique=True),
        sa.Column("razorpay_order_id", sa.String(100), unique=True),
        sa.Column("payment_datetime", sa.DateTime(timezone=True)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("refund_id", sa.String(100), unique=True),
        sa.Column("refund_status", sa.String(20)),
        sa.Column("refund_idempotency_key", sa.String(255), unique=True),
    )
    for column in ("payment_status", "payment_datetime"):
        op.create_index(f"ix_payments_{column}", "payments", [column])
    op.create_table(
        "razorpay_webhook_events",
        sa.Column("event_id", sa.String(100), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_razorpay_webhook_events_status", "razorpay_webhook_events", ["status"])


def downgrade():
    for table in ("razorpay_webhook_events", "payments", "orders", "admins", "users"):
        op.drop_table(table)
