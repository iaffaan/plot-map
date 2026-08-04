from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import (
    AIParserError,
    InfeasibleRequestError,
    OptimizationSolverError,
    TopologyValidationError,
    UnchartedException,
)
from app.core.logging import setup_logging

# Set up global logging config
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="FastAPI router and LLM orchestration parsing layer for spatial compilation.",
)

# Enable CORS for frontend integration
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.exception_handler(UnchartedException)
async def uncharted_exception_handler(request: Request, exc: UnchartedException) -> JSONResponse:
    """
    Global exception handler for all custom domain exceptions.
    Maps exception subclasses to standard HTTP status codes.
    """
    if isinstance(exc, (AIParserError, OptimizationSolverError, TopologyValidationError)):
        status_code = 422
    elif isinstance(exc, InfeasibleRequestError):
        return JSONResponse(
            status_code=400,
            content={
                "status": "infeasible",
                "reason": exc.detail or exc.message
            }
        )
        
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": exc.message,
            "detail": exc.detail
        }
    )

# Include v1 endpoints
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix="/api")
