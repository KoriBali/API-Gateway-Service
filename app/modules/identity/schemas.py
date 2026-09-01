from datetime import datetime, date

from pydantic import EmailStr, Field

from app.utils.base_schema import CamelBaseModel
from app.database.models.identity import (
    Role,
    RequestType,
    DesignType,
    RequestCategory,
    PoleKind,
    RequestStatus
)



# ===== Input =====
class RequestCreate(CamelBaseModel):
    pole_category_id: str = Field(min_length=1)

    request_no: str = Field(min_length=1, max_length=100)
    receipt_no: str = Field(min_length=1, max_length=100)
    pj_no: str = Field(min_length=1, max_length=100)

    request_type: RequestType
    design_type: DesignType
    request_category: RequestCategory

    pole_kind: PoleKind | None = None
    company_name: str | None = Field(default=None, max_length=200)
    project_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None
    confirm_supersede: bool = False


class RequestClone(CamelBaseModel):
    request_no: str = Field(min_length=1, max_length=100)
    receipt_no: str = Field(min_length=1, max_length=100)
    pj_no: str = Field(min_length=1, max_length=100)



class RequestUpdate(CamelBaseModel):
    pole_category_id: str | None = Field(default=None, min_length=1)
    request_no: str | None = Field(default=None, min_length=1, max_length=100)
    receipt_no: str | None = Field(default=None, min_length=1, max_length=100)
    pj_no: str | None = Field(default=None, min_length=1, max_length=100)
    request_type: RequestType | None = None
    design_type: DesignType | None = None
    request_category: RequestCategory | None = None
    pole_kind: PoleKind | None = None
    company_name: str | None = Field(default=None, max_length=200)
    project_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None



class DepartmentCreate(CamelBaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)



class DepartmentUpdate(CamelBaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=120)



class UserCreate(CamelBaseModel):
    username: str = Field(min_length= 3, max_length= 50)
    email: EmailStr
    full_name: str = Field(min_length= 1, max_length= 120)
    password: str = Field(min_length= 8, max_length= 64)
    role: Role = Role.drafter
    department_id: str | None = None



class UserUpdate(CamelBaseModel):
    full_name: str | None = Field(default= None, min_length= 1, max_length= 120)
    is_active: bool | None = None
    role: Role | None = None
    department_id: str | None = None



class LoginRequest(CamelBaseModel):
    username_or_email: str
    password: str



class RefreshRequest(CamelBaseModel):
    refresh_token: str



class LogoutRequest(CamelBaseModel):
    refresh_token: str



class PasswordChangeRequest(CamelBaseModel):
    old_password: str
    new_password: str = Field(min_length= 8, max_length= 64)



class PasswordResetRequest(CamelBaseModel):
    new_password: str = Field(min_length= 8, max_length= 64)



# ===== Output =====
class RequestRead(CamelBaseModel):
    id: str
    responsible_department_id: str
    created_by_user_id: str
    pole_category_id: str
    request_no: str
    receipt_no: str
    pj_no: str
    request_type: RequestType
    design_type: DesignType
    request_category: RequestCategory
    pole_kind: PoleKind | None = None
    company_name: str | None = None
    project_name: str | None = None
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime
    status: RequestStatus
    supersedes_request_id: str | None = None



class DepartmentRead(CamelBaseModel):
    id: str
    code: str
    name: str


    
class UserRead(CamelBaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: Role
    department_id: str | None = None
    is_active: bool
    is_verified: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime



class TokenPair(CamelBaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
