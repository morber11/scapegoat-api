from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class ChatRequest(BaseModel):
    messages: list[ChatMessage]

    @model_validator(mode="after")
    def first_message_must_be_user(self) -> ChatRequest:
        if not self.messages or self.messages[0].role != MessageRole.USER:
            raise ValueError("the first message must have role 'user'")
        return self


class ChatResponse(BaseModel):
    messages: list[ChatMessage]

