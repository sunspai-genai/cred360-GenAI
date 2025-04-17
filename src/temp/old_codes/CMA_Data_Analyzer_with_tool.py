import ast
import json
import os
import logging
import pandas as pd
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any, List
from typing_extensions import TypedDict

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool
from langchain.agents import initialize_agent, AgentType
from langgraph.graph import StateGraph
from textwrap import dedent

from win32comext.adsi.demos.scp import logger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    def __init__(self, llm=None, output_path="../output/walmart/report"):
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
            temperature=0
        )
        self.output_parser = StrOutputParser()
        self.output_path = output_path
        self.system_message = "You are an financial analyst, expert in analyzing and create Finacial Reports"

        # Ensure output directory exists
        os.makedirs(self.output_path, exist_ok=True)
        logging.info(f"Output directory set to: {self.output_path}")

        # Define tools
        self.tools = [
            Tool(
                name="Calculate P&L Metrics",
                func=self.calculate_profit_loss_metrics,
                description="Useful for calculating all the metrics related to P&L Statement. Input is the string format."
            )
        ]

        # Initialize agent
        self.agent_executor = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True  # Important for handling parsing errors
        )

    def extract_text_from_excel_to_markdown(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts data from Excel sheets and converts them to Markdown format."""
        excel_file_path = state["excel_file_path"]
        logging.info(f"Extracting text from Excel file: {excel_file_path}")

        try:
            xl = pd.ExcelFile(excel_file_path)
            sheets_data = {}

            for sheet in xl.sheet_names:

                if sheet in ["Profit & Loss Statement"]:
                    try:
                        df = pd.read_excel(excel_file_path, engine='openpyxl', sheet_name=sheet)
                        df_cleaned = df.dropna(how='all')
                        df2 = df_cleaned.fillna('').reset_index(drop=True)
                        markdown_text = str(df2.to_markdown())
                        text = f"##### {sheet} \n " + markdown_text

                        if any(char.isdigit() for char in sheet):
                            result = ''.join([char for char in sheet if not char.isdigit()])
                            if result in sheets_data:
                                sheets_data[result] = sheets_data[result] + "\n\n" + text
                            else:
                                sheets_data[result] = text
                        else:
                            sheets_data[sheet] = text
                        logging.info(f"Extracted data from sheet: {sheet}")
                    except Exception as e:
                        logging.error(f"Error processing sheet {sheet}: {e}")
                        raise

            result = {"sheets_data": sheets_data, "sheets_to_analyze": list(sheets_data.keys())}
            logging.debug(f"Extracted sheet data: {list(sheets_data.keys())}")
            return result

        except FileNotFoundError:
            logging.error(f"Excel file not found: {excel_file_path}")
            raise
        except Exception as e:
            logging.error(f"Error during Excel processing: {e}")
            raise

    def extract_data(self, state,sheet_data,data_format,sheet_name):
        """
        LLM Agent for Extracting Data in format, so the Tool can utilies the input for the calculations
        """
        data = sheet_data
        system = dedent("""
                You are an intelligent data extraction assistant. Your task is to analyze and understand the provided data, extract the data in the below format. 
                {%s}
                """%(data_format),)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("human", f"Data: {dedent(data)}")
            ]
        )

        math_data_extraction = prompt | self.llm | StrOutputParser()

        result = math_data_extraction.invoke({"data": data})
        with open(f"../output/account_2/extracted_metrics/{sheet_name}.md", "w") as f:
            f.write(result)
        state["result"] = result
        return state

    def calculate_profit_loss_metrics(self, data):
        """Calculates various financial metrics from the given data."""
        try:
            res = data.replace("```python", '').replace("```", '').replace("```json", "").replace("```", '').replace("json", '')
            data_dict = ast.literal_eval(res)
            df = pd.DataFrame(data_dict)
            # Calculate Total Revenue
            df["Total Revenue"] = df["Gross Sales Local"] + df["Gross Sales Exports"]

            # Calculate COGS
            df["COGS"] = df["Opening SIP"] + df["Raw Materials Imported"]+df["Raw Materials Indigeneous"] + df["Other Spares"] + df["Power & Fuel"] + df["Direct Labour"] + df["Repairs & Main"] + df["Other Operating Exp"] + df["Depreciation"] - df["Closing SIP"]

            # Calculate Gross Profit Margin
            df["Gross Profit Margin"] = (df["Total Revenue"] - df["COGS"]) / df["Total Revenue"]

            # Calculate Operating Expenses
            df["Operating Expenses"] = df["SG&A Expenses"]

            # Calculate EBIT
            df["EBIT"] = df["Total Revenue"] - df["COGS"] - df["Operating Expenses"]

            # Calculate Operating Profit Margin
            df["Operating Profit Margin"] = df["EBIT"] / df["Total Revenue"]

            # Calculate Net Income
            df["Net Income"] = df["Total Revenue"] - (df["COGS"] + df["Operating Expenses"] + df["Interest"] + df["Provision for Tax"])

            # Calculate Net Profit Margin
            df["Net Profit Margin"] = df["Net Income"] / df["Total Revenue"]

            # Calculate EPS (assuming no preferred stock and average outstanding shares is constant)
            average_outstanding_shares = len(df) # Assuming one share per year for simplicity
            df["EPS"] = (df["Net Income"]) / average_outstanding_shares

            # Calculate EBITDA
            df["EBITDA"] = df["EBIT"] + df["Depreciation"]

            # Calculate Depreciation and Amortization (assuming no amortization)
            df["Depreciation and Amortization"] = df["Depreciation"]

            # Calculate Interest Expense
            df["Interest Expense"] = df["Interest"]

            # Calculate Tax Expense
            tax_rate = df['Provision for Tax'] / (df['Net Sales'] - (df['COGS'] + df['Operating Expenses'] + df['Interest']))
            df['Tax Expense'] = tax_rate * (df['Net Sales'] - (df['COGS'] + df['Operating Expenses'] + df['Interest']))

            # Calculate EBIT to EBITDA Conversion
            df['EBITDA Conversion'] = df['EBIT'] + df['Depreciation']

            # Select only the calculated columns for the result DataFrame
            result_df = df[["Date",
                "Total Revenue", "COGS", "Gross Profit Margin", "Operating Expenses", "EBIT",
                "Operating Profit Margin", "Net Income", "Net Profit Margin", "EPS", "EBITDA",
                "Depreciation and Amortization", "Interest Expense", "Tax Expense", "EBITDA Conversion"
            ]]
            with open("") as f:
                f.write(result_df.to_string())
            return result_df.to_string()
        except Exception as e:
            logging.error(f"Error during financial metrics calculation: {e}")
            return "Error: An error occurred during financial metrics calculation."


    def get_sheet_specific_prompt(self, sheet_name: str, data_str: str, state) -> str:
        """Generates a specific prompt based on the sheet type."""
        logging.info(f"Generating prompt for sheet: {sheet_name}")
        prompts = {
            "Profit & Loss Statement": f"""

                You are an Financial analyst, expert in analyzing and Generating Finacial Reports,

                Begin by utilizing the 'Calculate P&L Metrics' tool with the provided P&L data {state["result"]}. 
                This will provide pre-calculated financial metrics essential for your analysis. 
                Ensure you record the output of this tool for inclusion in your report.
                
                Once you have the output from the 'Calculate P&L Metrics' tool, generate a analysis report focusing on
                the following KPIs. For each KPI, address the points listed and incorporate the calculated metrics from 
                the tool output to support your observations.
                
                    Key metrics that should be monitored in a Profit and Loss (P&L) Statement:
                        1. Revenue/Sales: Assess total revenue, breaking it down by product lines or business segments. Consider growth trends and seasonal variations.
                        2. Cost of Goods Sold (COGS): Analyze direct production costs. Discuss efficiency in managing production costs and its impact on profit margins.
                        3. Gross Profit Margin: reveals how well the company is managing its production costs relative to its sales.
                        4. Operating Expenses: Review operating expenses, including SG&A, R&D, and marketing. Assess the balance in spending.
                        5. Operating Income (EBIT): Analyze operating income (Earnings Before Interest and Taxes) and its trend. Determine operational efficiency excluding interest and taxes.
                        6. Operating Profit Margin
                        7. Net Income: Review net income (bottom line) reflecting total profitability after all expenses. Assess overall financial health.
                        8. Net Profit Margin
                        9. Earnings Per Share (EPS): If applicable, analyze EPS to evaluate profit per outstanding share. Compare EPS trends over time.
                        10. EBITDA: Evaluate Earnings Before Interest, Taxes, Depreciation, and Amortization as a measure of operational performance and cash flow generation.
                        11. Depreciation and Amortization: Examine the impact of depreciation and amortization on net income, especially for capital-intensive companies.
                        12. Interest Expense: Review the cost of debt and its effect on profitability. High interest expenses may indicate over-leverage.
                        13. Tax Expense: Assess tax liability and its impact on net income. Look for changes in tax rates or strategies.
                        14. EBIT to EBITDA Conversion: Understand the relationship between EBIT and EBITDA and how non-cash expenses (depreciation, amortization) affect profitability.
                """,
        }

        default_prompt = f"""
            Analyze this financial data from the '{sheet_name}' sheet and provide key insights. If you need to calculate CAGR or YOY growth, use the appropriate tools. Remember to provide ONLY the numbers required by the tool, separated by commas, without any extra text or descriptions. After using the tools, provide a comprehensive analysis incorporating the results.

            {data_str}

            Please include:
            1. Key trends and patterns
            2. Notable anomalies or concerns
            3. Actionable recommendations
            4. Important metrics to monitor
            5. Overall assessment
            """

        prompt = prompts.get(sheet_name, default_prompt)
        logging.debug(f"Using prompt: {prompt}")
        return prompt

    def analyze_sheets(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes the selected sheets using the LLM and tools."""
        sheets_data = state["sheets_data"]
        sheets_to_analyze = state["sheets_to_analyze"]
        logging.info(f"Analyzing sheets: {sheets_to_analyze}")
        insights = {}
        with open("../data/input_data_sources/tesla/data_extraction_format.json", "r") as f:
            data_format = json.loads(f.read())
        print(type(data_format))
        for sheet_name in sheets_to_analyze:
            logging.info(f"Analyzing sheet: {sheet_name}")
            try:
                sheet_data = sheets_data[sheet_name]
                dataFormat = data_format["data_format"][sheet_name]
                _ = self.extract_data(state,sheet_data,dataFormat,sheet_name)
                prompt = self.get_sheet_specific_prompt(sheet_name, sheet_data, state)

                logging.info(f"Invoking agent executor for sheet: {sheet_name}")
                result = self.agent_executor.invoke({"input": prompt})

                output_file_path = os.path.join(self.output_path, f"{sheet_name}.md")
                with open(output_file_path, "w") as f:  # Use "w" to overwrite existing files
                    f.write(result["output"])  # Save the final answer

                insights[sheet_name] = result["output"]
                logging.info(f"Analysis for {sheet_name} saved to {output_file_path}")

            except Exception as e:
                logging.error(f"Error analyzing sheet {sheet_name}: {e}")
                raise

        return {"insights": insights}

    def create_langgraph_workflow(self):
        """Creates a LangGraph workflow for CMA analysis."""
        logging.info("Creating LangGraph workflow")
        workflow = StateGraph(CMAAnalysisState)

        workflow.add_node("load_excel", self.extract_text_from_excel_to_markdown)
        # workflow.add_node("extract_data", self.extract_data)
        workflow.add_node("analyze_sheets", self.analyze_sheets)

        workflow.add_edge("load_excel", "analyze_sheets")
        # workflow.add_edge("extract_data", "analyze_sheets")

        workflow.set_entry_point("load_excel")

        compiled_workflow = workflow.compile()
        logging.info("LangGraph workflow created and compiled")
        return compiled_workflow

    def run_analysis(self, excel_file_path: str):
        """Runs the CMA analysis workflow."""
        logging.info(f"Starting CMA analysis for file: {excel_file_path}")
        try:
            app = self.create_langgraph_workflow()
            initial_state = {
                "excel_file_path": excel_file_path,
                "insights": {},
                "sheets_data": {},
                "output_path": self.output_path,
                "sheets_to_analyze": [],
                "intermediate_steps": []
            }

            app.invoke(initial_state)
            logging.info("LangGraph workflow completed successfully")

        except Exception as e:
            logging.error(f"Analysis failed: {e}")
            raise
        finally:
            logging.info("CMA Analysis completed.")


if __name__ == '__main__':
    # Example usage
    account = "tesla"
    excel_file_path = rf"..\data\input_data_sources\{account}\1. CMA_Data.xlsx"
    analyzer = CMAAnalyzer()
    try:
        analyzer.run_analysis(excel_file_path)
    except Exception as e:
        logging.error(f"Analysis failed: {e}")