import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Regex to identify run directories (adjust if your pattern differs)
# Assumes run directories start with 'run_' followed by YYYYMMDD_HHMMSS
run_dir_pattern = re.compile(r'^run_\d{8}_\d{6}$')

def sanitize_filename(input_string: str) -> str:
    """Sanitize input to prevent directory traversal and ensure safe file access."""
    if not input_string:
        return ""
    # Remove potentially harmful chars, allow alphanumeric, underscore, hyphen
    # sanitized = re.sub(r'[^\w\-]+', '_', input_string)
    sanitized = re.sub(r'[-, ]+', '_', input_string)
    # Limit length
    return sanitized.lower().strip()

def find_latest_run_dir(account_base_dir: Path) -> Optional[Path]:
    """Finds the latest run directory within the account's base directory."""
    run_dirs = []
    if not account_base_dir.is_dir():
        logger.warning(f"Account base directory not found: {account_base_dir}")
        return None

    for item in account_base_dir.iterdir():
        if item.is_dir() and run_dir_pattern.match(item.name):
            run_dirs.append(item)

    if not run_dirs:
        logger.warning(f"No run directories found matching pattern in: {account_base_dir}")
        return None

    # Sort directories lexicographically by name (YYYYMMDD_HHMMSS ensures latest is last)
    run_dirs.sort(key=lambda x: x.name)
    latest_run_dir = run_dirs[-1]
    logger.info(f"Identified latest run directory: {latest_run_dir}")
    return latest_run_dir
