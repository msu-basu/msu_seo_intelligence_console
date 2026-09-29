"""
auth.py
Secure, centralized Google Cloud authentication handler for MSU Analytics Pipeline.
Supports dual-mode authentication:
1. In-Memory Base64 (Production Cron Job / Zero-Disk-Files):
   Reads GOOGLE_CREDENTIALS_BASE64 directly from RAM.
2. File-Based (Local Development):
   Reads credentials/google_service_account.json from disk.
"""
import os
import json
import base64
from pathlib import Path
from typing import List, Optional
from google.oauth2 import service_account
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

def get_google_credentials(scopes: List[str], custom_path: Optional[str] = None) -> service_account.Credentials:
    """
    Returns authenticated Google Service Account credentials.
    Priority:
    1. GOOGLE_CREDENTIALS_BASE64 environment variable (in-memory, no files on disk).
    2. File at custom_path or GOOGLE_APPLICATION_CREDENTIALS (local file fallback).
    """
    # 1. Production Mode: In-Memory Base64 string
    raw_b64 = os.getenv("GOOGLE_CREDENTIALS_BASE64", "").strip()
    if raw_b64:
        try:
            decoded_bytes = base64.b64decode(raw_b64)
            key_dict = json.loads(decoded_bytes.decode("utf-8"))
            return service_account.Credentials.from_service_account_info(key_dict, scopes=scopes)
        except Exception as e:
            raise ValueError(f"Failed to decode GOOGLE_CREDENTIALS_BASE64 in-memory: {e}")

    # 2. Local Development Mode: Physical file on disk
    cred_path_raw = custom_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials/google_service_account.json")
    if not os.path.isabs(cred_path_raw):
        p = (project_root / cred_path_raw).resolve()
    else:
        p = Path(cred_path_raw)

    if p.exists():
        return service_account.Credentials.from_service_account_file(str(p), scopes=scopes)

    raise FileNotFoundError(
        f"No valid Google credentials found.\n"
        f"Provide GOOGLE_CREDENTIALS_BASE64 in the environment (for production)\n"
        f"or place your service account JSON key at {p} (for local dev)."
    )
