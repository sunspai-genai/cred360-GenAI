import logging
import sqlite3
from contextlib import contextmanager
from fastapi import APIRouter, HTTPException

# Use relative imports within the 'api' package
from ..core.config import APP_TASK_LOGGER_NAME

router = APIRouter(
    prefix="/companies", # Add a prefix for all routes in this router
    tags=["Companies"]   # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)
# Get the specific logger instance intended for the analysis task
app_task_logger = logging.getLogger(APP_TASK_LOGGER_NAME)

@contextmanager
def get_db_connection():
    """Provides a managed database connection."""
    # The DATABASE_URL format is "sqlite:///./path/to/db.file"
    # We need to extract the file path part.
    DATABASE_URL = "sqlite:///../database/cred360.db"
    db_path = DATABASE_URL.split("///")[-1]
    if db_path == ":memory:":
        logger.info("Connecting to in-memory SQLite database.")
    else:
        logger.info(f"Connecting to SQLite database at: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Optional: Access columns by name
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise # Re-raise the exception after logging
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed.")


def get_company_names():
    """
    Fetches distinct company names from the database and returns a structured
    JSON-like dictionary response including a status.

    Returns:
        dict: A dictionary with keys 'status', 'data', and 'message'.
              'status' (str): 'success' or 'error'.
              'data' (list | None): List of company names on success,
                                    or an empty list/None on error.
              'message' (str): A descriptive message about the outcome.
    """
    query = "SELECT TRIM(DISTINCT(company_name)) FROM customer_master ORDER BY company_name;"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            # Extract company names directly
            company_names = [row[0] for row in results if row[0]]  # Ensure None names are skipped if possible in DB

            success_message = f"Successfully fetched {len(company_names)} distinct company names."
            logger.info(success_message)
            return {
                "status": "success",
                "data": company_names,
                "message": success_message
            }

    except sqlite3.Error as e:
        # Corrected the table name in the error check
        if "no such table: customer_master" in str(e).lower():  # Use lower() for case-insensitivity
            error_message = "Database error: The 'customer_master1' table does not exist."
            logger.error(error_message)
        else:
            # Log the specific database error
            error_message = f"Database error fetching company names: {e}"
            logger.error(error_message)

        # Return a structured error response
        return {
            "status": "error",
            "data": [],  # Return empty list for data on error
            "message": error_message
        }

    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        # Use logger.exception to include stack trace for unexpected errors
        logger.exception(error_message)

        # Return a structured error response
        return {
            "status": "error",
            "data": [],  # Return empty list for data on error
            "message": error_message
        }


@router.get("")
async def retrieve_reports_endpoint():
    """
    Retrieves the latest analysis reports (individual sheets and cumulative)
    for a given account name. Reports are returned as HTML content with embedded charts.
    """
    logger.info(f"Received request to retrieve company names ")
    try:
        company_names = get_company_names()
        return company_names
    except HTTPException as http_exc:
        # Log HTTP exceptions specifically if needed, otherwise re-raise
        logger.warning(f"HTTP Exception retrieving company names {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error retrieving company names : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports due to an internal server error.")