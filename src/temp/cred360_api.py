import asyncio
import base64
import sys
import platform
import os
import logging
from csv import excel

if platform.system() == "Windows":
    print("Platform is Windows, attempting to set asyncio policy to WindowsSelectorEventLoopPolicy")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print(f"Policy set. Current policy type: {asyncio.get_event_loop_policy().__class__.__name__}")
    except Exception as e:
        print(f"ERROR setting event loop policy: {e}")
else:
    print(f"Platform is {platform.system()}, using default asyncio policy.")
# ---------------------------------------------

import sys
import os
import logging
import shutil
from typing import Optional, List, Dict, Any
import markdown2
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
import re
from pathlib import Path
from datetime import datetime

# --- Project Structure Setup ---
# Assuming api.py is in the project root or a known location
API_DIR = Path(__file__).parent
PROJECT_ROOT = API_DIR.parent # Adjust if api.py is nested deeper
# sys.path.insert(0, str(PROJECT_ROOT)) # Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# --- Import the async task function ---
try:
    # Assuming app.py is in PROJECT_ROOT/src/
    from src.app import run_cma_analysis_task
except ImportError as e:
    print(f"Error importing run_cma_analysis_task: {e}")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    # Fallback if structure is different
    # from app import run_cma_analysis_task # If app.py is in the same dir as api.py
    sys.exit("Could not import analysis task function. Check PROJECT_ROOT and sys.path.")


# --- Logging Setup ---
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"cma_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure root logger for FastAPI/Uvicorn and our app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout) # Also log to console
    ]
)
logger = logging.getLogger(__name__) # Logger for this API file
app_logger = logging.getLogger("CMAAnalysisTask") # Get logger used by the task/analyzer


# --- API Definition ---
api = FastAPI(
    title="CMA Analysis API",
    description="API to upload CMA data and trigger analysis.",
    version="1.0.0"
)

# --- Configuration (Centralized for API) ---
# Consider loading from a .env file or config management system
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
        "file_encoding": "utf-8",
        "sheets_to_analyze":["profit & loss statement","balance sheet","balance sheet2",
                             "fund flow", "fund flow2"]
        # "sheets_to_analyze":["profit & loss statement"]
    }
}
# Ensure base directories exist
API_CONFIG["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
API_CONFIG["OUTPUT_DIR"].mkdir(parents=True, exist_ok=True)

timestamp_pattern = re.compile(r'_\d{8}_\d{6}\.md$')

# --- Helper Functions ---
def sanitize_input(input_string: str) -> str:
    """Sanitize input to prevent directory traversal and ensure safe file access."""
    if not input_string:
        return ""
    # Remove potentially harmful chars, allow alphanumeric, underscore, hyphen
    sanitized = re.sub(r'[^\w\-]+', '_', input_string)
    # Limit length
    return sanitized[:100].lower()


def get_analysis_reports(account_name: str):
    """
    Retrieve analysis reports (individual sheets + cumulative)
    for a specific account. Converts Markdown to HTML.
    """
    safe_account = sanitize_input(account_name)

    if not safe_account:
        raise HTTPException(status_code=400, detail="Invalid account name provided.")

    account_output_dir = API_CONFIG["OUTPUT_DIR"] / safe_account

    reports_dir = account_output_dir / API_CONFIG["ANALYZER_CONFIG"]["reports_dir"]
    graph_dir = account_output_dir / API_CONFIG["ANALYZER_CONFIG"]["graph_dir"]
    individual_report_pattern = "*.md"

    report_files_content = []

    # Get individual reports
    if reports_dir.is_dir():
        for report_path in reports_dir.glob(individual_report_pattern):
            if not report_path.is_file():
                continue

            filename = report_path.name
            # *** FILTERING STEP ***
            if timestamp_pattern.search(filename):
                print(filename)
                logger.debug(f"Ignoring timestamped file: {filename}")
                continue  # Skip this file

            try:
                charts_per_sheet=[]
                # Extract sheet name from filename (e.g., balance_sheet_report_timestamp.md -> Balance Sheet)
                base_name = report_path.stem.split('.')[0]
                report_name = base_name.replace('_', ' ').title()
                with open(report_path, 'r', encoding=API_CONFIG["ANALYZER_CONFIG"]["file_encoding"]) as f:
                    content_md = f.read()
                    content_html = markdown2.markdown(content_md, extras=["tables", "fenced-code-blocks"])
                if base_name in os.listdir(graph_dir):
                    individual_graph_pattern = "*.svg"
                    graphs_sheets_dir = graph_dir/base_name
                    charts_per_sheet = {}
                    for graphs in graphs_sheets_dir.glob(individual_graph_pattern):
                        if not graphs.is_file():
                            continue
                        graph_filename = graphs.name
                        print(graph_filename)
                        with open(graphs, 'rb') as graph:
                            graph_content= graph.read()
                            svg_content_base64 = base64.b64encode(graph_content).decode('utf-8')
                            # print(svg_content_base64)
                            charts_per_sheet[graph_filename] = svg_content_base64

                report_files_content.append({
                    'report_name': report_name,
                    'content': content_html,
                    'type': 'individual',
                    'charts':charts_per_sheet
                })
            except Exception as e:
                logger.error(f"Error reading or processing report {report_path}: {e}")

    cumulative_path = os.path.join(account_output_dir,"Cumulative_Report.md")

    if not os.path.exists(cumulative_path):
        file_content = []
    else:
        try:
            with open(cumulative_path, 'r', encoding=API_CONFIG["ANALYZER_CONFIG"]["file_encoding"]) as file:
                content_md = file.read()
                content_html = markdown2.markdown(content_md, extras=["tables", "fenced-code-blocks"])
                report_files_content.append({
                     'report_name': "Cumulative Report",
                     'content': content_html,
                     'type': 'cumulative',
                     'charts': {}
                })
        except Exception as e:
             logger.error(f"Error reading or processing cumulative report {cumulative_path}: {e}")
             # Optionally add a placeholder if needed
         # report_files_content.append({'report_name': "Cumulative Report", 'content': '<p>Not generated or found.</p>', 'type': 'cumulative'})


    if not report_files_content:
        raise HTTPException(status_code=404, detail=f"No valid reports found in the latest run for account: {account_name}")

    # Sort reports (e.g., cumulative last)
    report_files_content.sort(key=lambda x: (x['type'] != 'cumulative', x['report_name']))

    return report_files_content


# --- API Endpoints ---



@api.post("/analyze", tags=["Analysis"])
async def trigger_analysis(
    account_name: str = Form(...),
    file: UploadFile = File(...) # Make file mandatory for analysis trigger
):
    """
    Uploads an Excel file (e.g., CMA_Data.xlsx) for a specific account
    and triggers the asynchronous analysis workflow.
    """

    # --- Log loop/policy info ---
    try:
        current_policy = asyncio.get_event_loop_policy()
        current_loop = asyncio.get_running_loop()
        # Removed AnyIO backend check
        logger.info(f"--- Inside /analyze endpoint ---")
        logger.info(f"Policy Type: {current_policy.__class__.__name__}")
        logger.info(f"Running Loop Type: {current_loop.__class__.__name__}")
        logger.info(f"--------------------------------")
    except Exception as log_err:
        logger.error(f"Error getting loop/policy info: {log_err}")
    # --- End logging ---

    # +++ Simplified Subprocess Test +++
    logger.info("--- Attempting simplified subprocess test ---")
    try:
        command = sys.executable
        args = ["--version"]
        logger.info(f"Running command: {command} {' '.join(args)}")

        process = await asyncio.create_subprocess_exec(
            command, *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        logger.info(f"Simplified test subprocess created with PID: {process.pid}")
        stdout, stderr = await process.communicate()
        logger.info(f"Simplified test subprocess exited with code: {process.returncode}")
        if stdout: logger.info(f"Simplified test STDOUT: {stdout.decode().strip()}")
        if stderr: logger.warning(f"Simplified test STDERR: {stderr.decode().strip()}")

        if process.returncode == 0:
            logger.info("--- Simplified subprocess test successful ---")
        else:
            logger.error("--- Simplified subprocess test failed (non-zero exit code) ---")
            raise HTTPException(status_code=500, detail="Server configuration error: Subprocess test failed.")

    except NotImplementedError as nie:
        logger.error(f"!!! Simplified subprocess test FAILED with NotImplementedError: {nie}", exc_info=True)
        raise HTTPException(status_code=500,
                            detail="Server configuration error: asyncio subprocess execution not supported.")
    except FileNotFoundError as fnf_err:
        logger.error(f"!!! Simplified subprocess test FAILED - Command not found: {command} - {fnf_err}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server configuration error: Python executable not found for test.")
    except Exception as test_err:
        logger.error(f"!!! Simplified subprocess test FAILED with other error: {test_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error during internal test: {test_err}")
    # +++ End Simplified Subprocess Test +++

    safe_account = sanitize_input(account_name)
    print(safe_account)
    if not safe_account:
        raise HTTPException(status_code=400, detail="Invalid account name provided.")

    # Validate file type if needed
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file (.xlsx, .xls).")

    try:
        account_dir = Path(API_CONFIG["UPLOAD_DIR"] / account_name)
        account_dir.mkdir(parents=True, exist_ok=True)
        file_path = os.path.join(account_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            excel_file_path = buffer.name # Get the path to the temporary file
        logger.info(f"File uploaded temporarily to: {excel_file_path} for account: {safe_account}")

        # --- Prepare paths and config for the analysis task ---
        # Use absolute path for MCP server script
        mcp_server_path = API_CONFIG["MCP_SERVER_SCRIPT"]
        if not Path(mcp_server_path).is_file():
             logger.error(f"MCP Server script not found at configured path: {mcp_server_path}")
             raise HTTPException(status_code=500, detail="Server configuration error: MCP script not found.")

        output_base_dir = str(API_CONFIG["OUTPUT_DIR"]) # Base directory for all account outputs

        # --- Call the async analysis task ---
        logger.info(f"Triggering analysis task for account: {safe_account}")
        try:
            # Pass the app_logger instance to the task
            final_state = await run_cma_analysis_task(
                account_name=safe_account,
                excel_file_path=excel_file_path,
                output_base_dir=output_base_dir,
                mcp_server_path=mcp_server_path,
                config=API_CONFIG["ANALYZER_CONFIG"],
                logger=app_logger # Pass the specific logger
            )
            logger.info(f"Analysis task finished for account: {safe_account}")

            # Check final state for errors logged during the run
            run_errors = final_state.get("error_logs", []) if final_state else ["Task did not return state."]
            if run_errors:
                 logger.warning(f"Analysis for {safe_account} completed with errors: {run_errors}")
                 # Return success but indicate errors occurred
                 return JSONResponse(content={
                     "status": "success",
                     "message": f"Analysis completed for {safe_account}, but some errors occurred during processing. Check server logs.",
                     "run_errors": run_errors
                 })
            else:
                 return JSONResponse(content={
                     "status": "success",
                     "message": f"Analysis successfully completed for {safe_account}."
                 })

        except Exception as e:
            # Catch errors raised from the analysis task itself
            logger.error(f"Analysis task execution failed for {safe_account}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Analysis workflow failed: {str(e)}")

    except HTTPException:
        raise # Re-raise HTTP exceptions directly
    except Exception as e:
        logger.error(f"Error during file upload or task preparation for {safe_account}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error during file handling: {str(e)}")
    finally:
        if file and hasattr(file, 'file') and not file.file.closed:
             file.file.close()


@api.get("/reports/{account_name}", tags=["Reports"],response_model=List[Dict[str, Any]])
async def retrieve_reports(account_name: str):
    """
    Retrieves the latest analysis reports (individual sheets and cumulative)
    for a given account name. Reports are returned as HTML content.
    """
    logger.info("Retrival API called")
    try:
        reports = get_analysis_reports(account_name)
        return reports
    except HTTPException:
        raise # Let FastAPI handle HTTP exceptions
    except Exception as e:
        logger.error(f"Error retrieving reports for account {account_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports: {str(e)}")


@api.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    # Add more checks if needed (e.g., dependency availability)
    return {"status": "healthy"}


# --- Main Execution (for running with uvicorn directly) ---
if __name__ == "__main__":
    logger.info("Starting API server with Uvicorn...")
    # uvicorn.run("cred360_api:api", host="0.0.0.0", port=8003,loop="asyncio")
