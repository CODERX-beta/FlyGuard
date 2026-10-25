from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.config import settings
from backend.app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="FlyGuard AI — Financial Intelligence & Mule Detection Platform",
    description=(
        "Decision-support financial intelligence API for detecting suspicious money-mule accounts, "
        "analyzing transaction networks, computing TreeSHAP explanations, and managing AML investigations."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Root"])
def root():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "docs_url": "/docs",
        "health_url": "/api/health",
    }

