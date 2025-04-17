import os
from textwrap import dedent
from typing import Dict, Any, List

from dotenv import load_dotenv, find_dotenv
import pandas as pd
from typing_extensions import TypedDict

from langgraph.graph import StateGraph
from langchain_openai import AzureChatOpenAI
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG,  # Set the desired logging level
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv(find_dotenv(), verbose=True, override=True)

# Load environment variables
load_dotenv()

os.environ["AZURE_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
os.environ["AZURE_ENDPOINT"] = os.getenv("AZURE_ENDPOINT")
os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")


class CMAAnalysisState(TypedDict):
    excel_file_path: str
    insights: Dict[str, str]
    sheets_data: Dict[str, str]
    output_path: str
    sheets_to_analyze: List[str]


class CMAAnalyzer:
    """
    A class for analyzing CMA data from Excel files using LLMs.
    """

    def __init__(self, llm=None, output_path="../data/output/walmart/reports"):
        """
        Initializes the CMAAnalyzer with an LLM and output path.

        Args:
            llm: The language model to use for analysis. Defaults to AzureChatOpenAI.
            output_path (str): The directory to save the output Markdown files.
        """
        self.llm = llm or AzureChatOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
            api_version=os.getenv("AZURE_API_VERSION"),
            temperature=0
        )
        self.output_parser = StrOutputParser()
        self.output_path = output_path
        self.system_message = "You are a financial analyst, expert in analyzing CMA data."

        # Ensure output directory exists
        os.makedirs(self.output_path, exist_ok=True)
        logging.info(f"Output directory set to: {self.output_path}")

    def extract_text_from_excel(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts data from Excel sheets and converts them to Markdown format.

        Args:
            state (Dict[str, Any]): The current state of the analysis, including the Excel file path.

        Returns:
            Dict[str, Any]: The updated state with the extracted sheet data.
        """
        logging.info("Starting extract_text_from_excel")
        excel_file_path = state["excel_file_path"]
        logging.debug(f"Excel file path: {excel_file_path}")

        try:
            xl = pd.ExcelFile(excel_file_path)
            sheet_names = xl.sheet_names
            logging.debug(f"Sheet names: {sheet_names}")
            sheets_data = {}

            if len(sheet_names) > 0:
                for sheet in sheet_names:
                    logging.debug(f"Processing sheet: {sheet}")
                    if sheet in ["Fund Flow", "Fund Flow2"]:
                        try:
                            df = pd.read_excel(excel_file_path, engine='openpyxl', sheet_name=sheet)
                            df_cleaned = df.dropna(how='all')
                            df2 = df_cleaned.fillna('').reset_index(drop=True)
                            markdown_text = str(df2.to_markdown())
                            text = f"##### {sheet} \n " + markdown_text

                            if any(char.isdigit() for char in sheet):
                                print(sheet)
                                result = ''.join([char for char in sheet if not char.isdigit()])
                                if result in sheets_data:
                                    temp_data = sheets_data[result] + "\n\n" + text
                                    sheets_data[result] = temp_data
                                else:
                                    sheets_data[result] = text
                            else:
                                sheets_data[sheet] = text
                            logging.debug(f"Extracted data from sheet: {sheet}")
                        except Exception as e:
                            logging.error(f"Error processing sheet {sheet}: {e}")
                            raise

            result = {"sheets_data": sheets_data, "sheets_to_analyze": list(sheets_data.keys())}
            logging.debug(f"Result of extract_text_from_excel: {result}")
            logging.info("Finished extract_text_from_excel")
            return result

        except FileNotFoundError:
            logging.error(f"Excel file not found: {excel_file_path}")
            raise
        except Exception as e:
            logging.error(f"An error occurred during Excel processing: {e}")
            raise

    def get_sheet_specific_prompt(self, sheet_name: str, data_str: str) -> str:
        """
        Generates a specific prompt based on the sheet type.

        Args:
            sheet_name (str): The name of the sheet.
            data_str (str): The data from the sheet in string format.

        Returns:
            str: The sheet-specific prompt.
        """
        logging.info(f"Generating prompt for sheet: {sheet_name}")
        prompts = {
            "Profit & Loss Statement": dedent(f"""Analyze this Profit & Loss Statement data and provide key insights:

            Key metrics that should be monitored in a Profit and Loss (P&L) Statement :
                1. Revenue/Sales: Assess total revenue, breaking it down by product lines or business segments. Consider growth trends and seasonal variations.
                2. Cost of Goods Sold (COGS): Analyze direct production costs. Discuss efficiency in managing production costs and its impact on profit margins. 
                3. Calculate and assess gross profit margin: Gross Profit Margin = (Gross Profit / Revenue), which helps to metric reveals how well the company is managing its production costs relative to its sales.
                4. Operating Expenses: Review operating expenses, including SG&A, R&D, and marketing. Assess the balance in spending.
                5. Operating Income (EBIT): Analyze operating income (Earnings Before Interest and Taxes) and its trend. Determine operational efficiency excluding interest and taxes.
                6. Operating Profit Margin: Calculate operating profit margin: Operating Profit Margin = (EBIT/Revenue)
                7. Net Income: Review net income (bottom line) reflecting total profitability after all expenses. Assess overall financial health.
                8. Net Profit Margin: Calculate net profit margin:  Net Profit Margin = (Net Income / Revenue)
                9. Earnings Per Share (EPS): If applicable, analyze EPS to evaluate profit per outstanding share. Compare EPS trends over time.
                10. EBITDA: Evaluate Earnings Before Interest, Taxes, Depreciation, and Amortization as a measure of operational performance and cash flow generation.
                11. Depreciation and Amortization: Examine the impact of depreciation and amortization on net income, especially for capital-intensive companies.
                12. Interest Expense: Review the cost of debt and its effect on profitability. High interest expenses may indicate over-leverage.
                13. Tax Expense: Assess tax liability and its impact on net income. Look for changes in tax rates or strategies.
                14. EBIT to EBITDA Conversion: Understand the relationship between EBIT and EBITDA and how non-cash expenses (depreciation, amortization) affect profitability.
            """),

            "Balance Sheet": dedent(f"""
            Analyze this Balance Sheet to assess the financial health and stability of a company. Focus on key financial metrics, including liquidity, solvency, profitability, 
            and efficiency. Examine trends in assets, liabilities, and equity to evaluate the company’s leverage, working capital, and overall financial position. Identify any 
            risks or red flags, such as liquidity shortages, excessive debt, or declining asset value. Provide insights into how these financial metrics align with business 
            performance and long-term sustainability. 

            Key Metrics to Monitor in Balance Sheet Analysis:

            - Liquidity Ratios (Short-term Financial Health):
                 -- Current Ratio: Current Assets / Current Liabilities. Measures the ability to cover short-term obligations.
                 -- Quick Ratio (Acid-Test Ratio): (Current Assets - Inventory) / Current Liabilities. A more stringent liquidity measure.
                 -- Working Capital: Current Assets - Current Liabilities. Indicates operational liquidity.
            - Solvency Ratios (Long-term Financial Stability):
                 -- Debt-to-Equity Ratio: Total Debt / Total Equity. Measures financial leverage.
                 -- Interest Coverage Ratio: EBIT / Interest Expense. Ability to service debt.
            - Asset Management & Efficiency Ratios:
                 -- Return on Assets (ROA): Net Income / Total Assets. Efficiency in using assets to generate profit.
                 -- Fixed Asset Turnover: Revenue / Fixed Assets. Effectiveness in utilizing fixed assets.
            - Profitability Indicators:
                 -- Return on Equity (ROE): Net Income / Shareholder’s Equity. Profitability from shareholder investment.
                 -- Gross Profit Margin: (Revenue - COGS) / Revenue. Measures core business profitability.
            - Capital Structure & Leverage Analysis:
                 -- Equity Ratio: Shareholder’s Equity / Total Assets. Indicates the proportion of assets financed by equity.
                 -- Debt Ratio: Total Debt / Total Assets. Shows the percentage of assets financed by debt.
            - Cash & Reserves Analysis:       
                 -- Cash and Cash Equivalents: Assess liquidity reserves.
                 -- Retained Earnings: Evaluate profit reinvestment for growth.
            """),

            "Fund Flow": dedent(f"""
            Analyze the key metrics that should be monitored in a Fund Flow Statement. The goal is to identify the most relevant 
            financial metrics and ratios that provide insights into the movement of funds within a business or organization. 
            Focus on the major inflows and outflows, their sources, and how they impact cash liquidity, profitability, and the 
            company's financial health.

            Be sure to discuss the following:

            1. Net Cash Flow: Determine whether the company has a positive or negative net cash flow and the implications of this for the business.
            2. Operating Cash Flow: Analyze cash generated or used by the company's core operating activities. Consider whether the company is effectively converting its income into cash.
            3. Investing Cash Flow: Identify significant capital expenditures or investments in assets, as well as proceeds from asset sales.
            4. Financing Cash Flow: Evaluate cash movements from activities like issuing or repaying debt, issuing equity, or paying dividends.
            5. Liquidity Position: Assess the company's liquidity based on available cash and equivalents, and how this affects its ability to meet short-term obligations.
            6. Working Capital: Review changes in working capital, such as increases or decreases in accounts receivable, inventory, and accounts payable, and their impact on cash flow.
            7. Free Cash Flow: Calculate and analyze the company’s ability to generate cash after capital expenditures.
            8. Debt Service: Review the company’s ability to meet its debt obligations, including principal and interest payments.
            9. Cash Flow from Operations to Net Income: Compare operating cash flow to net income, checking for discrepancies that might suggest non-cash adjustments.

        Fund Flow Statement Analysis Template
        1. Introduction 
            - Brief overview of the company's financial position. 
            - Purpose of the Fund Flow Statement analysis. 
            - Key observations on fund movements.
        2. Sources of Funds 
            (List out major sources of funds and their impact) 
            Source | Amount ($) | Remarks
            Net Profit (After Tax) | XXX | Indicates earnings available for reinvestment.
            Depreciation & Amortization| XXX | Non-cash expense added back as a source of funds.
            Sale of Fixed Assets | XXX | Liquidation of assets generating cash inflow.
            Issuance of Shares | XXX | Equity capital raised from investors.
            Loan Borrowings | XXX | New debt raised for business expansion.
            Other Inflows | XXX | Miscellaneous sources of funds.
        3. Application (Uses) of Funds 
           (List out major uses of funds and their impact) 
            | **Use**                        | **Amount ($)** | **Remarks**                                      |
            |--------------------------------|----------------|--------------------------------------------------|
            | Capital Expenditures           | XXX            | Investment in new assets, expansion projects.    |
            | Loan Repayment                 | XXX            | Debt reduction, improves solvency.               |
            | Dividend Payments              | XXX            | Returns given to shareholders.                   |
            | Increase in Working Capital    | XXX            | Indicates operational fund usage.                |
            | Purchase of Investments        | XXX            | Investment or strategic acquisitions.            |
            | Other Outflows                 | XXX            | Miscellaneous fund applications.                 |
        4. Changes in Working Capital 
            Increase in Current Assets (e.g., Inventory, Accounts Receivable) → Uses of funds. 
            Increase in Current Liabilities (e.g., Payables, Short-term Debt) → Sources of funds. 
            Net Change in Working Capital: Positive or negative impact on liquidity.
        5. Fund Flow from Different Activities
            | **Activity Type**        | **Net Inflow/Outflow ($)** | **Remarks**                                |
            |--------------------------|----------------------------|--------------------------------------------|
            | Operating Activities     | XXX                        | Profitability and core business cash flow. |
            | Investing Activities     | XXX                        | Asset purchases/sales impact.              |
            | Financing Activities     | XXX                        | Debt and equity transactions.              |
        6. Liquidity & Financial Stability Assessment 
            Cash Flow Sufficiency: Can the company meet short-term and long-term obligations? 
            Debt-Equity Ratio Impact: Does fund movement improve or worsen financial leverage? 
            Overall Business Strategy Alignment: Are fund flows supporting business growth? 
        7. Key Insights & Recommendations 
            Identify positive trends (e.g., strong cash inflows, reduced debt, improved working capital). 
            Highlight risk factors (e.g., declining liquidity, excessive debt, negative working capital). 
            Suggest strategic actions to optimize fund management
            """),
        }

        default_prompt = f"""
        Analyze this financial data from the '{sheet_name}' sheet and provide key insights:

        {data_str}

        Please include:
        1. Key trends and patterns
        2. Notable anomalies or concerns
        3. Actionable recommendations
        4. Important metrics to monitor
        5. Overall assessment
        """

        prompt = prompts.get(sheet_name, default_prompt)
        # logging.debug(f"Generated prompt: {prompt}")
        return prompt

    def analyze_sheets(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes the selected sheets using the LLM.

        Args:
            state (Dict[str, Any]): The current state of the analysis, including the sheet data and sheets to analyze.

        Returns:
            Dict[str, Any]: The updated state with the analysis insights.
        """
        logging.info("Starting analyze_sheets")
        sheets_data = state["sheets_data"]
        sheets_to_analyze = state["sheets_to_analyze"]
        logging.debug(f"Sheets to analyze: {sheets_to_analyze}")
        insights = {}

        for sheet_name in sheets_to_analyze:
            logging.info(f"Analyzing sheet: {sheet_name}")
            try:
                sheet_data = sheets_data[sheet_name]
                data_str = sheet_data

                prompt = self.get_sheet_specific_prompt(sheet_name, data_str)
                logging.debug(f"Prompt for {sheet_name}: {prompt}")

                system = self.system_message + prompt

                print(system)

                print(data_str)

                chain = (
                        ChatPromptTemplate.from_messages([
                            ("system", system),
                            ("human", data_str)
                        ])
                        | self.llm
                        | self.output_parser
                )

                logging.info(f"Invoking LLM chain for sheet: {sheet_name}")
                result = chain.invoke({})
                logging.debug(f"LLM result for {sheet_name}: {result}")

                output_file_path = os.path.join(self.output_path, f"{sheet_name}.md")
                with open(output_file_path, "w") as f:  # Use "w" to overwrite existing files
                    f.write(result)
                logging.info(f"Analysis for {sheet_name} saved to {output_file_path}")

                insights[sheet_name] = result

            except Exception as e:
                logging.error(f"Error analyzing sheet {sheet_name}: {e}")
                raise

        logging.info("Finished analyze_sheets")
        return {"insights": insights}

    def create_langgraph_workflow(self):
        """
        Creates a LangGraph workflow for CMA analysis.

        Returns:
            StateGraph: The compiled LangGraph workflow.
        """
        logging.info("Creating LangGraph workflow")
        workflow = StateGraph(CMAAnalysisState)

        workflow.add_node("load_excel", self.extract_text_from_excel)
        workflow.add_node("analyze_sheets", self.analyze_sheets)

        workflow.add_edge("load_excel", "analyze_sheets")
        workflow.set_entry_point("load_excel")

        compiled_workflow = workflow.compile()
        logging.info("LangGraph workflow created and compiled")
        return compiled_workflow

    def run_analysis(self, excel_file_path: str):
        """
        Runs the CMA analysis workflow.

        Args:
            excel_file_path (str): The path to the Excel file to analyze.
        """
        logging.info(f"Starting CMA analysis for file: {excel_file_path}")
        try:
            app = self.create_langgraph_workflow()
            initial_state = {"excel_file_path": excel_file_path,
                             "insights": {},
                             "sheets_data": {},
                             "output_path": self.output_path,
                             "sheets_to_analyze": []}
            logging.debug(f"Initial state: {initial_state}")

            logging.info("Invoking LangGraph workflow")
            app.invoke(initial_state)
            logging.info("LangGraph workflow completed successfully")

        except Exception as e:
            logging.error(f"An error occurred during the analysis: {e}")
            raise
        finally:
            logging.info("CMA Analysis completed.")


if __name__ == '__main__':
    excel_file_path = r"../../data/input_data_sources/tesla/1. CMA_Data.xlsx"
    analyzer = CMAAnalyzer()
    try:
        analyzer.run_analysis(excel_file_path)
    except Exception as e:
        logging.error(f"Analysis failed: {e}")