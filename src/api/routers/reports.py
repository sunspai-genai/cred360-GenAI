import json
import logging
import base64
import os
import re
from typing import List, Dict, Any
import markdown2
from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path

# Use relative imports within the 'api' package
from ..core.config import API_CONFIG
from ..utils.helpers import sanitize_filename, find_latest_run_dir

router = APIRouter(
    prefix="/reports",  # Add a prefix for all routes in this router
    tags=["Reports"]    # Tag for OpenAPI documentation
)
logger = logging.getLogger(__name__)


def get_analysis_reports(account_name: str) -> List[Dict[str, Any]]:
    """
    Retrieve analysis reports (individual sheets + cumulative)
    for a specific account FROM THE LATEST RUN.
    Converts Markdown to HTML. Uses configuration directly from core.config.
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

    # --- Define paths relative to the latest run directory ---
    reports_dir_name = API_CONFIG["ANALYZER_CONFIG"]["reports_dir"]
    graph_dir_name = API_CONFIG["ANALYZER_CONFIG"]["graph_dir"]
    graph_data_dir_name = API_CONFIG["ANALYZER_CONFIG"]["graph_data_dir"]
    file_encoding = API_CONFIG["ANALYZER_CONFIG"]["file_encoding"]
    cumulative_report_filename = "Cumulative_Report.md" # Standard name for cumulative

    reports_dir = latest_run_dir / reports_dir_name
    graph_dir = latest_run_dir / graph_dir_name
    graph_data_dir = latest_run_dir / graph_data_dir_name

    report_files_content = []
    processed_reports = set() # Keep track of base names processed

    # --- Get individual reports from the latest run's reports directory ---
    if reports_dir.is_dir():
        logger.info(f"Searching for individual reports in: {reports_dir}")
        individual_report_pattern = "*.md"
        for report_path in reports_dir.glob(individual_report_pattern):
            if not report_path.is_file():
                continue

            filename = report_path.name
            base_name = report_path.stem

            # Skip the cumulative report here, handle it separately
            if filename == cumulative_report_filename:
                logger.debug(f"Skipping cumulative report file in individual loop: {filename}")
                continue

            if base_name in processed_reports:
                logger.debug(f"Skipping already processed base report name: {base_name}")
                continue

            logger.info(f"Processing individual report: {report_path}")
            try:
                charts_per_sheet = []
                # Extract sheet name from filename (e.g., profit_&_loss_statement -> Profit & Loss Statement)
                report_name = base_name.replace('_', ' ').title()

                with open(report_path, 'r', encoding=file_encoding) as f:
                    content_md = f.read()
                    content_html = markdown2.markdown(content_md, extras=["tables", "fenced-code-blocks", "code-friendly"])

                # --- Look for corresponding graphs in the latest run's graph directory ---
                # Assume graph subfolder name matches the report base name (e.g., graphs/profit_&_loss_statement/)
                individual_graph_dir = graph_data_dir / base_name
                if individual_graph_dir.is_dir():
                    logger.info(f"Searching for graphs in: {individual_graph_dir}")
                    individual_graph_pattern = "*.json"
                    for graph_path in individual_graph_dir.glob(individual_graph_pattern):
                        if not graph_path.is_file():
                            continue
                        graph_filename = graph_path.name
                        logger.debug(f"Processing graph: {graph_path}")
                        try:
                            with open(graph_path, 'r') as graph_file:
                                graph_content = json.loads(graph_file.read())
                                charts_per_sheet.append(graph_content)
                                # # Encode as base64 to embed in HTML/JSON
                                # svg_content_base64 = base64.b64encode(graph_content).decode('utf-8')
                                # charts_per_sheet[graph_filename] = f"data:image/svg+xml;base64,{svg_content_base64}"
                        except Exception as graph_e:
                             logger.error(f"Error reading or encoding graph {graph_path}: {graph_e}")

                report_files_content.append({
                    'report_name': report_name,
                    'content': content_html,
                    'type': 'individual',
                    'charts': charts_per_sheet
                })
                processed_reports.add(base_name) # Mark as processed

            except Exception as e:
                logger.error(f"Error reading or processing report {report_path}: {e}")
    else:
        logger.warning(f"Individual reports directory not found in latest run: {reports_dir}")

    # --- Get Cumulative Report from the latest run's reports directory ---
    cumulative_path = latest_run_dir / cumulative_report_filename
    logger.info(f"Checking for cumulative report in latest run: {cumulative_path}")

    if cumulative_path.is_file():
        try:
            with open(cumulative_path, 'r', encoding=file_encoding) as file:
                content_md = file.read()
                content_html = markdown2.markdown(content_md, extras=["tables", "fenced-code-blocks", "code-friendly"])
                report_files_content.append({
                     'report_name': "Cumulative Report",
                     'content': content_html,
                     'type': 'cumulative',
                     'charts': [] # Assuming no specific charts for cumulative, adjust if needed
                })
                logger.info(f"Successfully processed cumulative report from latest run: {cumulative_path}")
        except Exception as e:
             logger.error(f"Error reading or processing cumulative report {cumulative_path}: {e}")
    else:
        logger.warning(f"Cumulative report not found in latest run at {cumulative_path}")

    if not report_files_content:
        # Raise 404 only if *no* reports (individual or cumulative) were found *in the latest run*
        raise HTTPException(status_code=404, detail=f"No reports found in the latest run for account: {account_name}")

    report_files_content.sort(key=lambda x: (x['type'] != 'cumulative', x['report_name']))

    return report_files_content


@router.get("/{account_name}", response_model=List[Dict[str, Any]])
async def retrieve_reports_endpoint(account_name: str):
    """
    Retrieves the analysis reports (individual sheets and cumulative)
    from the LATEST RUN for a given account name.
    Reports are returned as HTML content with embedded charts.
    """
    logger.info(f"Received request to retrieve latest run reports for account: {account_name}")
    try:
        reports = get_analysis_reports(account_name)
        return reports
    except HTTPException as http_exc:
        # Log HTTP exceptions specifically if needed, otherwise re-raise
        logger.warning(f"HTTP Exception retrieving latest reports for {account_name}: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error retrieving latest reports for account {account_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve reports due to an internal server error.")