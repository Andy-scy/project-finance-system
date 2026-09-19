"""FastAPI 入口：挂载 API 路由 + 托管前端静态文件（SPA）。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST
from .database import init_db
from .routers import companies, dashboard, extractions, projects, settings, transfer

app = FastAPI(title="项目财务与合同管理分析系统", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api")
app.include_router(companies.router, prefix="/api")
app.include_router(extractions.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(transfer.router, prefix="/api")


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "app": "项目财务与合同管理分析系统", "version": "1.1.0"}


# ── 前端静态托管（构建产物 frontend/dist）────────────────────
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
