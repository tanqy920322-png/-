"""Redis/DB worker stub for later image and floor-plan jobs.

The API records a stub result immediately so the demo does not wait on a model.
This process acknowledges queued jobs and never calls DashScope, Volcengine,
Qwen-VL, or Doubao.
"""

import logging

from sqlalchemy import select

from app.database import get_engine, get_session_factory
from app.models import Base, WorkerJob
from app.models import utcnow
from app.services.queue import get_queue

logger = logging.getLogger("worker")


def acknowledge(db, job_id: str) -> None:
    job = db.get(WorkerJob, job_id)
    if job is None:
        logger.info("skip missing job %s", job_id)
        return
    result = dict(job.result or {})
    if result.get("worker_ack"):
        return
    result["worker_ack"] = True
    result["worker_note"] = "队列消费者已确认。图像与识图适配器尚未接入，不调用外部模型。"
    job.result = result
    job.updated_at = utcnow()
    db.commit()
    logger.info("acked %s (%s)", job.id, job.kind)


def sweep(db) -> None:
    rows = db.scalars(
        select(WorkerJob).where(WorkerJob.status == "stub_completed").order_by(WorkerJob.created_at.desc()).limit(50)
    ).all()
    for job in rows:
        if not (job.result or {}).get("worker_ack"):
            acknowledge(db, job.id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Base.metadata.create_all(get_engine())
    queue = get_queue()
    factory = get_session_factory()
    logger.info("AI worker stub started")
    while True:
        job_id = queue.blocking_pop(timeout=5)
        db = factory()
        try:
            if job_id:
                acknowledge(db, job_id)
            sweep(db)
        finally:
            db.close()


if __name__ == "__main__":
    main()
