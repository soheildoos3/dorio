from datetime import date,datetime
from sqlalchemy import BigInteger,Date,DateTime,ForeignKey,String,Text,func
from sqlalchemy.orm import Mapped,mapped_column
from app.db.base import Base
class EmployeeProfile(Base):
 __tablename__="employee_profiles"; id:Mapped[int]=mapped_column(BigInteger,primary_key=True,autoincrement=True); user_id:Mapped[int]=mapped_column(BigInteger,ForeignKey("users.id",ondelete="CASCADE"),unique=True,index=True); personnel_code:Mapped[str]=mapped_column(String(30),unique=True,index=True); department:Mapped[str|None]=mapped_column(String(100)); job_title:Mapped[str|None]=mapped_column(String(100)); hire_date:Mapped[date|None]=mapped_column(Date); national_id:Mapped[str|None]=mapped_column(String(20)); address:Mapped[str|None]=mapped_column(Text); emergency_phone:Mapped[str|None]=mapped_column(String(20)); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
