"""enterprise accounting, manufacturing, costing and audit foundation

Revision ID: f4a9d31e7c20
Revises: b7d2f6a9c301
Create Date: 2026-10-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f4a9d31e7c20"
down_revision: Union[str, Sequence[str], None] = "b7d2f6a9c301"
branch_labels = None
depends_on = None


def _ix(table: str, column: str) -> None:
    op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    # ---- Accounting master data ----
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("allow_posting", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    _ix("accounts", "code"); _ix("accounts", "account_type"); _ix("accounts", "parent_id"); _ix("accounts", "is_active")

    op.create_table(
        "cost_centers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("center_type", sa.String(30), server_default="other", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("code"),
    )
    _ix("cost_centers", "code")

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("source_ref", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), server_default="posted", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("posted_by", sa.BigInteger(), nullable=True),
        sa.Column("reversed_by_entry_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("number"), sa.UniqueConstraint("reversed_by_entry_id"),
    )
    for c in ("number","entry_date","source_type","source_id","source_ref","status","created_by","posted_by","created_at"):_ix("journal_entries",c)

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.BigInteger(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("cost_center_id", sa.BigInteger(), nullable=True),
        sa.Column("debit", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("credit", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("memo", sa.String(255), nullable=True),
        sa.CheckConstraint("debit >= 0", name="ck_journal_lines_debit_nonnegative"),
        sa.CheckConstraint("credit >= 0", name="ck_journal_lines_credit_nonnegative"),
        sa.CheckConstraint("(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)", name="ck_journal_lines_one_side"),
        sa.ForeignKeyConstraint(["entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cost_center_id"], ["cost_centers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for c in ("entry_id","account_id","cost_center_id"):_ix("journal_lines",c)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=True),
        sa.Column("source_ref", sa.String(100), nullable=True),
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for c in ("user_id","action","entity_type","entity_id","source_ref","created_at"):_ix("audit_events",c)

    # ---- Manufacturing master/subledger ----
    op.create_table(
        "materials",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("reorder_point", sa.Numeric(18,4), server_default="0", nullable=False),
        sa.Column("weighted_average_cost", sa.Numeric(18,4), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("code"),
    )
    for c in ("code","name","category","is_active"):_ix("materials",c)

    op.create_table(
        "material_stock",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("material_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(18,4), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_material_stock_nonnegative"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("material_id","location_id", name="uq_material_stock_material_location"),
    )
    _ix("material_stock","material_id"); _ix("material_stock","location_id")

    op.create_table(
        "boms",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("product_id","version",name="uq_bom_product_version"),
    )
    _ix("boms","product_id"); _ix("boms","status")

    op.create_table(
        "bom_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("bom_id", sa.BigInteger(), nullable=False),
        sa.Column("material_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(18,4), nullable=False),
        sa.Column("normal_waste_percent", sa.Numeric(8,4), server_default="0", nullable=False),
        sa.CheckConstraint("quantity_per_unit > 0", name="ck_bom_item_qty_positive"),
        sa.CheckConstraint("normal_waste_percent >= 0", name="ck_bom_item_waste_nonnegative"),
        sa.ForeignKeyConstraint(["bom_id"], ["boms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("bom_id","material_id",name="uq_bom_item_material"),
    )
    _ix("bom_items","bom_id"); _ix("bom_items","material_id")

    op.create_table(
        "production_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_no", sa.String(50), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("tailor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("bom_id", sa.BigInteger(), nullable=False),
        sa.Column("fg_location_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("material_cost", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("labor_cost", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("overhead_cost", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("abnormal_scrap_cost", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("total_cost_snapshot", sa.Numeric(18,2), nullable=True),
        sa.Column("unit_cost_snapshot", sa.Numeric(18,4), nullable=True),
        sa.Column("prepared_units", sa.Integer(), server_default="0", nullable=False),
        sa.Column("qc_passed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("qc_failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_production_order_quantity_positive"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tailor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bom_id"], ["boms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fg_location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("order_no"),
    )
    for c in ("order_no","product_id","variant_id","tailor_user_id","bom_id","fg_location_id","status","due_at"):_ix("production_orders",c)

    op.create_table(
        "material_movements",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("material_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Numeric(18,4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18,4), nullable=False),
        sa.Column("total_cost", sa.Numeric(18,2), nullable=False),
        sa.Column("production_order_id", sa.BigInteger(), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_ref", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_material_movement_quantity_positive"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("number"),
    )
    for c in ("number","material_id","location_id","movement_type","production_order_id","reference_type","reference_ref","created_by","created_at"):_ix("material_movements",c)

    op.create_table(
        "labor_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("production_order_id", sa.BigInteger(), nullable=False),
        sa.Column("tailor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(10,2), server_default="0", nullable=False),
        sa.Column("pieces", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rate", sa.Numeric(18,2), nullable=False),
        sa.Column("rate_basis", sa.String(20), server_default="piece", nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_labor_amount_nonnegative"),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tailor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for c in ("production_order_id","tailor_user_id","work_date","status","approved_by"):_ix("labor_entries",c)

    op.create_table(
        "overhead_rates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("basis", sa.String(30), nullable=False),
        sa.Column("rate", sa.Numeric(18,4), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _ix("overhead_rates","is_active")

    # ---- Formal sales invoices / returns ----
    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("customer_name", sa.String(150), nullable=True),
        sa.Column("customer_phone", sa.String(30), nullable=True),
        sa.Column("external_reference", sa.String(100), nullable=True),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("total_amount", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_by", sa.BigInteger(), nullable=True),
        sa.Column("shipped_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["sales_channels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shipped_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("number"),
        sa.UniqueConstraint("channel_id","external_reference",name="uq_sales_invoice_channel_external"),
    )
    for c in ("number","channel_id","customer_phone","external_reference","status","created_by","confirmed_by","shipped_by","created_at"):_ix("sales_invoices",c)

    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("variant_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("warranty_id", sa.BigInteger(), nullable=True),
        sa.Column("reservation_id", sa.BigInteger(), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_list_price", sa.Numeric(18,2), nullable=False),
        sa.Column("unit_sale_price", sa.Numeric(18,2), nullable=False),
        sa.Column("line_total", sa.Numeric(18,2), nullable=False),
        sa.Column("unit_cost_snapshot", sa.Numeric(18,4), nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["sales_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["product_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warranty_id"], ["warranties.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reservation_id"], ["stock_reservations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("reservation_id"),
    )
    for c in ("invoice_id","variant_id","item_id","location_id","warranty_id","reservation_id"):_ix("sales_invoice_lines",c)

    op.create_table(
        "sales_returns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("invoice_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("total_refund", sa.Numeric(18,2), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["sales_invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("number"),
    )
    for c in ("number","invoice_id","created_by","created_at"):_ix("sales_returns",c)

    op.create_table(
        "sales_return_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("return_id", sa.BigInteger(), nullable=False),
        sa.Column("invoice_line_id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("location_id", sa.BigInteger(), nullable=False),
        sa.Column("refund_amount", sa.Numeric(18,2), nullable=False),
        sa.Column("unit_cost_snapshot", sa.Numeric(18,4), nullable=False),
        sa.ForeignKeyConstraint(["return_id"], ["sales_returns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["sales_invoice_lines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["product_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("invoice_line_id",name="uq_sales_return_invoice_line"),
    )
    for c in ("return_id","invoice_line_id","item_id","location_id"):_ix("sales_return_lines",c)

    # ---- Existing operational tables become cost/audit aware ----
    op.add_column("product_items", sa.Column("production_order_id", sa.BigInteger(), nullable=True))
    op.add_column("product_items", sa.Column("unit_cost_snapshot", sa.Numeric(18,4), nullable=True))
    op.create_foreign_key("fk_product_items_production_order", "product_items", "production_orders", ["production_order_id"], ["id"], ondelete="SET NULL")
    _ix("product_items","production_order_id")

    op.add_column("stock_movements", sa.Column("unit_cost_snapshot", sa.Numeric(18,4), nullable=True))
    op.add_column("qc_records", sa.Column("failure_action", sa.String(20), nullable=True))
    op.add_column("qc_records", sa.Column("waste_class", sa.String(20), nullable=True))
    _ix("qc_records","failure_action"); _ix("qc_records","waste_class")

    op.add_column("tailor_work_events", sa.Column("recorded_by", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_tailor_work_events_recorded_by", "tailor_work_events", "users", ["recorded_by"], ["id"], ondelete="SET NULL")
    _ix("tailor_work_events","recorded_by")

    # New permissions. Existing customized roles are preserved; only built-in defaults are supplemented.
    op.execute("""
        INSERT INTO permissions(code, name, description) VALUES
          ('tailors.report', 'ثبت تحویل کار خیاط', NULL),
          ('sales.manage', 'ثبت و تأیید فاکتور فروش', NULL),
          ('sales.ship', 'ارسال فاکتور و خروج فروش', NULL),
          ('sales.return', 'ثبت برگشت از فروش', NULL),
          ('accounting.view', 'مشاهده حسابداری و گزارش‌های مالی', NULL),
          ('accounting.manage', 'مدیریت کدینگ حساب و مراکز هزینه', NULL),
          ('accounting.post', 'ثبت و برگشت سند حسابداری', NULL),
          ('audit.view', 'مشاهده ردپای حسابرسی', NULL),
          ('manufacturing.view', 'مشاهده مواد، BOM و دستورهای تولید', NULL),
          ('manufacturing.manage', 'مدیریت مواد، BOM و دستورهای تولید', NULL),
          ('labor.manage', 'ثبت کارکرد و دستمزد تولید', NULL),
          ('labor.approve', 'تأیید کارکرد و دستمزد تولید', NULL)
        ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
    """)
    role_defaults = {
        "admin": ["tailors.report","sales.manage","sales.ship","sales.return","accounting.view","accounting.manage","accounting.post","audit.view","manufacturing.view","manufacturing.manage","labor.manage","labor.approve"],
        "manager": ["accounting.view","audit.view","manufacturing.view"],
        "warehouse_manager": ["manufacturing.view"],
        "production_manager": ["tailors.report","accounting.view","manufacturing.view","manufacturing.manage","labor.manage","labor.approve"],
        "sales_operator": ["sales.manage","sales.ship"],
        "sales_manager": ["sales.manage","sales.ship","sales.return"],
        "tailor": ["tailors.report","catalog.view"],
    }
    for role_code, perms in role_defaults.items():
        codes = ",".join(f"'{x}'" for x in perms)
        op.execute(f"""
            INSERT INTO role_permissions(role_id, permission_id)
            SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
            WHERE r.code = '{role_code}' AND p.code IN ({codes})
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    op.drop_index("ix_tailor_work_events_recorded_by", table_name="tailor_work_events")
    op.drop_constraint("fk_tailor_work_events_recorded_by", "tailor_work_events", type_="foreignkey")
    op.drop_column("tailor_work_events", "recorded_by")
    op.drop_index("ix_qc_records_waste_class", table_name="qc_records")
    op.drop_index("ix_qc_records_failure_action", table_name="qc_records")
    op.drop_column("qc_records", "waste_class")
    op.drop_column("qc_records", "failure_action")
    op.drop_column("stock_movements", "unit_cost_snapshot")
    op.drop_index("ix_product_items_production_order_id", table_name="product_items")
    op.drop_constraint("fk_product_items_production_order", "product_items", type_="foreignkey")
    op.drop_column("product_items", "unit_cost_snapshot")
    op.drop_column("product_items", "production_order_id")

    for table in ["sales_return_lines", "sales_returns", "sales_invoice_lines", "sales_invoices", "overhead_rates", "labor_entries", "material_movements", "production_orders", "bom_items", "boms", "material_stock", "materials", "audit_events", "journal_lines", "journal_entries", "cost_centers", "accounts"]:
        op.drop_table(table)
