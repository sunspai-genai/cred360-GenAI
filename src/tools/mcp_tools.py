import ast

from mcp.server.fastmcp import FastMCP
import pandas as pd

mcp = FastMCP("Finance Calculation")

print("MCP Tool Server Started.....")

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Adds two integers.

    Args:
        a (int): The first integer.
        b (int): The second integer.

    Returns:
        int: The sum of the two integers.
    """
    return a + b


def _clean_data(data: str) -> str:
    """Cleans the input data by removing code block markers.

    This function removes common code block markers like ```python, ```json, and ``` from the input string.

    Args:
        data (str): The input data string, potentially containing code block markers.
    Returns:
        str: The cleaned data string with code block markers removed.
    """
    cleaned_data = (
        data.replace("```python", "")
        .replace("```", "")
        .replace("```json", "")
        .replace("```", "")
        .replace("json", "")
    )
    return cleaned_data


@mcp.tool()
def calculate_balance_sheet_metrics(extracted_data_from_sheet) -> dict:
    """Calculates key performance indicators (KPIs) from a balance sheet.

    Args:
        extracted_data_from_sheet : A string containing the balance sheet data
    Returns:
        dict: A dictionary representation of a Pandas DataFrame containing the calculated
            metrics for each period in the balance sheet.
    """
    # Create a DataFrame
    cleaned_data = _clean_data(str(extracted_data_from_sheet))
    data_dict = ast.literal_eval(cleaned_data)
    df = pd.DataFrame(data_dict)

    # Calculate Liquidity Ratios
    df['Current Ratio'] = df['Current Assets'] / df['Current Liabilities']
    df['Quick Ratio (Acid-Test Ratio)'] = (df['Current Assets'] - df['Inventory']) / df['Current Liabilities']
    df['Working Capital'] = df['Current Assets'] - df['Current Liabilities']

    # Calculate Solvency Ratios
    df['Debt-to-Equity Ratio'] = df['Total Debt'] / df['Total Equity']
    df['Interest Coverage Ratio'] = df['EBIT (Earnings Before Interest and Taxes)'] / df['Interest Expense']

    # Calculate Asset Management & Efficiency Ratios
    df['Return on Assets (ROA)'] = df['Net Income'] / df['Total Assets']
    df['Fixed Asset Turnover'] = df['Revenue'] / df['Fixed Assets']

    # Calculate Profitability Indicators
    df['Return on Equity (ROE)'] = df['Net Income'] / df['Shareholders Equity']
    df['Gross Profit Margin'] = (df['Revenue'] - df['COGS (Cost of Goods Sold)']) / df['Revenue']

    # Calculate Capital Structure & Leverage Analysis
    df['Equity Ratio'] = df['Shareholders Equity'] / df['Total Assets']
    df['Debt Ratio'] = df['Total Debt'] / df['Total Assets']

    # Calculate Cash & Reserves Analysis
    df['Cash and Cash Equivalents'] = df['Cash'] + df['Cash Equivalents']
    df['Retained Earnings'] = df['Retained Earnings']  # This is already a component, so just include it as is

    result_df = df[['Date','Current Ratio','Quick Ratio (Acid-Test Ratio)','Working Capital','Debt-to-Equity Ratio','Interest Coverage Ratio',
                    'Return on Assets (ROA)','Fixed Asset Turnover','Return on Equity (ROE)','Gross Profit Margin','Equity Ratio','Debt Ratio',
                    'Cash and Cash Equivalents','Retained Earnings']]

    return result_df.to_dict()


@mcp.tool()
def calculate_pl_statement_metrics(extracted_data_from_sheet) -> dict:
    """Calculates key performance indicators (KPIs) from a Profit and Loss (P&L) statement.

    Args:
        extracted_data_from_sheet : Containing the P&L statement data
    Returns:
        dict: A dictionary representation of a Pandas DataFrame containing the calculated
            metrics for each period in the P&L statement.
    """
    cleaned_data = _clean_data(str(extracted_data_from_sheet))
    data_dict = ast.literal_eval(cleaned_data)
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

    return result_df.to_dict()


@mcp.tool()
def calculate_fund_flow_metrics(extracted_data_from_sheet) -> dict:
    """Calculates key performance indicators (KPIs) from a fund flow statement.

    Args:
        extracted_data_from_sheet (str): A string containing the fund flow statement data
    Returns:
        dict: A dictionary representation of a Pandas DataFrame containing the calculated
            metrics for each period in the fund flow statement.
    """

    cleaned_data = _clean_data(str(extracted_data_from_sheet))
    data_dict = ast.literal_eval(cleaned_data)
    df = pd.DataFrame(data_dict)

    # Calculate Net Cash Flow
    df['Net Cash Flow'] = df['Total Funds Available'] - df['Total Funds Used']

    # Calculate Operating Cash Flow
    df['Operating Cash Flow'] = df['Profit before tax'] + df['Depreciation'] - df['Taxes paid/payable']

    # Calculate Investing Cash Flow (No data provided for asset sales/purchases)
    df['Investing Cash Flow'] = 0

    # Calculate Financing Cash Flow (No data provided for financing activities)
    df['Financing Cash Flow'] = 0

    # Calculate Liquidity Position
    df['Liquidity Position'] = df['Total Funds Available']

    # Calculate Working Capital
    df['Working Capital'] = df['Increase in other current liabilities'] - df['Increase in Receivables'] - df[
        'Increase in Inventory']

    # Calculate Free Cash Flow (No data provided for capital expenditures)
    df['Free Cash Flow'] = df['Operating Cash Flow']

    # Calculate Debt Service
    df['Debt Service'] = df['Decrease in LT/Deb/DPG'] + df['Decrease in Other current liabilities']

    # Calculate Cash Flow from Operations to Net Income
    df['Cash Flow from Operations to Net Income'] = df['Operating Cash Flow'] / df['Profit before tax']

    result_df = df[['Date', 'Depreciation', 'Net Cash Flow', 'Operating Cash Flow', 'Investing Cash Flow',
                    'Financing Cash Flow', 'Liquidity Position', 'Working Capital', 'Free Cash Flow',
                    'Debt Service', 'Cash Flow from Operations to Net Income']]
    return result_df.to_dict()


if __name__ == "__main__":
    # Start a process that communicates via standard input/output
    mcp.run(transport="stdio")