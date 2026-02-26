"""
Celery worker for background analysis. Runs CrewAI crew and saves result to DB and outputs/ folder.
Start Redis, then: celery -A worker.celery_app worker --loglevel=info
On Windows use: celery -A worker.celery_app worker --loglevel=info --pool=solo
"""
import os
import sys

# Ensure project root is on path so worker can import crew_runner, database, etc.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from celery import Celery
from database import SessionLocal, AnalysisResult

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", "outputs")

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
# On Windows the default pool causes PermissionError (Access is denied). Use solo pool.
if sys.platform == "win32":
    celery_app.conf.worker_pool = "solo"


def _write_output_file(job_id: str, result_text: str) -> str | None:
    """Write analysis result to outputs/{job_id}.txt. Returns path or None."""
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(OUTPUTS_DIR, f"{job_id}.txt")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(result_text)
        return path
    except Exception:
        return None


def _get_run_crew():
    """Import run_crew from crew_runner; ensures project root is on path for Celery worker."""
    _root = os.path.dirname(os.path.abspath(__file__))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    import crew_runner
    return crew_runner.run_crew


@celery_app.task(bind=True, name="analyze_document")
def analyze_document_task(self, job_id: str, query: str, file_path: str):
    """
    Background task: run CrewAI crew, save result to DB and to outputs/ folder.
    Imports run_crew from crew_runner to avoid circular import with main.
    """
    run_crew = _get_run_crew()

    db = SessionLocal()
    job = None
    try:
        job = db.query(AnalysisResult).filter_by(job_id=job_id).first()
        if not job:
            return

        job.status = "processing"
        db.commit()

        result = run_crew(query=query, file_path=file_path)
        result_text = str(result)

        job.status = "done"
        job.result = result_text
        output_path = _write_output_file(job_id, result_text)
        if output_path:
            job.output_file = output_path
        db.commit()
        # Remove file only after success so retries still have the PDF
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    except Exception as e:
        if job:
            job.status = "failed"
            job.error = str(e)
            db.commit()
        raise self.retry(exc=e, countdown=10, max_retries=2)

    finally:
        db.close()
