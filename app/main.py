from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging

# from app.modules.internal.router import routerInternal
# from app.modules.load_object.router import routerLoadObject
from app.modules.opening_part.router import routerOpeningPart

# Database Needs
from app.core.database import engine, Base
# from app.database.models import StagingProject

# Master Data
from app.modules.master.router import routerMaster

# Identity Data
from app.modules.identity.routers import router as identityRouter

# setup logging saat app start
setup_logging()

# Staging Database
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dijalankan saat startup (BEFORE ALEMBIC)
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    
    yield 
    
    await engine.dispose()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="API Gateway",
    lifespan= lifespan
)


# CORS 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # bisa diganti url agar lebih spesifik
    allow_credentials=False,  # harus False kalau allow_origins="*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Master Data
app.include_router(routerMaster)

# Identity Data
app.include_router(identityRouter)

# register router
# app.include_router(routerInternal)

# app.include_router(routerLoadObject)
app.include_router(routerOpeningPart)



""" Entry Point Start """
@app.get("/")
async def api_info():
    return {
        "name": "Kori Bali API Gateway",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "version": app.version,
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "uptime": "running"
    }

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Route not found",
            "path": request.url.path
        }
    )
""" Entry Point End """
