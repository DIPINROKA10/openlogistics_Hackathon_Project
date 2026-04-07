"""
OpenLogistics - AI Supply Chain Optimization Environment
Main FastAPI application.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.routes import router, limiter

app = FastAPI(
    title="OpenLogistics",
    description="AI Supply Chain Optimization Environment (OpenEnv Standard)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.include_router(router, prefix="/api/v1")

# Frontend is served separately via npm run dev

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "OpenLogistics",
        "version": "1.0.0",
        "description": "AI Supply Chain Optimization Environment",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "api": "/api/v1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=7860, proxy_headers=True, forwarded_allow_ips="*", reload=True)
