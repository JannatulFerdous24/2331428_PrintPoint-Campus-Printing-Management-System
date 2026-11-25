"""
Server-side checks for uploaded print documents (never trust the browser).

Accepted: PDF and DOCX, 1 byte .. MAX_UPLOAD_BYTES (4,000,000 - below Vercel's
4.5 MB request limit; the bucket enforces the same limit as a second layer).
The file's CONTENT must match its extension, so a renamed .exe/.txt is refused.
"""

import io
import re
import unicodedata
import uuid
import zipfile

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 4_000_000
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED = {".pdf": PDF_MIME, ".docx": DOCX_MIME}


def safe_filename(name: str) -> str:
    """Display/download name only - the stored object key is random (see storage_key)."""
    name = (name or "").replace("\\", "/").split("/")[-1]           # drop any folder part
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        name = "document"
    if len(name) > 200:
        stem, dot, ext = name.rpartition(".")
        name = (stem[: 200 - len(ext) - 1] + "." + ext) if dot else name[:200]
    return name


def extension_of(name: str) -> str:
    return ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""


def _is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:  # reads the file list only, never extracts
            names = set(z.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and "word/document.xml" in names


def validate_document(filename: str, data: bytes) -> tuple[str, str]:
    """Returns (safe display name, content type) or raises 400/413/415."""
    name = safe_filename(filename)
    ext = extension_of(name)
    if ext not in ALLOWED:
        raise HTTPException(415, detail="Only PDF (.pdf) and Word (.docx) documents are accepted")
    if len(data) == 0:
        raise HTTPException(400, detail="The file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail=f"The file is too large (maximum {MAX_UPLOAD_BYTES:,} bytes, about 4 MB)")
    content_ok = data.startswith(b"%PDF-") if ext == ".pdf" else _is_docx(data)
    if not content_ok:
        raise HTTPException(415, detail=f"The file content is not a valid {ext[1:].upper()} document")
    return name, ALLOWED[ext]


def storage_key(request_id: int, ext: str) -> str:
    return f"requests/{request_id}/{uuid.uuid4().hex}{ext}"
