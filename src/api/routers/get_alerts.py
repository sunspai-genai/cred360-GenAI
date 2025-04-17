import io
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List

import pandas as pd
from fastapi import APIRouter, HTTPException

# Use relative imports within the 'api' package
from ..core.config import APP_TASK_LOGGER_NAME,API_CONFIG
from ..utils.helpers import sanitize_filename, find_latest_run_dir

router = APIRouter(
    prefix="/alerts", # Add a prefix for all routes in this router
    tags=["CustomerAlerts"]   # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)
# Get the specific logger instance intended for the analysis task
app_task_logger = logging.getLogger(APP_TASK_LOGGER_NAME)

BASE_DIR = API_CONFIG["OUTPUT_DIR"]
UNCLASSIFIED_PREFIX = "Unclassified Alert:"

def parse_and_filter_alerts(file_path: str,file_encoding) -> List[str]:
    """
    Reads the alert file, parses messages, and filters out unclassified alerts.

    Args:
        file_path (str): The path to the alert message file.

    Returns:
        List[str]: A list of alert message strings (excluding unclassified).

    Raises:
        FileNotFoundError: If the specified file does not exist.
        IOError: If there's an error reading the file.
        ValueError: If the file format is unexpected or parsing fails.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Alerts not generated.")

    try:
        with open(file_path, 'r', encoding=file_encoding) as f:
            alert_data = f.read()

        df = pd.read_csv(io.StringIO(alert_data), sep=r'\s{2,}', engine='python')

        df = df[~df['Alert Message'].str.contains('Unclassified Alert')]

        return df['Alert Message'].tolist()

    except Exception as e:
        # Catch other potential errors during file reading/processing
        # Re-raise as IOError for clearer API error handling
        raise IOError(f"Error processing file {file_path}: {str(e)}") from e

@router.get("/{account_name}")
def get_analysis_reports(account_name: str):
    """
        Retrieves all alert messages from the source file, excluding those marked as 'Unclassified Alert'.
    """
    safe_account = sanitize_filename(account_name)
    if not safe_account or safe_account == "invalid_input":
        raise HTTPException(status_code=400, detail="Invalid or unsafe account name provided.")

    # Base directory for the account, containing potentially multiple runs
    account_base_dir = Path(API_CONFIG["OUTPUT_DIR"]) / safe_account
    if not account_base_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Account directory not found: {account_name}")

    # --- Find the latest run directory ---
    latest_run_dir = find_latest_run_dir(account_base_dir)
    print(latest_run_dir)
    if not latest_run_dir:
        raise HTTPException(status_code=404, detail=f"No valid run directories found for account: {account_name}")

    customer_alert_dir = API_CONFIG["ANALYZER_CONFIG"]["customer_alert_dir"]
    file_encoding = API_CONFIG["ANALYZER_CONFIG"]["file_encoding"]
    alert_filename = "alert_messages.md"

    alert_path = latest_run_dir / customer_alert_dir /alert_filename
    logger.info(f"Checking for alert in latest run: {alert_path}")

    if alert_path.is_file():
        try:
            alerts = parse_and_filter_alerts(alert_path,file_encoding)
            return {"alerts": alerts if len(alerts)>0 else []}
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except (IOError, ValueError) as e:
            # Handle file reading/parsing errors as internal server errors
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        except Exception as e:
            # Catch any other unexpected errors
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    else:
        logger.warning(f"Alert not found in latest run at {alert_path}")
        return {"alerts":[]}
