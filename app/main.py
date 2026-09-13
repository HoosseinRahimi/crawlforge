import base64
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CrawlRequest,
    ExtractRequest,
    JobResponse,
    PaginatedResults,
    ScrapeRequest,
    ScrapeResponse,
)
from app.auth.api_keys import require_api_key
from app.auth.rate_limit import enforce_rate_limit
from app.config import get_settings
from app.db.models import APIKey, Job, JobType, ScrapeResult
from app.db.session import SessionLocal, engine, get_session
from app.llm.provider import OpenAIProvider
from app.observability.logging import configure_logging
from app.observability.metrics import jobs_queued, requests_total
from app.scraper.browser_pool import BrowserPool
from app.scraper.engine import ScraperEngine
from app.workers.tasks import run_job

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.browser = BrowserPool(settings.browser_pool_size)
    try:
        await app.state.browser.start()
    except Exception:
        await app.state.browser.stop()
        app.state.browser = None
    app.state.engine = ScraperEngine(settings, app.state.browser)
    if settings.environment != "production":
        from app.db.models import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    if app.state.browser:
        await app.state.browser.stop()
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(title="CrawlForge", version="0.1.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = (
        exc.detail
        if isinstance(exc.detail, dict)
        else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    )
    code = detail.get("code", "HTTP_ERROR")
    message = detail.get("message", "request failed")
    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": getattr(exc, "code", "INTERNAL_ERROR"), "message": "request failed"}},
        status_code=500,
    )


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    response = await call_next(request)
    requests_total.labels(request.method, request.url.path, response.status_code).inc()
    key = getattr(request.state, "rate_limit", None)
    if key:
        response.headers["RateLimit-Limit"] = str(key[0])
        response.headers["RateLimit-Remaining"] = str(key[1])
        response.headers["RateLimit-Reset"] = str(key[2])
    return response


async def guarded_key(request: Request, key: APIKey = Depends(require_api_key)) -> APIKey:
    await enforce_rate_limit(request, key, request.app.state.redis)
    return key


def output_model(result: Any, result_id: UUID | None = None) -> ScrapeResponse:
    return ScrapeResponse(
        result_id=result_id,
        url=result.url,
        final_url=result.final_url,
        status_code=result.status_code,
        title=result.title,
        html=result.html,
        markdown=result.markdown,
        metadata=result.metadata,
        scraping_method=result.scraping_method,
        duration_ms=result.duration_ms,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        async with SessionLocal() as session:
            await session.execute(select(1))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "error"
    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    ok = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ready" if ok else "not_ready", "dependencies": checks},
        status_code=200 if ok else 503,
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/scrape", response_model=ScrapeResponse)
async def scrape(
    request: ScrapeRequest,
    http_request: Request,
    key: APIKey = Depends(guarded_key),
    session: AsyncSession = Depends(get_session),
):
    result = await http_request.app.state.engine.scrape(
        str(request.url),
        render_js=request.render_js,
        outputs=request.output,
        timeout=request.timeout,
    )
    row = ScrapeResult(
        url=result.url,
        final_url=result.final_url,
        status_code=result.status_code,
        title=result.title,
        html=(result.html or "")[: settings.max_stored_html_bytes] or None,
        markdown=(result.markdown or "")[: settings.max_stored_markdown_bytes] or None,
        metadata_json=result.metadata,
        scraping_method=result.scraping_method,
        duration_ms=result.duration_ms,
        html_truncated=bool(result.html and len(result.html) > settings.max_stored_html_bytes),
        markdown_truncated=bool(
            result.markdown and len(result.markdown) > settings.max_stored_markdown_bytes
        ),
    )
    session.add(row)
    await session.commit()
    return output_model(result, row.id)


@app.post("/v1/jobs", response_model=JobResponse, status_code=202)
async def create_job(
    request: ScrapeRequest,
    key: APIKey = Depends(guarded_key),
    session: AsyncSession = Depends(get_session),
):
    job = Job(
        api_key_id=key.id,
        job_type=JobType.SCRAPE,
        request={
            "url": str(request.url),
            "render_js": request.render_js,
            "outputs": request.output,
            "timeout": request.timeout,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    run_job.delay(str(job.id))
    jobs_queued.inc()
    return JobResponse(
        job_id=job.id,
        type=job.job_type,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
    )


@app.post("/v1/crawl", response_model=JobResponse, status_code=202)
async def create_crawl(
    request: CrawlRequest,
    key: APIKey = Depends(guarded_key),
    session: AsyncSession = Depends(get_session),
):
    job = Job(
        api_key_id=key.id,
        job_type=JobType.CRAWL,
        request={
            "url": str(request.url),
            "max_depth": request.max_depth,
            "max_pages": request.max_pages,
            "allow_external": request.allow_external,
            "concurrency": request.concurrency,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    run_job.delay(str(job.id))
    jobs_queued.inc()
    return JobResponse(
        job_id=job.id,
        type=job.job_type,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
    )


@app.get("/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID, key: APIKey = Depends(guarded_key), session: AsyncSession = Depends(get_session)
):
    job = (
        await session.execute(select(Job).where(Job.id == job_id, Job.api_key_id == key.id))
    ).scalar_one_or_none()
    if not job:
        return JSONResponse(
            {"error": {"code": "JOB_NOT_FOUND", "message": "job not found"}}, status_code=404
        )
    error = (
        {"code": str(job.error_code), "message": str(job.error_message)} if job.error_code else None
    )
    return JobResponse(
        job_id=job.id,
        type=job.job_type,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=job.result_summary,
        error=error,
    )


@app.get("/v1/jobs/{job_id}/results", response_model=PaginatedResults)
async def get_results(
    job_id: UUID,
    cursor: str | None = None,
    limit: int = 50,
    key: APIKey = Depends(guarded_key),
    session: AsyncSession = Depends(get_session),
):
    limit = min(max(limit, 1), 100)
    query = (
        select(ScrapeResult)
        .join(Job)
        .where(ScrapeResult.job_id == job_id, Job.api_key_id == key.id)
        .order_by(ScrapeResult.created_at, ScrapeResult.id)
        .limit(limit + 1)
    )
    if cursor:
        query = query.offset(int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    rows = list((await session.execute(query)).scalars())
    next_cursor = (
        base64.urlsafe_b64encode(str((int(cursor) if cursor else 0) + limit).encode()).decode()
        if len(rows) > limit
        else None
    )
    return PaginatedResults(
        items=[
            ScrapeResponse(
                result_id=row.id,
                url=row.url,
                final_url=row.final_url,
                status_code=row.status_code,
                title=row.title,
                html=row.html,
                markdown=row.markdown,
                metadata=row.metadata_json,
                scraping_method=row.scraping_method,
                duration_ms=row.duration_ms,
            )
            for row in rows[:limit]
        ],
        next_cursor=next_cursor,
    )


@app.post("/v1/extract")
async def extract(
    request: ExtractRequest, http_request: Request, key: APIKey = Depends(guarded_key)
):
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail={"code": "LLM_DISABLED", "message": "LLM provider is not configured"},
        )
    provider = OpenAIProvider(settings)
    result = await http_request.app.state.engine.scrape(
        str(request.url), render_js=request.render_js, outputs=["markdown"], timeout=request.timeout
    )
    data = await provider.extract(result.markdown or "", request.schema_)
    return {
        "url": result.final_url,
        "data": data,
        "metadata": result.metadata,
        "duration_ms": result.duration_ms,
    }
