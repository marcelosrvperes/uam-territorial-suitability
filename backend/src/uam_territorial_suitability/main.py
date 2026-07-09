from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from uam_territorial_suitability.api.routes import router

app = FastAPI(
    title="UAM Territorial Suitability API",
    description="Backend for the Módulo 02 territorial aptitude tool (UAM Planning Framework thesis).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
