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

from src.prompts.prompt_utils import Tools,PromptGenerator

# Configure logging
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

CWD = os.getcwd()

LOG_FILE = CWD +f"/src/logs/cma_analysis_{TIMESTAMP}.log"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename=LOG_FILE
)
logger = logging.getLogger(__name__)  # Get a logger instance

# Load environment variables
load_dotenv(find_dotenv(), verbose=True, override=True)

# Set environment variables for Azure OpenAI
os.environ["AZURE_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
os.environ["AZURE_ENDPOINT"] = os.getenv("AZURE_ENDPOINT")
os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")


class CMAAnalysisState(TypedDict):
    excel_file_path: str
    insights: Dict[str, str]
    sheets_data: Dict[str, str]
    output_path: str
    sheets_to_analyze: List[str]
    intermediate_steps: List[Any]  # For agent's thought process
    result: str


class CMAAnalyzer:
    """
    A class for analyzing CMA data from Excel files using LLMs and tools.
    """

    def __init__(self, output_path, llm=None,):
        """
        Initializes the CMAAnalyzer with an LLM and output path.

        Args:
            llm: The language model to use for analysis. Defaults to AzureChatOpenAI.
            output_path (str): The directory to save the output Markdown files.
        """
        self.llm = llm or AzureChatOpenAI(
            model="gpt-4o",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
            api_version=os.getenv("AZURE_API_VERSION"),
            temperature=0,
        )
        self.output_parser = StrOutputParser()
        self.output_path = Path(output_path)  # Use Path object
        self.logger = logger
        self.timestamp = TIMESTAMP


        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory set to: {self.output_path}")

        tools = Tools(self.output_path,self.timestamp,self.logger)

        # Define tools
        self.tools = [
            Tool(
                name="Calculate P&L Metrics",
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
            )
        ]

        # Initialize agent
        self.agent_executor = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
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
            xl = pd.ExcelFile(excel_file_path)
            sheets_data = {}
            # "profit & loss statement", "fund flow", "fund flow2",
            for sheet in xl.sheet_names:
                # if sheet.lower() in ["profit & loss statement", "fund flow", "fund flow2"]:
                if sheet.lower() in ["balance sheet","balance sheet2"]:
                    try:
                        excel_data = pd.read_excel(
                            excel_file_path, engine="openpyxl", sheet_name=sheet
                        )
                        cleaned_excel_data = excel_data.dropna(how="all")
                        processed_excel_data = cleaned_excel_data.fillna("").reset_index(drop=True)
                        markdown_text = str(processed_excel_data.to_markdown())
                        text = f"##### {sheet} \n " + markdown_text

                        if any(char.isdigit() for char in sheet):
                            result = "".join([char for char in sheet if not char.isdigit()])
                            if result in sheets_data:
                                sheets_data[result] = sheets_data[result] + "\n\n" + text
                            else:
                                sheets_data[result] = text
                        else:
                            sheets_data[sheet] = text
                        logger.info(f"Extracted data from sheet: {sheet}")
                    except Exception as e:
                        logger.error(f"Error processing sheet {sheet}: {e}")
                        raise

            for filename, content in sheets_data.items():
                file = f"{filename}_{TIMESTAMP}"
                try:
                    file_path = self.output_path / "extracted_markdown" / f"{file}.md"
                    file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
                    with open(file_path, "w", encoding="utf-8") as f:  # Specify encoding
                        f.write(content)
                    logger.info(f"Created Markdown file: {file_path}")
                except Exception as e:
                    logger.error(f"Error creating Markdown file {file}.md: {e}")

            logger.debug(f"Extracted sheet data: {list(sheets_data.keys())}")
            return {"sheets_data": sheets_data, "sheets_to_analyze": list(sheets_data.keys())}

        except FileNotFoundError:
            logger.error(f"Excel file not found: {excel_file_path}")
            raise
        except Exception as e:
            logger.error(f"Error during Excel processing: {e}")
            raise

    def extract_data(self, state, sheet_data, data_format, sheet_name):
        """
        LLM Agent for Extracting Data in format, so the Tool can utilies the input for the calculations
        """
        try:
            self.logger.info("Extracting data in requested format for tool calculation..")
            system = dedent(
                f"""
                    You are an intelligent data extraction assistant. Your task is to analyze and understand the provided data, extract the data in the below format. 
                    {{{data_format}}}
                    
                    Output must be in the above format only. Produce a clean output without any ```json ``` or ```python ```.
                    If you are unable to find any value, put 0 respectively.
                    """,
            )

            prompt = ChatPromptTemplate.from_messages(
                [("system", system), ("human", f"Data: {dedent(sheet_data)}")]
            )

            data_extraction = prompt | self.llm | StrOutputParser()

            result = data_extraction.invoke({"data": sheet_data})

            output_file_path = self.output_path / "extracted_metrics" / f"{sheet_name}_{TIMESTAMP}.md"
            output_file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            try:
                with open(output_file_path, "w") as f:
                    f.write(result)
                self.logger.info(f"Extracted data written to: {output_file_path}")
            except Exception as e:
                self.logger.error(f"Error writing to file {output_file_path}: {e}")
                raise
            state["result"] = result
            return state
        except Exception as err:
            self.logger.error(f"Failed to extract the data in requested format for {sheet_name} due to {err}")

    def analyze_markdown_and_generate_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes the selected sheets using the LLM and tools."""
        get_prompt = PromptGenerator(self.logger)
        sheets_data = state["sheets_data"]
        sheets_to_analyze = state["sheets_to_analyze"]
        logger.info(f"Sheets to Analyze: {sheets_to_analyze}")
        insights = {}

        data_format_file = Path(CWD+f"/src/data/input_data_sources/{account}/data_extraction_format.json")
        if not data_format_file.exists():
            logger.error(f"Data format file not found: {data_format_file}")
            raise FileNotFoundError(f"Data format file not found: {data_format_file}")

        try:
            with open(data_format_file, "r") as f:
                data_format = json.loads(f.read())
        except Exception as e:
            logger.error(f"Error reading data format file: {e}")
            raise

        for sheet_name in sheets_to_analyze:
            logger.info(f"Analyzing sheet: {sheet_name}")
            try:
                sheet_data = sheets_data[sheet_name]
                data_format_sheet = data_format["data_format"].get(sheet_name, {})
                _ = self.extract_data(state, sheet_data, data_format_sheet, sheet_name)
                prompt = get_prompt.get_sheet_specific_prompt(sheet_name, state)
                if prompt:
                    logger.info(f"Invoking agent executor for sheet: {sheet_name}")
                    result = self.agent_executor.invoke({"input": prompt})
                    insights[sheet_name] = result["output"]
                    output_file_path = self.output_path / "reports" / f"{sheet_name}.md"
                    output_file_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        with open(output_file_path, "w") as f:
                            f.write(result["output"])
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

        return {"insights": insights}

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
            app = self.create_langgraph_workflow()
            initial_state = {
                "excel_file_path": str(excel_file_path),  # Store as string
                "insights": {},
                "sheets_data": {},
                "output_path": str(self.output_path),  # Store as string
                "sheets_to_analyze": [],
                "intermediate_steps": [],
            }

            app.invoke(initial_state)
            logger.info("LangGraph workflow completed successfully")

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
        finally:
            logger.info("CMA Analysis completed.")


if __name__ == "__main__":
    # Example usage
    account = "tesla"
    excel_file_path =  CWD + rf"\src\data\input_data_sources\{account}\1. CMA_Data.xlsx"
    output_path = CWD+f"/src/output/{account}"
    analyzer = CMAAnalyzer(output_path = output_path)
    try:
        analyzer.run_analysis(excel_file_path)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")