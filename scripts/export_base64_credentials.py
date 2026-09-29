"""
export_base64_credentials.py
Helper utility to encode your Service Account JSON key into a Base64 string
for zero-file production cron job deployments.
"""
import os
import sys
import base64
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
json_path = project_root / "credentials" / "google_service_account.json"

if not json_path.exists():
    print(f"[ERROR] Service account file not found at: {json_path}")
    sys.exit(1)

with open(json_path, "rb") as f:
    b64_string = base64.b64encode(f.read()).decode("utf-8")

print("\n" + "=" * 70)
print("     BASE64 ENCODED GOOGLE SERVICE ACCOUNT CREDENTIALS")
print("=" * 70)
print("\nCopy the single line below and set it as an environment variable in production:\n")
print(f"GOOGLE_CREDENTIALS_BASE64={b64_string}")
print("\n" + "=" * 70)
print("[OK] When this variable is set on your server, you can delete all .json files!")
print("=" * 70 + "\n")
