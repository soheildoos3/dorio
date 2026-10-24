from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

WorkStatus = Literal["open", "completed", "cancelled"]


class TailorRead(BaseModel):
    id: int
    full_name: str
    phone: str | None
    status: str
    panel_access: bool
    role_id: int | None


class WorkCreate(BaseModel):
    tailor_user_id: int
    work_no: str | None = Field(default=None, min_length=1, max_length=50)
    product_id: int | None = None
    production_order_id: int | None = None
    quantity: int = Field(gt=0)
    assigned_at: date | None = None
    due_at: date | None = None
    notes: str | None = None


class WorkUpdate(BaseModel):
    tailor_user_id: int | None = None
    product_id: int | None = None
    quantity: int | None = Field(default=None, gt=0)
    due_at: date | None = None
    completed_at: date | None = None
    status: WorkStatus | None = None
    notes: str | None = None


class WorkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tailor_user_id: int
    work_no: str
    product_id: int | None
    production_order_id: int | None
    quantity: int
    delivered_good: int
    returned_for_fix: int
    damaged: int
    assigned_at: date
    due_at: date | None
    completed_at: date | None
    status: str
    notes: str | None
    created_at: datetime


class TailorStats(BaseModel):
    tailor_user_id: int
    assigned: int
    delivered_good: int
    returned_for_fix: int
    damaged: int
    defect_rate: float
    open_work: int
    overdue_work: int


class WorkReport(BaseModel):
    delivered_good: int = Field(default=0, ge=0)
    returned_for_fix: int = Field(default=0, ge=0)
    damaged: int = Field(default=0, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def not_empty(self):
        if self.delivered_good + self.returned_for_fix + self.damaged == 0:
            raise ValueError("حداقل یک مقدار برای گزارش تحویل لازم است")
        return self


class MonthlyStats(BaseModel):
    month: str
    delivered_good: int
    returned_for_fix: int
    damaged: int
    defect_rate: float
