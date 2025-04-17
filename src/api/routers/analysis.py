import logging
import asyncio
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse

# Use relative imports within the 'api' package
from ..core.config import API_CONFIG, run_cma_analysis_task, APP_TASK_LOGGER_NAME
from ..utils.helpers import sanitize_filename

router = APIRouter(
    prefix="/analysis", # Add a prefix for all routes in this router
    tags=["Analysis"]   # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)
# Get the specific logger instance intended for the analysis task
app_task_logger = logging.getLogger(APP_TASK_LOGGER_NAME)


async def run_subprocess_test():
    """Runs a simple subprocess test to check asyncio compatibility."""
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
        exit_code = await process.wait() # Ensure process finishes
        logger.info(f"Simplified test subprocess exited with code: {exit_code}") # Use exit_code from wait()

        if stdout: logger.info(f"Simplified test STDOUT: {stdout.decode().strip()}")
        if stderr: logger.warning(f"Simplified test STDERR: {stderr.decode().strip()}")

        if exit_code == 0:
            logger.info("--- Simplified subprocess test successful ---")
            return True
        else:
            logger.error(f"--- Simplified subprocess test failed (exit code: {exit_code}) ---")
            return False

    except NotImplementedError as nie:
        logger.error(f"!!! Simplified subprocess test FAILED with NotImplementedError: {nie}", exc_info=True)
        # This is critical, indicates Proactor event loop might be needed on Windows or subprocess isn't supported
        raise HTTPException(status_code=500,
                            detail="Server configuration error: asyncio subprocess execution not supported by the current event loop.")
    except FileNotFoundError as fnf_err:
        logger.error(f"!!! Simplified subprocess test FAILED - Command not found: {command} - {fnf_err}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server configuration error: Python executable not found for test.")
    except Exception as test_err:
        logger.error(f"!!! Simplified subprocess test FAILED with other error: {test_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error during internal subprocess test: {test_err}")

def _rename_file_for_archiving(file_path):
    """Archives an existing file by appending its last modified time."""
    file_path = Path(file_path)
    if not file_path.is_file():
        return # Nothing to archive

    try:
        modified_time_ts = file_path.stat().st_mtime
        formatted_time = datetime.fromtimestamp(modified_time_ts).strftime('%Y%m%d_%H%M%S')
        archive_name = f"{file_path.stem}_{formatted_time}{file_path.suffix}"
        archive_path = file_path.with_name(archive_name)

        # Handle potential naming conflict if archive already exists
        counter = 1
        while archive_path.exists():
            archive_name = f"{file_path.stem}_{formatted_time}_{counter}{file_path.suffix}"
            archive_path = file_path.with_name(archive_name)
            counter += 1

        file_path.rename(archive_path)
        logger.info(f"Archived previous file '{file_path.name}' as: {archive_path.name}")
    except OSError as err:
        logger.error(f"Failed to archive file {file_path}: {err}")
    except Exception as err:
        logger.error(f"Unexpected error during file archiving for {file_path}: {err}", exc_info=True)


@router.post("", status_code=202) # Use 202 Accepted for async tasks
async def trigger_analysis(
    account_name: str = Form(...),
    file: UploadFile = File(...),
    # data_source: str = Form(...),
        # Dependency Injection for the test: runs the test before the main endpoint logic
    # subprocess_ok: bool = Depends(run_subprocess_test) # Optional: run test on each request
):
    """
    Uploads an Excel file (e.g., CMA_Data.xlsx) for a specific account
    and triggers the asynchronous analysis workflow.
    """
    # --- Log loop/policy info (optional, for debugging) ---
    try:
        current_policy = asyncio.get_event_loop_policy()
        current_loop = asyncio.get_running_loop()
        logger.info(f"--- Inside /analysis/trigger endpoint ---")
        logger.info(f"Policy Type: {current_policy.__class__.__name__}")
        logger.info(f"Running Loop Type: {current_loop.__class__.__name__}")
        logger.info(f"--------------------------------")
    except Exception as log_err:
        logger.error(f"Error getting loop/policy info: {log_err}")
    # --- End logging ---

    # +++ Run subprocess test explicitly if not using Depends +++
    # Comment out if using Depends(run_subprocess_test)
    subprocess_ok = await run_subprocess_test()
    if not subprocess_ok:
         # The test function already raised HTTPException, but double-check
         raise HTTPException(status_code=500, detail="Server configuration error preventing analysis.")
    # +++ End explicit test run +++


    safe_account = sanitize_filename(account_name)  # Spaces will be replaced with underscore and special
    if not safe_account or safe_account == "invalid_input":
        raise HTTPException(status_code=400, detail="Invalid or unsafe account name provided.")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(('.xlsx', '.xls')):
         logger.warning(f"Invalid file type uploaded for account {safe_account}: {file.filename}")
         raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file (.xlsx, .xls).")

    # Define paths using config
    upload_dir = Path(API_CONFIG["UPLOAD_DIR"])
    account_upload_dir = upload_dir / safe_account
    output_base_dir = str(API_CONFIG["OUTPUT_DIR"]) # Base directory for all account outputs
    mcp_server_path = API_CONFIG["MCP_SERVER_SCRIPT"]

    # Ensure MCP script exists
    if not Path(mcp_server_path).is_file():
         logger.error(f"MCP Server script not found at configured path: {mcp_server_path}")
         raise HTTPException(status_code=500, detail="Server configuration error: Analysis script not found.")

    # Create account-specific upload directory
    try:
        account_upload_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Could not create upload directory {account_upload_dir}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server error: Could not create directory for upload.")

    # Sanitize filename as well
    safe_filename = sanitize_filename(Path(file.filename).stem) + Path(file.filename).suffix
    file_path = account_upload_dir / file.filename
    _rename_file_for_archiving(file_path)
    try:
        # Save the uploaded file
        logger.info(f"Saving uploaded file to: {file_path} for account: {safe_account}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File successfully saved: {file_path}")
        # --- Trigger the async analysis task ---
        logger.info(f"Triggering analysis task for account: {safe_account}, file: {file_path}")
        try:
            # Using create_task to run it in the background without awaiting here
            # The endpoint returns immediately (202 Accepted)
            # if data_source.lower().strip() == "cma_data":
            final_state = await run_cma_analysis_task(
                account_name=safe_account,
                excel_file_path=str(file_path),
                output_base_dir=output_base_dir,
                mcp_server_path=mcp_server_path,
                config=API_CONFIG["ANALYZER_CONFIG"],
                logger=app_task_logger  # Pass the specific logger
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
                    "message": f"Analysis successfully completed for {account_name}."
                })
        except Exception as task_e:
            # Catch errors during task *scheduling* (less likely)
            logger.error(f"Failed to schedule analysis task for {safe_account}: {task_e}", exc_info=True)
            # Clean up saved file if scheduling fails? Maybe not, user might retry.
            raise HTTPException(status_code=500, detail=f"Failed to schedule analysis workflow: {str(task_e)}")

    except IOError as io_err:
        logger.error(f"File I/O error during upload for {safe_account}: {io_err}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error during file saving: {str(io_err)}")
    except HTTPException:
        raise # Re-raise HTTP exceptions directly
    except Exception as e:
        logger.error(f"Unexpected error during file upload or task preparation for {safe_account}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")
    finally:
        # Ensure the uploaded file stream is closed
        if file and hasattr(file, 'file') and not file.file.closed:
             await file.close() # Use await for async close if available, otherwise sync close
             # file.file.close() # Use if await file.close() is not available/needed
