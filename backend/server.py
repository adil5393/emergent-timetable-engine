"""FastAPI entry point."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from auth import seed_default_users
from database import Base, SessionLocal, engine
from models import *  # noqa: F401,F403  (register models with Base)

# Routers
from routers import auth as auth_router
from routers import exports as exports_router
from routers import imports as imports_router
from routers import master_data as master_router
from routers import projects as projects_router
from routers import timetables as timetables_router
from routers import validation as validation_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="Timetable Management System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_users(db)
    logger.info("Startup complete: tables ensured, default users seeded.")


@app.get("/api")
def index():
    return {"app": "Timetable Management System", "status": "ok"}


app.include_router(auth_router.router)
app.include_router(projects_router.router)
app.include_router(master_router.router)
app.include_router(imports_router.router)
app.include_router(validation_router.router)
app.include_router(timetables_router.router)
app.include_router(exports_router.router)
