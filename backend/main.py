import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from auth.router import users_router
from config import get_settings
from database import init_db
from errors import register_error_handlers
from routers.admin import router as admin_router
from routers.groups import router as groups_router
from routers.print_requests import router as print_requests_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if JWT_SECRET / PASSWORD_PEPPER are missing or too weak.
    get_settings()
    # SQLite: creates tables. PostgreSQL: no-op (Alembic migrations own the schema).
    init_db()
    yield


app = FastAPI(
    title="PrintPoint API",
    description="Campus Printing Management System REST API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS - allow Vite dev server and Vercel frontend
origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "Content-Disposition"],  # pagination totals, CSV file names
)

register_error_handlers(app)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(print_requests_router)
app.include_router(groups_router)
app.include_router(admin_router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "PrintPoint API"}


# Serve built frontend in production
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
