import os

import markdown2
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import re

from starlette.requests import Request

app = FastAPI(title="Markdown Retriever API")


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


@app.get("/cma_data")
async def retrieve_compressive_report(request:Request):
    """
    API endpoint to retrieve markdown files for a specific account and sheet
    """
    try:
        request_body = await request.json()
        account_name = request_body.get("account_name",None)
        if account_name:
            markdown_files = get_cumulative_report(account_name)
            return JSONResponse(content={
                "status": "success",
                "reports": markdown_files
            })
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "status": "error",
                "message": str(e.detail)
            }
        )

# Optional: Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
