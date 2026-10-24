"""link tailor work to production orders and add dynamic QR routing settings

Revision ID: aa91d4e7c612
Revises: f4a9d31e7c20
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "aa91d4e7c612"
down_revision: Union[str, Sequence[str], None] = "f4a9d31e7c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tailor_works", sa.Column("production_order_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_tailor_works_production_order_id",
        "tailor_works",
        "production_orders",
        ["production_order_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tailor_works_production_order_id", "tailor_works", ["production_order_id"], unique=True)

    # If an older installation already created a manual tailor-work using the
    # production order number, link that exact same-tailor row instead of creating
    # a duplicate. Its existing counters/history are preserved.
    op.execute(sa.text("""
        UPDATE tailor_works AS tw
        SET production_order_id = po.id
        FROM production_orders AS po
        WHERE tw.production_order_id IS NULL
          AND tw.work_no = po.order_no
          AND tw.tailor_user_id = po.tailor_user_id
          AND po.tailor_user_id IS NOT NULL
    """))

    # Backfill every remaining production order with an assigned tailor so old
    # orders immediately appear in the tailor work queue after the migration.
    op.execute(sa.text("""
        INSERT INTO tailor_works (
            tailor_user_id, work_no, product_id, production_order_id, quantity,
            delivered_good, returned_for_fix, damaged, assigned_at, due_at,
            completed_at, status, notes
        )
        SELECT
            po.tailor_user_id,
            CASE
                WHEN EXISTS (SELECT 1 FROM tailor_works occupied WHERE occupied.work_no = po.order_no)
                    THEN LEFT('SYS-PO-' || po.id::text || '-' || md5(po.order_no || ':' || po.id::text), 50)
                ELSE po.order_no
            END,
            po.product_id,
            po.id,
            po.quantity,
            CASE
                WHEN po.status = 'completed' THEN po.quantity
                ELSE LEAST(po.quantity, GREATEST(COALESCE(po.prepared_units, 0), COALESCE(po.qc_passed, 0)))
            END,
            0,
            0,
            COALESCE(CAST(po.created_at AS date), CURRENT_DATE),
            po.due_at,
            CASE WHEN po.status = 'completed' THEN COALESCE(CAST(po.completed_at AS date), CURRENT_DATE) ELSE NULL END,
            CASE
                WHEN po.status = 'completed' THEN 'completed'
                WHEN po.status = 'cancelled' THEN 'cancelled'
                ELSE 'open'
            END,
            po.notes
        FROM production_orders po
        WHERE po.tailor_user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM tailor_works tw WHERE tw.production_order_id = po.id
          )
    """))

    op.add_column("warranty_settings", sa.Column("qr_base_url", sa.String(length=500), nullable=True))
    op.add_column("warranty_settings", sa.Column("qr_destination_template", sa.String(length=1000), nullable=True))
    op.add_column("warranties", sa.Column("qr_redirect_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("warranties", "qr_redirect_url")
    op.drop_column("warranty_settings", "qr_destination_template")
    op.drop_column("warranty_settings", "qr_base_url")
    op.drop_index("ix_tailor_works_production_order_id", table_name="tailor_works")
    op.drop_constraint("fk_tailor_works_production_order_id", "tailor_works", type_="foreignkey")
    op.drop_column("tailor_works", "production_order_id")
