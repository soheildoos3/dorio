from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class EmployeeCreate(BaseModel):
    user_id: int
    personnel_code: str = Field(min_length=1, max_length=30)
    department: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=100)
    hire_date: date | None = None
    national_id: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_phone: str | None = Field(default=None, max_length=20)

class EmployeeUpdate(BaseModel):
    department: str | None = Field(default=None, max_length=100)
    job_title: str | None = Field(default=None, max_length=100)
    hire_date: date | None = None
    national_id: str | None = Field(default=None, max_length=20)
    address: str | None = None
    emergency_phone: str | None = Field(default=None, max_length=20)

class EmployeeRead(EmployeeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
