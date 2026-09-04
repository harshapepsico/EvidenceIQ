"""Environment and runtime settings."""

import os
from dotenv import load_dotenv

load_dotenv()

ORG = "PepsiCoIT2"
API_VERSION = "7.1"
POINT_PAGE_SIZE = 1000
MAX_WORKERS = max(1, int(os.getenv("ADO_MAX_WORKERS", "4")))
ADO_MAX_RETRIES = int(os.getenv("ADO_MAX_RETRIES", "4"))
ADO_BACKOFF_SECONDS = float(os.getenv("ADO_BACKOFF_SECONDS", "1"))
ADO_MAX_BACKOFF_SECONDS = float(os.getenv("ADO_MAX_BACKOFF_SECONDS", "30"))
TEAM_ID = os.getenv("TEAM_ID","")
PROJECT_ID = os.getenv("PROJECT_ID")
DEVX_API_KEY = os.getenv("DEVX_API_KEY")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")


def get_pat() -> str:
    return os.getenv("ADO_PAT", "")
