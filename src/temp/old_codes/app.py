import asyncio
import logging
import os
from datetime import datetime
from src.agents.CMA_Data_Analyzer_with_MCP import CMAAnalyzer
import sys
import os

async def run_cma_analysis_task(account_name):

    print(account_name)
    # --- Configuration and Setup ---

    # 1. Centralized Configuration:  Use a dictionary or config file for settings.
    # "profit & loss statement","fund flow","fund flow2",
    # ,"fund flow","fund flow2","balance sheet","balance sheet2"
    CONFIG = {
        "log_level": logging.INFO,
        "model_name": "gpt-4o",
        # "model_name": "gemini-1.5-flash",
        # "sheets_to_analyze": ["balance sheet","balance sheet2","dscr"],  # Define sheets to analyze
        "data_extraction_format_filename": "data_extraction_format.json",
        "extracted_markdown_dir": "extracted_markdown",
        "extracted_metrics_dir": "extracted_metrics",
        "reports_dir": "reports",
        "file_encoding": "utf-8",
    }

    # 2. Logging Configuration:  Initialize logger at the module level.
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    CWD = os.getcwd()
    LOG_FILE = os.path.join(CWD, f"logs/{account_name}_cma_analysis_{TIMESTAMP}.log")
    print(LOG_FILE)
    logging.basicConfig(
        level=CONFIG["log_level"], format="%(asctime)s - %(levelname)s - %(message)s", filename=LOG_FILE
    )
    logger = logging.getLogger(__name__)
    excel_file_path = os.path.join(CWD, rf"data\input_data_sources\{account_name}\1. CMA_Data.xlsx")
    output_path = os.path.join(CWD, f"output/{account_name}")
    mcp_server_path = os.path.join(CWD, r"tools/mcp_tools.py")
    analyzer = CMAAnalyzer(output_path=output_path, account=account_name, config=CONFIG, mcp_server_path=mcp_server_path,
                           logger=logger)
    try:
        await analyzer.run_analysis(excel_file_path)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")

if __name__ == "__main__":
    account = "ltimindtree"
    print(account)
    main(account)
