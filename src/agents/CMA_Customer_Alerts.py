import os
import re
import json
import pandas as pd
from datetime import datetime
from textwrap import dedent
from typing import List, Dict, Any, Optional # Added Optional
from pathlib import Path # Use pathlib for better path handling

# Third-party imports
from dotenv import load_dotenv, find_dotenv
from openpyxl import Workbook # Keep if needed for direct manipulation, else remove
from openpyxl.utils.dataframe import dataframe_to_rows # Keep if needed
from openpyxl.styles import Font, Border, Side, Alignment # Keep if needed
from PIL import Image # Keep if needed

# LangChain and LangGraph imports
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.tools.AlertTool import create_alerts_data, classify_financial_attributes

# Removed unused imports: sqlglot, sqlparse, AzureChatOpenAI, ChatOllama

# --- Configuration ---
# Load environment variables ONCE at the start
load_dotenv(find_dotenv(), verbose=True, override=True)

# Define constants for paths and configurations

# --- Helper Function (can be static method or standalone) ---
def remove_llm_formatting(text: str) -> str:
    """Removes markdown code block fences and language specifiers."""
    if not isinstance(text, str):
        return "" # Return empty string if input is not string
    # Remove potential markdown code block fences and language specifier (like ```json)
    text = re.sub(r'^```(json)?\s*', '', text.strip(), flags=re.MULTILINE)
    # Remove potential closing ```
    text = re.sub(r'\s*```$', '', text.strip())
    return text.strip()

# --- Main Class ---
class FinancialDataExtractor:
    """
    Orchestrates the process of extracting financial data from Excel,
    processing it, using an LLM via LangGraph, and saving the results.
    """

    def __init__(self,
                 excel_file_path: str | Path,
                 customer_alert_output_directory: str,
                 config,llm
                 ):
        """
        Initializes the extractor with necessary configurations.

        Args:
            excel_file_path: Path to the input Excel file.
            customer_alert_output_directory: Directory to save intermediate Markdown files.
        """
        self.customer_alert_output_directory = customer_alert_output_directory
        self.excel_file_path = Path(excel_file_path)
        self.config = config
        self.llm = llm
        self.sheets_to_process = ['Profit & Loss Statement', 'Balance Sheet', 'Balance Sheet2', 'Summary Sheet', 'Ratio']

        self.target_date = self._calculate_target_date()
        self.base_sheet_names: List[str] = [] # To store unique base names for combining

        print(f"Initialized FinancialDataExtractor:")
        print(f"  Excel File: {self.excel_file_path}")
        print(f"  Sheets: {self.sheets_to_process}")
        print(f"  Target Date: {self.target_date}")
        print(f"  Output Path: {self.customer_alert_output_directory}")

    def _calculate_target_date(self) -> str:
        """Calculates the target date based on the current month (end of last FY)."""
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        # Determine the date based on the current month (Financial Year ends March 31st)
        if current_month > 3: # April onwards - FY ended March 31st of current year
            date_str = f"31.03.{current_year}"
        else: # Jan, Feb, March - FY ended March 31st of *previous* year
            date_str = f"31.03.{current_year - 1}"
        print(f"Determined target date: {date_str}")
        return date_str

    def preprocess_excel_to_markdown(self) -> None:
        """
        Extracts data from specified Excel sheets, combines sheets with the same base name,
        and saves them as individual Markdown files.
        """
        print(f"\n--- Preprocessing Excel file: {self.excel_file_path} ---")
        if not self.excel_file_path.exists():
            print(f"Error: Excel file not found at {self.excel_file_path}")
            raise FileNotFoundError(f"Excel file not found: {self.excel_file_path}")

        if not self.sheets_to_process:
            print("Warning: No sheet names provided for processing.")
            return

        excel_file = pd.ExcelFile(self.excel_file_path)
        text = ""
        for sheet in self.sheets_to_process:
            excel_data = pd.read_excel(excel_file, engine="openpyxl", sheet_name=sheet)
            cleaned_excel_data = excel_data.dropna(how="all").fillna("").reset_index(drop=True)
            markdown_text = cleaned_excel_data.to_markdown(index=False)  # Often better without index
            text = text + f"##### Sheet: {sheet}\n\n{markdown_text}\n\n"

        if "text" in locals() and text:
            combine_markdown_file_path = Path(self.customer_alert_output_directory) / "combined_data.md"
            with open(combine_markdown_file_path, "w", encoding=self.config.get("file_encoding", "utf-8")) as md_file:
                md_file.write(text)
        print("--- Excel preprocessing finished ---")


    def combine_markdown_files(self) -> None:
        """
        Combines the content of the generated Markdown files into a single file.
        Uses the `base_sheet_names` generated during preprocessing.
        """
        print(f"\n--- Combining Markdown files into: {self.combined_data_path} ---")
        all_content = ""
        files_processed_count = 0

        if not self.base_sheet_names:
            print("Warning: No base sheet names found from preprocessing. Cannot combine files.")
            # Ensure the combined file is empty if it exists from a previous run
            if self.combined_data_path.exists():
                 self.combined_data_path.unlink()
            return

        for base_name in self.base_sheet_names:
            file_path = self.processed_inputs_dir / f"{base_name}.md"
            if file_path.exists():
                try:
                    print(f"  Reading: {file_path}")
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                    # Add a header for clarity in the combined file
                    all_content += f"## Content from: {base_name}.md\n\n{content}\n\n---\n\n"
                    files_processed_count += 1
                except Exception as e:
                    print(f"  Error reading file {file_path}: {e}")
            else:
                print(f"  Warning: File {file_path} does not exist. Skipping.")

        if all_content:
            try:
                with open(self.combined_data_path, 'w', encoding='utf-8') as md_file:
                    md_file.write(all_content)
                print(f"--- Combined content from {files_processed_count} file(s) written to {self.combined_data_path} ---")
            except Exception as e:
                 print(f"Error writing combined file {self.combined_data_path}: {e}")
        else:
            print("--- No content found to combine. Combined file not created or overwritten. ---")
            # Ensure the combined file is empty if it exists from a previous run
            if self.combined_data_path.exists():
                 self.combined_data_path.unlink()


    @staticmethod
    def _build_system_prompt(target_date: str) -> str:
        """Builds the system prompt for the LLM, inserting the target date."""
        # **Crucially, escape literal curly braces in the JSON example with {{ and }}**
        return dedent(f"""
            You are a specialized data extraction agent. Your task is to process the provided text, locate specific data tables (like Profit & Loss, Balance Sheet, Ratios, Summary), and extract numerical values *only* from the column corresponding to the specific date '{target_date}' and designated as 'Actuals'. Format this extracted data into a precise JSON structure.

            **Instructions:**

            1.  **Scan the Text:** Search the input text (which contains combined data from different sheets like 'Profit & Loss Statement', 'Balance Sheet', 'Ratio', 'Summary Sheet') for tables containing financial or operational data structured with row headers (like 'Gross Sales Local', 'Depreciation', 'Current Ratio', etc.) and columns representing time periods.
            2.  **Identify Target Column:**
                *   Within each relevant table, look for a column header that explicitly represents the fiscal year ending on **'{target_date}'**. The format in the table might be exactly '{target_date}', 'FY {target_date}', 'FY{target_date[-4:]}', or similar variations. Prioritize exact matches but be flexible.
                *   Verify that this specific column is also designated with the label **'Actuals'** (often found directly beneath the date header or as part of a combined header). This identified column is your sole target column for data extraction within that table.
            3.  **Extract Values:**
                *   For each row header in the tables that *exactly matches* one of the keys listed in the target JSON format below, extract its corresponding numerical value *only* from the single target column identified in step 2 (the '{target_date}' Actuals column). Extract numbers precisely (e.g., 1.23, 5.00, 10). If a value is represented like '(0.50)', extract it as -0.50. Handle thousands separators (,) correctly.
            4.  **Format Output:** Structure the extracted data *strictly* into the following JSON format. Use the row headers from the tables as the source for the values corresponding to the JSON keys.

                ```json
                {{{{
                    "Date": ["{target_date}"],
                    "Period_Type": ["Actuals"],
                    // Look for the below in Profit & Loss Statement section
                    "Gross Sales Local": [],
                    "Gross Sales Exports": [],
                    "Raw Materials Imported": [],
                    "Raw Materials Indigeneous": [],
                    "Other Spares": [],
                    "Power & Fuel": [],
                    "Direct Labour": [],
                    "Repairs & Main": [],
                    "Other Operating Exp": [],
                    "Depreciation": [],
                    "Opening S.I.P.": [],
                    "Closing S.I.P": [],
                    "SG&A Expenses": [],
                    "Interest": [],
                    // Look for the below in Balance Sheet section
                    "a) R.M. Imported": [],
                    "b) R.M. Indigenous": [],
                    "c) Stock in Process": [],
                    "d) Finished Goods": [],
                    "e) Other Consumables": [],
                    // Look for the below in Ratio section
                    "Current Ratio": [],
                    "Debt/Equity Ratio": [],
                    "TOL/TNW Ratio": [],
                    "Debt/EBIDTA %": [],
                    "Net Profit margin %": [],
                    "Cash Accruals": [],
                    // Look for the below in Summary Sheet section
                    "Adjusted TNW": [],
                    "Net Sales": [], // Domestic + Export
                    "Return on Equity %": [],
                    "FACR": [],
                    "Current Assets": [],
                    "Current Liabilities": [],
                    "DSCR": [] // Look for only value in summary sheet **Average DSCR (for**
                }}}}
                ```
                *(Instructions for filling the JSON values based on extracted data)*
                *   For each key above (like "Gross Sales Local"), find the matching row header in the relevant table section (P&L, Balance Sheet, etc.).
                *   Extract the numeric value from that row *within the '{target_date}' Actuals column*.
                *   Place the extracted numeric value inside the list for that key, e.g., `"Depreciation": [1.20]`. If the value is clearly zero, use `[0.0]` or `[0]`. If the value is negative like (0.50), use `[-0.50]`.
                *   For "DSCR", specifically look for a row like "Average DSCR (for..." and extract the value associated with it for the target date/actuals column.

            5.  **Handling Missing Data:**
                *   If a row header matching a JSON key (e.g., "Other Spares") is *not found* in the relevant table section, use an empty list `[]` for its value in the output JSON.
                *   If a matching row header *is* found, but its value in the target '{target_date}' Actuals column is blank, non-numeric (e.g., '-', 'NA', ' '), or explicitly missing, use an empty list `[]` for its value.
                *   Ensure the output JSON contains *all* the specified keys from the template, even if their values are empty lists.
            6.  **Strict Focus:** Extract data *exclusively* from the identified '{target_date}' Actuals column within the relevant tables. Ignore all data from other columns (different dates, 'Estimated', etc.) and any text outside the relevant table structures, except for the specific "Average DSCR (for..." case.
            7.  **Output Purity:** Provide *only* the final JSON object as the output. Do not include any introductory text, explanations, comments, or markdown formatting (like ```json ... ```) around the JSON. Just the raw, valid JSON structure.

            Now, process the following text based on these instructions:
        """)

    def extract_math_data_agent(self,input_filepath):
        """
        LangGraph node: Reads data, calls LLM, cleans/validates result.
        Uses configuration passed via the state dictionary.
        """
        llm_response = None
        status="failed"
        print(f"Reading data from: {input_filepath}")
        with open(input_filepath, "r", encoding="utf-8") as f:
            data = f.read()
        system_prompt = dedent(f"""
                    You are a specialized data extraction agent. Your task is to process the provided text, locate a specific data table, and extract numerical values *only* from the column corresponding to the specific date '{self.target_date}' and designated as 'Actuals'. Format this extracted data into a precise JSON structure.

                    **Instructions:**

                    1.  **Scan the Text:** Search the input text for a table containing financial or operational data structured with row headers (like 'Gross Sales Local', 'Depreciation', etc.) and columns representing time periods.
                    2.  **Identify Target Column:**
                        *   Look for a column header that explicitly represents the fiscal year ending on **'{self.target_date}'**. The format in the table might be exactly '{self.target_date}', 'FY {self.target_date}', 'FY{self.target_date[-4:]}', or similar variations. Prioritize exact matches but be flexible.
                        *   Verify that this specific column is also designated with the label **'Actuals'** (often found directly beneath the date header). This identified column is your sole target column for data extraction. If multiple tables exist, find the one most likely containing these operational/financial items.
                    3.  **Extract Values:**
                        *   For each row header in the table that *exactly matches* one of the keys listed in the target JSON format below, extract its corresponding numerical value *only* from the single target column identified in step 2 (the '{self.target_date}' Actuals column). Extract numbers precisely (e.g., 1.23, 5.00, 10). If a value is represented like '(0.50)', extract it as -0.50.
                    4.  **Format Output:** Structure the extracted data *strictly* into the following JSON format. Use the row headers from the table as the source for the values corresponding to the JSON keys.

                        ```json
                        {{{{  # <-- Escaped outer brace
                            "Date": ["{self.target_date}"], # <-- Variable insertion uses single braces
                            "Period_Type": ["Actuals"],
                            / Look for the below in pl statement sheet
                            "Gross Sales Local": [],
                            "Gross Sales Exports": [],
                            "Raw Materials Imported": [],
                            "Raw Materials Indigeneous": [],
                            "Other Spares": [],
                            "Power & Fuel": [],
                            "Direct Labour": [],
                            "Repairs & Main": [],
                            "Other Operating Exp": [],
                            "Depreciation": [],
                            "Opening S.I.P.": [],
                            "Closing S.I.P": [],
                            "SG&A Expenses": [],
                            "Interest":[],
                            // Look for the below in Balance Sheet
                            "a) R.M. Imported":[], 
                            "b) R.M. Indigenous":[],
                            "c) Stock in Process":[],
                            "d) Finished Goods":[],
                            "e) Other Consumables":[],
                            // Look for the below in Ratio sheet
                            "Current Ratio" : [],
                            "Debt/Equity Ratio": [],
                            "TOL/TNW Ratio" : [],
                            "Debt/EBIDTA %":[],
                            "Net Profit margin %":[],
                            "Cash Accruals":[],
                            // Look for the below in Summary sheet
                            "Adjusted TNW":[],
                            "Net Sales":[], //Domestic + Export
                            "Return on Equity %": [],
                            "FACR":[],
                            "Current Assets": [],
                            "Current Liabilities": [],
                            "DSCR": [],//look for only value in summary sheet **Average DSCR (for**
                        }}}} # <-- Escaped outer brace
                        ```
                        *(Instructions for filling the JSON values based on extracted data)*
                        *   For each key above (like "Gross Sales Local"), find the matching row header in the table.
                        *   Extract the numeric value from that row *within the '{self.target_date}' Actuals column*.
                        *   Place the extracted numeric value inside the list for that key, e.g., `"Depreciation": [1.20]`. If the value is clearly zero, use `[0.0]` or `[0]`.

                    5.  **Handling Missing Data:**
                        *   If a row header matching a JSON key (e.g., "Other Spares") is *not found* in the table, use an empty list `[]` for its value in the output JSON.
                        *   If a matching row header *is* found, but its value in the target '{self.target_date}' Actuals column is blank, non-numeric (e.g., '-', 'NA', ' '), or explicitly missing, use an empty list `[]` for its value.
                        *   Ensure the output JSON contains *all* the specified keys from the template.
                    6.  **Strict Focus:** Extract data *exclusively* from the identified '{self.target_date}' Actuals column. Ignore all data from other columns (different dates, 'Estimated', etc.) and any text outside the relevant table structure,execpt for "Average DSCR (for".
                    7.  **Output Purity:** Provide *only* the final JSON object as the output. Do not include any introductory text, explanations, comments, or markdown formatting (like ```json ... ```) around the JSON. Just the raw, valid JSON structure.

                    Now, process the following text based on these instructions:
            """)

        # --- 4. Setup LangChain Components ---
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "Data:\n{input_data}")  # Use a placeholder for data
            ]
        )

        try:
            chain = prompt_template | self.llm
            print("LLM and chain initialized successfully.")
            print("Invoking LLM chain...")
            # Pass the actual data content to the 'input_data' variable in the prompt
            llm_agent = chain.invoke({"input_data": data})
            llm_response = llm_agent
            print("LLM invocation successful.")
            if hasattr(llm_agent, 'content'):
                status = "completed"
                result = llm_agent.content
            else:
                status = "failed"

        except Exception as e:
            error =  f"Error initializing LLM or chain: {str(e)}"
            print(f"Error: {error = }")
        print("Cleaning LLM output...")
        cleaned_result = remove_llm_formatting(result)
        print(cleaned_result)
        # exit()
        try:
            # Validate if the cleaned result is valid JSON
            json.loads(cleaned_result)
            print("LLM output is valid JSON.")
        except json.JSONDecodeError as json_err:
            error = f"LLM output is not valid JSON after cleaning: {json_err}. See raw output."
            # Keep the potentially broken cleaned_result in the state for inspection
            print(f"Error: {error}")
            # Optionally, you might want to return state here or attempt recovery
            # return state
        except Exception as e:
            error = f"Unexpected error during JSON validation: {str(e)}"
            print(f"Error: {error}")

        # --- 7. Write Output ---
        output_filepath = Path(self.customer_alert_output_directory) / "extracted_kpis_data.md"
        # Only write if there wasn't a JSON validation error (or decide based on requirements)
        try:
            print(f"Appending cleaned result to: {output_filepath}")
            os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
            with open(output_filepath, "a", encoding="utf-8") as f:
                f.write(cleaned_result + "\n\n")  # Add extra newline for separation
            print("Successfully appended result.")
        except Exception as e:
            error = f"Error writing output file '{output_filepath}': {str(e)}"
            print(f"Error: {error}")
        else:
            print("Skipping writing output due to previous errors (likely invalid JSON).")

        print("--- Exiting extract_math_data_agent ---")
        return output_filepath,llm_response, status

    def run(self):
        """
        Executes the entire data extraction and processing pipeline.

        Returns:
            The final state dictionary from the LangGraph execution.
        """
        print("\n>>> Starting Financial Data Extraction Pipeline <<<")
        token_use = None
        # 1. Preprocess Excel
        try:
            self.preprocess_excel_to_markdown()
        except Exception as e:
            print(f"FATAL: Failed during Excel preprocessing: {e}")
            # Return a state indicating the failure point
            return {"error": f"Excel preprocessing failed: {e}"}

        combined_data_path = Path(self.customer_alert_output_directory) / "combined_data.md"

        # # Check if the combined file exists and has content before proceeding
        if not combined_data_path.exists() or combined_data_path.stat().st_size == 0:
             print(f"Warning: Combined input file '{combined_data_path}' is missing or empty. LLM step might yield no results.")
             # Decide if this should be a fatal error or just a warning
             # return {"error": f"Combined input file '{self.combined_data_path}' is missing or empty."}
        output_file_path, token_usage,status = self.extract_math_data_agent(combined_data_path)
        try:
            token_use = token_usage
            with open(output_file_path,'r') as file:
                extracted_data = json.loads(file.read())
            year = extracted_data["Date"][0].split(".")[-1]
            financial_year = f"FY{year}-{int(year[2:]) + 1}"
            alert_data = create_alerts_data(extracted_data)

            alert_type = classify_financial_attributes(alert_data, financial_year)
            if not alert_type.empty:
                final_alert_path = Path(self.customer_alert_output_directory) / "alert_messages.md"
                with open(final_alert_path,'w') as f:
                    f.write(alert_type.to_string())
        except Exception as err:
            print(f"Error Occured - {err}")

        return token_use, status
