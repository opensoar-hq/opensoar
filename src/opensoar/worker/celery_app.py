from celery import Celery

from opensoar.config import settings

celery_app = Celery(
    "opensoar",
    broker=settings.effective_celery_broker_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.autodiscover_tasks(["opensoar.worker"])

# Import task modules that are not auto-discovered by the default Celery
# conventions (which only discover `tasks.py` per package). These imports also
# register their Celery beat schedules on module-load.
import opensoar.worker.retention  # noqa: E402, F401
