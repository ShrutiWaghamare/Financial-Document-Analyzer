import os
import uuid

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

from crew_runner import run_crew, _get_pdf_from_data_folder
from database import init_db, get_db, AnalysisResult

app = FastAPI(title="Financial Document Analyzer")

DATA_DIR = "data"
OUTPUTS_DIR = os.environ.get("OUTPUTS_DIR", "outputs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


# ─── Sync: analyze first PDF in data/ (no upload) ─────────────────────────────

@app.get("/")
async def root():
    """Health check."""
    return {"message": "Financial Document Analyzer API is running"}


@app.get("/analyze-data")
async def analyze_from_data_folder(
    query: str = "Analyze this financial document for investment insights",
):
    """Analyze the first PDF in the data/ folder. Synchronous; no queue."""
    try:
        response = run_crew(query=query.strip(), file_path=None)
        return {
            "status": "success",
            "query": query,
            "analysis": str(response),
            "source": "data_folder",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Async queue: upload PDF, get job_id, poll for result ─────────────────────

@app.post("/analyze")
async def analyze_queued(
    file: UploadFile = File(...),
    query: str = Form(default="Analyze this financial document for investment insights"),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF and queue analysis. Returns job_id immediately.
    Poll GET /result/{job_id} for status and result. Result is also written to outputs/{job_id}.txt.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id = str(uuid.uuid4())
    file_path = os.path.join(DATA_DIR, f"{job_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    query = (query or "").strip() or "Analyze this financial document for investment insights"

    job = AnalysisResult(
        job_id=job_id,
        status="pending",
        query=query,
        filename=file.filename,
    )
    db.add(job)
    db.commit()

    # Pass absolute path so Celery worker (possibly different cwd) can find the PDF
    abs_file_path = os.path.abspath(file_path)
    from worker import analyze_document_task
    analyze_document_task.delay(job_id, query, abs_file_path)

    return {
        "status": "queued",
        "job_id": job_id,
        "message": "Document queued for analysis. Poll GET /result/{job_id} for updates. Result is also saved to outputs/.",
    }


@app.get("/result/{job_id}")
async def get_result(job_id: str, db: Session = Depends(get_db)):
    """Get status and result of an analysis job. status: pending | processing | done | failed."""
    job = db.query(AnalysisResult).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "query": job.query,
        "filename": job.filename,
        "result": job.result,
        "error": job.error,
        "output_file": job.output_file,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@app.get("/history")
async def get_history(db: Session = Depends(get_db)):
    """List all analysis jobs, newest first."""
    jobs = db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).all()
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "query": j.query,
            "filename": j.filename,
            "output_file": j.output_file,
            "created_at": j.created_at,
        }
        for j in jobs
    ]


@app.delete("/result/{job_id}")
async def delete_result(job_id: str, db: Session = Depends(get_db)):
    """Delete a job record from the database. Does not remove outputs/ file."""
    job = db.query(AnalysisResult).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    db.delete(job)
    db.commit()
    return {"message": f"Job {job_id} deleted."}


# ─── Optional: synchronous upload (immediate response, no queue) ───────────────

@app.post("/analyze-sync")
async def analyze_sync(
    file: UploadFile = File(...),
    query: str = Form(default="Analyze this financial document for investment insights"),
):
    """Upload a PDF and get analysis in the response (synchronous). No queue or DB."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id = str(uuid.uuid4())
    file_path = os.path.join(DATA_DIR, f"sync_{job_id}.pdf")
    try:
        with open(file_path, "wb") as f:
            f.write(await file.read())
        q = (query or "").strip() or "Analyze this financial document for investment insights"
        response = run_crew(query=q, file_path=file_path)
        return {
            "status": "success",
            "query": q,
            "analysis": str(response),
            "file_processed": file.filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
