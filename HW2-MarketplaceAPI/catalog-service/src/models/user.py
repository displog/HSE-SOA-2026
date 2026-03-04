from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Enum as SAEnum
from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import uuid4, UUID


class UserRole(str, Enum):
    USER = "USER"
    SELLER = "SELLER"
    ADMIN = "ADMIN"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str = Field(max_length=255)
    role: UserRole = Field(
        default=UserRole.USER,
        sa_column=Column(SAEnum(UserRole, native_enum=False), default=UserRole.USER),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
