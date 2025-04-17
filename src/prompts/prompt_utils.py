########################## Prompts for different sheets ########################################
class PromptGenerator:
    """
    A class for generating prompts based on the sheet type.
    """

    def __init__(self, logger,account):
        """
        Initializes the PromptGenerator with a logger.

        Args:
            logger (logging.Logger, optional): A logger instance. Defaults to None.
        """
        self.logger = logger  # Use provided logger or create a default
        self.account = account
        self.prompts = {
            "profit & loss statement": """
                You are an Financial analyst, expert in analyzing and Generating Profit & Loss Reports,

                Begin by utilizing the Profit & Loss tool with the provided data {state_result}. 
                This will provide pre-calculated required metrics essential for your analysis. 
                Ensure you record the output of this tool for inclusion in your report.

                Once you have the output from  tool, generate a analysis report focusing on
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

            "balance sheet": """
                Begin by utilizing the Balance Sheet tool with the provided data {state_result}. 
                This will provide pre-calculated financial metrics essential for generate balance sheet report. 
                Ensure you record the output of this tool for inclusion in your report.
                
                Once you have the output from the tool, generate a report focusing on the following KPIs. For each KPI, address the points listed and incorporate the calculated metrics from 
                the tool output to support your observations.

                Key Metrics to Address:
                    1. Liquidity Ratios (Short-term Financial Health)
                      - Current Ratio: [Value] (Interpret the company's ability to cover short-term obligations)
                      - Quick Ratio (Acid-Test Ratio): [Value] (Evaluate the company's stringent liquidity measure)
                      - Working Capital: [Value] (Assess operational liquidity)
                    2. Solvency Ratios (Long-term Financial Stability)
                      - Debt-to-Equity Ratio: [Value] (Analyze financial leverage)
                      - Interest Coverage Ratio: [Value] (Determine the ability to service debt)
                    3. Asset Management & Efficiency Ratios
                      - Return on Assets (ROA): [Value] (Evaluate efficiency in using assets to generate profit)
                      - Fixed Asset Turnover: [Value] (Assess effectiveness in utilizing fixed assets)
                    4. Profitability Indicators
                      - Return on Equity (ROE): [Value] (Analyze profitability from shareholder investment)
                      - Gross Profit Margin: [Value] (Measure core business profitability)
                    5. Capital Structure & Leverage Analysis
                      - Equity Ratio: [Value] (Indicate proportion of assets financed by equity)
                      - Debt Ratio: [Value] (Show percentage of assets financed by debt)
                    6. Cash & Reserves Analysis
                      - Cash and Cash Equivalents: [Value] (Assess liquidity reserves)
                      - Retained Earnings: [Value] (Evaluate profit reinvestment for growth)
                Note: Don't change the position of Image in output.
            """,

            "fund flow": """
                Begin by utilizing the 'Calculate Fund Flow Metrics' tool with the provided Fund Flow data {state_result}. 
                This will provide pre-calculated financial metrics essential for generate analysis report. 
                Ensure you record the output of this tool for inclusion in your report.

                Analyze tool output data to assess the financial health and stability of a company. Focus on key metrics to understand the movement of funds, 
                their sources, and their impact on cash liquidity, profitability, and overall financial health.

                Key Metrics to Address:
                    Net Cash Flow: [Value] - Determine if the company has a positive or negative net cash flow and its implications.
                    Operating Cash Flow: [Value] - Analyze cash generated or used by core operating activities.
                    Investing Cash Flow: [Value] - Identify significant capital expenditures or asset investments and proceeds from asset sales.
                    Financing Cash Flow: [Value] - Evaluate cash movements from debt issuance/repayment, equity issuance, or dividend payments.
                    Liquidity Position: [Value] - Assess liquidity based on available cash and equivalents.
                    Working Capital: [Value] - Review changes in working capital and their impact on cash flow.
                    Free Cash Flow: [Value] - Calculate and analyze cash generation after capital expenditures.
                    Debt Service: [Value] - Review the ability to meet debt obligations, including principal and interest payments.
                    Cash Flow from Operations to Net Income: [Value] - Compare operating cash flow to net income for discrepancies.

                Output: Assemble the report in below format
                    1. Introduction 
                        - Brief overview of the company's financial position. 
                        - Purpose of the Fund Flow Statement analysis. 
                        - Key observations on fund movements.
                    2. Sources of Funds 
                        | Source                       | Amount ($) | Remarks                                               |
                        |------------------------------|------------|-------------------------------------------------------|
                        | Net Profit (After Tax)       | XXX        | Indicates earnings available for reinvestment.        |
                        | Depreciation & Amortization  | XXX        | Non-cash expense added back as a source of funds.     |
                        | Sale of Fixed Assets         | XXX        | Liquidation of assets generating cash inflow.         |
                        | Issuance of Shares           | XXX        | Equity capital raised from investors.                 |
                        | Loan Borrowings              | XXX        | New debt raised for business expansion.               |
                        | Other Inflows                | XXX        | Miscellaneous sources of funds.                       |
                    3. Application (Uses) of Funds 
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
            """
        }
        self.default_prompt="""Analyze this financial data {state_result} and provide key insights:
     
                        Please include:
                        1. Key trends and patterns
                        2. Notable anomalies or concerns
                        3. Actionable recommendations
                        4. Important metrics to monitor
                        5. Overall assessment
                    """


    def get_sheet_specific_prompt(self, sheet_name: str, state: dict) -> str:
        """
        Generates a specific prompt based on the sheet type.

        Args:
            sheet_name (str): The name of the sheet.
            state (dict): A dictionary containing the current state of the analysis.

        Returns:
            str: The generated prompt.
        """
        self.logger.info(f"Generating prompt for sheet: {sheet_name}")
        prompt_template = self.prompts.get(sheet_name.lower(), None)
        if prompt_template is None:
            prompt_template = self.default_prompt

        # if sheet_name.lower() in self.prompts:
        prompt = prompt_template.format(state_result = state["llm_agent_result"] if state["llm_agent_result"] else state.get("sheets_data",{}).get([sheet_name.lower()]))
        # print(prompt)
        # else:
        #     prompt = None
        #     # prompt = prompt_template.format(sheet_name=sheet_name, data_str=data_str)
        #     self.logger.error(f"Prompt not defined for the sheet - {sheet_name}")
        # print(prompt)
        self.logger.debug(f"Using prompt: {prompt}")
        return prompt