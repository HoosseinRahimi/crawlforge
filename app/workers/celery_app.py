from celery import Celery

from app.config import get_settings

settings = get_settings()
celery = Celery("crawlforge", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    beat_schedule={
        "retention-cleanup": {"task": "app.workers.tasks.cleanup_retention", "schedule": 86400}
    },
)
