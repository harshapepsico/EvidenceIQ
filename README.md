# EvidenceIQ

EvidenceIQ now runs as two processes: a FastAPI backend that fetches Azure
DevOps data, and a Streamlit UI that renders the dashboard.

## Setup

Install the dependencies and make sure `ADO_PAT` is present in `.env`:

```powershell
python -m pip install -r requirements.txt
```

## Run

Start the backend from the repository root:

```powershell
uvicorn backend.app:app --reload
```

In a second terminal, start the UI:

```powershell
python -m streamlit run frontend/ui/app.py
```

The UI calls `http://127.0.0.1:8000` by default. To use another backend,
set `EVIDENCEIQ_API_URL` before starting Streamlit.

The backend exposes one dashboard operation:

```http
POST /dashboard/load
Content-Type: application/json

{
  "project": "MyProject",
  "plan_id": "12345",
  "suite_ids": "100,101"
}
```

`suite_ids` is optional. When omitted, the existing Azure DevOps service
discovers the plan's suites and recursively loads their child suites.

For large plans, ADO request concurrency and retry behavior can be tuned in
`.env` without changing the API request:

```text
ADO_MAX_WORKERS=4
ADO_MAX_RETRIES=4
ADO_BACKOFF_SECONDS=1
ADO_MAX_BACKOFF_SECONDS=30
```

The service honors numeric `Retry-After` responses. When retries are
exhausted while loading a suite, that suite is logged and skipped so other
suites can still be displayed.

Dashboard loads run as background jobs. The UI polls the job until its result
is ready, and completed results are cached in the backend for one hour. A
repeated request with the same project, plan, and suite IDs reuses that
cached result.

Dashboard records include `Bug Attached`: failed test cases show `Yes` or
`No` based on linked Azure DevOps Bug work items; passed and other outcomes
show `N/A`.


uvicorn backend.app:app --reload
python -m streamlit run frontend/ui/app.py