"""
Private document storage (Supabase Storage bucket `print-documents`).

The backend is the ONLY thing that talks to the bucket, using the secret key from
backend/.env (never sent to the browser). Students and staff never get a public
URL: after the backend checks their permission it hands out a signed link that
expires after SIGNED_URL_SECONDS.

Tests use MemoryStorage (no network); see tests/test_documents.py.
"""

import logging
import os
from functools import lru_cache
from typing import Optional, Protocol
from urllib.parse import quote

import httpx
from fastapi import HTTPException

log = logging.getLogger("printpoint")
SIGNED_URL_SECONDS = 60


class Storage(Protocol):
    def upload(self, path: str, data: bytes, content_type: str) -> None: ...
    def delete(self, path: str) -> None: ...
    def signed_url(self, path: str, download_name: str) -> str: ...


class StorageError(Exception):
    pass


class SupabaseStorage:
    def __init__(self, base_url: str, key: str, bucket: str):
        self.base = f"{base_url.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    def _call(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            res = httpx.request(method, f"{self.base}{path}", headers={**self.headers, **kw.pop("headers", {})},
                                timeout=30, **kw)
        except httpx.HTTPError as exc:
            raise StorageError(f"storage unreachable: {exc.__class__.__name__}") from exc
        if res.status_code >= 400:
            raise StorageError(f"storage error HTTP {res.status_code}")
        return res

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self._call("POST", f"/object/{self.bucket}/{quote(path)}", content=data,
                   headers={"Content-Type": content_type, "x-upsert": "false"})

    def delete(self, path: str) -> None:
        self._call("DELETE", f"/object/{self.bucket}", json={"prefixes": [path]})

    def signed_url(self, path: str, download_name: str) -> str:
        res = self._call("POST", f"/object/sign/{self.bucket}/{quote(path)}",
                         json={"expiresIn": SIGNED_URL_SECONDS})
        signed = res.json()["signedURL"]  # "/object/sign/<bucket>/<path>?token=..."
        return f"{self.base}{signed}&download={quote(download_name)}"


class MemoryStorage:
    """In-memory stand-in used by the automated tests."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        if path in self.objects:
            raise StorageError("object exists")
        self.objects[path] = (data, content_type)

    def delete(self, path: str) -> None:
        self.objects.pop(path, None)

    def signed_url(self, path: str, download_name: str) -> str:
        if path not in self.objects:
            raise StorageError("object not found")
        return f"https://storage.test/signed/{quote(path)}?expires={SIGNED_URL_SECONDS}&download={quote(download_name)}"


@lru_cache
def _configured() -> Optional[SupabaseStorage]:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "print-documents").strip()
    if not url or not key:
        return None
    return SupabaseStorage(url, key, bucket)


def get_storage() -> Storage:
    """FastAPI dependency. 503 if storage is not configured (e.g. a local setup without Supabase)."""
    storage = _configured()
    if storage is None:
        raise HTTPException(503, detail="Document storage is not configured on this server")
    return storage


def get_optional_storage() -> Optional[Storage]:
    """For deletes: works (and simply skips file removal) when storage is not configured."""
    return _configured()


def delete_quietly(storage: Optional[Storage], path: Optional[str]) -> None:
    """Remove a stored file after its database row is gone. A failure only leaves an
    orphan file in the PRIVATE bucket, so it is logged instead of failing the request."""
    if storage is None or not path:
        return
    try:
        storage.delete(path)
    except StorageError as exc:
        log.warning("could not delete stored document %s: %s", path, exc)
