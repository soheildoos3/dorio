from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user, require_permission
from app.modules.hr.model import EmployeeProfile
from app.modules.hr.schemas import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.modules.user.model import User

router = APIRouter(prefix="/hr", tags=["hr"], dependencies=[Depends(get_current_user), Depends(require_permission("hr.manage"))])

@router.get("/employees", response_model=list[EmployeeRead])
async def list_employees(db: AsyncSession = Depends(get_db)):
    return list((await db.execute(select(EmployeeProfile).order_by(EmployeeProfile.id.desc()))).scalars().all())

@router.post("/employees", response_model=EmployeeRead, status_code=201)
async def create_employee(payload: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(404, "User account not found")
    if user.user_type != "employee":
        raise HTTPException(409, "Only users with employee type can have an HR employee profile")
    obj = EmployeeProfile(**payload.model_dump())
    db.add(obj)
    try:
        await db.commit()
        await db.refresh(obj)
        return obj
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Personnel code or user profile already exists") from exc

@router.patch("/employees/{employee_id}", response_model=EmployeeRead)
async def update_employee(employee_id: int, payload: EmployeeUpdate, db: AsyncSession = Depends(get_db)):
    obj = await db.get(EmployeeProfile, employee_id)
    if obj is None:
        raise HTTPException(404, "Employee profile not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    try:
        await db.commit()
        await db.refresh(obj)
        return obj
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Employee data conflicts with an existing record") from exc
