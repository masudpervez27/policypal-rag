from pydantic import BaseModel, Field
from typing import Literal


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str
    session_id: str = Field(..., min_length=1, max_length=128)
    tenant: str = Field(default="default", min_length=1, max_length=64)
    top_k: int = Field(default=5, ge=1, le=20)


class SourceChunk(BaseModel):
    content: str
    source_file: str
    page: int | None = None
    score: float


class UploadResponse(BaseModel):
    tenant: str
    chunks_indexed: int
    files: list[str]
    message: str


class TenantsResponse(BaseModel):
    tenants: list[str]


class HistoryClearResponse(BaseModel):
    deleted: int
    session_id: str
