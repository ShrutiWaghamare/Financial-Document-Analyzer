import os
import uuid

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv

load_dotenv()

from crew_runner import run_crew, _get_pdf_from_data_folder
from database import init_db, get_db, AnalysisResult
from worker import analyze_document_task

app = FastAPI(title="Financial Document Analyzer")

DATA_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


@app.on_event("startup")
def startup():
    init_db()


# ─── 1. Health check ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "Financial Document Analyzer API is running"}


# ─── 2. Upload PDF → queue → poll for result ──────────────────────────────────

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    query: str = Form(default="Analyze this financial document for investment insights"),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF + query. Returns job_id immediately.
    Poll GET /result/{job_id} to check status and get result.
    The uploaded PDF is kept until you fetch the result, then deleted.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    job_id    = str(uuid.uuid4())
    # Save with UUID name so each upload is unique and won't conflict
    file_path = os.path.abspath(os.path.join(DATA_DIR, f"{job_id}.pdf"))

    with open(file_path, "wb") as f:
        f.write(await file.read())

    query = query.strip() or "Analyze this financial document for investment insights"

    job = AnalysisResult(
        job_id   = job_id,
        status   = "pending",
        query    = query,
        filename = file.filename,
    )
    db.add(job)
    db.commit()

    analyze_document_task.delay(job_id, query, file_path)

    return {
        "status" : "queued",
        "job_id" : job_id,
        "message": f"Document queued. Poll GET /result/{job_id} for updates.",
    }


# ─── 3. PDF already in data/ folder → queue → poll for result ─────────────────

@app.get("/analyze-data")
async def analyze_from_data_folder(
    query: str = "Analyze this financial document for investment insights",
    db: Session = Depends(get_db),
):
    """
    PDF already exists in the data/ folder (no upload needed).
    Returns job_id immediately. Poll GET /result/{job_id} for result.
    """
    file_path = _get_pdf_from_data_folder()
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="No PDF found in data/ folder. Upload one via POST /analyze."
        )

    job_id = str(uuid.uuid4())
    query  = query.strip() or "Analyze this financial document for investment insights"

    job = AnalysisResult(
        job_id   = job_id,
        status   = "pending",
        query    = query,
        filename = os.path.basename(file_path),
    )
    db.add(job)
    db.commit()

    analyze_document_task.delay(job_id, query, file_path)

    return {
        "status"  : "queued",
        "job_id"  : job_id,
        "filename": os.path.basename(file_path),
        "message" : f"Document queued. Poll GET /result/{job_id} for updates.",
    }


# ─── 4. Poll for result ────────────────────────────────────────────────────────

@app.get("/result/{job_id}")
async def get_result(job_id: str, db: Session = Depends(get_db)):
    """
    Check status and get result of a queued job.
    status: pending | processing | done | failed
    Once status is done, the uploaded PDF is cleaned up automatically.
    """
    job = db.query(AnalysisResult).filter_by(job_id=job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # ── Clean up uploaded PDF once result is fetched ───────────────────────────
    # Only delete UUID-named files (uploaded ones), not original files in data/
    if job.status == "done":
        uploaded_pdf = os.path.join(DATA_DIR, f"{job_id}.pdf")
        if os.path.exists(uploaded_pdf):
            try:
                os.remove(uploaded_pdf)
            except Exception:
                pass

    return {
        "job_id"     : job.job_id,
        "status"     : job.status,
        "query"      : job.query,
        "filename"   : job.filename,
        "result"     : job.result,
        "error"      : job.error,
        "output_file": job.output_file,
        "created_at" : job.created_at,
        "updated_at" : job.updated_at,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)