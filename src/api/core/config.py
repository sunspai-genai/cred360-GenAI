# api/core/config.py
import os
from pathlib import Path
from datetime import datetime
import logging

# --- Project Structure Setup ---
# Assumes this file is in api/core/
CORE_DIR = Path(__file__).parent
API_DIR = CORE_DIR.parent
PROJECT_ROOT = API_DIR.parent # Adjust if structure differs

# --- Logging Setup ---
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"cma_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# --- API Configuration ---
# Consider loading sensitive parts from .env files
API_CONFIG = {
    "UPLOAD_DIR": PROJECT_ROOT / "data" / "input_data_sources",
    "OUTPUT_DIR": PROJECT_ROOT / "output",
    "MCP_SERVER_SCRIPT": str(PROJECT_ROOT / "tools" / "mcp_tools.py"), # Absolute path
    "ANALYZER_CONFIG": {
        # Configuration specific to CMAAnalyzer
        "model_name": os.getenv("DEFAULT_MODEL", "gemini-2.0-flash"), # Use env var or default
        "data_extraction_format_filename": "data_extraction_format.json",
        "extracted_markdown_dir": "extracted_markdown",
        "extracted_metrics_dir": "extracted_metrics",
        "reports_dir": "reports",
        "audit_data_dir": "audit_data",
        "graph_dir": "graphs",
        "graph_data_dir": "graph_data",
        "customer_alert_dir": "customer_alerts",
        "file_encoding": "utf-8",
        "sheets_to_analyze": ["profit & loss statement", "balance sheet", "balance sheet2",
                              "fund flow", "fund flow2"]
        # "sheets_to_analyze":["fund flow", "fund flow2"]
    }
}

# Ensure base directories exist
try:
    API_CONFIG["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    API_CONFIG["OUTPUT_DIR"].mkdir(parents=True, exist_ok=True)
except OSError as e:
    # Use basic print/logging here as full logging might not be set up yet
    print(f"Warning: Could not create directories {API_CONFIG['UPLOAD_DIR']} or {API_CONFIG['OUTPUT_DIR']}: {e}")
    # Depending on severity, you might want to raise the exception or exit
    # raise e

# --- Add project root to sys.path ---
# Be cautious with sys.path manipulation. It's often better to run
# your application from the project root or use package structures.
import sys
# sys.path.insert(0, str(PROJECT_ROOT)) # Add project root to path if needed
# A potentially safer way if your src/app.py is structured as a package:
sys.path.append(str(PROJECT_ROOT)) # Add project root for src import

# --- Import the async task function ---
# Moved here to ensure PROJECT_ROOT is defined and sys.path is updated
try:
    from src.app import run_cma_analysis_task
except ImportError as e:
    print(f"Error importing run_cma_analysis_task: {e}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    sys.exit("Could not import analysis task function. Check PROJECT_ROOT, sys.path, and src/app.py.")

# --- Get Loggers ---
# Define logger names centrally if needed, although getting them
# in each module with __name__ is standard practice.
API_LOGGER_NAME = "CMA_API"
APP_TASK_LOGGER_NAME = "CMAAnalysisTask"
