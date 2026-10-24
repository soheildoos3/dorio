"""warranty lifecycle, product warranty duration and scan defaults

Revision ID: e8a1b2c3d4e5
Revises: c41d9e8a7b22
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "c41d9e8a7b22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("warranty_months", sa.Integer(), server_default="12", nullable=False))
    op.add_column("warranty_settings", sa.Column("grace_period_months", sa.Integer(), server_default="6", nullable=False))

    op.add_column("warranties", sa.Column("warranty_months", sa.Integer(), server_default="12", nullable=False))
    op.add_column("warranties", sa.Column("outbound_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("warranties", sa.Column("auto_activate_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("warranties", sa.Column("activation_source", sa.String(length=20), nullable=True))
    op.create_index("ix_warranties_outbound_at", "warranties", ["outbound_at"])
    op.create_index("ix_warranties_auto_activate_at", "warranties", ["auto_activate_at"])
    op.create_index("ix_warranties_expires_at", "warranties", ["expires_at"])

    # Existing warranties inherit the product-level duration when it can be resolved.
    op.execute("""
        UPDATE warranties w
        SET warranty_months = p.warranty_months
        FROM product_items i
        JOIN product_variants v ON v.id = i.variant_id
        JOIN products p ON p.id = v.product_id
        WHERE w.item_id = i.id
    """)

    # Legacy active warranties sometimes had no expiry. Give them the product duration.
    op.execute("""
        UPDATE warranties
        SET expires_at = activated_at + make_interval(months => warranty_months)
        WHERE activated_at IS NOT NULL AND expires_at IS NULL AND status <> 'void'
    """)

    # Every serialized physical item must have a warranty row from the moment it is created.
    # Sold items start in the post-outbound grace window; warehouse items stay inactive.
    op.execute("""
        INSERT INTO warranties(
            item_id, serial, status, warranty_months,
            outbound_at, auto_activate_at, created_at
        )
        SELECT
            i.id,
            i.warranty_serial,
            CASE WHEN i.status::text = 'sold' THEN 'grace' ELSE 'inactive' END,
            p.warranty_months,
            CASE WHEN i.status::text = 'sold' THEN COALESCE(i.sold_at, i.moved_out_at, i.created_at, now()) ELSE NULL END,
            CASE WHEN i.status::text = 'sold' THEN COALESCE(i.sold_at, i.moved_out_at, i.created_at, now()) + make_interval(months => 6) ELSE NULL END,
            COALESCE(i.created_at, now())
        FROM product_items i
        JOIN product_variants v ON v.id = i.variant_id
        JOIN products p ON p.id = v.product_id
        LEFT JOIN warranties w ON w.item_id = i.id
        WHERE i.warranty_serial IS NOT NULL AND w.id IS NULL
    """)

    # Upgrade only the old development defaults. Never overwrite a custom domain/LAN URL.
    op.execute("""
        UPDATE warranty_settings
        SET base_url = 'http://127.0.0.1:5174/warranty'
        WHERE base_url IN ('http://127.0.0.1:8000/warranty', 'http://localhost:8000/warranty')
    """)

    # A usable default QR destination for the standalone React warranty app.
    op.execute("""
        INSERT INTO warranty_settings(name, base_url, grace_period_months, is_default)
        SELECT 'صفحه گارانتی', 'http://127.0.0.1:5174/warranty', 6, true
        WHERE NOT EXISTS (SELECT 1 FROM warranty_settings)
    """)


def downgrade() -> None:
    op.drop_index("ix_warranties_expires_at", table_name="warranties")
    op.drop_index("ix_warranties_auto_activate_at", table_name="warranties")
    op.drop_index("ix_warranties_outbound_at", table_name="warranties")
    op.drop_column("warranties", "activation_source")
    op.drop_column("warranties", "auto_activate_at")
    op.drop_column("warranties", "outbound_at")
    op.drop_column("warranties", "warranty_months")
    op.drop_column("warranty_settings", "grace_period_months")
    op.drop_column("products", "warranty_months")
