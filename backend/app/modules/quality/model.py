from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.modules.quality.constants import DefectSeverity, LabelType, QCRecordResult

class QCRecord(Base):
    __tablename__ = 'qc_records'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_items.id', ondelete='CASCADE'), nullable=False, index=True)
    result: Mapped[QCRecordResult] = mapped_column(Enum(QCRecordResult, name='qc_record_result_enum', values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    checked_by: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    defect_type: Mapped[str | None] = mapped_column(String(100))
    defect_severity: Mapped[DefectSeverity | None] = mapped_column(Enum(DefectSeverity, name='defect_severity_enum', values_callable=lambda e: [x.value for x in e]), index=True)
    failure_action: Mapped[str | None] = mapped_column(String(20), index=True)
    waste_class: Mapped[str | None] = mapped_column(String(20), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    photos: Mapped[list[dict[str, Any]] | list[str] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Label(Base):
    __tablename__ = 'labels'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('product_items.id', ondelete='CASCADE'), nullable=False, index=True)
    label_type: Mapped[LabelType] = mapped_column(Enum(LabelType, name='label_type_enum', values_callable=lambda e: [x.value for x in e]), nullable=False, index=True)
    printed_by: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    printed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
