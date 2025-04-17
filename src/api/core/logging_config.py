import logging
import sys
from .config import LOG_FILE, API_LOGGER_NAME, APP_TASK_LOGGER_NAME

def setup_logging():
    """Configures logging, avoiding redundant basicConfig calls."""
    # Check if the root logger already has handlers configured
    # This helps prevent issues when the module is reloaded by Uvicorn's reloader
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        logging.warning("Logging already configured. Skipping basicConfig.")
        # Optionally, just add the file handler if it's missing
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(LOG_FILE) for h in root_logger.handlers):
             file_handler = logging.FileHandler(LOG_FILE)
             formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(name)s] - %(message)s")
             file_handler.setFormatter(formatter)
             root_logger.addHandler(file_handler)
             logging.info(f"Added missing FileHandler for {LOG_FILE}")
        return # Exit if already configured

    # If no handlers, configure fresh
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout) # Also log to console
        ]
    )
    logging.info("Logging configured.")