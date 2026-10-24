# Dario Backend API v3

FastAPI + PostgreSQL 18 + Async SQLAlchemy + Alembic. این پروژه فقط Backend است؛ پنل React در پروژه جداگانه `dario-panel` قرار دارد.

## راه‌اندازی

```powershell
py -3.14 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`

## هویت و دسترسی

یک جدول `users` برای مشتری، کارمند و خیاط استفاده می‌شود. `user_type` نوع رابطه با مجموعه را مشخص می‌کند و `role`/permission سطح دسترسی پنل را. `panel_access=false` یعنی همان حساب می‌تواند برای سایت/فروشگاه استفاده شود ولی وارد پنل عملیاتی نمی‌شود. دسترسی مؤثر هر کاربر از permissionهای Role + overrideهای فردی محاسبه می‌شود.

اولین مدیر از endpoint bootstrap در `/api/auth/bootstrap` ساخته می‌شود؛ بعد از ایجاد اولین کاربر، bootstrap بسته می‌شود.

## محصول و تنوع

SKU محصول و تنوع اختیاری است. ویژگی‌ها رابطه‌ای هستند: محصول -> ویژگی‌ها/مقادیر مجاز -> تنوع -> مقادیر ویژگی. تصاویر می‌توانند عمومی محصول یا مخصوص یک Variant باشند و فایل در `storage/media` نگه‌داری می‌شود.

## شماره گارانتی

برای هر `product_item` هنگام ایجاد، شماره گارانتی خودکار ساخته می‌شود:

`YYYY-MM-DD-######-C`

- تاریخ بر اساس `WARRANTY_TIMEZONE`
- شمارنده روزانه ۶ رقمی و اتمیک PostgreSQL
- رقم آخر Luhn واقعی روی `YYYYMMDD######`
- unique constraint دیتابیس مانع تکرار می‌شود

سریال داخلی اختیاری است و شماره گارانتی از API قابل تعیین/ویرایش نیست.

## شماره اسناد عملیاتی

شماره انتقال، اصلاح، انبارگردانی و کار خیاط از کاربر دریافت نمی‌شود و اتمیک ساخته می‌شود:

- `TRF-YYYYMMDD-######`
- `ADJ-YYYYMMDD-######`
- `CC-YYYYMMDD-######`
- `TW-YYYYMMDD-######`

## Migration

در نسخه تازه فقط اجرا کنید:

```powershell
python -m alembic upgrade head
```

`revision --autogenerate` را فقط بعد از تغییر مدل‌ها بسازید.

اگر دیتابیس قدیمی هنوز revision حذف‌شده `cb0cf603f543` را در `alembic_version` داشته باشد، `env.py` فقط در صورتی آن را به baseline فعلی نگاشت می‌کند که تمام جدول‌های baseline واقعاً در دیتابیس موجود باشند؛ در غیر این صورت migration متوقف می‌شود تا از stamp اشتباه و خراب شدن schema جلوگیری شود.
