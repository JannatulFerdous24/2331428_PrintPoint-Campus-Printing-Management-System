"""
Consistent error responses.

* HTTPException and validation errors keep FastAPI's standard {"detail": ...} shape.
* Any unexpected exception becomes {"detail": "Internal server error"} with status
  500. The real error is written to the server log only - never sent to the client
  (no stack traces, file paths or SQL leak to users).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("printpoint")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
