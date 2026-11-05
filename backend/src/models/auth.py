from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

class Credentials(BaseModel):
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


class LoginRequest(Credentials):
    role: Literal['user', 'admin'] = 'user'


class SignupRequest(Credentials):
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


class ProfileUpdate(UserUpdate):
    email: str | None = Field(default=None, min_length=3, max_length=254)

    @field_validator('name', 'surname', 'organization', mode='before')
    @classmethod
    def trim_profile_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('email')
    @classmethod
    def validate_profile_email(cls, value):
        if value is None:
            raise ValueError('Email cannot be null')
        return Credentials.normalize_email(value)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=8, max_length=1024)
    confirm_password: SecretStr = Field(min_length=8, max_length=1024)

    @model_validator(mode='after')
    def validate_password_change(self):
        new = self.new_password.get_secret_value()
        if new != self.confirm_password.get_secret_value():
            raise ValueError('New passwords do not match')
        if new == self.current_password.get_secret_value():
            raise ValueError('Choose a password different from your current password')
        if not (any(c.isupper() for c in new) and any(c.islower() for c in new)
                and any(c.isdigit() for c in new)
                and any(not c.isalnum() and not c.isspace() for c in new)):
            raise ValueError('Use at least 8 characters with uppercase, lowercase, a number and a symbol')
        return self


class AdminUserCreate(SignupRequest):
    role: Literal['user', 'admin'] = 'user'
    is_active: bool = True

    @field_validator('name', 'surname', 'organization', mode='before')
    @classmethod
    def trim_admin_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class AdminUserUpdate(ProfileUpdate):
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


class AdminUserResponse(UserResponse):
    analysis_count: int = 0
