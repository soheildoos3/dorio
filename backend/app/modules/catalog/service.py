from __future__ import annotations

from datetime import datetime, timezone
from itertools import product as cartesian_product

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.model import AttributeValue, ProductVariant, VariantAttributeValue
from app.modules.inventory.model import ProductItem, Stock, StockMovement, StockReservation
from app.modules.catalog.repository import CatalogRepository
from app.modules.catalog.schemas import (
    AttributeCreate, AttributeValueCreate, CategoryCreate, CategoryUpdate, GenerateVariantsRequest,
    MediaCreate, ProductAttributesUpdate, ProductCreate, ProductUpdate, ProductVariantCreate, ProductVariantUpdate,
)


class CatalogNotFoundError(LookupError): pass
class CatalogConflictError(ValueError): pass


class CatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session; self.repo = CatalogRepository(session)

    async def create_category(self, payload: CategoryCreate):
        parent = await self.repo.get_category(payload.parent_id) if payload.parent_id else None
        if payload.parent_id and not parent: raise CatalogNotFoundError("Parent category not found")
        path = f"{parent.path}/{payload.name}" if parent else payload.name
        obj = await self.repo.create_category(**payload.model_dump(), path=path, level=(parent.level + 1 if parent else 0))
        await self.session.commit(); await self.session.refresh(obj); return obj

    async def _refresh_category_descendants(self, category):
        for child in await self.repo.list_category_children(category.id):
            child.path = f"{category.path}/{child.name}"; child.level = category.level + 1
            await self._refresh_category_descendants(child)

    async def update_category(self, category_id: int, payload: CategoryUpdate):
        obj = await self.repo.get_category(category_id)
        if not obj: raise CatalogNotFoundError("Category not found")
        data = payload.model_dump(exclude_unset=True); new_parent_id = data.get("parent_id", obj.parent_id)
        if new_parent_id == category_id: raise CatalogConflictError("Category cannot be its own parent")
        parent = await self.repo.get_category(new_parent_id) if new_parent_id else None
        if new_parent_id and not parent: raise CatalogNotFoundError("Parent category not found")
        if parent and (parent.path == obj.path or parent.path.startswith(f"{obj.path}/")): raise CatalogConflictError("Invalid category hierarchy")
        name = data.get("name", obj.name); data["path"] = f"{parent.path}/{name}" if parent else name; data["level"] = parent.level + 1 if parent else 0
        await self.repo.update(obj, **data); await self._refresh_category_descendants(obj); await self.session.commit(); await self.session.refresh(obj); return obj

    async def create_product(self, payload: ProductCreate):
        data = payload.model_dump(); data["sku"] = (data.get("sku") or "").strip() or None
        try:
            obj = await self.repo.create_product(**data); await self.session.commit(); await self.session.refresh(obj); return obj
        except IntegrityError as exc:
            await self.session.rollback(); raise CatalogConflictError("SKU محصول تکراری است یا داده مرجع معتبر نیست") from exc

    async def update_product(self, product_id: int, payload: ProductUpdate):
        obj = await self.repo.get_product(product_id)
        if not obj or obj.deleted_at is not None: raise CatalogNotFoundError("Product not found")
        data = payload.model_dump(exclude_unset=True)
        if "sku" in data: data["sku"] = (data.get("sku") or "").strip() or None
        try:
            await self.repo.update(obj, **data); await self.session.commit(); await self.session.refresh(obj); return obj
        except IntegrityError as exc:
            await self.session.rollback(); raise CatalogConflictError("SKU محصول تکراری است") from exc

    async def soft_delete_product(self, product_id: int):
        obj = await self.repo.get_product(product_id)
        if not obj or obj.deleted_at is not None: raise CatalogNotFoundError("Product not found")
        obj.deleted_at = datetime.now(timezone.utc); await self.session.commit()

    async def _validate_variant_values(self, product_id: int, value_ids: list[int]):
        config = await self.repo.get_product_attribute_config(product_id)
        allowed = {pv.attribute_value_id for pa in config for pv in pa.values}
        values = list((await self.session.scalars(select(AttributeValue).where(AttributeValue.id.in_(value_ids)))).all()) if value_ids else []
        if len(values) != len(set(value_ids)): raise CatalogConflictError("یکی از مقادیر ویژگی پیدا نشد")
        if any(v.id not in allowed for v in values): raise CatalogConflictError("مقدار ویژگی برای این محصول مجاز نیست")
        by_attribute = {}
        for value in values:
            if value.attribute_id in by_attribute: raise CatalogConflictError("برای هر ویژگی فقط یک مقدار در هر تنوع مجاز است")
            by_attribute[value.attribute_id] = value.id
        return values

    async def _ensure_unique_variant_combination(self, product_id: int, value_ids: list[int], exclude_variant_id: int | None = None):
        target = tuple(sorted(set(value_ids)))
        variants = await self.repo.list_variants(product_id=product_id)
        for variant in variants:
            if exclude_variant_id is not None and variant.id == exclude_variant_id:
                continue
            current = tuple(sorted(row.attribute_value_id for row in variant.attribute_values))
            if current == target:
                raise CatalogConflictError("این ترکیب ویژگی قبلاً برای محصول ساخته شده است")

    async def create_variant(self, payload: ProductVariantCreate):
        product_obj = await self.repo.get_product(payload.product_id)
        if not product_obj: raise CatalogNotFoundError("Product not found")
        await self._validate_variant_values(payload.product_id, payload.attribute_value_ids)
        await self._ensure_unique_variant_combination(payload.product_id, payload.attribute_value_ids)
        data = payload.model_dump(exclude={"attribute_value_ids"}); data["sku"] = data["sku"].strip() or None if data.get("sku") else None
        try:
            obj = await self.repo.create_variant(**data); await self.repo.replace_variant_values(obj, payload.attribute_value_ids)
            await self.session.commit(); return await self.repo.get_variant(obj.id)
        except IntegrityError as exc:
            await self.session.rollback(); raise CatalogConflictError("SKU تنوع تکراری است یا ترکیب معتبر نیست") from exc

    async def update_variant(self, variant_id: int, payload: ProductVariantUpdate):
        obj = await self.repo.get_variant(variant_id)
        if not obj: raise CatalogNotFoundError("Variant not found")
        data = payload.model_dump(exclude_unset=True); value_ids = data.pop("attribute_value_ids", None)
        if "sku" in data: data["sku"] = (data.get("sku") or "").strip() or None
        if value_ids is not None:
            await self._validate_variant_values(obj.product_id, value_ids); await self._ensure_unique_variant_combination(obj.product_id, value_ids, exclude_variant_id=obj.id); await self.repo.replace_variant_values(obj, value_ids)
        try:
            await self.repo.update(obj, **data); await self.session.commit(); return await self.repo.get_variant(obj.id)
        except IntegrityError as exc:
            await self.session.rollback(); raise CatalogConflictError("SKU تنوع تکراری است") from exc

    async def delete_variant(self, variant_id: int):
        obj = await self.repo.get_variant(variant_id)
        if not obj:
            raise CatalogNotFoundError("Variant not found")
        checks = [
            select(func.count(ProductItem.id)).where(ProductItem.variant_id == variant_id),
            select(func.count(StockMovement.id)).where(StockMovement.variant_id == variant_id),
            select(func.count(StockReservation.id)).where(StockReservation.variant_id == variant_id),
            select(func.coalesce(func.sum(Stock.quantity + Stock.reserved), 0)).where(Stock.variant_id == variant_id),
        ]
        has_history = False
        for stmt in checks:
            if int((await self.session.scalar(stmt)) or 0) > 0:
                has_history = True
                break
        if has_history:
            obj.is_active = False
            await self.session.commit()
            return "deactivated"
        await self.session.delete(obj)
        await self.session.commit()
        return "deleted"

    async def set_product_attributes(self, product_id: int, payload: ProductAttributesUpdate):
        if not await self.repo.get_product(product_id): raise CatalogNotFoundError("Product not found")
        seen_attrs = set()
        for selection in payload.selections:
            if selection.attribute_id in seen_attrs: raise CatalogConflictError("ویژگی تکراری است")
            seen_attrs.add(selection.attribute_id)
            attr = await self.repo.get_attribute(selection.attribute_id)
            if not attr: raise CatalogNotFoundError("Attribute not found")
            for value_id in selection.value_ids:
                value = await self.repo.get_attribute_value(value_id)
                if not value or value.attribute_id != selection.attribute_id: raise CatalogConflictError("مقدار ویژگی با ویژگی انتخاب‌شده تطابق ندارد")
        selected_value_ids = {value_id for selection in payload.selections for value_id in selection.value_ids}
        used_value_ids = set((await self.session.scalars(
            select(VariantAttributeValue.attribute_value_id)
            .join(ProductVariant, ProductVariant.id == VariantAttributeValue.variant_id)
            .where(ProductVariant.product_id == product_id)
        )).all())
        removed_in_use = used_value_ids - selected_value_ids
        if removed_in_use:
            raise CatalogConflictError("بعضی مقادیر انتخابی در تنوع‌های موجود استفاده شده‌اند؛ ابتدا آن تنوع‌ها را ویرایش کنید")
        result = await self.repo.replace_product_attribute_config(product_id, payload.selections)
        await self.session.commit(); return await self.repo.get_product_attribute_config(product_id)

    async def generate_variants(self, product_id: int, payload: GenerateVariantsRequest):
        product_obj = await self.repo.get_product(product_id)
        if not product_obj: raise CatalogNotFoundError("Product not found")
        config = await self.repo.get_product_attribute_config(product_id)
        axes = [pa for pa in config if pa.attribute.is_variant_axis and pa.values]
        if not axes: raise CatalogConflictError("برای محصول هیچ ویژگی تنوع‌ساز با مقدار انتخاب نشده است")
        combos = list(cartesian_product(*[[pv.attribute_value for pv in pa.values] for pa in axes]))
        axis_attribute_ids = {pa.attribute_id for pa in axes}
        existing = await self.repo.list_variants(product_id=product_id)
        existing_keys = {
            tuple(sorted(row.attribute_value_id for row in v.attribute_values if row.attribute_value.attribute_id in axis_attribute_ids))
            for v in existing
        }
        created = []
        for combo in combos:
            key = tuple(sorted(v.id for v in combo))
            if key in existing_keys: continue
            variant = ProductVariant(product_id=product_id, sku=None, sale_price=payload.default_price, is_active=True, attributes={})
            self.session.add(variant); await self.session.flush(); await self.repo.replace_variant_values(variant, list(key)); created.append(variant)
            existing_keys.add(key)
        await self.session.commit(); return await self.repo.list_variants(product_id=product_id)

    async def create_media(self, payload: MediaCreate):
        product_obj = await self.repo.get_product(payload.product_id)
        if not product_obj or product_obj.deleted_at is not None: raise CatalogNotFoundError("Product not found")
        if payload.variant_id is not None:
            variant = await self.repo.get_variant(payload.variant_id)
            if not variant or variant.product_id != payload.product_id: raise CatalogConflictError("تنوع به این محصول تعلق ندارد")
        if payload.is_primary: await self.repo.clear_primary_media(payload.product_id, payload.variant_id)
        obj = await self.repo.create_media(**payload.model_dump()); await self.session.commit(); await self.session.refresh(obj); return obj

    async def update_media(self, media_id: int, payload):
        obj = await self.repo.get_media(media_id)
        if not obj: raise CatalogNotFoundError("Media not found")
        data = payload.model_dump(exclude_unset=True)
        if "variant_id" in data and data["variant_id"] is not None:
            variant = await self.repo.get_variant(data["variant_id"])
            if not variant or variant.product_id != obj.product_id: raise CatalogConflictError("تنوع به این محصول تعلق ندارد")
        target_variant = data.get("variant_id", obj.variant_id)
        if data.get("is_primary") is True: await self.repo.clear_primary_media(obj.product_id, target_variant)
        await self.repo.update(obj, **data); await self.session.commit(); await self.session.refresh(obj); return obj

    async def delete_media(self, media_id: int):
        obj = await self.repo.get_media(media_id)
        if not obj: raise CatalogNotFoundError("Media not found")
        await self.repo.delete_media(obj); await self.session.commit(); return obj

    async def create_attribute(self, payload: AttributeCreate):
        try:
            obj = await self.repo.create_attribute(**payload.model_dump()); await self.session.commit(); await self.session.refresh(obj); return obj
        except IntegrityError as exc:
            await self.session.rollback(); raise CatalogConflictError("Attribute code already exists") from exc

    async def create_attribute_value(self, payload: AttributeValueCreate):
        if not await self.repo.get_attribute(payload.attribute_id): raise CatalogNotFoundError("Attribute not found")
        try:
            obj = await self.repo.create_attribute_value(**payload.model_dump()); await self.session.commit(); await self.session.refresh(obj); return obj
        except IntegrityError as exc:
            await self.session.rollback(); raise CatalogConflictError("Attribute value already exists") from exc
