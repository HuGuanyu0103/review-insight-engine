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
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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

# CORS — allow frontend dev on any port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No-cache on all responses (dev mode)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

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


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file and trigger the analysis pipeline in background."""
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

    # Launch pipeline in background thread — returns immediately
    thread = threading.Thread(
        target=_run_pipeline_background,
        args=(job_id, str(input_path)),
        daemon=True,
    )
    thread.start()

    return JSONResponse({
        "job_id": job_id,
        "status": "accepted",
        "message": "Pipeline started in background",
    }, status_code=202)


def _infer_job_status(job_id: str) -> str:
    """Infer job status from filesystem when in-memory store is empty."""
    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists():
        return None
    report_path = job_dir / "reports" / "insight_report.json"
    if report_path.exists():
        return "completed"
    input_csv = job_dir / "input.csv"
    if input_csv.exists():
        return "running"  # has input, no report yet = was running
    return "pending"


@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    """Get the status of a pipeline job."""
    job = JOBS.get(job_id)
    if not job:
        # Fallback: check filesystem
        inferred = _infer_job_status(job_id)
        if inferred is None:
            raise HTTPException(404, f"Job {job_id} not found")
        return {"job_id": job_id, "status": inferred, "summary": None, "error": None}
    return JobStatus(**job)


@app.get("/api/report/{job_id}")
def get_report(job_id: str):
    """Get the generated insight report for a job."""
    report_path = OUTPUT_DIR / job_id / "reports" / "insight_report.json"
    if not report_path.exists():
        inferred = _infer_job_status(job_id)
        status_text = inferred or "unknown"
        raise HTTPException(404, f"Report not found for job {job_id}. Status: {status_text}")

    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/job/{job_id}/pools")
def get_job_pools(job_id: str):
    """Return three review pools with counts + content: all, filtered, hitl."""
    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(404, f"Job {job_id} not found")

    result = {"job_id": job_id, "pools": {}}

    # Pool 1: 全部评论 (from input.csv)
    input_csv = job_dir / "input.csv"
    if input_csv.exists():
        import csv as csv_mod
        all_reviews = []
        with open(input_csv, encoding="utf-8-sig") as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                all_reviews.append({
                    "review_id": row.get("review_id", ""),
                    "content": row.get("review_content", ""),
                    "rating": row.get("rating", ""),
                    "user_tier": row.get("user_tier", ""),
                    "product_name": row.get("product_name", ""),
                })
        result["pools"]["all"] = {"count": len(all_reviews), "label": "全部评论", "reviews": all_reviews}
    else:
        result["pools"]["all"] = {"count": 0, "label": "全部评论", "reviews": []}

    # Pool 2: 已拦截 (from filter_log.json)
    filter_log = job_dir / "structured" / "filter_log.json"
    if filter_log.exists():
        with open(filter_log, encoding="utf-8") as f:
            filtered = json.load(f)
        # Normalize: filter_log can be list of dicts or strings
        filtered_list = []
        for item in filtered:
            if isinstance(item, dict):
                filtered_list.append({
                    "review_id": item.get("review_id", ""),
                    "content": item.get("review_content", ""),
                    "reason": item.get("reason", item.get("filter_reason", "低质量评论")),
                })
            else:
                filtered_list.append({"review_id": "", "content": str(item), "reason": "低质量评论"})
        result["pools"]["filtered"] = {"count": len(filtered_list), "label": "已拦截评论", "reviews": filtered_list}
    else:
        result["pools"]["filtered"] = {"count": 0, "label": "已拦截评论", "reviews": []}

    # Pool 3: HITL 待复核 (from hitl_queue.csv)
    hitl_csv = job_dir / "hitl" / "hitl_queue.csv"
    if hitl_csv.exists():
        import csv as csv_mod
        hitl_items = []
        with open(hitl_csv, encoding="utf-8-sig") as f:
            reader = csv_mod.DictReader(f)
            for row in reader:
                hitl_items.append({
                    "review_id": row.get("review_id", ""),
                    "content": row.get("review_content", ""),
                    "reason": row.get("failure_reason", row.get("gate_reason", "待人工复核")),
                    "retry_count": row.get("retry_count", "0"),
                })
        result["pools"]["hitl"] = {"count": len(hitl_items), "label": "待人工复核", "reviews": hitl_items}
    else:
        result["pools"]["hitl"] = {"count": 0, "label": "待人工复核", "reviews": []}

    return result


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


# ---- Static Files (Frontend SPA) ----

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "website" / "app"

class NoCacheStaticFiles(StaticFiles):
    """Static files with Cache-Control: no-cache to avoid stale JS during dev."""
    async def __call__(self, scope, receive, send):
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"cache-control"] = b"no-cache, no-store, must-revalidate"
                message["headers"] = list(headers.items())
            await send(message)
        await super().__call__(scope, receive, send_wrapper)


if FRONTEND_DIR.exists():
    app.mount("/css", NoCacheStaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", NoCacheStaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    app.mount("/data", NoCacheStaticFiles(directory=str(FRONTEND_DIR / "data")), name="data")

    @app.get("/app/{full_path:path}")
    async def spa_fallback(full_path: str = ""):
        """Serve the SPA index.html for client-side routing."""
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "Frontend not found"}

    @app.get("/app")
    async def spa_root():
        """Serve the SPA entry point."""
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"error": "Frontend not found"}

    @app.get("/")
    async def redirect_to_app():
        """Redirect root to the frontend app."""
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/app")
else:
    @app.get("/")
    def root():
        return {"service": "商品评论洞察引擎", "version": "0.1.0", "status": "running"}


# ---- Health ----


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
