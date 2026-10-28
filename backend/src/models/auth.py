from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if value.count('@') != 1 or not all(value.split('@')) or any(c.isspace() for c in value):
            raise ValueError('Invalid email address')
        return value


class SignupRequest(LoginRequest):
    password: str = Field(min_length=8, max_length=1024)
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    organization: str = Field(default='', max_length=200)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, min_length=1, max_length=100)
    surname: str | None = Field(default=None, min_length=1, max_length=100)
    organization: str | None = Field(default=None, max_length=200)

    @field_validator('name', 'surname', 'organization')
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError('Field cannot be null')
        return value


class AdminUserUpdate(UserUpdate):
    role: Literal['user', 'admin'] | None = None
    is_active: bool | None = None

    @field_validator('role', 'is_active')
    @classmethod
    def reject_null_admin(cls, value):
        if value is None:
            raise ValueError('Field cannot be null')
        return value


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    surname: str
    organization: str
    role: Literal['user', 'admin']
    is_active: bool
    created_at: str


class TokenResponse(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = 'bearer'
    user: UserResponse
