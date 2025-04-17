# -*- coding: utf-8 -*-
import json
import os
import re
import time

import pandas as pd
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any, List

from langchain_core.messages import ToolMessage, HumanMessage
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

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters, stdio_client

from src.prompts.prompt_utils import PromptGenerator

# 1.  Environment Variable Handling:  Load once and store.  Handle missing variables gracefully.
load_dotenv(find_dotenv(), verbose=True, override=True)

AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not all([AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION]):
    raise ValueError(
        "Missing Azure OpenAI environment variables.  Please set AZURE_OPENAI_API_KEY, AZURE_ENDPOINT, and AZURE_API_VERSION."
    )

# 3. Logging Configuration:  Initialize logger at the module level.
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
CWD = os.getcwd()
LOG_FILE = os.path.join(CWD, f"src/logs/cma_analysis_{TIMESTAMP}.log")


# --- Data Structures ---
class CMAAnalysisState(TypedDict,total=False):
    excel_file_path: str
    insights: Dict[str, str]
    sheets_data: Dict[str, str]
    output_path: str
    sheets_to_analyze: List[str]
    intermediate_steps: List[Any]  # For agent's thought process
    llm_agent_result: str
    final_report: str



# --- CMAAnalyzer Class ---
class CMAAnalyzer:
    """
    A class for analyzing CMA data from Excel files using LLMs and tools.
    """

    def __init__(self, output_path, account,config,mcp_server_path,logger,llm=None):
        """
        Initializes the CMAAnalyzer with an LLM and output path.

        Args:
            llm: The language model to use for analysis. Defaults to AzureChatOpenAI.
            output_path (str): The directory to save the output Markdown files.
        """
        self.CONFIG = config
        self.mcp_server_path = mcp_server_path
        self.llm_agent_executor = None
        if str(self.CONFIG["model_name"]).__contains__("gpt"):
            self.llm = llm or AzureChatOpenAI(
                model=self.CONFIG["model_name"],
                api_key=AZURE_API_KEY,
                azure_endpoint=AZURE_ENDPOINT,
                api_version=AZURE_API_VERSION,
                temperature=0,
            )
        elif str(self.CONFIG["model_name"]).__contains__("gemini"):
            self.llm = ChatGoogleGenerativeAI(model=self.CONFIG["model_name"],
                                              google_api_key=GOOGLE_API_KEY,
                                              temperature=0)

        self.string_output_parser = StrOutputParser()
        self.output_path = Path(output_path)  # Use Path object
        self.logger = logger
        self.timestamp = TIMESTAMP
        self.account = account  # Store account information
        self.tools = []
        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Output directory set to: {self.output_path}")

        ########
        # client for MCP server

        self.server_params = StdioServerParameters(
            command="python",
            args=[self.mcp_server_path],
        )

        self.mcp_client = None
        self.read = None
        self.write = None
        self.mcp_session = None

    async def __aenter__(self):
        """Asynchronous context manager entry."""
        try:
            self.mcp_client = stdio_client(self.server_params)
            self.read, self.write = await self.mcp_client.__aenter__()
            self.mcp_session = ClientSession(self.read, self.write)
            await self.mcp_session.__aenter__()
            await self.mcp_session.initialize()
            return self
        except Exception as e:
            self.logger.error(f"Error entering context: {e}")
            await self.__aexit__(type(e), e, e.__traceback__)  # Ensure cleanup on failure
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Asynchronous context manager exit."""
        try:
            if self.mcp_session:
                await self.mcp_session.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            self.logger.error(f"Error exiting mcp_session: {e}")
        finally:
            self.mcp_session = None

        try:
            if self.mcp_client:
                await self.mcp_client.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            self.logger.error(f"Error exiting mcp_client: {e}")
        finally:
            self.mcp_client = None
            self.read = None
            self.write = None


    async def initialize_agent(self):
        """Initializes the agent with tools."""
        try:
            await self.get_tools()
            self.llm_agent_executor = create_react_agent(self.llm, self.tools, debug=True)
        except Exception as e:
            self.logger.error(f"Error initializing agent: {e}")
            raise

    async def get_tools(self):
        """Retrieves tools from the MCP server."""
        try:
            self.tools = await load_mcp_tools(self.mcp_session)
            print(self.tools)
        except Exception as e:
            self.logger.error(f"Error getting tools from MCP server: {e}")
            raise

    def sanitize_input(self,input_string):
        """
        Sanitize input to prevent directory traversal and ensure safe file access
        """
        # Remove any non-alphanumeric characters except underscores and hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', input_string).lower()
        return sanitized

    def extract_data_from_excel_to_markdown(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts data from Excel sheets and converts them to Markdown format."""
        excel_file_path = Path(state["excel_file_path"])  # Convert to Path object
        self.logger.info(f"Extracting text from Excel file: {excel_file_path}")

        if not excel_file_path.exists():
            self.logger.error(f"Excel file not found: {excel_file_path}")
            raise FileNotFoundError(f"Excel file not found: {excel_file_path}")

        try:
            excel_file = pd.ExcelFile(excel_file_path)
            extracted_sheets_data = {}
            for sheet_name in excel_file.sheet_names:
                # if sheet_name.lower() in self.CONFIG["sheets_to_analyze"]:
                try:
                    excel_data = pd.read_excel(
                        excel_file_path, engine="openpyxl", sheet_name=sheet_name
                    )
                    cleaned_excel_data = excel_data.dropna(how="all")
                    processed_excel_data = cleaned_excel_data.fillna("").reset_index(drop=True)
                    markdown_text = str(processed_excel_data.to_markdown())
                    text = f"##### {sheet_name} \n " + markdown_text

                    if any(char.isdigit() for char in sheet_name):
                        result = "".join([char for char in sheet_name if not char.isdigit()])
                        if result in extracted_sheets_data:
                            extracted_sheets_data[result] = extracted_sheets_data[result] + "\n\n" + text
                        else:
                            extracted_sheets_data[result] = text
                    else:
                        extracted_sheets_data[sheet_name] = text
                    self.logger.info(f"Extracted data from sheet: {sheet_name}")
                except Exception as e:
                    self.logger.error(f"Error processing sheet {sheet_name}: {e}")
                    raise

            extracted_markdown_path = self.output_path / self.CONFIG["extracted_markdown_dir"]
            extracted_markdown_path.mkdir(parents=True, exist_ok=True)

            for filename, content in extracted_sheets_data.items():
                markdown_file_name = f"{filename}_{self.timestamp}".lower()
                try:
                    markdown_file_path = extracted_markdown_path / f"{markdown_file_name}.md"
                    with open(markdown_file_path, "w",
                              encoding=self.CONFIG["file_encoding"]) as markdown_file:  # Specify encoding
                        markdown_file.write(content)
                    self.logger.info(f"Created Markdown file: {markdown_file_path}")
                except Exception as e:
                    self.logger.error(f"Error creating Markdown file for Sheet - {filename}: {e}")

            self.logger.debug(f"Extracted sheet data: {list(extracted_sheets_data.keys())}")
            return {"sheets_data": extracted_sheets_data, "sheets_to_analyze": list(extracted_sheets_data.keys())}

        except FileNotFoundError:
            self.logger.error(f"Excel file not found: {excel_file_path}")
            raise
        except Exception as e:
            self.logger.error(f"Error during Excel processing: {e}")
            raise

    def extract_data_in_required_format(self, state, sheet_data, data_format, sheet_name):
        """
        LLM Agent for Extracting Data in format, so the Tool can utilies the input for the calculations
        """
        try:
            self.logger.info("Extracting data in requested format for tool calculation..")
            system_prompt = dedent(
                f"""
                    You are an intelligent data extraction assistant. Your task is to analyze and understand the provided data, extract the data in the below format. 
                    {{{data_format}}}

                    Output must be in the above format only. Produce a clean output without any ```json ``` or ```python ```.
                    If you are unable to find any value, put 0 respectively. Values should be Numeric. Modify the date in same format (DD-MM-YYYY).
                    """,
            )

            prompt = ChatPromptTemplate.from_messages(
                [("system", system_prompt), ("human", f"Data: {dedent(sheet_data)}")]
            )

            data_extraction_chain = prompt | self.llm | self.string_output_parser

            llm_agent_result = data_extraction_chain.invoke({"data": sheet_data})

            extracted_metrics_path = self.output_path / self.CONFIG["extracted_metrics_dir"]
            extracted_metrics_path.mkdir(parents=True, exist_ok=True)

            output_file_path = extracted_metrics_path / f"{sheet_name}_{self.timestamp}.md".lower()
            print(output_file_path)
            try:
                with open(output_file_path, "w", encoding=self.CONFIG["file_encoding"]) as output_file:
                    output_file.write(llm_agent_result)
                self.logger.info(f"Extracted data written to: {output_file_path}")
            except Exception as e:
                self.logger.error(f"Error writing to file {output_file_path}: {e}")
                raise
            finally:
                output_file.close()
            state["llm_agent_result"] = llm_agent_result
            return state
        except Exception as err:
            self.logger.error(
                f"Failed to extract the data in requested format for {sheet_name} due to {err}"
            )
            raise

    def rename_file_with_modified_time(self,file_path):
        """Function to renaming the files in reports folder."""
        try:
            if os.path.exists(file_path):
                # Get the last modified time
                modified_time = os.path.getmtime(file_path)
                # Format the modified time
                formatted_time = time.strftime('%Y%m%d_%H%M%S', time.localtime(modified_time))
                # Get the file directory and extension
                file_dir, file_name = os.path.split(file_path)
                file_base, file_ext = os.path.splitext(file_name)
                # Create the new file name
                new_file_name = f"{file_base}_{formatted_time}{file_ext}"
                new_file_path = os.path.join(file_dir, new_file_name)
                # Rename the file
                os.rename(file_path, new_file_path)
                self.logger.info(f"File renamed to: {new_file_path}")
        except Exception as err:
            self.logger.error(f"Failed to rename the files due to {err}")

    async def analyze_markdown_and_generate_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes the selected sheets using the LLM and tools."""
        prompt_generator = PromptGenerator(self.logger,self.account)
        extracted_sheets_data = state["sheets_data"]
        sheets_to_analyze = state["sheets_to_analyze"]
        self.logger.info(f"Sheets to Analyze: {sheets_to_analyze}")
        analysis_insights = {}

        data_format_file_path = Path(
            CWD
            + f"/data/input_data_sources/{self.CONFIG['data_extraction_format_filename']}"
        )
        if not data_format_file_path.exists():
            self.logger.error(f"Data format file not found: {data_format_file_path}")
            raise FileNotFoundError(f"Data format file not found: {data_format_file_path}")

        try:
            with open(data_format_file_path, "r") as data_format_file:
                data_format = json.load(data_format_file)
        except Exception as e:
            self.logger.error(f"Error reading data format file: {e}")
            raise

        reports_path = self.output_path / self.CONFIG["reports_dir"]
        reports_path.mkdir(parents=True, exist_ok=True)
        #kn_df = []
        for sheet_name in sheets_to_analyze:
            self.logger.info(f"Analyzing sheet: {sheet_name}")
            try:
                sheet_data = extracted_sheets_data[sheet_name]
                data_format_for_sheet = data_format["data_format"].get(sheet_name, None)
                if data_format_for_sheet:
                    _ = self.extract_data_in_required_format(state, sheet_data, data_format_for_sheet, sheet_name)
                    print("Type of Extracted Data : ", type(state["llm_agent_result"]))
                prompt = prompt_generator.get_sheet_specific_prompt(sheet_name, state)
                if prompt:
                    self.logger.info(f"Invoking agent executor for sheet: {sheet_name}")
                    llm_agent_result = await self.llm_agent_executor.ainvoke({"messages":prompt})
                    llm_response = llm_agent_result["messages"]

                    tool_message = next((msg for msg in llm_response if isinstance(msg, ToolMessage) and not str(msg.content).__contains__("Error")), None)

                    if tool_message:
                        audit_data_path = self.output_path / "audit_data" / f"{sheet_name}_{self.timestamp}.md".lower()
                        audit_data_path.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            # audit_data = pd.DataFrame(ast.literal_eval(tool_message.content))
                            audit_data = pd.DataFrame(json.loads(tool_message.content))
                            with open(audit_data_path, "w",encoding=self.CONFIG["file_encoding"]) as f:
                                f.write(audit_data.to_string())
                            f.close()
                        except Exception as e:
                            self.logger.error(f"Error writing tool data: {e}")
                            raise

                    output = llm_agent_result["messages"][-1].__dict__
                    output_file_path = reports_path / f"{sheet_name}.md".lower()
                    self.rename_file_with_modified_time(output_file_path)
                    try:
                        with open(output_file_path, "w", encoding=self.CONFIG["file_encoding"]) as output_file:
                            output_file.write(output["content"])
                        self.logger.info(f"Analysis for {sheet_name} saved to {output_file_path}")
                        analysis_insights[sheet_name] = output["content"]
                    except Exception as e:
                        self.logger.error(f"Error writing to {output_file_path}: {e}")
                        raise
                    self.logger.info(f"Analysis for {sheet_name} saved to {output_file_path}")
                else:
                    self.logger.info(f"Prompt is not available for {sheet_name}")
                # else:
                #     self.logger.error(f"Data Extraction Format is not available for {sheet_name}")
            except Exception as e:
                self.logger.error(f"Error analyzing sheet {sheet_name}: {e}")
                continue
        # final_report = run_markdown_analysis()
        return {"insights": analysis_insights}

    def generate_cumulative_report(self,state: Dict[str, Any]):
        """Generates the final cumulative report."""
        messages = [
            HumanMessage(
                content=f"""You are a Markdown analysis and reporting tool. Your task is to analyze a collection of Markdown files provided as input 
            and generate a single, comprehensive report summarizing key aspects of the content.

            Here are the individual analyses by section:

            {state["insights"]}

            Please format the final report with appropriate headings and ensuring a cohesive narrative throughout.

            Output format:
                Introduction: Summary of all the sheets
                ##Name of Sheet
                   - Analysis of the respective Sheet
                Conclusion: Based on analysis of all sheets
            """
            )
        ]
        try:
            response = self.llm.invoke(messages)

            # Store the final report
            state["final_report"] = response.content
            cumulative_path = self.output_path / f"Cumulative Report.md"
            self.rename_file_with_modified_time(cumulative_path)
            with open(cumulative_path, "w",encoding=self.CONFIG["file_encoding"]) as f:
                f.write(response.content)
        except Exception as err:
            self.logger.error(f"Failed to create cumulative report due to {err}")

        return state


    def create_langgraph_workflow(self):
        """Creates a LangGraph workflow for CMA analysis."""
        self.logger.info("Creating LangGraph workflow")
        workflow = StateGraph(CMAAnalysisState)
        workflow.add_node("Load and Convert Excel in Markdown", self.extract_data_from_excel_to_markdown)
        workflow.add_node("Analyze Markdown and Generate Report", self.analyze_markdown_and_generate_report)
        workflow.add_node("Generate Cumulative Report", self.generate_cumulative_report)

        workflow.add_edge("Load and Convert Excel in Markdown", "Analyze Markdown and Generate Report")
        workflow.add_edge("Analyze Markdown and Generate Report", "Generate Cumulative Report")

        workflow.set_entry_point("Load and Convert Excel in Markdown")

        compiled_workflow = workflow.compile()
        self.logger.info("LangGraph workflow created and compiled")
        return compiled_workflow

    async def run_analysis(self, excel_file_path: str):
        """Runs the CMA analysis workflow."""
        excel_file_path = Path(excel_file_path)  # Convert to Path object
        self.logger.info(f"Starting CMA analysis for file: {excel_file_path}")
        try:
            async with self:  # Use the class as an async context manager
                await self.initialize_agent()  # Initialize the agent before running the workflow
                analysis_workflow = self.create_langgraph_workflow()
                # initial_state = {
                #     "excel_file_path": str(excel_file_path),  # Store as string
                #     "insights": {},
                #     "sheets_data": {},
                #     "output_path": str(self.output_path),  # Store as string
                #     "sheets_to_analyze": [],
                #     "intermediate_steps": [],
                #     "llm_agent_result": "",
                # }
                initial_state = {
                    "excel_file_path": str(excel_file_path),  # Path to the Excel file
                    "insights": {},  # Initialize as an empty dictionary
                    "sheets_data": {},  # Initialize as an empty dictionary
                    "output_path": str(self.output_path),  # Path to the output directory
                    "sheets_to_analyze": [],  # Initialize as an empty list
                    "intermediate_steps": [],  # Initialize as an empty list
                    "llm_agent_result": "",  # Initialize as an empty string
                    "final_report": "",  # Initialize as an empty string
                    "error_logs": [],  # Initialize as an empty list
                    "timestamp": self.timestamp,  # Use the timestamp from the analyzer
                }
                # compiled_workflow = analysis_workflow.compile()
                result = await analysis_workflow.ainvoke(initial_state,{"recursion_limit": 10})
                self.logger.info(f"LangGraph workflow completed successfully. Result: {result}")

        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            raise
        finally:
            self.logger.info("CMA Analysis completed.")