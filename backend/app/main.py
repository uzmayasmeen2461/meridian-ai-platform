import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.domain.schemas import HealthResponse

app = FastAPI(title="Meridian AI Platform Backend")

if os.getenv("MERIDIAN_ENABLE_DEV_CORS", "1") == "1":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5177",
            "http://localhost:5177",
        ],
        allow_methods=["GET", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "X-User-Id", "X-User-Email"],
    )

app.include_router(api_router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
