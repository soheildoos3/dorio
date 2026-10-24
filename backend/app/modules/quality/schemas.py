from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.modules.quality.constants import DefectSeverity, LabelType, QCRecordResult

class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class QCRecordCreate(BaseModel):
    item_id: int
    result: QCRecordResult
    checked_by: int | None = None
    defect_type: str | None = Field(default=None, max_length=100)
    defect_severity: DefectSeverity | None = None
    failure_action: str | None = Field(default=None, pattern="^(rework|scrap)$")
    waste_class: str | None = Field(default=None, pattern="^(normal|abnormal)$")
    notes: str | None = None
    photos: list[dict[str, Any]] | list[str] | None = None

    @model_validator(mode='after')
    def validate_failed_qc(self) -> 'QCRecordCreate':
        if self.result == QCRecordResult.PASSED:
            if self.defect_type or self.defect_severity or self.failure_action or self.waste_class:
                raise ValueError('Passed QC cannot contain defect/failure fields')
        else:
            if self.failure_action is None:
                self.failure_action = 'rework'
            if self.failure_action == 'scrap' and self.waste_class is None:
                raise ValueError('Scrapped QC failures require waste_class')
            if self.failure_action == 'rework':
                self.waste_class = None
        return self

class QCRecordRead(ORMModel):
    id: int
    item_id: int
    result: QCRecordResult
    checked_by: int | None = None
    checked_at: datetime
    defect_type: str | None
    defect_severity: DefectSeverity | None
    failure_action: str | None
    waste_class: str | None
    notes: str | None
    photos: list[dict[str, Any]] | list[str] | None
    created_at: datetime

class LabelCreate(BaseModel):
    item_id: int
    label_type: LabelType
    printed_by: int | None = None

class LabelRead(ORMModel):
    id: int
    item_id: int
    label_type: LabelType
    printed_by: int | None = None
    printed_at: datetime


class LabelBatchCreate(BaseModel):
    variant_id: int
    label_type: LabelType
    limit: int = Field(default=100, ge=1, le=200)


class LabelBatchRead(BaseModel):
    item_ids: list[int]
    count: int
