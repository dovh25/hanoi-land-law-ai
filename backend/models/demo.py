from typing import Any, Literal

from pydantic import BaseModel, Field


class DemoHistoryMessage(BaseModel):
    role: Literal["user", "assistant", "ai"]
    content: str = Field(min_length=1, max_length=2000)


class DemoChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    history: list[DemoHistoryMessage] = Field(default_factory=list, max_length=20)


class DemoSource(BaseModel):
    evidence_id: str
    chunk_id: str
    document_number: str
    document_title: str
    document_type: str = ""
    issuing_authority: str = ""
    article_number: str
    article_heading: str = ""
    source_url: str
    source_start: int
    source_end: int
    excerpt: str
    validity_status: Literal["unknown", "in_force", "expired", "partially_expired"] = "unknown"
    review_status: str = "technical_validation_only"
    corpus_label: str = "MVP_DEMO_CORPUS"


class DemoRateLimit(BaseModel):
    limit: int
    remaining: int


class DemoChatResponse(BaseModel):
    answer: str
    status: str
    sources: list[DemoSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rejected_citations: list[str] = Field(default_factory=list)
    llm_used: bool = False
    request_id: str
    abstention_reason: str | None = None
    corpus: dict[str, Any] = Field(default_factory=dict)
    rate_limit: DemoRateLimit | None = None
