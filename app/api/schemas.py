from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator


def default_outputs() -> list[Literal["markdown", "html"]]:
    return ["markdown"]


class ScrapeRequest(BaseModel):
    url: HttpUrl
    render_js: bool | Literal["auto"] = "auto"
    output: list[Literal["markdown", "html"]] = Field(default_factory=default_outputs)
    timeout: int = Field(default=30, ge=1, le=60)

    @model_validator(mode="after")
    def unique_outputs(self) -> "ScrapeRequest":
        self.output = list(dict.fromkeys(self.output))
        return self


class CrawlRequest(BaseModel):
    url: HttpUrl
    max_depth: int = Field(default=3, ge=0, le=10)
    max_pages: int = Field(default=100, ge=1, le=1000)
    allow_external: bool = False
    concurrency: int = Field(default=5, ge=1, le=20)


class ExtractRequest(BaseModel):
    model_config = {"populate_by_name": True}
    url: HttpUrl
    schema_: dict[str, Any] = Field(alias="schema", min_length=1)
    render_js: bool | Literal["auto"] = "auto"
    timeout: int = Field(default=30, ge=1, le=60)


class ScrapeResponse(BaseModel):
    result_id: UUID | None = None
    url: str
    final_url: str
    status_code: int
    title: str | None
    html: str | None = None
    markdown: str | None = None
    metadata: dict[str, Any]
    scraping_method: str
    duration_ms: int


class JobResponse(BaseModel):
    job_id: UUID
    type: str
    status: str
    progress: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None


class PaginatedResults(BaseModel):
    items: list[ScrapeResponse]
    next_cursor: str | None = None
