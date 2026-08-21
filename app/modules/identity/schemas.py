from datetime import datetime

from pydantic import EmailStr, Field

from app.utils.base_schema import CamelBaseModel
from app.database.models.identity import Role



# ===== Input =====
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
