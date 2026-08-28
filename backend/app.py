"""FastAPI application for loading EvidenceIQ dashboard data."""

import json
import logging

import requests
from fastapi import FastAPI, HTTPException

from backend.schemas import DashboardRequest, DashboardResponse
from evidenceiq.processing.metrics import calculate_metrics
from evidenceiq.services.ado_service import fetch_test_points

logger = logging.getLogger(__name__)

app = FastAPI(title="EvidenceIQ API", version="1.0.0")

@app.get("/")
def home():
    return {"message": "EvidenceIQ API is live"}



@app.post("/dashboard/load", response_model=DashboardResponse)
def load_dashboard(request: DashboardRequest) -> DashboardResponse:
    """Fetch Azure DevOps test data and return dashboard-ready records."""
    try:
        dataframe = fetch_test_points(
            project=request.project.strip(),
            plan_id=request.plan_id.strip(),
            suite_ids=None,
            pat=None,
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
