"""Environment and runtime settings."""

import os
from dotenv import load_dotenv

load_dotenv()

ORG = "PepsiCoIT"
API_VERSION = "7.1"
POINT_PAGE_SIZE = 1000
MAX_WORKERS = min(20, os.cpu_count() * 4 if os.cpu_count() else 4)


def get_pat() -> str:
    return os.getenv("ADO_PAT", "")
