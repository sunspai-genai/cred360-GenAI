import logging
from datetime import datetime
from pathlib import Path

# Import the analyzer class
try:
    # Assuming app.py is in 'src' and analyzer is in 'src/agents'
    from agents.CMA_Data_Analyzer_with_MCP_Graph import CMAAnalyzer
except ImportError:
    # Fallback if structure is different or running from another context
    from src.agents.CMA_Data_Analyzer_with_MCP_Graph import CMAAnalyzer


async def run_cma_analysis_task(
    account_name: str,
    excel_file_path: str, # Pass the specific file path
    output_base_dir: str, # Pass the base output directory
    mcp_server_path: str, # Pass the absolute path
    config: dict,
    logger: logging.Logger
):
    """
    Asynchronous task to run the CMA analysis.
    Designed to be awaited by an async API endpoint.
    """
    logger.info(f"--- Starting CMA Analysis Task for Account: {account_name} ---")
    logger.info(f"Input Excel: {excel_file_path}")
    logger.info(f"Output Base: {output_base_dir}")
    logger.info(f"MCP Server: {mcp_server_path}")

    # Define output path specific to this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(output_base_dir) / account_name / f"run_{timestamp}"
    logger.info(f"Full Output Path for this run: {output_path}")

    # Ensure paths exist before passing to analyzer
    Path(excel_file_path).parent.mkdir(parents=True, exist_ok=True)
    # output_path.parent.mkdir(parents=True, exist_ok=True) # Create account dir if needed

    analyzer = CMAAnalyzer(
        output_path=str(output_path), # Pass the run-specific path
        account=account_name,
        config=config,
        mcp_server_path=mcp_server_path,
        logger=logger
    )

    final_state = None
    try:
        # Use 'async with' for proper MCP client lifecycle management per request
        async with analyzer:
            final_state = await analyzer.run_analysis(excel_file_path)
        logger.info(f"--- CMA Analysis Task Completed for Account: {account_name} ---")
        return final_state # Return the result state

    except FileNotFoundError as e:
         logger.error(f"File not found during analysis task: {e}", exc_info=True)
         raise # Re-raise for the API to catch
    except ValueError as e:
         logger.error(f"Configuration or value error during analysis task: {e}", exc_info=True)
         raise # Re-raise
    except Exception as e:
        logger.error(f"Analysis task failed unexpectedly: {e}", exc_info=True)
        raise # Re-raise
    # No finally block needed here, 'async with' handles cleanup

# Note: The if __name__ == "__main__": block from the original app.py
# is now effectively replaced by the standalone execution logic
# at the end of CMA_Data_Analyzer_with_MCP.py for testing purposes.
# This app.py file now only contains the async task function.