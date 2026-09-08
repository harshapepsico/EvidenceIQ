"""FastAPI application for loading EvidenceIQ dashboard data."""

import json
import hashlib
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

import requests
from fastapi import FastAPI, HTTPException, status

from backend.schemas import DashboardRequest, DashboardResponse
from backend.processing.metrics import calculate_metrics
from backend.services.ado_service import fetch_test_points

logger = logging.getLogger(__name__)

app = FastAPI(title="EvidenceIQ API", version="1.0.0")
job_executor = ThreadPoolExecutor(max_workers=2)
job_lock = threading.Lock()
dashboard_jobs: Dict[str, Dict[str, Any]] = {}
JOB_TTL_SECONDS = 3600

@app.get("/")
def home():
    return {"message": "EvidenceIQ API is live"}


def _request_key(request: DashboardRequest) -> str:
    pat_digest = hashlib.sha256(
        request.pat.get_secret_value().encode("utf-8")
    ).hexdigest()
    return json.dumps(
        {
            "project": request.project.strip(),
            "plan_id": request.plan_id.strip(),
            "suite_ids": (request.suite_ids or "").strip(),
            "pat": pat_digest,
        },
        sort_keys=True,
    )


def _remove_expired_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    expired = [
        job_id
        for job_id, job in dashboard_jobs.items()
        if job.get("status") == "completed" and job.get("updated_at", 0) < cutoff
    ]
    for job_id in expired:
        dashboard_jobs.pop(job_id, None)


def _load_dashboard_job(job_id: str, request: DashboardRequest) -> None:
    try:
        pat = request.pat.get_secret_value()
        with job_lock:
            dashboard_jobs[job_id]["status"] = "running"
            dashboard_jobs[job_id]["updated_at"] = time.time()

        def update_progress(completed: int, total: int) -> None:
            percentage = round(completed / total * 100) if total else 100
            with job_lock:
                dashboard_jobs[job_id].update(
                    completed_suites=completed,
                    total_suites=total,
                    progress=percentage,
                    updated_at=time.time(),
                )

        dataframe = fetch_test_points(
            project=request.project.strip(),
            plan_id=request.plan_id.strip(),
            suite_ids=None,
            pat=pat,
            suite_ids_input=(request.suite_ids or "").strip(),
            progress_callback=update_progress,
        )
        result = {
            "records": json.loads(dataframe.to_json(orient="records")),
            "metrics": calculate_metrics(dataframe),
        }
        with job_lock:
            dashboard_jobs[job_id].update(
                status="completed", progress=100, result=result, updated_at=time.time()
            )
    except Exception:
        logger.exception("Unexpected error while loading dashboard job %s", job_id)
        with job_lock:
            dashboard_jobs[job_id].update(
                status="failed",
                error="Unable to load dashboard data.",
                updated_at=time.time(),
            )


@app.post("/dashboard/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_dashboard_job(request: DashboardRequest) -> Dict[str, str]:
    """Start or reuse a dashboard load without holding the HTTP request open."""
    request_key = _request_key(request)
    with job_lock:
        _remove_expired_jobs()
        for job_id, job in dashboard_jobs.items():
            if job.get("request_key") == request_key and job.get("status") in {
                "queued", "running", "completed"
            }:
                return {"job_id": job_id, "status": job["status"]}

        job_id = uuid.uuid4().hex
        dashboard_jobs[job_id] = {
            "request_key": request_key,
            "status": "queued",
            "progress": 0,
            "completed_suites": 0,
            "total_suites": 0,
            "updated_at": time.time(),
        }
        job_executor.submit(_load_dashboard_job, job_id, request)
    return {"job_id": job_id, "status": "queued"}

@app.get("/dashboard/jobs/{job_id}")
def get_dashboard_job(job_id: str) -> Dict[str, Any]:
    with job_lock:
        _remove_expired_jobs()
        job = dashboard_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Dashboard job not found.")
        return {
            "job_id": job_id,
            "status": job["status"],
            "progress": job.get("progress", 0),
            "completed_suites": job.get("completed_suites", 0),
            "total_suites": job.get("total_suites", 0),
            "error": job.get("error"),
        }


@app.get("/dashboard/jobs/{job_id}/result", response_model=DashboardResponse)
def get_dashboard_result(job_id: str) -> DashboardResponse:
    with job_lock:
        job = dashboard_jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Dashboard job not found.")
        if job["status"] != "completed":
            raise HTTPException(status_code=409, detail="Dashboard job is not completed.")
        return DashboardResponse(**job["result"])



@app.post("/dashboard/load", response_model=DashboardResponse)
def load_dashboard(request: DashboardRequest) -> DashboardResponse:
    """Fetch Azure DevOps test data and return dashboard-ready records."""
    try:
        dataframe = fetch_test_points(
            project=request.project.strip(),
            plan_id=request.plan_id.strip(),
            suite_ids=None,
            pat=request.pat.get_secret_value(),
            suite_ids_input=(request.suite_ids or "").strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Azure DevOps request failed: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error while loading the dashboard")
        raise HTTPException(
            status_code=500,
            detail="Unable to load dashboard data.",
        ) from exc

    # pandas' JSON conversion changes NaN/NaT values to JSON null.
    records = json.loads(dataframe.to_json(orient="records"))
    return DashboardResponse(
        records=records,
        metrics=calculate_metrics(dataframe),
    )
