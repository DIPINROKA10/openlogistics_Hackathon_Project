"""
OpenLogistics - AI Supply Chain Optimization Environment
Main FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="OpenLogistics",
    description="AI Supply Chain Optimization Environment (OpenEnv Standard)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "OpenLogistics",
        "version": "1.0.0",
        "description": "AI Supply Chain Optimization Environment",
        "docs": "/docs",
        "api": "/api/v1"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
