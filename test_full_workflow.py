# test_full_workflow.py
"""End‑to‑end demo for the Autonomous Internship Agent.
The script:
1️⃣ Uploads a resume (uses the provided PDF file).
2️⃣ Creates a dummy job via the debug endpoint `/debug/create-job`.
3️⃣ Calls `/apply` with the returned `job_id`.
4️⃣ Prints the responses so you can see the flow.

Make sure the FastAPI server (`main.py`) is running on http://127.0.0.1:8000 before executing this script.
"""

import requests
from pathlib import Path

API_URL = "http://127.0.0.1:8000"

# ----------------------------------------------------------------------
# 1️⃣  Upload the resume – field name must be `file` as defined in the API.
# ----------------------------------------------------------------------
resume_path = Path(__file__).parent / "Manthan_Raut_Resume (1).pdf"
if not resume_path.is_file():
    raise FileNotFoundError(f"Resume file not found at {resume_path}")

with open(resume_path, "rb") as f:
    files = {"file": (resume_path.name, f, "application/pdf")}
    print("Uploading resume…")
    upload_resp = requests.post(f"{API_URL}/upload-resume", files=files)
    print("Upload response:", upload_resp.json())

# ----------------------------------------------------------------------
# 2️⃣  Create a dummy job (debug endpoint). This gives us a `job_id`.
# ----------------------------------------------------------------------
job_payload = {
    "title": "Software Engineer (Demo)",
    "company": "Acme Corp",
    "link": "https://indeed.com/viewjob?jk=demo123",
}
print("\nCreating dummy job…")
job_resp = requests.post(f"{API_URL}/debug/create-job", json=job_payload)
print(f"  HTTP {job_resp.status_code}")
if job_resp.status_code != 200:
    print("  Error:", job_resp.text)
    exit(1)
job_info = job_resp.json()
job_id = job_info.get("job_id")
print("Created job:", job_info)

# ----------------------------------------------------------------------
# 3️⃣  Apply to the job – the API expects `job_id` as a query parameter.
# ----------------------------------------------------------------------
print("\nApplying to the job…")
apply_resp = requests.post(f"{API_URL}/apply", params={"job_id": job_id})
print("Apply response:", apply_resp.json())

# ----------------------------------------------------------------------
# 4️⃣  Optional: fetch status summary.
# ----------------------------------------------------------------------
print("\nCurrent status summary:")
print(requests.get(f"{API_URL}/status").json())

print("\nDone. Check your WhatsApp (Twilio sandbox) for the approval prompt and reply 'yes' or 'no'.")
