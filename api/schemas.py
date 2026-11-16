
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogCreate(BaseModel):

    event_id: UUID

    timestamp: datetime

    application: str = Field(
        min_length=2,
        max_length=100
    )

    level: LogLevel

    message: str = Field(
        min_length=1,
        max_length=2000
    )

    response_time: int = Field(
        ge=0,
        le=600000
    )

    status_code: int = Field(
        ge=100,
        le=599
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value):
        if value.tzinfo is None:
            raise ValueError(
                "Timestamp must include a timezone"
            )
        return value.astimezone(timezone.utc)

    @field_validator("application")
    @classmethod
    def clean_application(cls, value):
        value = value.strip()

        if not value:
            raise ValueError(
                "Application cannot be empty"
            )

        return value

    @field_validator("message")
    @classmethod
    def validate_message(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty")
        return value


class LogBatch(BaseModel):

    logs: list[LogCreate] = Field(
        min_length=1,
        max_length=1000
    )


class LogAccepted(BaseModel):
    event_id: UUID
    status: str
    queue: str


class LogBatchAccepted(BaseModel):
    status: str
    accepted_count: int
    event_ids: list[UUID]
    queue: str
