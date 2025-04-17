# -*- coding: utf-8 -*-
import ast
import asyncio
import json
import os
import re
import sys
import threading
import logging

import aiosqlite
import pandas as pd
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any, List, Optional

# Langchain/Langgraph Imports
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage # Added AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from typing_extensions import TypedDict
from pathlib import Path
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph
from textwrap import dedent
from langchain_experimental.tools import PythonREPLTool

# MCP Imports
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters, stdio_client

from src.prompts.graph_prompts import GraphPromptGenerator
from src.agents.CMA_Customer_Alerts import FinancialDataExtractor

try:
    from .prompts.prompt_utils import PromptGenerator
except ImportError:
    from src.prompts.prompt_utils import PromptGenerator # Fallback for different execution contexts


# --- Environment Variable Handling ---
# Load only once if needed, but ensure they are set in the server's environment
load_dotenv(find_dotenv(), verbose=True, override=True)

AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION]):
    # This might be too strict if only using Gemini
    logging.warning("Azure OpenAI environment variables might be missing.")
if not GOOGLE_API_KEY:
     logging.warning("Google API key environment variable might be missing.")


# --- Data Structures ---
class CMAAnalysisState(TypedDict, total=False):
    excel_file_path: str
    insights: Dict[str, str]
    sheets_data: Dict[str, str]
    output_path: str # Should be Path object internally, string for state
    sheets_to_analyze: List[str]
    intermediate_steps: List[Any]
    llm_agent_result: str
    final_report: str
    error_logs: List[str] # Add error logging to state
    timestamp: str # Add timestamp to state
    graph_inputs: Dict[str,str] # Add timestamp to state


# --- CMAAnalyzer Class ---
class CMAAnalyzer:
    """
    A class for analyzing CMA data from Excel files using LLMs and tools.
    Designed to be instantiated per analysis run.
    """

    def __init__(self, output_path: str, account: str, config: Dict[str, Any], mcp_server_path: str, logger: logging.Logger,llm: Optional[Any] = None):
        """
        Initializes the CMAAnalyzer.

        Args:
            output_path (str): The base directory to save the output files.
            account (str): The account identifier.
            config (Dict[str, Any]): Configuration dictionary.
            mcp_server_path (str): Absolute path to the mcp_tools.py script.
            logger (logging.Logger): Logger instance.
            llm: Pre-configured language model (optional).
        """
        self.config = config
        self.mcp_server_path = mcp_server_path # Ensure this is an absolute path when passed in
        self.llm_agent_executor = None
        self.logger = logger
        self.account = account
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") # Generate timestamp per instance

        # --- LLM Initialization ---
        self.model_name = str(self.config.get("model_name", "")).lower()
        if llm:
             self.llm = llm
        elif "gpt" in self.model_name:
            if not all([AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION]):
                 raise ValueError("Missing Azure OpenAI environment variables for GPT model.")
            self.llm = AzureChatOpenAI(
                model=self.config["model_name"],
                api_key=AZURE_API_KEY,
                azure_endpoint=AZURE_ENDPOINT,
                api_version=AZURE_API_VERSION,
                temperature=0,
            )
        elif "gemini" in self.model_name:
            if not GOOGLE_API_KEY:
                 raise ValueError("Missing GOOGLE_API_KEY environment variable for Gemini model.")
            self.llm = ChatGoogleGenerativeAI(
                model=self.config["model_name"],
                google_api_key=GOOGLE_API_KEY,
                temperature=0
            )
        else:
            raise ValueError(f"Unsupported or missing model_name in config: {self.config.get('model_name')}")

        self.string_output_parser = StrOutputParser()
        # Ensure output_path is absolute and specific to this run/account
        self.output_path = Path(output_path).resolve() # Use resolve() for absolute path
        self.tools = []

        # Ensure output directory exists (safer to do it just before writing)
        self.output_path.mkdir(parents=True, exist_ok=True) # Moved lower
        self.logger.info(f"Analyzer initialized. Output base path set to: {self.output_path}")
        self.logger.info(f"Timestamp for this run: {self.timestamp}")

        # --- MCP Client Setup ---
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.mcp_server_path],
        )
        self.mcp_client = None
        self.read = None
        self.write = None
        self.mcp_session = None

        self.run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.db_conn = None
        db_dir = Path(__file__).parent.parent / "database"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / "cred360.db"

        self.logger.info(f"LLM Call logging configured. Database path: {self.db_path}")
        self.logger.info(f"Analyzer initialized in Thread ID: {threading.get_ident()}")  # Log init thread


    async def __aenter__(self):
        """Asynchronous context manager entry: Starts MCP client and session."""
        self.logger.info("Entering async context: Initializing MCP client and session...")
        try:
            await self._setup_database()

            self.mcp_client = stdio_client(self.server_params)
            self.read, self.write = await self.mcp_client.__aenter__()
            self.mcp_session = ClientSession(self.read, self.write)
            await self.mcp_session.__aenter__()
            await self.mcp_session.initialize()
            self.logger.info("MCP client and session initialized successfully.")
            return self
        except Exception as e:
            self.logger.error(f"Error entering async context: {e}", exc_info=True)
            # Attempt cleanup even if entry failed partially
            await self.__aexit__(type(e), e, e.__traceback__)
            raise # Re-raise the exception

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asynchronous context manager exit: Cleans up MCP session and client."""
        current_thread_id = threading.get_ident()
        if self.db_conn:
            self.logger.info(f"Closing LLM call database connection (Thread ID: {current_thread_id})...")
            try:
                await self.db_conn.close()
                self.logger.info("LLM call database connection closed.")
            except Exception as e:
                self.logger.error(f"aiosqlite Error during closing connection: {e}", exc_info=True)
            finally:
                self.db_conn = None
        self.logger.info("Exiting async context: Cleaning up MCP session and client...")
        # Exit session first
        try:
            if self.mcp_session:
                self.logger.debug("Exiting MCP session...")
                await self.mcp_session.__aexit__(exc_type, exc_val, exc_tb)
                self.logger.debug("MCP session exited.")
        except Exception as e:
            # Log the specific error mentioned in the issue
            if "generator didn't stop after athrow()" in str(e):
                 self.logger.error(f"Error exiting mcp_session (known generator issue): {e}", exc_info=True)
            else:
                 self.logger.error(f"Error exiting mcp_session: {e}", exc_info=True)
        finally:
            self.mcp_session = None # Ensure it's cleared

        # Exit client
        try:
            if self.mcp_client:
                self.logger.debug("Exiting MCP client...")
                await self.mcp_client.__aexit__(exc_type, exc_val, exc_tb)
                self.logger.debug("MCP client exited.")
        except Exception as e:
            # Log the specific error mentioned in the issue
            if "generator didn't stop after athrow()" in str(e):
                 self.logger.error(f"Error exiting mcp_client (known generator issue): {e}", exc_info=True)
            else:
                 self.logger.error(f"Error exiting mcp_client: {e}", exc_info=True)
        finally:
            self.mcp_client = None # Ensure it's cleared
            self.read = None
            self.write = None
        self.logger.info("Async context exited.")


    async def initialize_agent(self):
        """Initializes the agent with tools. Requires active MCP session."""
        if not self.mcp_session:
             raise RuntimeError("MCP session not initialized. Call within 'async with' block.")
        try:
            self.logger.info("Initializing agent...")
            await self.get_tools()
            if not self.tools:
                self.logger.warning("No tools loaded from MCP server. Agent might be limited.")
            # Ensure LLM is initialized
            if not self.llm:
                 raise RuntimeError("LLM not initialized.")
            self.llm_agent_executor = create_react_agent(self.llm, self.tools or [], debug=True) # Handle empty tools
            self.logger.info("Agent initialized successfully.")
        except Exception as e:
            self.logger.error(f"Error initializing agent: {e}", exc_info=True)
            raise

    async def get_tools(self):
        """Retrieves tools from the MCP server. Requires active MCP session."""
        if not self.mcp_session:
             raise RuntimeError("MCP session not initialized. Call within 'async with' block.")
        try:
            self.logger.info("Loading tools from MCP server...")
            self.tools = await load_mcp_tools(self.mcp_session)
            self.logger.info(f"Loaded tools: {[tool.name for tool in self.tools]}")
        except Exception as e:
            self.logger.error(f"Error getting tools from MCP server: {e}", exc_info=True)
            self.tools = [] # Ensure tools is empty on failure
            # Decide if this is fatal
            # raise # Option: re-raise if tools are essential

    def _get_sub_dir(self, dir_key: str) -> Path:
        """Helper to get and create a subdirectory path."""
        sub_dir = self.output_path / self.config.get(dir_key, dir_key) # Use key as dir name if not in config
        sub_dir.mkdir(parents=True, exist_ok=True)
        return sub_dir

    def _extract_token_usage(self, response: Any) -> Dict[str, int]:
        """Helper to extract token usage from various response types."""
        tokens = {"input": 0, "output": 0, "total": 0}
        try:
            metadata_dict = None  # Variable to hold the actual metadata dictionary

            # --- Case 1: Response has response_metadata (Common for OpenAI/Azure) ---
            if "gpt" in self.model_name.lower():
                if hasattr(response, 'response_metadata') and response.response_metadata and isinstance(
                        response.response_metadata, dict):
                    metadata_dict = response.response_metadata
                    self.logger.debug("Checking response.response_metadata")

            # --- Case 2: Response has usage_metadata (Common for Gemini) ---
            elif "gemini" in self.model_name.lower() and hasattr(response, 'usage_metadata') and response.usage_metadata and isinstance(response.usage_metadata,
                                                                                                dict):
                metadata_dict = response.usage_metadata
                self.logger.debug("Checking response.usage_metadata")

            # --- Case 3: Response *is* the metadata dict (Less common direct invoke) ---
            elif isinstance(response, dict) and (
                    'token_usage' in response or 'usage' in response or 'prompt_tokens' in response):
                metadata_dict = response  # The response itself is the dict
                self.logger.debug("Checking response dictionary directly")

            # --- Case 4: Agent results (dict with 'messages') - check last AIMessage ---
            elif isinstance(response, dict) and "messages" in response:
                self.logger.debug("Checking messages list in agent response dict")
                final_ai_message = next((msg for msg in reversed(response["messages"]) if isinstance(msg, AIMessage)),
                                        None)
                if final_ai_message:
                    # RECURSE *only* on the extracted AIMessage from the list
                    self.logger.debug("Recursing on final AIMessage from agent response")
                    return self._extract_token_usage(final_ai_message)
                else:
                    self.logger.debug("No AIMessage found in agent response messages list")

            # --- Case 5: Response is an AIMessage itself ---
            # This needs to check *inside* the AIMessage's metadata attributes
            elif isinstance(response, AIMessage):
                self.logger.debug("Checking AIMessage object directly for its metadata attributes")
                if hasattr(response, 'usage_metadata') and response.usage_metadata and isinstance(
                        response.usage_metadata, dict):
                    metadata_dict = response.usage_metadata
                    self.logger.debug("Found usage_metadata within AIMessage")
                elif hasattr(response, 'response_metadata') and response.response_metadata and isinstance(
                        response.response_metadata, dict):
                    metadata_dict = response.response_metadata
                    self.logger.debug("Found response_metadata within AIMessage")
                # Add check for additional_kwargs if necessary
                # elif hasattr(response, 'additional_kwargs') and response.additional_kwargs and isinstance(response.additional_kwargs, dict):
                #     metadata_dict = response.additional_kwargs # Less standard, but possible

            # --- Now, process the found metadata_dict ---
            if metadata_dict:
                self.logger.debug(f"Processing metadata dictionary: {metadata_dict}")
                # Look for 'token_usage' or 'usage' keys first
                usage = metadata_dict.get('token_usage', metadata_dict.get('usage', None))
                if usage and isinstance(usage, dict):
                    self.logger.debug(f"Found 'usage'/'token_usage' sub-dictionary: {usage}")
                    tokens["input"] = usage.get('prompt_tokens', usage.get('input_tokens', 0))
                    tokens["output"] = usage.get('completion_tokens', usage.get('output_tokens', 0))
                    tokens["total"] = usage.get('total_tokens', 0)
                else:
                    # If no 'usage' dict, look for keys directly in metadata_dict
                    self.logger.debug("Looking for direct token keys in metadata dictionary")
                    tokens["input"] = metadata_dict.get('prompt_tokens', metadata_dict.get('input_tokens', 0))
                    tokens["output"] = metadata_dict.get('completion_tokens', metadata_dict.get('output_tokens', 0))
                    tokens["total"] = metadata_dict.get('total_tokens', 0)

                # Calculate total if missing or zero but input/output exist
                if tokens["total"] == 0 and (tokens["input"] > 0 or tokens["output"] > 0):
                    tokens["total"] = tokens["input"] + tokens["output"]
                    self.logger.debug(f"Calculated total tokens: {tokens['total']}")

                if tokens["total"] > 0:
                    self.logger.debug(f"Successfully extracted tokens: {tokens}")
                    return tokens
                else:
                    self.logger.debug("Found metadata dictionary, but no token usage keys found inside.")

            # --- If no metadata_dict was found or processed ---
            if not metadata_dict:
                self.logger.warning(f"Could not find usable metadata dictionary in response type: {type(response)}")

        except Exception as e:
            self.logger.error(f"Error extracting token usage: {e}", exc_info=True)

        # Return zeros if extraction failed at any point
        self.logger.warning(f"Returning zero tokens after checking response type: {type(response)}")
        return tokens

    async def _setup_database(self):
        """Initializes the SQLite database connection and creates the table if needed."""
        # This method MUST be called from an async context, like __aenter__
        try:
            # Connect asynchronously
            self.db_conn = await aiosqlite.connect(self.db_path)
            # Enable Write-Ahead Logging for better concurrency (optional but recommended)
            await self.db_conn.execute("PRAGMA journal_mode=WAL;")
            await self.db_conn.commit()

            async with self.db_conn.cursor() as cursor:
                # Add status column
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_llm_calls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_timestamp TEXT NOT NULL,
                        account_name TEXT NOT NULL,
                        call_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        model_name TEXT NOT NULL,
                        call_purpose TEXT NOT NULL,
                        langgraph_node TEXT,
                        input_tokens INTEGER NOT NULL,
                        output_tokens INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        status TEXT NOT NULL CHECK(status IN ('completed', 'failed'))
                    )
                """)
            await self.db_conn.commit()
            self.logger.info(f"Async DB connection established and table checked in Thread ID: {threading.get_ident()}")
        except Exception as e: # Catch generic Exception as aiosqlite might raise different errors
            self.logger.error(f"aiosqlite Error during setup: {e}", exc_info=True)
            if self.db_conn:
                await self.db_conn.close() # Use await for close
            self.db_conn = None
            raise

    async def _log_llm_call(self, call_purpose: str, langgraph_node: Optional[str],
                            input_tokens: int, output_tokens: int, total_tokens: int, status: str):
        """Logs the details of an LLM call to the SQLite database using aiosqlite."""
        # This method MUST be awaited

        current_thread_id = threading.get_ident()  # Get current thread ID for logging
        if not self.db_conn:
            self.logger.warning(
                f"Database connection not available (Thread ID: {current_thread_id}). Skipping LLM call log.")
            return

        # Validate status
        if status not in ('completed', 'failed'):
            self.logger.error(
                f"Invalid status '{status}' provided for LLM log (Thread ID: {current_thread_id}). Defaulting to 'failed'.")
            status = 'failed'

        try:
            call_timestamp = datetime.now()
            # Use async context manager for the cursor
            async with self.db_conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO audit_llm_calls (
                        run_timestamp, account_name, call_timestamp, model_name,
                        call_purpose, langgraph_node,
                        input_tokens, output_tokens, total_tokens, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.run_timestamp, self.account, call_timestamp, self.model_name,
                    call_purpose, langgraph_node,
                    input_tokens, output_tokens, total_tokens, status
                ))
            await self.db_conn.commit()  # Commit changes
            self.logger.debug(
                f"Logged LLM call (Thread ID: {current_thread_id}): Purpose='{call_purpose}', Node='{langgraph_node}', Tokens={total_tokens}, Status='{status}'")
        except Exception as e:  # Catch generic Exception
            self.logger.error(f"aiosqlite Error during logging LLM call (Thread ID: {current_thread_id}): {e}",
                              exc_info=True)

    # --- Graph Nodes ---

    def extract_data_from_excel_to_markdown(self, state: CMAAnalysisState) -> Dict[str, Any]:
        """Node: Extracts data from Excel sheets to Markdown format."""
        excel_file_path = Path(state["excel_file_path"])
        self.logger.info(f"Node: Extracting text from Excel file: {excel_file_path}")

        if not excel_file_path.is_file():
            self.logger.error(f"Excel file not found: {excel_file_path}")
            raise FileNotFoundError(f"Excel file not found: {excel_file_path}")

        extracted_sheets_data = {}
        try:
            excel_file = pd.ExcelFile(excel_file_path)
            sheet_names_to_process = excel_file.sheet_names # Process all sheets by default

            # Optional: Filter sheets based on config (if needed)
            configured_sheets = self.config.get("sheets_to_analyze")
            if configured_sheets:
                sheet_names_to_process = [s for s in sheet_names_to_process if s.lower() in configured_sheets]
                self.logger.info(f"Filtering sheets based on config: {sheet_names_to_process}")

            for sheet_name in sheet_names_to_process:
                self.logger.debug(f"Processing sheet: {sheet_name}")
                try:
                    # Read, clean, and convert to markdown
                    excel_data = pd.read_excel(excel_file, engine="openpyxl", sheet_name=sheet_name)
                    cleaned_excel_data = excel_data.dropna(how="all").fillna("").reset_index(drop=True)
                    markdown_text = cleaned_excel_data.to_markdown(index=False) # Often better without index
                    text = f"##### Sheet: {sheet_name}\n\n{markdown_text}" # Clearer header

                    # Simplified aggregation logic (adjust if needed)
                    # Aggregate "Sheet 1", "Sheet 2" into "Sheet" etc.
                    base_name = re.sub(r'\d+$', '', sheet_name).strip() # Remove trailing digits
                    if base_name in extracted_sheets_data:
                        extracted_sheets_data[base_name] += f"\n\n---\n\n{text}" # Add separator
                    else:
                        extracted_sheets_data[base_name] = text
                    self.logger.info(f"Extracted data from sheet: {sheet_name} (aggregated as {base_name})")

                except Exception as e:
                    self.logger.error(f"Error processing sheet '{sheet_name}': {e}", exc_info=True)
                    # Continue to next sheet, maybe add error to state?
                    state.setdefault("error_logs", []).append(f"Excel Processing Error (Sheet: {sheet_name}): {e}")


            # Save extracted markdown files (optional, mainly for debugging)
            extracted_md_path = self._get_sub_dir("extracted_markdown_dir")
            graph_inputs = {}
            for filename_base, content in extracted_sheets_data.items():
                # Sanitize filename
                # safe_filename_base = re.sub(r'[^\w\-]+', '_', filename_base)
                safe_filename_base = re.sub(r'[-, ]+', '_', filename_base)
                md_file_name = f"{safe_filename_base}_{self.timestamp}.md".lower()
                md_file_path = extracted_md_path / md_file_name
                try:
                    with open(md_file_path, "w", encoding=self.config.get("file_encoding", "utf-8")) as md_file:
                        md_file.write(content)
                        graph_inputs[filename_base] = md_file_path
                    self.logger.info(f"Saved extracted Markdown: {md_file_path}")
                except Exception as e:
                    self.logger.error(f"Error saving extracted Markdown '{md_file_path}': {e}")
                    state.setdefault("error_logs", []).append(f"File Write Error (Extracted MD: {md_file_name}): {e}")

            sheets_to_analyze = list(extracted_sheets_data.keys())
            self.logger.info(f"Sheets extracted and aggregated for analysis: {sheets_to_analyze}")
            return {"sheets_data": extracted_sheets_data, "sheets_to_analyze": sheets_to_analyze,
                    "graph_inputs":graph_inputs}

        except FileNotFoundError:
            self.logger.error(f"Excel file disappeared during processing: {excel_file_path}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error during Excel processing: {e}", exc_info=True)
            raise

    async def extract_data_in_required_format(self, state: CMAAnalysisState, sheet_name: str) -> Optional[str]:
        """
        Sub-step: Uses LLM to extract data in a specific format for a given sheet.
        Returns the formatted string or None on failure.
        """
        self.logger.info(f"Sub-step: Extracting formatted data for sheet: {sheet_name}")
        sheet_data = state.get("sheets_data", {}).get(sheet_name)
        if not sheet_data:
            self.logger.warning(f"No sheet data found for '{sheet_name}' in state.")
            return None

        try:
            tokens = {"input": 0, "output": 0, "total": 0}
            status = "failed"
            current_dir = Path(__file__).parent
            project_root = current_dir.parent
            data_format_file_path = project_root / "data" / "input_data_sources" / self.config['data_extraction_format_filename']

            if not data_format_file_path.is_file():
                self.logger.error(f"Data format file not found at expected path: {data_format_file_path}")
                state.setdefault("error_logs", []).append(f"Config Error: Data format file not found for {sheet_name}")
                return None

            with open(data_format_file_path, "r", encoding=self.config.get("file_encoding", "utf-8")) as f:
                data_format_config = json.load(f)

            data_format_template = data_format_config.get("data_format", {}).get(sheet_name)
            if not data_format_template:
                self.logger.warning(f"No specific data format found for sheet '{sheet_name}' in {data_format_file_path}. Skipping formatting.")
                return None # Not an error, just no format defined

        except (FileNotFoundError, json.JSONDecodeError, KeyError, Exception) as e:
            self.logger.error(f"Error loading or parsing data format file : {e}", exc_info=True)
            state.setdefault("error_logs", []).append(f"Config Error: Failed to load data format for {sheet_name}: {e}")
            return None # Cannot proceed reliably

        # --- Call LLM for Formatting ---
        try:
            self.logger.info(f"Invoking LLM to format data for: {sheet_name}")
            system_prompt = dedent(
                f"""
                                You are an intelligent data extraction assistant. Your task is to analyze and understand the provided data, extract the data in the below format. 
                                {{{data_format_template}}}

                                Output must be in the above format only. Produce a clean output without any ```json or ```python or ```.
                                If you are unable to find any value, put 0 respectively. Values should be Numeric. Modify the date in same format (DD-MM-YYYY).
                                """,
            )

            prompt = ChatPromptTemplate.from_messages(
                [("system", system_prompt), ("human", f"Data: {dedent(sheet_data)}")]
            )

            data_extraction_chain = prompt | self.llm

            llm_agent = data_extraction_chain.invoke({"data": sheet_data})

            tokens = self._extract_token_usage(llm_agent)

            if hasattr(llm_agent, 'content'):
                status = "completed"
                llm_agent_result = llm_agent.content
                extracted_metrics_path = self._get_sub_dir("extracted_metrics_dir")
                # safe_sheet_name = re.sub(r'[^\w\-]+', '_', sheet_name)
                safe_sheet_name = re.sub(r'[-, ]+', '_', sheet_name)
                output_file_path = extracted_metrics_path / f"{safe_sheet_name}_{self.timestamp}.json".lower() # Save as JSON
                try:
                    with open(output_file_path, "w", encoding=self.config.get("file_encoding", "utf-8")) as output_file:
                        output_file.write(llm_agent_result)
                    self.logger.info(f"Saved formatted data extract: {output_file_path}")
                except Exception as e:
                    self.logger.error(f"Error saving formatted data extract '{output_file_path}': {e}")
                    state.setdefault("error_logs", []).append(f"File Write Error (Formatted Data: {sheet_name}): {e}")
            else:
                llm_agent_result = str(llm_agent)
                self.logger.warning(
                    f"LLM result for formatting '{sheet_name}' did not have 'content' attribute. Type: {type(llm_agent_result)}")

            return llm_agent_result

        except Exception as err:
            self.logger.error(f"LLM formatting failed for sheet '{sheet_name}': {err}", exc_info=True)
            state.setdefault("error_logs", []).append(f"LLM Formatting Error ({sheet_name}): {err}")
            return None
        finally:
            if "tokens" in locals():
                await self._log_llm_call(
                    call_purpose=f'data_formatting_for_tool_calculation of sheet {sheet_name}',
                    langgraph_node='extract_data_in_required_format',  # Or the calling node name if different
                    input_tokens=tokens["input"],
                    output_tokens=tokens["output"],
                    total_tokens=tokens["total"],
                    status=status
                )

    def _rename_file_for_archiving(self, file_path: Path):
        """Archives an existing file by appending its last modified time."""
        if not file_path.is_file():
            return # Nothing to archive

        try:
            modified_time_ts = file_path.stat().st_mtime
            formatted_time = datetime.fromtimestamp(modified_time_ts).strftime('%Y%m%d_%H%M%S')
            archive_name = f"{file_path.stem}_{formatted_time}{file_path.suffix}"
            archive_path = file_path.with_name(archive_name)

            # Handle potential naming conflict if archive already exists
            counter = 1
            while archive_path.exists():
                archive_name = f"{file_path.stem}_{formatted_time}_{counter}{file_path.suffix}"
                archive_path = file_path.with_name(archive_name)
                counter += 1

            file_path.rename(archive_path)
            self.logger.info(f"Archived previous file '{file_path.name}' as: {archive_path.name}")
        except OSError as err:
            self.logger.error(f"Failed to archive file {file_path}: {err}")
        except Exception as err:
            self.logger.error(f"Unexpected error during file archiving for {file_path}: {err}", exc_info=True)

    async def analyze_markdown_and_generate_report(self, state: CMAAnalysisState) -> Dict[str, Any]:
        """Node: Analyzes markdown data for each sheet using the LLM agent."""
        self.logger.info("Node: Analyzing Markdown and Generating Reports...")
        if not self.llm_agent_executor:
             self.logger.error("Agent executor not initialized. Cannot analyze.")
             raise RuntimeError("Agent executor not initialized before analysis node.")

        # Ensure prompt generator is initialized correctly
        try:
            prompt_generator = PromptGenerator(self.logger, self.account)
        except Exception as e:
            self.logger.error(f"Failed to initialize PromptGenerator: {e}", exc_info=True)
            raise

        extracted_sheets_data = state.get("sheets_data", {})
        sheets_to_analyze = state.get("sheets_to_analyze", [])
        self.logger.info(f"Sheets queued for analysis: {sheets_to_analyze}")
        analysis_insights = state.get("insights", {}) # Continue from previous state if any

        reports_path = self._get_sub_dir("reports_dir")
        audit_data_path = self._get_sub_dir("audit_data") # For tool outputs
        knowledge_df = pd.DataFrame()
        for sheet_name in sheets_to_analyze:
            self.logger.info(f"--- Analyzing Sheet: {sheet_name} ---")
            try:
                sheet_data = extracted_sheets_data.get(sheet_name)
                if not sheet_data:
                    self.logger.warning(f"No data found in state for sheet: {sheet_name}. Skipping.")
                    analysis_insights[sheet_name] = "Error: No data found in state."
                    state.setdefault("error_logs", []).append(f"Analysis Skip (No Data): {sheet_name}")
                    continue

                # --- Optional: Data Formatting Sub-step ---
                formatted_data = await self.extract_data_in_required_format(state, sheet_name)
                # Update state if formatting produced output (used by prompt generator)
                if formatted_data:
                    extracted_format_data = (formatted_data.replace("```json","")
                                             .replace("```python","").replace("```",""))
                    converted_dict = ast.literal_eval(extracted_format_data)
                    if not isinstance(converted_dict, dict):
                        raise TypeError("String did not evaluate to a dictionary")
                    print(f"  Successfully converted to dict: {converted_dict}")

                    temp_df = pd.DataFrame(converted_dict)
                    if knowledge_df.empty:
                        knowledge_df = pd.concat([knowledge_df, temp_df], ignore_index=True)
                    else:
                        knowledge_df = pd.merge(knowledge_df, temp_df, on='Date', how='inner')
                    print(knowledge_df)
                    print("  Appended to global DataFrame.")

                    state["llm_agent_result"] = formatted_data # Store potentially formatted data
                else:
                    state["llm_agent_result"] = ""

                # --- Generate Prompt ---
                prompt_messages = prompt_generator.get_sheet_specific_prompt(sheet_name, state)

                if not prompt_messages:
                    self.logger.warning(f"No prompt generated for sheet: {sheet_name}. Skipping analysis.")
                    analysis_insights[sheet_name] = "Skipped: No analysis prompt available."
                    state.setdefault("error_logs", []).append(f"Analysis Skip (No Prompt): {sheet_name}")
                    continue

                # --- Invoke Agent ---
                self.logger.info(f"Invoking agent for sheet: {sheet_name}")
                agent_input = {"messages": prompt_messages}

                llm_agent_result = await self.llm_agent_executor.ainvoke(agent_input)
                self.logger.info(f"Agent invocation complete for sheet: {sheet_name}")
                tokens = self._extract_token_usage(llm_agent_result)
                status = 'completed'

                # --- Process Agent Output ---
                if not llm_agent_result or "messages" not in llm_agent_result:
                    status = 'failed'
                    await self._log_llm_call(
                        call_purpose=f'Analyze Markdown and Generate Report for {sheet_name}',
                        langgraph_node='analyze_markdown_and_generate_report',  # Or the calling node name if different
                        input_tokens=tokens["input"],
                        output_tokens=tokens["output"],
                        total_tokens=tokens["total"],
                        status=status
                    )
                    self.logger.error(f"Agent returned unexpected or empty result for {sheet_name}: {llm_agent_result}")
                    analysis_insights[sheet_name] = f"Error: Agent returned invalid result for {sheet_name}."
                    state.setdefault("error_logs", []).append(f"Agent Error (Invalid Result): {sheet_name}")
                    continue

                llm_response_messages = llm_agent_result["messages"]
                await self._log_llm_call(
                    call_purpose=f'Analyze Markdown and Generate Report for {sheet_name}',
                    langgraph_node='analyze_markdown_and_generate_report',  # Or the calling node name if different
                    input_tokens=tokens["input"],
                    output_tokens=tokens["output"],
                    total_tokens=tokens["total"],
                    status=status
                )
                # --- Save Tool Call Audit Data ---
                tool_message = next((msg for msg in llm_response_messages if isinstance(msg, ToolMessage) and not str(msg.content).__contains__("Error")), None)
                if tool_message:
                    # safe_sheet_name = re.sub(r'[^\w\-]+', '_', sheet_name)
                    safe_sheet_name = re.sub(r'[-, ]+', '_', sheet_name)
                    audit_path = audit_data_path / f"{safe_sheet_name}_{self.timestamp}.md".lower()
                    try:
                        # audit_data = pd.DataFrame(ast.literal_eval(tool_message.content))
                        audit_data = pd.DataFrame(json.loads(tool_message.content))
                        # knowledge_df = pd.concat([knowledge_df, audit_data], ignore_index=True)
                        knowledge_df = pd.merge(knowledge_df, audit_data, on='Date', how='inner')

                        with open(audit_path, "w", encoding=self.config.get("file_encoding", "utf-8")) as f:
                            f.write(audit_data.to_string())
                        f.close()
                    except Exception as e:
                        self.logger.error(f"Error writing tool data: {e}")
                        raise

                # --- Extract Final Report Content ---
                # Find the last AIMessage which usually contains the final answer
                final_ai_message = next((msg for msg in reversed(llm_response_messages) if isinstance(msg, AIMessage)), None)

                if final_ai_message and hasattr(final_ai_message, 'content'):
                    final_content = final_ai_message.content
                    self.logger.info(f"Extracted final AI response for {sheet_name}.")

                    # --- Save Individual Report ---
                    # safe_sheet_name = re.sub(r'[^\w\-]+', '_', sheet_name)
                    safe_sheet_name = re.sub(r'[-, ]+', '_', sheet_name)
                    # Use timestamp in the main report name for uniqueness per run
                    output_file_name = f"{safe_sheet_name}.md".lower()
                    output_file_path = reports_path / output_file_name

                    # Archive previous versions if any (less likely with timestamp in name)
                    self._rename_file_for_archiving(output_file_path) # Probably not needed now

                    try:
                        with open(output_file_path, "w", encoding=self.config.get("file_encoding", "utf-8")) as output_file:
                            output_file.write(final_content)
                        self.logger.info(f"Analysis report for {sheet_name} saved to {output_file_path}")
                        analysis_insights[sheet_name] = final_content # Store successful analysis
                    except Exception as e:
                        self.logger.error(f"Error writing analysis report to {output_file_path}: {e}")
                        analysis_insights[sheet_name] = f"Error: Failed to save report for {sheet_name}."
                        state.setdefault("error_logs", []).append(f"File Write Error (Report: {sheet_name}): {e}")

                else:
                    self.logger.warning(f"Could not find final AI message content for sheet: {sheet_name}")
                    analysis_insights[sheet_name] = f"Error: No final AI response found for {sheet_name}."
                    state.setdefault("error_logs", []).append(f"Agent Error (No Final Msg): {sheet_name}")

            except Exception as e:
                self.logger.error(f"Critical error during analysis of sheet '{sheet_name}': {e}", exc_info=True)
                analysis_insights[sheet_name] = f"Error: Analysis failed critically for {sheet_name}."
                state.setdefault("error_logs", []).append(f"Analysis Error (Sheet: {sheet_name}): {e}")
                continue # Continue to the next sheet
        self.logger.info("Finished analyzing all sheets.")
        return {"insights": analysis_insights}

    async def graph_data_agent(self,state: CMAAnalysisState):
        graph_input = state.get("graph_inputs", {})
        if graph_input:
            graph_prompts = GraphPromptGenerator(self.logger,self.account)
            for sheet_name, file_path in graph_input.items():
                tokens = {"input": 0, "output": 0, "total": 0}
                status = "failed"
                try:
                    if not os.path.exists(file_path):
                        print(f"Warning: {file_path} not found.")
                    with open(file_path, "r") as f:
                        data = f.read()
                except FileNotFoundError:
                    error = f"File not found: {file_path}. Please ensure the .md file is available."
                except Exception as e:
                    error = f"Error reading file {file_path}: {e}"
                if not data:
                    self.logger.error("Failed to extract text from the file (file might be empty).")

                try:
                    safe_sheet_name = re.sub(r'[-, ]+', '_', sheet_name).lower()
                    graph_dir = f'{self.output_path}/graphs/{safe_sheet_name}/'
                    os.makedirs(graph_dir, exist_ok=True)
                    prompt_messages = graph_prompts.get_sheet_specific_prompt(sheet_name, state,self.account)
                    if prompt_messages is None:
                        self.logger.error(f"No Graph prompts available for sheet {sheet_name}")
                        continue
                    prompt = ChatPromptTemplate.from_messages(
                        [
                            ("system", prompt_messages),
                            ("human", f"Data:\n{data}")
                        ]
                    )
                    graph_generation_chain = prompt | self.llm

                    try:
                        generated_code_agent = await graph_generation_chain.ainvoke({"data": data,"output_path":str(self.output_path).replace("\\","/"),
                                                                                     "sheet_directory":safe_sheet_name})
                        tokens = self._extract_token_usage(generated_code_agent)
                        if hasattr(generated_code_agent,'content'):
                            status = 'completed'
                            generated_code = generated_code_agent.content
                            # state["result"] = generated_code  # Store the generated code
                            print("--- Generated Python Code ---")
                            print(generated_code)
                            print("-----------------------------")
                    except Exception as e:
                        print(f"Error invoking LLM chain: {e}")
                        return state

                    if "generated_code" in locals() and generated_code:
                        print("--- Executing Code with PythonREPLTool ---")
                        repl = PythonREPLTool()
                        try:
                            # Ensure the output directory exists *before* running the REPL
                            # The generated code should also do this, but it's safer to ensure here.
                            # safe_sheet_name = re.sub(r'[^\w\-]+', '_', sheet_name)
                            # safe_sheet_name = re.sub(r'[-, ]+', '_', sheet_name)
                            # os.makedirs(f'../output/{self.account}/graphs/{safe_sheet_name.lower()}/', exist_ok=True)

                            execution_output = repl.run(generated_code)
                            print("--- REPL Execution Output ---")
                            print(execution_output)
                            print("-----------------------------")
                            if "error" in execution_output.lower() or "traceback" in execution_output.lower():
                                print(f"Warning: Execution via REPL might have failed. Output:\n{execution_output}")

                        except Exception as e:
                            error_message = f"Error executing code with PythonREPLTool: {e}\nCode:\n{generated_code}"
                            print(error_message)
                            # No need to return state here, let the graph proceed, but the error is logged in the state
                    else:
                        error = "LLM did not generate any code."
                        status = "failed"
                        print(error)
                except Exception as err:
                    status = "failed"
                finally:
                    if "tokens" in locals():
                        await self._log_llm_call(
                            call_purpose='Graph Generator',
                            langgraph_node='graph_data_agent',  # Or the calling node name if different
                            input_tokens=tokens["input"],
                            output_tokens=tokens["output"],
                            total_tokens=tokens["total"],
                            status=status
                        )

    async def generate_cumulative_report(self, state: CMAAnalysisState) -> Dict[str, Any]:
        """Node: Generates the final cumulative report from individual insights."""
        self.logger.info("Node: Generating Cumulative Report...")
        insights = state.get("insights", {})
        if not insights:
            self.logger.warning("No analysis insights found to generate cumulative report.")
            return {"final_report": "No analysis insights were generated to create a cumulative report."}

        # Format insights for the prompt
        insights_str = "\n\n".join(
            f"## Analysis for: {name}\n\n{content}"
            for name, content in insights.items()
            if "Error:" not in content and "Skipped:" not in content # Exclude errors from summary
        )

        if not insights_str:
             self.logger.warning("All sheet analyses resulted in errors or were skipped. No cumulative report generated.")
             return {"final_report": "Cumulative report could not be generated as all sheet analyses failed or were skipped."}

        tokens = {"input": 0, "output": 0, "total": 0}
        status = "failed"

        # --- LLM Call for Synthesis ---
        prompt_content = f"""You are a financial analyst assistant. You have received individual analysis reports for different sections (sheets) of a financial dataset (like a CMA report). Your task is to synthesize these reports into a single, cohesive cumulative report.
            Structure the report logically:
            1.  **Introduction:** Briefly state the purpose (e.g., summary of CMA analysis for {self.account}) and list the sections analyzed.
            2.  **Section Summaries:** For each analyzed section (sheet name), provide a concise summary of its key findings based on the input provided below. Use the sheet names as headings (e.g., `## Balance Sheet`).
            3.  **Overall Conclusion/Key Takeaways:** Provide a high-level summary synthesizing the findings across all sections. Highlight any major trends, risks, or important points derived from the combined analysis.
            
            Ensure the output is clean Markdown.
            
            **Individual Section Analyses Input:**
            
            {insights_str}
            
            **Generate the Cumulative Report:**
            
            Final output should be without ```markdown and ```.
            """
        messages = [HumanMessage(content=prompt_content)]

        try:
            self.logger.info("Invoking LLM to generate cumulative report...")
            response = await self.llm.ainvoke(messages)
            tokens = self._extract_token_usage(response)
            final_report_content = response.content if hasattr(response, 'content') else str(response)
            self.logger.info("Cumulative report content generated by LLM.")
            status = 'completed'

            # --- Save Cumulative Report ---
            # Use timestamp for uniqueness per run
            cumulative_filename = f"Cumulative_Report.md"
            cumulative_path = self.output_path / cumulative_filename # Place it in the base output dir

            # Archive previous cumulative reports for the same account (optional)
            # You might want a different archiving strategy here, e.g., keeping only the last N
            self._rename_file_for_archiving(cumulative_path) # Less useful with timestamp in name

            with open(cumulative_path, "w", encoding=self.config.get("file_encoding", "utf-8")) as f:
                f.write(final_report_content)
            self.logger.info(f"Cumulative report saved to: {cumulative_path}")

            return {"final_report": final_report_content}

        except Exception as err:
            status = 'failed'
            self.logger.error(f"Failed to generate or save cumulative report: {err}", exc_info=True)
            state.setdefault("error_logs", []).append(f"Cumulative Report Error: {err}")
            return {"final_report": f"Error: Failed to generate cumulative report due to: {err}"}

        finally:
            if "tokens" in locals():
                await self._log_llm_call(
                    call_purpose='Generating Cumulative Report',
                    langgraph_node='generate_cumulative_report',
                    input_tokens=tokens["input"],
                    output_tokens=tokens["output"],
                    total_tokens=tokens["total"],
                    status=status
                )

    async def generate_customer_alert(self, state: CMAAnalysisState):
        customer_alert_output_path = Path(state["output_path"]) / "customer_alerts"
        customer_alert_output_path.mkdir(parents=True, exist_ok=True)
        extractor = FinancialDataExtractor(
            excel_file_path=Path(state["excel_file_path"]),
            customer_alert_output_directory = str(customer_alert_output_path),
            config = self.config,
            llm = self.llm
        )
        token_use,status = extractor.run()
        tokens = self._extract_token_usage(token_use)
        if tokens is not None:
            await self._log_llm_call(
                call_purpose=f'generate customer alert',
                langgraph_node='customer_alert',  # Or the calling node name if different
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                total_tokens=tokens["total"],
                status=status
            )
        print()

    def _create_langgraph_workflow(self) -> StateGraph:
        """Creates the LangGraph workflow definition."""
        self.logger.info("Defining LangGraph workflow...")
        workflow = StateGraph(CMAAnalysisState)

        # Add nodes
        workflow.add_node("extract_excel", self.extract_data_from_excel_to_markdown)
        workflow.add_node("graph_data_node", self.graph_data_agent)
        workflow.add_node("analyze_sheets", self.analyze_markdown_and_generate_report)
        workflow.add_node("summarize_report", self.generate_cumulative_report)
        workflow.add_node("customer_alert", self.generate_customer_alert)

        # Define edges
        workflow.set_entry_point("extract_excel")
        workflow.add_edge("extract_excel", "graph_data_node")
        workflow.add_edge("graph_data_node", "analyze_sheets")
        workflow.add_edge("analyze_sheets", "summarize_report")
        workflow.add_edge("summarize_report", "customer_alert")
        workflow.set_finish_point("customer_alert") # Explicit finish point

        self.logger.info("LangGraph workflow defined.")
        return workflow

    async def run_analysis(self, excel_file_path: str):
        """
        Runs the full CMA analysis workflow for the given Excel file.
        Should be called within the 'async with' block of the analyzer instance.
        """
        excel_file_path_obj = Path(excel_file_path)
        self.logger.info(f"Starting CMA analysis workflow for file: {excel_file_path_obj}")

        if not self.mcp_session or not self.mcp_client:
             raise RuntimeError("MCP Client/Session not active. Ensure run_analysis is called within 'async with CMAAnalyzer(...):'")

        try:
            # --- Initialize Agent (requires active MCP session) ---
            await self.initialize_agent()

            # --- Compile Workflow ---
            analysis_workflow_graph = self._create_langgraph_workflow()
            compiled_workflow = analysis_workflow_graph.compile()
            self.logger.info("LangGraph workflow compiled.")

            # --- Prepare Initial State ---
            initial_state: CMAAnalysisState = {
                "excel_file_path": str(excel_file_path_obj),
                "output_path": str(self.output_path), # Pass output path in state
                "timestamp": self.timestamp, # Pass timestamp in state
                "insights": {},
                "sheets_data": {},
                "sheets_to_analyze": [],
                "intermediate_steps": [],
                "llm_agent_result": "",
                "final_report": "",
                "error_logs": [],
            }

            # --- Invoke Workflow ---
            self.logger.info("Invoking LangGraph workflow...")
            # Set a reasonable recursion limit for ReAct agents
            final_state = await compiled_workflow.ainvoke(initial_state, {"recursion_limit": 15})
            self.logger.info("LangGraph workflow invocation complete.")

            # --- Log Final Status ---
            if final_state:
                self.logger.info(f"Final report status: {'Generated' if final_state.get('final_report') and 'Error:' not in final_state.get('final_report','') else 'Failed or Not Generated'}")
                errors = final_state.get("error_logs", [])
                if errors:
                    self.logger.warning("Workflow completed with errors:")
                    for error in errors:
                        self.logger.warning(f"- {error}")
                else:
                    self.logger.info("Workflow completed successfully with no logged errors in state.")
                # Return the final state for potential use by the caller
                return final_state
            else:
                self.logger.error("Workflow invocation returned None or empty state.")
                return {"error_logs": ["Workflow invocation failed."]}


        except Exception as e:
            self.logger.error(f"CMA Analysis workflow failed critically: {e}", exc_info=True)
            # Ensure the exception is propagated
            raise
        finally:
            self.logger.info("CMA Analysis run_analysis method finished.")

# --- Standalone Execution Logic (Keep for testing) ---
async def run_standalone_analysis(account_name):
    """Runs the analysis as a standalone script."""
    print(f"Running standalone analysis for account: {account_name}")

    # --- Configuration ---
    CONFIG = {
        "log_level": logging.INFO,
        "model_name": "gpt-4o", # Or "gemini-1.5-flash" etc.
        "data_extraction_format_filename": "data_extraction_format.json",
        "extracted_markdown_dir": "extracted_markdown",
        "extracted_metrics_dir": "extracted_metrics",
        "reports_dir": "reports",
        "audit_data": "audit_data",
        "sheets_to_analyze": ["profit & loss statement","balance sheet","balance sheet2","fund flow","fund flow2"],
        "file_encoding": "utf-8",
    }

    # --- Paths ---
    # Use paths relative to this script file for standalone execution
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent# Adjust if structure differs
    print(PROJECT_ROOT)
    LOG_DIR = PROJECT_ROOT / "logs"
    OUTPUT_BASE_DIR = PROJECT_ROOT / "output"
    DATA_DIR = PROJECT_ROOT / "data" / "input_data_sources"
    TOOLS_DIR = PROJECT_ROOT / "tools" # Assuming tools dir is at project root

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = LOG_DIR / f"{account_name}_cma_analysis_standalone_{TIMESTAMP}.log"

    # --- Logging ---
    logging.basicConfig(
        level=CONFIG["log_level"],
        format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
        filename=LOG_FILE,
        filemode='w' # Overwrite log file for each standalone run
    )
    # Add console handler for standalone runs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(CONFIG["log_level"])
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger('').addHandler(console_handler)

    logger = logging.getLogger("StandaloneCMA")
    logger.info("--- Starting Standalone CMA Analysis ---")

    # --- File Paths ---
    excel_file_path = DATA_DIR / account_name / "1. CMA_Data.xlsx"
    # Output path specific to this account and run
    output_path = OUTPUT_BASE_DIR / account_name / f"run_{TIMESTAMP}"
    mcp_server_path = str(TOOLS_DIR / "mcp_tools.py") # Pass as string

    logger.info(f"Excel Input: {excel_file_path}")
    logger.info(f"Output Path: {output_path}")
    logger.info(f"MCP Server Script: {mcp_server_path}")
    logger.info(f"Log File: {LOG_FILE}")

    if not excel_file_path.is_file():
        logger.error(f"Input Excel file not found: {excel_file_path}")
        return

    if not Path(mcp_server_path).is_file():
        logger.error(f"MCP Server script not found: {mcp_server_path}")
        return

    # --- Instantiate and Run ---
    try:
        # Use 'async with' to manage the analyzer's context (MCP client)
        async with CMAAnalyzer(output_path=str(output_path), account=account_name, config=CONFIG, mcp_server_path=mcp_server_path, logger=logger) as analyzer:
            final_state = await analyzer.run_analysis(str(excel_file_path))
            # Optional: print final report path or summary
            if final_state and final_state.get("final_report") and "Error:" not in final_state.get("final_report"):
                 logger.info(f"Analysis successful. Final report likely in {output_path}")
            else:
                 logger.error("Analysis finished with errors or no final report.")

    except Exception as e:
        logger.error(f"Standalone analysis failed: {e}", exc_info=True)
    finally:
        logger.info("--- Standalone CMA Analysis Finished ---")


# if __name__ == "__main__":
#     # Example for standalone testing
#     account = "siemens_energy" # Replace with your test account
#     # Use asyncio.run() only here at the top level for the standalone script
#     asyncio.run(run_standalone_analysis(account))