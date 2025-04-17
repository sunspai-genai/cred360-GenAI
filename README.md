# CMA Analysis Tool

This tool automates the analysis of CMA (Credit Monitoring Arrangement) data from Excel files using Large Language Models (LLMs) and a LangGraph workflow. It extracts data, performs calculations, and generates reports.

## Prerequisites

*   **Python 3.12**
*   **Azure OpenAI Account:** You need an Azure OpenAI account with access to a suitable model (e.g., `gpt-4o`).
*   **Environment Variables:**  Set the following environment variables:
    *   `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key.
    *   `AZURE_ENDPOINT`: Your Azure OpenAI endpoint.
    *   `AZURE_API_VERSION`: The Azure OpenAI API version you are using.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2. **Install dependencies (using pip):**

    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  **Environment Variables:**  Ensure the required environment variables are set.  You can create a `.env` file in the project root:

    ```
    AZURE_OPENAI_API_KEY=<your_azure_openai_api_key>
    AZURE_ENDPOINT=<your_azure_openai_endpoint>
    AZURE_API_VERSION=<your_azure_openai_api_version>
    ```

2.  **Configuration File (`CONFIG` dictionary):**  The `CONFIG` dictionary in the `cma_analyzer.py` file allows you to customize the tool's behavior.  Key settings include:

    *   `log_level`:  The logging level (e.g., `logging.INFO`, `logging.DEBUG`).
    *   `model_name`:  The name of the Azure OpenAI model to use (e.g., `"gpt-4o"`).
    *   `agent_type`:  The type of Langchain agent to use (e.g., `AgentType.ZERO_SHOT_REACT_DESCRIPTION`).
    *   `sheets_to_analyze`:  A list of sheet names to analyze from the Excel file.
    *   `data_extraction_format_filename`: The name of the JSON file containing the data extraction format.  This file should be located in `src/data/input_data_sources/<account>/`.
    *   `extracted_markdown_dir`: The directory where extracted Markdown files are saved.
    *   `extracted_metrics_dir`: The directory where extracted metrics are saved.
    *   `reports_dir`: The directory where analysis reports are saved.
    *   `file_encoding`: The encoding to use for reading and writing files (e.g., `"utf-8"`).

3.  **Data Extraction Format:** Create a JSON file (specified by `data_extraction_format_filename` in the `CONFIG`) that defines the format for extracting data from each sheet.  This file should be located in `src/data/input_data_sources/<account>/`.  See the example structure in the code comments.

4.  **Input Data:** Place your CMA Excel files in the `src/data/input_data_sources/<account>/` directory.

## Usage

1.  **Run the Cred360 APIs:**
    ```bash
    cd cred360/src/api
    uvicorn cred360_API:api --host 0.0.0.0 --port 8003 --loop asyncio
    ```

2.  **Output:** The tool will generate the following output:

    *   **Logs:**  Detailed logs are written to `src/logs/cma_analysis_<timestamp>.log`.
    *   **Extracted Markdown:** Markdown representations of the extracted data are saved in `src/output/<account_name>/extracted_markdown/<sheet_name>_<timestamp>.md`.
    *   **Extracted Metrics:** Extracted metrics in the required format are saved in `src/output/<account_name>/extracted_metrics/<sheet_name>_<timestamp>.md`.
    *   **Calculated Metrics:** Calculated metrics in the dataframe format are saved in `src/output/<account_name>/audit_data/<sheet_name>_<timestamp>.md`.
    *   **Analysis Reports:** Analysis reports for each sheet are saved in `src/output/<account_name>/reports/<sheet_name>.md`.
    *   **Cumulative Reports:** Cumulative reports are saved in `src/output/<account_name>/Cumulative Report.md`.

## Directory Structure

cred360/
├── src/
│ ├── agents
│ │ ├── CMA_Data_Analyzer_with_MCP_Graph.py   # Agent to analyze excel data, generate reports and cumulative report.
│ │ ├── CMA_Customer_Alerts.py   # Agent to analyze P & L Statement, Balance Sheet, Summary Sheet ,Ratio and generate customer alerts.
│ ├── api #API endpoints for Cred360
│ ├── tools
│ │ ├── mcp_tools.py # MCP tools
│ │ ├── AlertTool.py # Tool to generate alerts
│ ├── logs/ # Directory for log files
│ ├── database/ # Directory for DB files
│ │ ├── cred360.db  # Used to store token usage 
│ │ ├── cred360_ddl.sql  # DDL Script to create required tables.
│ ├── data/
│ │ ├── input_data_sources/
│ │ │ ├── data_extraction_format.json # Data extraction format
│ │ │ ├── ltimindtree/ # Example account directory
│ │ │ │ ├── 1. CMA_Data.xlsx # Example CMA Excel file
│ ├── output/
│ │ ├── ltimindtree/ # Output directory for ltimindtree
│ │ │ ├── extracted_markdown/ # Extracted Markdown files
│ │ │ ├── extracted_metrics/ # Extracted metrics files
│ │ │ ├── audit_data/ # Calculated values of tool
│ │ │ ├── customer_alerts/ # Used to store customer alerts
│ │ │ ├── reports/ # Analysis reports
│ │ │ ├── graphs/ #Generated Graphs
│ │ │ ├── Cumulative Report.md
│ ├── prompts/  
│ │ ├── graph_prompts.py  # Graph Prompts for respective sheets
│ │ ├── prompt_utils.py   # Report Prompts for respective sheets
├── requirements.txt   # Project dependencies
├── README.md # This file

## Troubleshooting

*   **Missing Environment Variables:**  Ensure all required environment variables are set correctly.
*   **Azure OpenAI Errors:**  Check your Azure OpenAI account and model deployment for any issues.
*   **Dependency Issues:**  Make sure all dependencies are installed correctly, especially if using `pip`.
*   **File Not Found Errors:**  Verify that the Excel file path and data extraction format file path are correct.
*   **Data Extraction Errors:**  Review the data extraction format file to ensure it matches the structure of your Excel sheets.
*   **Agent Errors:** Check the logs for errors from the LLM agent.  Adjust the prompts or tools as needed.