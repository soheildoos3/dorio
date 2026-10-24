"""grant catalog read permission to tailor role

Revision ID: b7d2f6a9c301
Revises: 2591b3a9215c
Create Date: 2026-10-20 23:42:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7d2f6a9c301"
down_revision: Union[str, Sequence[str], None] = "2591b3a9215c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE roles SET name = 'مدیر کل' WHERE code = 'admin' AND name = 'مدیر سیستم'")
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles AS r
        CROSS JOIN permissions AS p
        WHERE r.code = 'tailor' AND p.code = 'catalog.view'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("UPDATE roles SET name = 'مدیر سیستم' WHERE code = 'admin' AND name = 'مدیر کل'")
    op.execute(
        """
        DELETE FROM role_permissions AS rp
        USING roles AS r, permissions AS p
        WHERE rp.role_id = r.id
          AND rp.permission_id = p.id
          AND r.code = 'tailor'
          AND p.code = 'catalog.view'
        """
    )
