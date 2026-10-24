"""channel pricing, sales snapshots and permission defaults

Revision ID: c41d9e8a7b22
Revises: 7b478d243b18
Create Date: 2026-10-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c41d9e8a7b22"
down_revision: Union[str, Sequence[str], None] = "7b478d243b18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_channel_prices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("list_price", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("discount_type", sa.String(20), nullable=True),
        sa.Column("discount_value", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["sales_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("variant_id", "channel_id", name="uq_product_channel_price_variant_channel"),
    )
    op.create_index("ix_product_channel_prices_variant_id", "product_channel_prices", ["variant_id"])
    op.create_index("ix_product_channel_prices_channel_id", "product_channel_prices", ["channel_id"])
    op.create_index("ix_product_channel_prices_is_active", "product_channel_prices", ["is_active"])

    op.add_column("stock_movements", sa.Column("unit_list_price", sa.Numeric(15, 2), nullable=True))
    op.add_column("stock_movements", sa.Column("unit_sale_price", sa.Numeric(15, 2), nullable=True))
    op.add_column("stock_movements", sa.Column("discount_total", sa.Numeric(15, 2), nullable=True))
    op.add_column("stock_movements", sa.Column("line_total", sa.Numeric(15, 2), nullable=True))
    op.create_index("ix_stock_movements_line_total", "stock_movements", ["line_total"])

    # Add new permissions without disturbing customized existing roles.
    op.execute("""
        INSERT INTO permissions(code, name, description) VALUES
          ('dashboard.view', 'مشاهده داشبورد مدیریتی', NULL),
          ('pricing.view', 'مشاهده قیمت‌های پلتفرمی', NULL),
          ('pricing.manage', 'مدیریت قیمت و تخفیف پلتفرم‌ها', NULL),
          ('sales.view', 'مشاهده گزارش فروش', NULL)
        ON CONFLICT (code) DO NOTHING
    """)

    # Existing admin gets all new permissions.
    op.execute("""
        INSERT INTO role_permissions(role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code = 'admin' AND p.code IN ('dashboard.view','pricing.view','pricing.manage','sales.view')
        ON CONFLICT DO NOTHING
    """)
    # Sensible defaults for existing built-in roles; individual overrides remain untouched.
    role_defaults = {
        "manager": ["dashboard.view", "pricing.view", "sales.view"],
        "warehouse_manager": ["dashboard.view", "pricing.view", "sales.view"],
        "warehouse_operator": ["dashboard.view", "pricing.view"],
        "qc_operator": ["dashboard.view"],
        "production_manager": ["dashboard.view"],
        "hr_manager": ["dashboard.view"],
        "sales_operator": ["dashboard.view", "pricing.view", "sales.view"],
        "warranty_manager": ["dashboard.view"],
        "viewer": ["dashboard.view"],
    }
    for role_code, perms in role_defaults.items():
        codes = ",".join(f"'{x}'" for x in perms)
        op.execute(f"""
            INSERT INTO role_permissions(role_id, permission_id)
            SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
            WHERE r.code = '{role_code}' AND p.code IN ({codes})
            ON CONFLICT DO NOTHING
        """)

    # Tailor must only see own tailor workspace by default; remove legacy catalog access.
    op.execute("""
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id=r.id AND rp.permission_id=p.id AND r.code='tailor' AND p.code='catalog.view'
    """)

    # Add a sales manager template if it does not exist.
    op.execute("""
        INSERT INTO roles(code, name, is_system)
        VALUES ('sales_manager', 'مدیر فروش', true)
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions(role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.code='sales_manager' AND p.code IN (
          'dashboard.view','catalog.view','inventory.view','inventory.outbound',
          'pricing.view','pricing.manage','sales.view','channels.manage','warranty.view'
        ) ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_stock_movements_line_total", table_name="stock_movements")
    op.drop_column("stock_movements", "line_total")
    op.drop_column("stock_movements", "discount_total")
    op.drop_column("stock_movements", "unit_sale_price")
    op.drop_column("stock_movements", "unit_list_price")
    op.drop_index("ix_product_channel_prices_is_active", table_name="product_channel_prices")
    op.drop_index("ix_product_channel_prices_channel_id", table_name="product_channel_prices")
    op.drop_index("ix_product_channel_prices_variant_id", table_name="product_channel_prices")
    op.drop_table("product_channel_prices")
