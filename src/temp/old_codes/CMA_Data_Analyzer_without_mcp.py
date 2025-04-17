import json
import logging
import os
import pandas as pd
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any, List
from typing_extensions import TypedDict
from pathlib import Path
from datetime import datetime

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool
from langchain.agents import initialize_agent, AgentType
from langgraph.graph import StateGraph
from textwrap import dedent

from src.prompts.prompt_utils import Tools, PromptGenerator

# --- Configuration and Setup ---

# 1. Centralized Configuration:  Use a dictionary or config file for settings.
CONFIG = {
    "log_level": logging.INFO,
    "model_name": "gpt-4o",
    "agent_type": AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    "sheets_to_analyze": ["profit & loss statement"],  # Define sheets to analyze
# ,"fund flow","fund flow2","balance sheet", "balance sheet2
    "data_extraction_format_filename": "data_extraction_format.json",
    "extracted_markdown_dir": "extracted_markdown",
    "extracted_metrics_dir": "extracted_metrics",
    "reports_dir": "reports",
    "file_encoding": "utf-8",
}

# 2.  Environment Variable Handling:  Load once and store.  Handle missing variables gracefully.
load_dotenv(find_dotenv(), verbose=True, override=True)

AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

if not all([AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION]):
    raise ValueError(
        "Missing Azure OpenAI environment variables.  Please set AZURE_OPENAI_API_KEY, AZURE_ENDPOINT, and AZURE_API_VERSION."
    )

# 3. Logging Configuration:  Initialize logger at the module level.
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
CWD = os.getcwd()
LOG_FILE = os.path.join(CWD, f"src/logs/cma_analysis_{TIMESTAMP}.log")

logging.basicConfig(
    level=CONFIG["log_level"], format="%(asctime)s - %(levelname)s - %(message)s", filename=LOG_FILE
)
logger = logging.getLogger(__name__)


# --- Data Structures ---
class CMAAnalysisState(TypedDict):
    excel_file_path: str
    insights: Dict[str, str]
    sheets_data: Dict[str, str]
    output_path: str
    sheets_to_analyze: List[str]
    intermediate_steps: List[Any]  # For agent's thought process
    llm_agent_result: str


# --- CMAAnalyzer Class ---
class CMAAnalyzer:
    """
    A class for analyzing CMA data from Excel files using LLMs and tools.
    """

    def __init__(self, output_path, account, llm=None):
        """
        Initializes the CMAAnalyzer with an LLM and output path.

        Args:
            llm: The language model to use for analysis. Defaults to AzureChatOpenAI.
            output_path (str): The directory to save the output Markdown files.
        """
        self.llm = llm or AzureChatOpenAI(
            model=CONFIG["model_name"],
            api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_ENDPOINT,
            api_version=AZURE_API_VERSION,
            temperature=0,
        )
        self.string_output_parser = StrOutputParser()
        self.output_path = Path(output_path)  # Use Path object
        self.logger = logger
        self.timestamp = TIMESTAMP
        self.account = account  # Store account information

        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory set to: {self.output_path}")

        tools = Tools(self.output_path, self.timestamp, self.logger)

        # Define tools
        self.analysis_tools = [
            Tool(
                name="Calculate Profit and Loss Metrics",
                func=tools.calculate_profit_loss_metrics,
                description="Useful for calculating all the metrics related to P&L Statement. Input is the string format.",
            ),
            Tool(
                name="Calculate Fund Flow Metrics",
                func=tools.calculate_fund_flow_metrics,
                description="Useful for calculating all the metrics related to Fund Flow. Input is the string format.",
            ),
            Tool(
                name="Calculate Balance Sheet Metrics",
                func=tools.calculate_balance_sheet_metrics,
                description="Useful for calculating all the metrics related to Balance Sheet. Input is the string format.",
            ),
        ]

        # Initialize agent
        self.llm_agent_executor = initialize_agent(
            self.analysis_tools,
            self.llm,
            agent=CONFIG["agent_type"],
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,  # Important for handling parsing errors
        )

    def extract_data_from_excel_to_markdown(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts data from Excel sheets and converts them to Markdown format."""
        excel_file_path = Path(state["excel_file_path"])  # Convert to Path object
        logger.info(f"Extracting text from Excel file: {excel_file_path}")

        if not excel_file_path.exists():
            logger.error(f"Excel file not found: {excel_file_path}")
            raise FileNotFoundError(f"Excel file not found: {excel_file_path}")

        try:
            excel_file = pd.ExcelFile(excel_file_path)
            extracted_sheets_data = {}
            for sheet_name in excel_file.sheet_names:
                if sheet_name.lower() in CONFIG["sheets_to_analyze"]:
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
                        logger.info(f"Extracted data from sheet: {sheet_name}")
                    except Exception as e:
                        logger.error(f"Error processing sheet {sheet_name}: {e}")
                        raise

            extracted_markdown_path = self.output_path / CONFIG["extracted_markdown_dir"]
            extracted_markdown_path.mkdir(parents=True, exist_ok=True)

            for filename, content in extracted_sheets_data.items():
                markdown_file_name = f"{filename}_{self.timestamp}"
                try:
                    markdown_file_path = extracted_markdown_path / f"{markdown_file_name}.md"
                    with open(markdown_file_path, "w",
                              encoding=CONFIG["file_encoding"]) as markdown_file:  # Specify encoding
                        markdown_file.write(content)
                    logger.info(f"Created Markdown file: {markdown_file_path}")
                except Exception as e:
                    logger.error(f"Error creating Markdown file {markdown_file_name}.md: {e}")

            logger.debug(f"Extracted sheet data: {list(extracted_sheets_data.keys())}")
            return {"sheets_data": extracted_sheets_data, "sheets_to_analyze": list(extracted_sheets_data.keys())}

        except FileNotFoundError:
            logger.error(f"Excel file not found: {excel_file_path}")
            raise
        except Exception as e:
            logger.error(f"Error during Excel processing: {e}")
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
                    If you are unable to find any value, put 0 respectively.
                    """,
            )

            prompt = ChatPromptTemplate.from_messages(
                [("system", system_prompt), ("human", f"Data: {dedent(sheet_data)}")]
            )

            data_extraction_chain = prompt | self.llm | self.string_output_parser

            llm_agent_result = data_extraction_chain.invoke({"data": sheet_data})

            extracted_metrics_path = self.output_path / CONFIG["extracted_metrics_dir"]
            extracted_metrics_path.mkdir(parents=True, exist_ok=True)

            output_file_path = extracted_metrics_path / f"{sheet_name}_{self.timestamp}.md"
            try:
                with open(output_file_path, "w", encoding=CONFIG["file_encoding"]) as output_file:
                    output_file.write(llm_agent_result)
                self.logger.info(f"Extracted data written to: {output_file_path}")
            except Exception as e:
                self.logger.error(f"Error writing to file {output_file_path}: {e}")
                raise
            state["llm_agent_result"] = llm_agent_result
            return state
        except Exception as err:
            self.logger.error(
                f"Failed to extract the data in requested format for {sheet_name} due to {err}"
            )
            raise

    def analyze_markdown_and_generate_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes the selected sheets using the LLM and tools."""
        prompt_generator = PromptGenerator(self.logger)
        extracted_sheets_data = state["sheets_data"]
        sheets_to_analyze = state["sheets_to_analyze"]
        logger.info(f"Sheets to Analyze: {sheets_to_analyze}")
        analysis_insights = {}

        data_format_file_path = Path(
            CWD
            + f"/src/data/input_data_sources/{self.account}/{CONFIG['data_extraction_format_filename']}"
        )
        if not data_format_file_path.exists():
            logger.error(f"Data format file not found: {data_format_file_path}")
            raise FileNotFoundError(f"Data format file not found: {data_format_file_path}")

        try:
            with open(data_format_file_path, "r") as data_format_file:
                data_format = json.load(data_format_file)
        except Exception as e:
            logger.error(f"Error reading data format file: {e}")
            raise

        reports_path = self.output_path / CONFIG["reports_dir"]
        reports_path.mkdir(parents=True, exist_ok=True)

        for sheet_name in sheets_to_analyze:
            logger.info(f"Analyzing sheet: {sheet_name}")
            try:
                sheet_data = extracted_sheets_data[sheet_name]
                data_format_for_sheet = data_format["data_format"].get(sheet_name, {})
                _ = self.extract_data_in_required_format(state, sheet_data, data_format_for_sheet, sheet_name)
                prompt = prompt_generator.get_sheet_specific_prompt(sheet_name, state)
                if prompt:
                    logger.info(f"Invoking agent executor for sheet: {sheet_name}")
                    llm_agent_result = self.llm_agent_executor.invoke({"input": prompt})
                    analysis_insights[sheet_name] = llm_agent_result["output"]
                    output_file_path = reports_path / f"{sheet_name}.md"
                    try:
                        with open(output_file_path, "w", encoding=CONFIG["file_encoding"]) as output_file:
                            output_file.write(llm_agent_result["output"])
                        logger.info(f"Analysis for {sheet_name} saved to {output_file_path}")
                    except Exception as e:
                        logger.error(f"Error writing to {output_file_path}: {e}")
                        raise
                    logger.info(f"Analysis for {sheet_name} saved to {output_file_path}")
                else:
                    logger.info(f"Prompt is not available for {sheet_name}")
            except Exception as e:
                logger.error(f"Error analyzing sheet {sheet_name}: {e}")
                raise

        return {"insights": analysis_insights}

    def create_langgraph_workflow(self):
        """Creates a LangGraph workflow for CMA analysis."""
        logger.info("Creating LangGraph workflow")
        workflow = StateGraph(CMAAnalysisState)

        workflow.add_node("Load and Convert Excel in Markdown", self.extract_data_from_excel_to_markdown)
        workflow.add_node("Analyze Markdown and Generate Report", self.analyze_markdown_and_generate_report)

        workflow.add_edge("Load and Convert Excel in Markdown", "Analyze Markdown and Generate Report")

        workflow.set_entry_point("Load and Convert Excel in Markdown")

        compiled_workflow = workflow.compile()
        logger.info("LangGraph workflow created and compiled")
        return compiled_workflow

    def run_analysis(self, excel_file_path: str):
        """Runs the CMA analysis workflow."""
        excel_file_path = Path(excel_file_path)  # Convert to Path object
        logger.info(f"Starting CMA analysis for file: {excel_file_path}")
        try:
            analysis_workflow = self.create_langgraph_workflow()
            initial_state = {
                "excel_file_path": str(excel_file_path),  # Store as string
                "insights": {},
                "sheets_data": {},
                "output_path": str(self.output_path),  # Store as string
                "sheets_to_analyze": [],
                "intermediate_steps": [],
                "llm_agent_result": "",
            }

            analysis_workflow.invoke(initial_state)
            logger.info("LangGraph workflow completed successfully")

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
        finally:
            logger.info("CMA Analysis completed.")


if __name__ == "__main__":
    account = "tesla"
    excel_file_path = os.path.join(CWD, rf"src\data\input_data_sources\{account}\1. CMA_Data.xlsx")
    output_path = os.path.join(CWD, f"src/output/{account}")
    analyzer = CMAAnalyzer(output_path=output_path, account=account)
    try:
        analyzer.run_analysis(excel_file_path)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")