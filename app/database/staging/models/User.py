import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base



# === Department ===
class Department(Base):
    __tablename__ = 'departments'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String, nullable=False)



# === Role Enum ===
class Role(str, enum.Enum):
    superadmin = 'superadmin'
    admin = 'admin'
    drafter = 'drafter'

# === Users ===
class User(Base):
    __tablename__ = 'users'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    department_id = Column(String, ForeignKey('departments.id', ondelete='CASCADE', onupdate='CASCADE'))
    role = Column(Enum(Role), default=Role.drafter)
    username = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(String, nullable=False)
    is_verfied = Column(String, nullable=False)
    last_login_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, 
                        default=lambda: datetime.now(timezone.utc),
                        onUpdate=lambda: datetime.now(timezone.utc)
                        )



# === Request Type Enum ===
class RequestType(str, enum.Enum):
    generally = "generally"
    special = "special"

# === Design Type Enum ===
class DesignType(str, enum.Enum):
    drawing = "drawing"
    calculation = "calculation"
    drawing_calculation = "drawing_calculation"

# === Request Category === 
class RequestCategory(str, enum.Enum):
    new = "new"
    revision = "revision"

# === Request ===
class Request(Base):
    __tablename__ = 'requests'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    responsible_department_id = Column(String, ForeignKey('departments.id', ondelete="CASCADE", onupdate="CASCADE"))
    created_by_user_id = Column(String, ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"))
    reqeust_no = Column(String, nullable=False)
    reciept_no = Column(String, nullable=False)
    pj_no = Column(String, nullable=False)
    request_type = Column(RequestType, nullable=False)
    design_type = Column(DesignType, nullable=False)
    request_category = Column(RequestCategory, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, 
                        default=lambda: datetime.now(timezone.utc),
                        onUpdate=lambda: datetime.now(timezone.utc)
                        )
