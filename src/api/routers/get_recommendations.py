from ..core.config import APP_TASK_LOGGER_NAME
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# --- Configuration ---
DATABASE_URL = "sqlite:///../database/cred360.db" # Define DB URL centrally

router = APIRouter(
    prefix="/recommendations", # Add a prefix for all routes in this router
    tags=["Recommendations"]   # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)
# Get the specific logger instance intended for the analysis task
# Ensure this logger is configured elsewhere in your application setup
try:
    app_task_logger = logging.getLogger(APP_TASK_LOGGER_NAME)
except Exception: # Fallback if not configured
    app_task_logger = logger
    logger.warning(f"Logger '{APP_TASK_LOGGER_NAME}' not found, using default logger.")


# --- Database Connection ---
@contextmanager
def get_db_connection():
    """Provides a managed database connection."""
    db_path = DATABASE_URL.split("///")[-1]
    if db_path == ":memory:":
        logger.info("Connecting to in-memory SQLite database.")
    else:
        logger.info(f"Connecting to SQLite database at: {db_path}")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row # Access columns by name
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Database connection error.") # Raise HTTP error for API
    finally:
        if conn:
            conn.close()
            logger.debug("Database connection closed.")

# --- Date Helper Functions ---
def parse_db_date(date_str: Optional[str]) -> Optional[date]:
    """Parses date string from DB ('M/D/YY' or 'YYYY-MM-DD') into a date object."""
    if not date_str:
        return None
    formats_to_try = ['%m/%d/%y', '%Y-%m-%d', '%d/%m/%Y', '%d-%b-%Y', '%m/%d/%Y']
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    logger.warning(f"Could not parse date string: '{date_str}' with known formats.")
    return None

def format_date_for_output(date_obj: Optional[date]) -> str:
    """Formats a date object into DD.MM.YYYY string."""
    if date_obj is None:
        return "N/A"
    return date_obj.strftime('%d.%m.%Y')

# --- Recommendation Generation Logic ---

def generate_recommendations(company_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Generates recommendations for current month and next 3 months based on rules.
    Returns a dictionary containing lists of recommendation strings.
    Handles specific dependencies for Rule 4 and Rule 7 future checks.
    """
    current_month_actions: List[str] = []
    next_3_month_actions: List[str] = []

    today = date.today()
    next_3_months_limit = today + relativedelta(months=3)

    # --- Rule Definitions ---
    # Note: Rule 7 (date_of_last_audit) is removed from this list
    #       as its future check requires separate handling.
    #       Rule 4 (date_of_bank_credit_report) is also handled separately.
    standard_rules = [
        {
            "attribute": "date_valuation_report",
            "display_name": "Date Valuation Report",
            "current_threshold": relativedelta(years=3),
            "future_window_start": relativedelta(years=3),
            "current_action": "Obtain latest valuation report before it expires; last valuation report was taken on <date>",
            "future_action": "Obtain latest valuation report before it expires; last valuation report was taken on <date>",
        },
        {
            "attribute": "date_last_sanction",
            "display_name": "Date Last Sanction",
            "current_threshold": relativedelta(months=11),
            "future_window_start": relativedelta(years=1),
            "current_action": "The account is due for renewal; last sanction/renewal date was <date>",
            "future_action": "The account will be due for renewal; last sanction/renewal date was <date>",
        },
        {
            "attribute": "date_lsr",
            "display_name": "Date LSR",
            "current_threshold": relativedelta(years=3),
            "future_window_start": relativedelta(years=3),
            "current_action": "Obtain latest LSR (Legal Search Report) from Panel Advocate before it expires; last LSR was taken on <date>",
            "future_action": "Obtain latest LSR (Legal Search Report) from Panel Advocate before it expires; last LSR was taken on <date>",
        },
        # Rule 4 handled separately
        {
            "attribute": "date_internal_rating",
            "display_name": "Date Internal Rating",
            "current_threshold": relativedelta(months=6),
            "future_window_start": relativedelta(months=6),
            "current_action": "Conduct Internal Rating Assessment as the last internal rating was done on <date>",
            "future_action": "Conduct Internal Rating Assessment as the last internal rating was done on <date>",
        },
        {
            "attribute": "date_external_rating",
            "display_name": "Date External Rating",
            "current_threshold": relativedelta(months=6),
            "future_window_start": relativedelta(months=6),
            "current_action": "Obtain External Rating Assessment as the last external rating was done on <date>",
            "future_action": "Obtain External Rating Assessment as the last external rating was done on <date>",
        },
        # Rule 7 handled separately
        {
            "attribute": "date_tev_report",
            "display_name": "Date TEV Report",
            "current_threshold": relativedelta(years=3),
            "future_window_start": relativedelta(years=3),
            "current_action": "Obtain latest TEV Report before it expires; last TEV was done on <date>",
            "future_action": "Obtain latest TEV Report before it expires; last TEV was done on <date>",
        },
        {
            "attribute": "date_stock_statement",
            "display_name": "Date Stock Statement",
            "current_threshold": relativedelta(days=10),
            "future_window_start": None,
            "current_action": "Obtain certified Stock Statement from Customer for current month",
            "future_action": None,
        },
    ]

    # --- Process Standard Rules ---
    for rule in standard_rules:
        attribute = rule["attribute"]
        date_str = company_data.get(attribute)
        db_date = parse_db_date(date_str)

        if db_date:
            formatted_date = format_date_for_output(db_date)
            current_action_triggered = False

            # Check if due currently
            current_due_date = today - rule["current_threshold"]
            if db_date < current_due_date:
                action_template = rule["current_action"]
                action_str = action_template.replace("<date>", formatted_date) if "<date>" in action_template else action_template
                if action_str not in current_month_actions:
                    current_month_actions.append(action_str)
                current_action_triggered = True

            # Check if due in the next 3 months (standard logic)
            if rule["future_action"] and rule["future_window_start"]:
                expiry_or_renewal_date = db_date + rule["future_window_start"]
                if today <= expiry_or_renewal_date < next_3_months_limit:
                    # Optional: Uncomment if future action should NOT be shown if current is already triggered
                    # if not current_action_triggered:
                        action_template = rule["future_action"]
                        action_str = action_template.replace("<date>", formatted_date) if "<date>" in action_template else action_template
                        if action_str not in next_3_month_actions:
                             next_3_month_actions.append(action_str)

    # --- Get Dates needed for Special Rules (4 & 7) ---
    date_last_sanction_str = company_data.get("date_last_sanction")
    date_bank_credit_report_str = company_data.get("date_of_bank_credit_report")
    date_last_audit_str = company_data.get("date_of_last_audit")

    date_last_sanction = parse_db_date(date_last_sanction_str)
    date_bank_credit_report = parse_db_date(date_bank_credit_report_str)
    date_last_audit = parse_db_date(date_last_audit_str)

    # --- Process Rule 4 (Bank Credit Report - Special Conditions) ---
    if date_last_sanction and date_bank_credit_report:
        formatted_bcr_date = format_date_for_output(date_bank_credit_report)
        current_action_r4_triggered = False

        # Current Condition: date_bcr < date_last_sanction AND date_last_sanction < today - 11m
        cond1_curr_r4 = date_bank_credit_report < date_last_sanction
        threshold_sanction_r4 = today - relativedelta(months=11)
        cond2_curr_r4 = date_last_sanction < threshold_sanction_r4

        if cond1_curr_r4 and cond2_curr_r4:
            action_str_r4_curr = f"Get CIR (Confidential Information Report) from Banks; the last credit report was obtained on {formatted_bcr_date}"
            if action_str_r4_curr not in current_month_actions:
                current_month_actions.append(action_str_r4_curr)
            current_action_r4_triggered = True

        # Future Condition: date_bcr + 11m falls in next 3 months
        future_check_date_r4 = date_bank_credit_report + relativedelta(months=11)
        if today <= future_check_date_r4 < next_3_months_limit:
             # Optional: Uncomment if future action should NOT be shown if current is already triggered
             # if not current_action_r4_triggered:
                action_str_r4_fut = f"Get CIR (Confidential Information Report) from Banks; the last credit report was obtained on {formatted_bcr_date}"
                if action_str_r4_fut not in next_3_month_actions:
                    next_3_month_actions.append(action_str_r4_fut)

    # --- Process Rule 7 (Last Audit - Special Future Condition) ---
    rule7_current_threshold = relativedelta(months=11)
    rule7_current_action_template = "Account is due for Credit Audit as the last audit was done on <date>"
    rule7_future_action_template = "Account will be due for Credit Audit as the last audit was done on <date>" # Uses last_audit date in text

    # Current Condition (depends only on date_last_audit)
    if date_last_audit:
        formatted_last_audit_date = format_date_for_output(date_last_audit)
        current_due_date_r7 = today - rule7_current_threshold
        if date_last_audit < current_due_date_r7:
            action_str_r7_curr = rule7_current_action_template.replace("<date>", formatted_last_audit_date)
            if action_str_r7_curr not in current_month_actions:
                current_month_actions.append(action_str_r7_curr)

    # Future Condition (depends on date_bank_credit_report, but message uses date_last_audit)
    # Both dates are needed: date_bank_credit_report for the trigger, date_last_audit for the message text
    if date_bank_credit_report and date_last_audit:
        formatted_last_audit_date_for_future = format_date_for_output(date_last_audit) # Date needed for the message
        future_check_date_r7 = date_bank_credit_report + relativedelta(months=11) # Date used for the trigger condition

        if today <= future_check_date_r7 < next_3_months_limit:
            # Optional: Consider if this future action should be suppressed if the *current* audit action was already triggered.
            # Add a check here if needed, e.g., `if action_str_r7_curr not in current_month_actions:`
            action_str_r7_fut = rule7_future_action_template.replace("<date>", formatted_last_audit_date_for_future)
            if action_str_r7_fut not in next_3_month_actions:
                next_3_month_actions.append(action_str_r7_fut)
    elif date_bank_credit_report and not date_last_audit:
         # Log a warning if the trigger date exists but the date needed for the message doesn't
         future_check_date_r7 = date_bank_credit_report + relativedelta(months=11)
         if today <= future_check_date_r7 < next_3_months_limit:
             logger.warning("Rule 7 future condition triggered based on 'date_of_bank_credit_report', but 'date_of_last_audit' is missing for message generation. Skipping future recommendation.")


    # --- Return the lists in a dictionary ---
    return {
        "current_month": current_month_actions,
        "next_3_month": next_3_month_actions
    }


# --- Data Fetching Function ---
def get_recommendations_for_account(account_name: str) -> Dict[str, List[str]]:
    """
    Fetches company data and generates recommendations.
    Handles database errors and missing data scenarios.
    Returns a dictionary with 'current_month' and 'next_3_month' lists.
    """
    company_name_lower = account_name.lower().strip()
    query = """
        SELECT
            cm.company_name,
            cm.customer_id,
            ld.*
        FROM customer_master cm
        LEFT JOIN loan_data ld ON cm.customer_id = ld.customer_id
        WHERE LOWER(TRIM(cm.company_name)) = ?
    """

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (company_name_lower,))
            company_data_row = cursor.fetchone()

            if not company_data_row:
                logger.warning(f"Company '{account_name}' not found in database.")
                raise HTTPException(status_code=404, detail=f"Company '{account_name}' not found.")

            company_data_dict = dict(company_data_row)

            if company_data_dict.get('loan_id') is None:
                 logger.warning(f"Company '{account_name}' found but has no associated loan data.")

            recommendations = generate_recommendations(company_data_dict)
            logger.info(f"Generated {len(recommendations.get('current_month',[]))} current and {len(recommendations.get('next_3_month',[]))} future recommendations for '{account_name}'.")
            return recommendations

    except sqlite3.Error as e:
        logger.error(f"Database error fetching data for '{account_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error accessing database.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred fetching recommendations for '{account_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred.")


# --- API Endpoint ---
# Added Response Model Definition (requires `Dict`, `List` from `typing`)
from typing import Dict, List
class RecommendationResponse(BaseModel): # Requires `from pydantic import BaseModel`
    current_month: List[str]
    next_3_month: List[str]

class FinalResponse(BaseModel): # Requires `from pydantic import BaseModel`
    recommended_action: RecommendationResponse


@router.get("/{account_name}", response_model=FinalResponse) # Use the Pydantic model
async def retrieve_recommendation_endpoint(account_name: str):
    """
    Retrieves recommendations for the current month and the next three months
    for a given account name, formatted as requested.
    """
    # Need pydantic for response_model
    from pydantic import BaseModel # Place at top of file ideally

    logger.info(f"Received request for recommendations for account: '{account_name}'")
    try:
        recommendations_data = get_recommendations_for_account(account_name)

        output = {
            "recommended_action": {
                "current_month": recommendations_data.get('current_month', []),
                "next_3_month": recommendations_data.get('next_3_month', [])
            }
        }
        if not output["recommended_action"]["current_month"] and not output["recommended_action"]["next_3_month"]:
             logger.info(f"No recommendations generated for '{account_name}'.")

        return output

    except HTTPException as http_exc:
        logger.warning(f"HTTP Exception for '{account_name}': {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error processing request for '{account_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve recommendations due to an internal server error.")

# Remember to add `from pydantic import BaseModel` at the top of your file
# if you use the response_model feature as shown.