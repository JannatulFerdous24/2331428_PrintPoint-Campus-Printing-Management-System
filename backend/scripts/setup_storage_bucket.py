"""
Create the PRIVATE Supabase Storage bucket for uploaded print documents.

    python scripts/setup_storage_bucket.py            # DRY RUN (default): shows what would happen
    python scripts/setup_storage_bucket.py --execute  # actually creates the bucket

Safety:
- Only runs against the printpoint-dev project (project ref checked below) and never on Vercel.
- Dry run makes ONE read-only request (does the bucket already exist?) and changes nothing.
- --execute only CREATES a missing bucket. It never updates, empties or deletes a bucket:
  if the bucket already exists it only reports how its settings differ.
- The secret key is read from backend/.env and is never printed.
"""

import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEV_PROJECT_REF = "vxgubnunysotatnbfpip"  # printpoint-dev (Production is a separate project)

BUCKET_ID = "print-documents"
MAX_UPLOAD_BYTES = 4_000_000  # approved limit: stays under Vercel's 4.5 MB request-body limit
ALLOWED_MIME_TYPES = [
    "application/pdf",                                                          # .pdf
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
]
BUCKET_CONFIG = {
    "id": BUCKET_ID,
    "name": BUCKET_ID,
    "public": False,  # PRIVATE: files are only reachable through short signed links from the backend
    "file_size_limit": MAX_UPLOAD_BYTES,
    "allowed_mime_types": ALLOWED_MIME_TYPES,
}


def fail(msg: str) -> None:
    sys.exit(f"SAFETY STOP: {msg}")


def main() -> None:
    execute = "--execute" in sys.argv
    env = dotenv_values(BACKEND_DIR / ".env")
    if env.get("VERCEL") or "VERCEL" in __import__("os").environ:
        fail("refusing to run on Vercel")
    base = (env.get("SUPABASE_URL") or "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if base != f"https://{DEV_PROJECT_REF}.supabase.co":
        fail("SUPABASE_URL is not the printpoint-dev project")
    if not key:
        fail("SUPABASE_SERVICE_ROLE_KEY is empty")
    if (env.get("SUPABASE_STORAGE_BUCKET") or "") != BUCKET_ID:
        fail(f"SUPABASE_STORAGE_BUCKET in .env must be '{BUCKET_ID}'")

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    print(f"Mode:     {'EXECUTE' if execute else 'DRY RUN (nothing will be created or changed)'}")
    print(f"Project:  printpoint-dev ({DEV_PROJECT_REF})")

    with httpx.Client(base_url=f"{base}/storage/v1", headers=headers, timeout=30) as http:
        # Read-only: does the bucket exist already?
        res = http.get(f"/bucket/{BUCKET_ID}")
        exists = res.status_code == 200
        if not exists and res.status_code not in (400, 404):
            fail(f"unexpected answer while checking the bucket: HTTP {res.status_code}")
        print(f"Check:    GET /storage/v1/bucket/{BUCKET_ID} -> HTTP {res.status_code} "
              f"({'bucket EXISTS' if exists else 'bucket does not exist'})")

        if exists:
            current = res.json()
            diffs = {k: (current.get(k), v) for k, v in BUCKET_CONFIG.items()
                     if k not in ("id", "name") and current.get(k) != v}
            print("Result:   bucket already exists - this script never modifies existing buckets.")
            print("          settings differ:" if diffs else "          settings match the approved config.")
            for k, (have, want) in diffs.items():
                print(f"            {k}: current={have!r} approved={want!r}")
            return

        print("Would send (exactly one request):")
        print(f"          POST /storage/v1/bucket   (headers: apikey + Authorization = <secret key, hidden>)")
        print("          body:")
        for k, v in BUCKET_CONFIG.items():
            print(f"            {k}: {v!r}")
        if not execute:
            print("DRY RUN finished - nothing was created. Re-run with --execute after approval.")
            return

        res = http.post("/bucket", json=BUCKET_CONFIG)
        if res.status_code not in (200, 201):
            fail(f"bucket creation failed: HTTP {res.status_code} {res.text[:200]}")
        created = http.get(f"/bucket/{BUCKET_ID}").json()
        print("Created:  " + ", ".join(f"{k}={created.get(k)!r}" for k in
                                       ("id", "public", "file_size_limit", "allowed_mime_types")))
        if created.get("public") is not False:
            fail("bucket is NOT private - check the Supabase dashboard immediately")

    # Anonymous request (no key): a private bucket must not serve public URLs.
    anon = httpx.get(f"{base}/storage/v1/object/public/{BUCKET_ID}/does-not-exist.pdf", timeout=30)
    print(f"Verify:   anonymous public-URL request -> HTTP {anon.status_code} (expected 400/404: not public)")


if __name__ == "__main__":
    main()
