import os

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dario_test:dario_test@127.0.0.1:5432/dario_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-0123456789-abcdef")
