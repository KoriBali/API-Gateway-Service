import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean ,Float, Integer, Enum, ForeignKey, Date, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.staging_database import Base



# === Department ===
class Department(Base):
    __tablename__ = 'departments'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)

    # Parent
    users = relationship("User", back_populates="department", cascade="all, delete-orphan", passive_deletes=True)
    requests = relationship("Request", back_populates="responsible_department", cascade="all, delete-orphan", passive_deletes=True)



# === Role Enum ===
class Role(str, enum.Enum):
    superadmin = 'superadmin'
    admin = 'admin'
    drafter = 'drafter'

# === Users ===
class User(Base):
    __tablename__ = 'users'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    department_id = Column(String, ForeignKey('departments.id', ondelete='CASCADE', onupdate='CASCADE'))
    role = Column(Enum(Role), default=Role.drafter)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, 
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc),
                        nullable=False
                        )

    # Child
    department = relationship("Department", back_populates="users")

    # Parent
    requests = relationship("Request", back_populates="created_by_user", cascade="all, delete-orphan", passive_deletes=True)
    calculation_cases = relationship("CalculationCase", back_populates="owner_user", cascade="all, delete-orphan", passive_deletes=True)


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
    modification = "modification"
    replacement = "replacement"

# === Pole Kind === 
class PoleKind(str, enum.Enum):
    standard = "standard"
    custom = "custom" 

# === Request ===
class Request(Base):
    __tablename__ = 'requests'

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    responsible_department_id = Column(String, ForeignKey('departments.id', ondelete="CASCADE", onupdate="CASCADE"))
    created_by_user_id = Column(String, ForeignKey('users.id', ondelete="CASCADE", onupdate="CASCADE"))
    pole_category_id = Column(String, ForeignKey('pole_categories.id', ondelete="CASCADE", onupdate="CASCADE"))
    request_no = Column(String, nullable=False)
    receipt_no = Column(String, nullable=False)
    pj_no = Column(String, nullable=False)
    request_type = Column(Enum(RequestType), nullable=False)
    design_type = Column(Enum(DesignType), nullable=False)
    request_category = Column(Enum(RequestCategory), nullable=False)
    pole_kind = Column(Enum(PoleKind), nullable=True)
    company_name = Column(String, nullable=True)
    project_name = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, 
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc),
                        nullable=False
                        )

    # Child
    created_by_user = relationship("User", back_populates="requests")
    responsible_department = relationship("Department", back_populates="requests")

    # Parent
    calculation_cases = relationship("CalculationCase", back_populates="request", cascade="all, delete-orphan", passive_deletes=True)
