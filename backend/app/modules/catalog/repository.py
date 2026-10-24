from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.model import (
    Attribute,
    AttributeValue,
    Category,
    Media,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductVariant,
    VariantAttributeValue,
)


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_category(self, category_id: int):
        return await self.session.get(Category, category_id)

    async def list_categories(self, active_only=False):
        stmt = select(Category).order_by(Category.sort_order, Category.id)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return list((await self.session.scalars(stmt)).all())

    async def create_category(self, **data):
        obj = Category(**data); self.session.add(obj); await self.session.flush(); return obj

    async def list_category_children(self, parent_id: int):
        return list((await self.session.scalars(select(Category).where(Category.parent_id == parent_id).order_by(Category.sort_order, Category.id))).all())

    async def get_product(self, product_id: int):
        return await self.session.get(Product, product_id)

    async def list_products(self, include_deleted=False, offset=0, limit=100):
        stmt = select(Product).order_by(Product.id.desc())
        if not include_deleted:
            stmt = stmt.where(Product.deleted_at.is_(None))
        return list((await self.session.scalars(stmt.offset(offset).limit(limit))).all())

    async def create_product(self, **data):
        obj = Product(**data); self.session.add(obj); await self.session.flush(); return obj

    async def get_variant(self, variant_id: int):
        return await self.session.get(ProductVariant, variant_id)

    async def list_variants(self, product_id=None, offset=0, limit=1000):
        stmt = select(ProductVariant).order_by(ProductVariant.id.desc())
        if product_id is not None:
            stmt = stmt.where(ProductVariant.product_id == product_id)
        return list((await self.session.execute(stmt.offset(offset).limit(limit))).scalars().unique().all())

    async def create_variant(self, **data):
        obj = ProductVariant(**data); self.session.add(obj); await self.session.flush(); return obj

    async def replace_variant_values(self, variant: ProductVariant, value_ids: list[int]):
        await self.session.execute(delete(VariantAttributeValue).where(VariantAttributeValue.variant_id == variant.id))
        values = []
        if value_ids:
            values = list((await self.session.scalars(select(AttributeValue).where(AttributeValue.id.in_(value_ids)))).all())
            for value in values:
                self.session.add(VariantAttributeValue(variant_id=variant.id, attribute_value_id=value.id))
        variant.attributes = {v.attribute.code: v.value for v in values}
        await self.session.flush()
        return values

    async def create_media(self, **data):
        obj = Media(**data); self.session.add(obj); await self.session.flush(); return obj

    async def list_media(self, product_id: int):
        return list((await self.session.scalars(select(Media).where(Media.product_id == product_id).order_by(Media.sort_order, Media.id))).all())

    async def get_media(self, media_id: int):
        return await self.session.get(Media, media_id)

    async def clear_primary_media(self, product_id: int, variant_id: int | None):
        stmt = update(Media).where(Media.product_id == product_id)
        stmt = stmt.where(Media.variant_id.is_(None)) if variant_id is None else stmt.where(Media.variant_id == variant_id)
        await self.session.execute(stmt.values(is_primary=False))

    async def delete_media(self, obj):
        await self.session.delete(obj); await self.session.flush()

    async def create_attribute(self, **data):
        obj = Attribute(**data); self.session.add(obj); await self.session.flush(); return obj

    async def get_attribute(self, attribute_id: int):
        return await self.session.get(Attribute, attribute_id)

    async def list_attributes(self):
        return list((await self.session.execute(select(Attribute).order_by(Attribute.sort_order, Attribute.id))).scalars().unique().all())

    async def create_attribute_value(self, **data):
        obj = AttributeValue(**data); self.session.add(obj); await self.session.flush(); return obj

    async def get_attribute_value(self, value_id: int):
        return await self.session.get(AttributeValue, value_id)

    async def list_attribute_values(self, attribute_id=None, offset=0, limit=1000):
        stmt = select(AttributeValue).order_by(AttributeValue.attribute_id, AttributeValue.sort_order, AttributeValue.id)
        if attribute_id is not None:
            stmt = stmt.where(AttributeValue.attribute_id == attribute_id)
        return list((await self.session.scalars(stmt.offset(offset).limit(limit))).all())

    async def get_product_attribute_config(self, product_id: int):
        stmt = select(ProductAttribute).where(ProductAttribute.product_id == product_id).order_by(ProductAttribute.sort_order, ProductAttribute.id)
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def replace_product_attribute_config(self, product_id: int, selections):
        await self.session.execute(delete(ProductAttribute).where(ProductAttribute.product_id == product_id))
        await self.session.flush()
        result = []
        for selection in selections:
            pa = ProductAttribute(product_id=product_id, attribute_id=selection.attribute_id, sort_order=selection.sort_order)
            self.session.add(pa); await self.session.flush()
            for value_id in selection.value_ids:
                self.session.add(ProductAttributeValue(product_attribute_id=pa.id, attribute_value_id=value_id))
            result.append(pa)
        await self.session.flush()
        return result

    async def update(self, obj, **data):
        for key, value in data.items():
            setattr(obj, key, value)
        await self.session.flush(); return obj
