from celery import Celery
from kombu import Queue

from opensoar.config import settings
from opensoar.worker.routing import QUEUE_DEFAULT, QUEUE_HIGH, QUEUE_LOW

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
    # ── Clustered workers / priority queues (issue #85) ─────────────────────
    # Three named queues; a worker process consumes one or more of them via
    # ``celery worker -Q high,default`` (hot path) or ``-Q low`` (background).
    task_default_queue=QUEUE_DEFAULT,
    task_queues=(
        Queue(QUEUE_HIGH),
        Queue(QUEUE_DEFAULT),
        Queue(QUEUE_LOW),
    ),
    # Static routing: observable enrichment is always background work.
    # Playbook execution is routed dynamically at enqueue time (see
    # ``opensoar.worker.tasks.execute_playbook_task``) because the queue
    # depends on each playbook's declared priority.
    task_routes={
        "opensoar.enrich_observable": {"queue": QUEUE_LOW},
    },
)

celery_app.autodiscover_tasks(["opensoar.worker"])
