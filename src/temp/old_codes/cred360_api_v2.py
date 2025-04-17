import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import logging
import os
import shutil
from typing import Optional
import markdown2
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import re
from pathlib import Path
from src.temp.old_codes.app import main

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api = FastAPI(title="Markdown Retriever API")




def sanitize_input(input_string):
    """
    Sanitize input to prevent directory traversal and ensure safe file access
    """
    # Remove any non-alphanumeric characters except underscores and hyphens
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', input_string).lower()
    return sanitized

def get_cumulative_report(account_name):
    """
    Retrieve Compressive Report for a specific account
    """
    # Sanitize inputs
    safe_account = sanitize_input(account_name)

    # Define the base directory for markdown files
    base_dir = os.path.join('../../output', safe_account, "reports")

    # Check if directory exists
    if not os.path.exists(base_dir):
        raise HTTPException(status_code=404, detail=f"No Reports found for given account - {account_name}")

    # Collect markdown files
    markdown_files = []
    for filename in os.listdir(base_dir):
        if filename.endswith('.md'):
            if "_" not in filename:
                file_path = os.path.join(base_dir, filename)

                # Read file contents
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_content = markdown2.markdown(file.read())

                markdown_files.append({
                    'report_name': filename.split(".")[0].title(),
                    'content': file_content
                })

    cumulative_path = os.path.join('../../output', safe_account, "Cumulative Report.md")

    if not os.path.exists(cumulative_path):
        file_content = []
    else:
        with open(cumulative_path, 'r', encoding='utf-8') as file:
            file_content = markdown2.markdown(file.read())

    markdown_files.append({
        'report_name': "Cumulative Report",
        'content': file_content
        })

    # If no markdown files found
    if not markdown_files:
        raise HTTPException(status_code=404, detail=f"No Reports found for account - {account_name}")

    return markdown_files


@api.post("/cma_data")
def retrieve_compressive_report(account_name= Form(...),file: Optional[UploadFile] = File(None)):
    """
    API endpoint to retrieve markdown files for a specific account and sheet
    """
    try:
        # request_body = await request.json()
        account_name = sanitize_input(account_name)
        print(account_name)
        account_dir = Path(f"../data/input_data_sources/{account_name}")
        account_dir.mkdir(parents=True, exist_ok=True)

        if file and account_name:
            try:
                # Save the uploaded file to the account's directory
                file_path = os.path.join(account_dir, file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                logger.info(f"File uploaded: {file_path}")
                logger.info("Starting Analysis....")
                main(account_name)
                logger.info("Analysis Completed.")
            except Exception as e:
                logger.exception(f"File upload failed: {str(e)}")
                raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
        # if account_name:
        #     markdown_files = get_cumulative_report(account_name)
        #     return JSONResponse(content={
        #         "status": "success",
        #         "reports": markdown_files
        #     })
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "status": "error",
                "message": str(e.detail)
            }
        )

# Optional: Health check endpoint
@api.get("/health")
async def health_check():
    return {"status": "healthy"}
