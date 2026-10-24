DEFAULT_PERMISSION_DEFINITIONS = [
    ("dashboard.view", "مشاهده داشبورد مدیریتی"),
    ("catalog.view", "مشاهده کاتالوگ"),
    ("catalog.manage", "مدیریت کاتالوگ"),
    ("warehouse.view", "مشاهده انبار"),
    ("warehouse.manage", "مدیریت انبار و مکان‌ها"),
    ("inventory.view", "مشاهده موجودی"),
    ("inventory.manage", "مدیریت موجودی"),
    ("inventory.outbound", "ثبت خروج انبار"),
    ("quality.view", "مشاهده کنترل کیفیت"),
    ("quality.manage", "ثبت و مدیریت کنترل کیفیت"),
    ("quality.print", "چاپ لیبل"),
    ("users.view", "مشاهده کاربران"),
    ("users.manage", "مدیریت کاربران"),
    ("roles.manage", "مدیریت نقش‌ها و دسترسی‌ها"),
    ("hr.manage", "مدیریت منابع انسانی"),
    ("tailors.view", "مشاهده داشبورد خیاط‌ها"),
    ("tailors.manage", "مدیریت کار خیاط‌ها"),
    ("tailors.report", "ثبت تحویل کار خیاط"),
    ("warranty.view", "مشاهده گارانتی"),
    ("warranty.manage", "مدیریت گارانتی"),
    ("channels.manage", "مدیریت کانال‌های خروج"),
    ("pricing.view", "مشاهده قیمت‌های پلتفرمی"),
    ("pricing.manage", "مدیریت قیمت و تخفیف پلتفرم‌ها"),
    ("sales.view", "مشاهده گزارش فروش"),
    ("sales.manage", "ثبت و تأیید فاکتور فروش"),
    ("sales.ship", "ارسال فاکتور و خروج فروش"),
    ("sales.return", "ثبت برگشت از فروش"),
    ("accounting.view", "مشاهده حسابداری و گزارش‌های مالی"),
    ("accounting.manage", "مدیریت کدینگ حساب و مراکز هزینه"),
    ("accounting.post", "ثبت و برگشت سند حسابداری"),
    ("audit.view", "مشاهده ردپای حسابرسی"),
    ("manufacturing.view", "مشاهده مواد، BOM و دستورهای تولید"),
    ("manufacturing.manage", "مدیریت مواد، BOM و دستورهای تولید"),
    ("labor.manage", "ثبت کارکرد و دستمزد تولید"),
    ("labor.approve", "تأیید کارکرد و دستمزد تولید"),
]

DEFAULT_ROLE_TEMPLATES = {
    "admin": {"name": "مدیر کل", "permissions": ["*"]},
    "manager": {
        "name": "مدیر عملیات",
        "permissions": [
            "dashboard.view", "catalog.view", "warehouse.view", "inventory.view", "inventory.outbound",
            "quality.view", "tailors.view", "warranty.view", "pricing.view", "sales.view",
            "accounting.view", "manufacturing.view", "audit.view",
        ],
    },
    "warehouse_manager": {
        "name": "مدیر انبار",
        "permissions": [
            "dashboard.view", "catalog.view", "warehouse.view", "warehouse.manage", "inventory.view",
            "inventory.manage", "inventory.outbound", "pricing.view", "sales.view",
            "manufacturing.view",
        ],
    },
    "warehouse_operator": {
        "name": "انباردار",
        "permissions": ["dashboard.view", "catalog.view", "warehouse.view", "inventory.view", "inventory.manage", "inventory.outbound", "pricing.view"],
    },
    "qc_operator": {
        "name": "کنترل کیفیت",
        "permissions": ["dashboard.view", "catalog.view", "inventory.view", "quality.view", "quality.manage", "quality.print", "warranty.view"],
    },
    "production_manager": {
        "name": "مدیر تولید",
        "permissions": ["dashboard.view", "catalog.view", "inventory.view", "tailors.view", "tailors.manage", "tailors.report", "quality.view", "manufacturing.view", "manufacturing.manage", "labor.manage", "labor.approve", "accounting.view"],
    },
    "tailor": {
        "name": "خیاط",
        "permissions": ["tailors.view", "tailors.report", "catalog.view"],
    },
    "hr_manager": {
        "name": "منابع انسانی",
        "permissions": ["dashboard.view", "users.view", "hr.manage", "tailors.view"],
    },
    "sales_operator": {
        "name": "فروش و خروج کالا",
        "permissions": ["dashboard.view", "catalog.view", "inventory.view", "inventory.outbound", "warranty.view", "pricing.view", "sales.view", "sales.manage", "sales.ship"],
    },
    "sales_manager": {
        "name": "مدیر فروش",
        "permissions": ["dashboard.view", "catalog.view", "inventory.view", "inventory.outbound", "pricing.view", "pricing.manage", "sales.view", "sales.manage", "sales.ship", "sales.return", "channels.manage", "warranty.view"],
    },
    "warranty_manager": {
        "name": "مدیر گارانتی",
        "permissions": ["dashboard.view", "catalog.view", "warranty.view", "warranty.manage", "quality.print"],
    },
    "viewer": {
        "name": "مشاهده‌گر",
        "permissions": ["dashboard.view", "catalog.view", "warehouse.view", "inventory.view", "quality.view", "tailors.view", "warranty.view"],
    },
}
