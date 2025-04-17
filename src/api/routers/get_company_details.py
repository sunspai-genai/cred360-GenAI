import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime,date

from fastapi import APIRouter, HTTPException

# Use relative imports within the 'api' package
from ..core.config import APP_TASK_LOGGER_NAME

router = APIRouter(
    prefix="/company_details", # Add a prefix for all routes in this router
    tags=["CompanyDetails"]   # Tag for OpenAPI documentation
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


def get_company_details():
    """
    Fetches customer loan details from the database, calculates the days
    since the last sanction (parsing 'M/D/YY' format), and returns a
    structured JSON-like dictionary response.

    Returns:
        dict: A dictionary with keys 'status', 'data', and 'message'.
              'status' (str): 'success' or 'error'.
              'data' (list): List of dictionaries (each representing a loan
                             record with calculated days) on success, or an
                             empty list on error.
              'message' (str): A descriptive message about the outcome.
    """
    query = """
    SELECT
        cm.company_name,
        ld.date_last_sanction,
        ld.loan_type_1,
        ld.loan1_amount,
        ld.loan_type_2,
        ld.loan2_amount
    FROM
        customer_master cm
    JOIN
        loan_data ld ON cm.customer_id = ld.customer_id;
    """
    processed_results = []

    try:
        # *** Use the context manager correctly with 'with' ***
        with get_db_connection() as conn: # 'conn' here IS the actual connection object
            cursor = conn.cursor() # This will now work
            cursor.execute(query)
            results = cursor.fetchall()

        today = date.today()
        for row in results:
            row_dict = dict(row)
            raw_date_str = row_dict.get("date_last_sanction")
            days_diff = None

            if raw_date_str and isinstance(raw_date_str, str):
                try:
                    parsed_date = datetime.strptime(raw_date_str, "%m/%d/%y").date()
                    delta = today - parsed_date
                    days_diff = delta.days
                except ValueError:
                    logger.warning(
                        f"Could not parse date format '{raw_date_str}' for company "
                        f"'{row_dict.get('company_name')}'. Setting days_since_last_sanction to null."
                    )
                    days_diff = None
                except TypeError:
                     logger.warning(
                        f"Invalid type for date '{raw_date_str}' for company "
                        f"'{row_dict.get('company_name')}'. Setting days_since_last_sanction to null."
                     )
                     days_diff = None

            row_dict["days_since_last_sanction"] = days_diff
            processed_results.append(row_dict)

        success_message = f"Successfully fetched {len(processed_results)} loan records."
        logger.info(success_message)
        return {
            "status": "success",
            "data": processed_results,
            "message": success_message
        }

    # --- Error handling remains the same ---
    except sqlite3.Error as e:
        # Check if the error is due to the connection failing within the context manager
        # (though specific connection errors might be handled inside get_db_connection)
        if "no such table: customer_master" in str(e).lower():
            error_message = "Database error: The 'customer_master' table does not exist."
            logger.error(error_message)
        # Add more specific checks if needed, e.g., for connection errors if not handled inside get_db_connection
        # elif "unable to open database file" in str(e).lower():
        #     error_message = "Database error: Unable to open database file."
        #     logger.error(error_message)
        else:
            error_message = f"Database error fetching loan details: {e}"
            logger.error(error_message)

        return {
            "status": "error",
            "data": [],
            "message": error_message
        }

    except Exception as e:
        error_message = f"An unexpected error occurred while processing loan details: {e}"
        logger.exception(error_message)

        return {
            "status": "error",
            "data": [],
            "message": error_message
        }


@router.get("")
async def retrieve_company_details_endpoint():
    """
    Retrieves the latest analysis reports (individual sheets and cumulative)
    for a given account name. Reports are returned as HTML content with embedded charts.
    """
    logger.info(f"Received request to retrieve company names ")
    try:
        company_names = get_company_details()
        return company_names
    except HTTPException as http_exc:
        # Log HTTP exceptions specifically if needed, otherwise re-raise
        logger.warning(f"HTTP Exception retrieving company names {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error retrieving company names : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports due to an internal server error.")