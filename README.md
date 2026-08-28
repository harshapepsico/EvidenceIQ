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
python -m streamlit run evidenceiq/ui/app.py
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
