"""
Celery worker for background analysis.

Windows:  celery -A worker.celery_app worker --loglevel=info --pool=solo
Linux:    celery -A worker.celery_app worker --loglevel=info
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

from celery import Celery

REDIS_URL   = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
OUTPUTS_DIR = os.path.join(_PROJECT_ROOT, "outputs")

celery_app = Celery(
    "financial_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    worker_prefetch_multiplier=1,
)

if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"


def _ensure_project_on_path():
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    os.chdir(_PROJECT_ROOT)


def _write_output_file(job_id: str, result_text: str) -> str | None:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(OUTPUTS_DIR, f"{job_id}.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(result_text)
        return path
    except Exception:
        return None


@celery_app.task(bind=True, name="analyze_document")
def analyze_document_task(self, job_id: str, query: str, file_path: str):
    _ensure_project_on_path()

    from crew_runner import run_crew
    from database import SessionLocal, AnalysisResult

    # ── Debug logging ──────────────────────────────────────────────────────────
    logger.info(f"[worker] job_id   : {job_id}")
    logger.info(f"[worker] file_path: {file_path}")
    logger.info(f"[worker] exists   : {os.path.exists(file_path)}")

    # ── Abort early if file missing ────────────────────────────────────────────
    if not os.path.exists(file_path):
        db = SessionLocal()
        try:
            job = db.query(AnalysisResult).filter_by(job_id=job_id).first()
            if job:
                job.status = "failed"
                job.error  = f"PDF file not found at: {file_path}"
                db.commit()
        finally:
            db.close()
        return  # no retry — file is gone

    db  = SessionLocal()
    job = None

    try:
        job = db.query(AnalysisResult).filter_by(job_id=job_id).first()
        if not job:
            return

        job.status = "processing"
        db.commit()

        result      = run_crew(query=query, file_path=file_path)
        result_text = str(result)

        job.status = "done"
        job.result = result_text

        output_path = _write_output_file(job_id, result_text)
        if output_path:
            job.output_file = output_path

        db.commit()

        # ── NOTE: File is NOT deleted here ─────────────────────────────────────
        # Deletion is handled by main.py GET /result/{job_id} after user reads result
        # This prevents race conditions where worker deletes file before agents finish

    except Exception as e:
        logger.error(f"[worker] Task failed: {e}")
        if job:
            job.status = "failed"
            job.error  = str(e)
            db.commit()
        # Only retry if file still exists
        if os.path.exists(file_path):
            raise self.retry(exc=e, countdown=10, max_retries=2)

    finally:
        db.close()