"""FastAPI wrapper for the 商品评论洞察引擎.

Provides RESTful endpoints for:
- CSV upload and pipeline trigger
- Pipeline status query
- Report retrieval
- RAG Q&A
- HITL review queue management
- Webhook integration (Feishu/DingTalk)
"""

import json
import uuid
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.pipeline.orchestrator import Pipeline
from src.pipeline.state import PipelineState, StageStatus
from src.rag.qa_engine import QAEngine
from src.models.extraction import ExtractedReview
from src.report.generator import generate_report

logger = logging.getLogger(__name__)

app = FastAPI(
    title="商品评论洞察引擎 API",
    description="AI-powered e-commerce review insight engine",
    version="0.1.0",
)

# In-memory job store (replace with DB for production)
JOBS: dict[str, dict] = {}
OUTPUT_DIR = Path("./outputs/api/")


# ---- Request/Response Models ----


class AskRequest(BaseModel):
    question: str
    n_results: int = 10


class AskResponse(BaseModel):
    answer: str
    citations: list[dict]
    retrieved_count: int


class HITLCorrection(BaseModel):
    review_id: str
    sentiment: str
    primary_category: str
    urgency_level: int
    core_issue_summary: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    summary: Optional[dict] = None
    error: Optional[str] = None


# ---- Background Pipeline Runner ----


def _run_pipeline_background(job_id: str, input_path: str):
    """Run pipeline in background and update job status."""
    try:
        JOBS[job_id]["status"] = "running"
        pipeline = Pipeline(
            input_path=input_path,
            output_dir=str(OUTPUT_DIR / job_id),
        )
        summary = pipeline.run()
        JOBS[job_id]["status"] = "completed"
        JOBS[job_id]["summary"] = summary
    except Exception as e:
        logger.exception("Pipeline job %s failed", job_id)
        JOBS[job_id]["status"] = "failed"
        JOBS[job_id]["error"] = str(e)


# ---- Endpoints ----


@app.get("/")
def root():
    return {"service": "商品评论洞察引擎", "version": "0.1.0", "status": "running"}


@app.post("/api/upload")
async def upload_csv(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
):
    """Upload a CSV file and trigger the analysis pipeline."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are accepted")

    job_id = uuid.uuid4().hex[:12]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    input_path = job_dir / "input.csv"
    content = await file.read()
    with open(input_path, "wb") as f:
        f.write(content)

    JOBS[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "input_file": str(input_path),
        "created_at": datetime.now().isoformat(),
    }

    # Launch pipeline in background
    if background_tasks:
        background_tasks.add_task(_run_pipeline_background, job_id, str(input_path))
    else:
        # Synchronous fallback
        _run_pipeline_background(job_id, str(input_path))

    return JSONResponse({
        "job_id": job_id,
        "status": "accepted",
        "message": "Pipeline started",
    }, status_code=202)


@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    """Get the status of a pipeline job."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return JobStatus(**job)


@app.get("/api/report/{job_id}")
def get_report(job_id: str):
    """Get the generated insight report for a job."""
    report_path = OUTPUT_DIR / job_id / "reports" / "insight_report.json"
    if not report_path.exists():
        raise HTTPException(404, f"Report not found for job {job_id}. Status: {JOBS.get(job_id, {}).get('status', 'unknown')}")

    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/ask")
def ask_question(req: AskRequest):
    """Natural language Q&A using RAG."""
    engine = QAEngine()
    result = engine.ask(question=req.question, n_results=req.n_results)
    return AskResponse(**result)


@app.get("/api/hitl/{job_id}")
def get_hitl_queue(job_id: str):
    """Get the HITL (Human-In-The-Loop) review queue for a job."""
    hitl_path = OUTPUT_DIR / job_id / "hitl" / "hitl_queue.csv"
    if not hitl_path.exists():
        return {"items": [], "count": 0}

    import csv
    items = []
    with open(hitl_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(row)

    return {"items": items, "count": len(items)}


@app.post("/api/hitl/{job_id}/{review_id}")
def submit_hitl_correction(job_id: str, review_id: str, correction: HITLCorrection):
    """Submit a manual correction for a HITL review item."""
    # In production: update the structured data and re-run reduce/report
    return {
        "status": "accepted",
        "message": f"Correction for {review_id} received",
        "correction": correction.model_dump(),
    }


@app.post("/api/webhook/feishu")
def feishu_webhook(payload: dict):
    """Feishu (飞书) card message webhook integration."""
    # Parse Feishu message, trigger pipeline or Q&A
    return {"status": "ok", "message": "Feishu webhook received"}


@app.post("/api/webhook/urgent")
def urgent_webhook(payload: dict):
    """Urgency level-3 alert webhook."""
    logger.warning("🚨 URGENT ALERT: %s", payload)
    return {"status": "ok", "alert_escalated": True}


# ---- Health ----


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
