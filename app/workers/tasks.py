import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, update

from app.config import get_settings
from app.crawler.crawler import Crawler
from app.db.models import Job, JobStatus, JobType, ScrapeResult
from app.db.session import SessionLocal
from app.observability.metrics import jobs_queued
from app.scraper.browser_pool import BrowserPool
from app.scraper.engine import ScraperEngine
from app.workers.celery_app import celery


async def _run_job(job_id: str) -> None:
    settings = get_settings()
    pool = BrowserPool(settings.browser_pool_size)
    browser: BrowserPool | None = pool
    try:
        await pool.start()
    except Exception:
        browser = None
    engine = ScraperEngine(settings, browser)
    async with SessionLocal() as session:
        job = await session.get(Job, UUID(job_id))
        if not job:
            return
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        await session.commit()
        started = time.perf_counter()
        try:
            if job.job_type == JobType.SCRAPE:
                result = await engine.scrape(**job.request)
                rows = [result]
            else:
                request = job.request
                rows = await Crawler(
                    engine,
                    concurrency=request.get("concurrency", 5),
                    delay=settings.host_delay_seconds,
                ).crawl(
                    request["url"],
                    max_depth=request["max_depth"],
                    max_pages=request["max_pages"],
                    allow_external=request["allow_external"],
                )
            for result in rows:
                html = result.html or ""
                markdown = result.markdown or ""
                row = ScrapeResult(
                    job_id=job.id,
                    url=result.url,
                    final_url=result.final_url,
                    status_code=result.status_code,
                    title=result.title,
                    html=html[: settings.max_stored_html_bytes] or None,
                    markdown=markdown[: settings.max_stored_markdown_bytes] or None,
                    metadata_json=result.metadata,
                    scraping_method=result.scraping_method,
                    duration_ms=result.duration_ms,
                    html_truncated=len(html) > settings.max_stored_html_bytes,
                    markdown_truncated=len(markdown) > settings.max_stored_markdown_bytes,
                )
                session.add(row)
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.result_summary = {
                "pages": len(rows),
                "urls": [item.final_url for item in rows[:20]],
            }
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_code = getattr(exc, "code", "SCRAPE_FAILED")
            job.error_message = str(exc)
        job.duration_ms = int((time.perf_counter() - started) * 1000)
        job.completed_at = datetime.now(UTC)
        await session.commit()
    if browser:
        await browser.stop()
    jobs_queued.dec()


@celery.task(
    bind=True, autoretry_for=(ConnectionError, TimeoutError), retry_backoff=True, max_retries=2
)
def run_job(self: Any, job_id: str) -> None:
    asyncio.run(_run_job(job_id))


@celery.task
def cleanup_retention() -> None:
    asyncio.run(_cleanup())


async def _cleanup() -> None:
    settings = get_settings()
    async with SessionLocal() as session:
        body_cutoff = datetime.now(UTC) - timedelta(days=settings.retention_body_days)
        record_cutoff = datetime.now(UTC) - timedelta(days=settings.retention_record_days)
        await session.execute(
            update(ScrapeResult)
            .where(ScrapeResult.created_at < body_cutoff)
            .values(html=None, markdown=None)
        )
        await session.execute(delete(ScrapeResult).where(ScrapeResult.created_at < record_cutoff))
        await session.execute(delete(Job).where(Job.created_at < record_cutoff))
        await session.commit()
