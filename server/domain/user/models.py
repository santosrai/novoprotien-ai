"""User domain models."""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class UserCreate(BaseModel):
    """Model for user registration."""
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    """Model for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Model for user response."""
    id: str
    email: str
    username: str
    role: UserRole
    email_verified: bool
    credits: int
    created_at: datetime
    last_login: Optional[datetime] = None


class CreditTransaction(BaseModel):
    """Model for credit transaction."""
    id: str
    user_id: str
    amount: int
    transaction_type: str
    description: Optional[str] = None
    related_job_id: Optional[str] = None
    created_at: datetime


class UsageHistory(BaseModel):
    """Model for usage history."""
    id: str
    user_id: str
    action_type: str
    resource_consumed: dict
    metadata: dict
    created_at: datetime


class UserReport(BaseModel):
    """Model for user report."""
    id: str
    user_id: str
    report_type: str
    title: str
    description: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    admin_notes: Optional[str] = None
    assigned_admin_id: Optional[str] = None

