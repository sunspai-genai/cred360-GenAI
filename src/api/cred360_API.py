# api/cred360_API.py
import asyncio
import os
import platform
import logging
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware


# --- Early Platform Setup ---
# Do this before importing other modules that might rely on the loop policy
if platform.system() == "Windows":
    print("Platform is Windows, attempting to set asyncio policy to WindowsSelectorEventLoopPolicy")
    try:
        # Note: ProactorEventLoop is often needed for subprocesses on Windows with asyncio
        # Consider trying that if WindowsSelectorEventLoopPolicy causes issues with run_cma_analysis_task
        # asyncio.set_event_loop_policy(asyncio.ProactorEventLoopPolicy())
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print(f"Policy set. Current policy type: {asyncio.get_event_loop_policy().__class__.__name__}")
    except Exception as e:
        print(f"ERROR setting event loop policy: {e}")
else:
    print(f"Platform is {platform.system()}, using default asyncio policy.")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


# --- Import project modules AFTER potential policy changes ---
from src.api.core.config import API_CONFIG, PROJECT_ROOT, API_LOGGER_NAME
from src.api.core.logging_config import setup_logging
from src.api.routers import analysis, reports, get_company_names, get_alerts,get_company_details,get_recommendations  # Import router modules
from src.api.middleware.request_logging import RequestLoggingMiddleware # Import middleware

# --- Setup Logging ---
# Call the setup function to configure logging globally
setup_logging()
logger = logging.getLogger(API_LOGGER_NAME) # Get the main API logger

logger.info("--- Starting FastAPI Application Setup ---")
logger.info(f"Project Root: {PROJECT_ROOT}")
logger.info(f"Using Upload Directory: {API_CONFIG['UPLOAD_DIR']}")
logger.info(f"Using Output Directory: {API_CONFIG['OUTPUT_DIR']}")

# --- Create FastAPI App ---
api = FastAPI(
    title="CMA Analysis API",
    description="API to upload CMA data, trigger analysis, and retrieve reports.",
    version="1.0.1" # Incremented version
)

# --- Add Middleware ---
logger.info("Adding RequestLoggingMiddleware")
api.add_middleware(RequestLoggingMiddleware)
# Add other middleware here (CORS, Authentication, etc.) if needed
# from fastapi.middleware.cors import CORSMiddleware
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Include Routers ---
logger.info("Including API routers")
# Add prefixes if you want to version or group your API endpoints
api.include_router(analysis.router, prefix="/api")
api.include_router(reports.router, prefix="/api")
api.include_router(get_company_names.router, prefix="/api")
api.include_router(get_alerts.router, prefix="/api")
api.include_router(get_company_details.router, prefix="/api")
api.include_router(get_recommendations.router, prefix="/api")
# Example: api.include_router(analysis.router, prefix="/api/v1/analysis")


# --- Optional: Global Exception Handler ---
@api.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception for request {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected internal server error occurred."},
    )

# --- Main Execution (for running with uvicorn directly) ---
if __name__ == "__main__":
    # This block allows running the API directly using `python -m api.main`
    logger.info("Starting API server with Uvicorn...")
    uvicorn.run(
        "api.main:api", # Point to the FastAPI app instance
        host="0.0.0.0",
        port=8003,
        log_level="info", # Uvicorn's log level
        loop="asyncio" # Usually default, explicitly set if needed
    )

# To run:
# 1. Navigate to `your_project_root` in your terminal.
# 2. Run: `python -m api.main`
# Or using uvicorn directly:
#    `uvicorn api.main:api --host 0.0.0.0 --port 8003 --reload`