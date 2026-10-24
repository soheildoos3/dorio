# Validation v3

موارد بررسی‌شده در زمان بسته‌بندی:

- Python `compileall` روی `app`, migrations و tests: PASS
- SQLAlchemy `configure_mappers()`: PASS
- 36 جدول ORM؛ FK/mapping بدون conflict: PASS
- Alembic chain تا `dario_v3_doc_numbers`: PASS
- `alembic upgrade head --sql`: PASS
- Unit tests شماره گارانتی/Luhn: 3/3 PASS
- TypeScript/TSX parse/transpile روی تمام `src`: PASS
- Backend و Dario Panel از نظر فایل/پروژه کاملاً جدا شده‌اند.

محدودیت محیط ساخت: نصب کامل npm از registry و در نتیجه اجرای نهایی `npm run build` در این محیط قابل اتکا نبود. روی سیستم مقصد `npm ci && npm run build` اجرا شود؛ سورس TS/TSX از نظر syntax بررسی شده است.
