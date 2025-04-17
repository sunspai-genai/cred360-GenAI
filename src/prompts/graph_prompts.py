########################## Prompts for different sheets ########################################
class GraphPromptGenerator:
    """
    A class for generating prompts based on the sheet type.
    """

    def __init__(self, logger, account):
        """
        Initializes the PromptGenerator with a logger.

        Args:
            logger (logging.Logger, optional): A logger instance. Defaults to None.
        """
        self.logger = logger  # Use provided logger or create a default
        self.account = account
        self.prompts = {
            "balance sheet": """
            You are the Graph Data Generator Agent. Your task is to process financial data, calculate key financial ratios, generate a Python script using Pygal to create line graphs visualizing these ratio trends with specific styling using randomly selected **darker pastel/muted** colors, save the underlying graph data (including chart type and **chart name**) for **each chart to a separate structured JSON file**, and then modify the resulting SVG files to add a label.

            **Input Data Assumptions:**
            
            You will need to structure the script assuming you have access to yearly data (replace placeholder values in the script with actual data when available) for the following, covering both historical and projected/estimated years.
            Date should be same format (yyyy-mm-dd).

            *   Data required to calculate:
                *   Current Assets
                *   Current Liabilities
                *   Inventory
                *   Total Debt
                *   Total Equity (or Shareholder's Equity)
                *   EBIT (Earnings Before Interest and Taxes)
                *   Interest Expense
                *   Net Income
                *   Total Assets
                *   Revenue (or Net Sales)
                *   Fixed Assets
                *   COGS (Cost of Goods Sold)
            
            **Instructions:**
            
            Generate a *single*, complete Python script that performs the following tasks precisely:
            
            1.  **Imports:** Include necessary imports: `import pygal`, `from pygal.style import Style`, `import os`, `import xml.etree.ElementTree as ET`, `import random`, `import json`.
            2.  **Data Storage & Calculation:**
                *   Define a variable for the account name/identifier (e.g., `account_name = 'placeholder_account'`) to be used in file paths.
                *   Store the financial years (including indicators like '(E)', '(P)') in a list.
                *   Store the extracted yearly raw data needed for calculations within the script (e.g., lists for Current Assets, Current Liabilities, Inventory, etc.). Use placeholder values if actual data isn't provided.
                *   Calculate the following ratios for each available year and store them in lists. Include comments explaining the formula used for each ratio:
                    *   Current Ratio (Comment: Current Assets / Current Liabilities)
                    *   Quick Ratio (Comment: (Current Assets - Inventory) / Current Liabilities)
                    *   Debt-to-Equity Ratio (Comment: Total Debt / Total Equity)
                    *   Interest Coverage Ratio (Comment: EBIT / Interest Expense)
                    *   Return on Assets (ROA) (Comment: Net Income / Total Assets)
                    *   Fixed Asset Turnover (Comment: Revenue / Fixed Assets)
                    *   Return on Equity (ROE) (Comment: Net Income / Shareholder’s Equity)
                    *   Gross Profit Margin (Comment: (Revenue - COGS) / Revenue)
                    *   Equity Ratio (Comment: Shareholder’s Equity / Total Assets)
                    *   Debt Ratio (Comment: Total Debt / Total Assets)
                *   Handle potential division by zero errors gracefully during calculation (e.g., return `None` or `0` and add a comment).
            3.  **Directory Creation:**
                *   Define the graph output directory path: `graph_output_dir = f'{output_path}/graphs/{sheet_directory}/'`.
                *   Define the data output directory path where **individual JSON files for each graph** will be stored: `data_output_dir = f'{output_path}/graph_data/{sheet_directory}/'`.
                *   Include logic to create both output directories if they don't exist: `os.makedirs(graph_output_dir, exist_ok=True)` and `os.makedirs(data_output_dir, exist_ok=True)`.
            4.  **Data Output (JSON):** *(This section is intentionally minimal - JSON writing happens in Instruction #7)*
                *(Ensure the `data_output_dir` is defined and created as per Instruction #3).*
            5.  **Custom Darker Color Style Definition (Randomized):**
                *   Define the list of **darker, more visible** pastel/muted hex color codes:
                    ```python
                    # Darker / More Saturated Pastel/Muted Palette
                    darker_colors = [
                        "#E57373", "#FFB74D", "#FFF176", "#81C784", "#64B5F6", "#BA68C8",
                        "#4DB6AC", "#FF8A65", "#9575CD", "#4DD0E1", "#A1887F", "#F06292",
                        "#7986CB", "#AED581", "#90A4AE", "#D81B60", "#1E88E5", "#43A047"
                     ]
                    ```
                *   **Shuffle the color list randomly:** Use `random.shuffle(darker_colors)` immediately after defining the list.
                *   Create a custom `Style` object using the *shuffled* list: `custom_darker_style = Style(colors=darker_colors)`.
            6.  **Chart Styling and Layout (Apply to ALL charts):**
                *   **Apply Custom Style:** Ensure that *all* chart objects created in the next step are initialized using the `custom_darker_style` defined above (e.g., `pygal.Line(style=custom_darker_style, ...)`).
                *   **Maximize Chart Width:** Configure charts for a wider plot area. Set `margin=40`. Explicitly set `width=1000`.
                *   **Prevent Label Truncation:** Configure all charts to *strictly avoid label truncation*. Set `truncate_label=-1` and `truncate_legend=-1`. Set `legend_at_bottom=True`.
                *   **Label Font Sizes:** Use reasonably small font sizes. Set `label_font_size=10`, `major_label_font_size=10`, and `legend_font_size=10`. Keep `title_font_size=14` or `16`.
                *   Enable tooltips for data points on all charts (`tooltip_border_radius=5`).
            7.  **Chart Generation (Pygal) and Individual JSON Data Output:** Use the `pygal` library to generate and save **five separate line charts** and their corresponding data files, saving SVG charts to the `graph_output_dir` and JSON files to the `data_output_dir`:
            
                *   **Chart 1: Liquidity Ratios Trend**
                    *   Define the SVG output path: `chart1_svg_path = os.path.join(graph_output_dir, 'liquidity_ratios_graph.svg')`.
                    *   Define the JSON output path: `chart1_json_path = os.path.join(data_output_dir, 'liquidity_ratios_data.json')`.
                    *   Create a Python dictionary for this chart including: `chart_type` ("line"), **`c_name` ("Liquidity Ratios Trend")**, `financial_years` (list), and `data_series` (dictionary mapping 'Current Ratio' and 'Quick Ratio' to their calculated data lists).
                    *   Write this dictionary to `chart1_json_path` using `json.dump()`.
                    *   Create a `pygal.Line()` object, apply styling/layout from steps 5 & 6. Title: "Liquidity Ratios Trend". X-labels: financial years.
                    *   Plot 'Current Ratio', 'Quick Ratio'. Handle `None` values.
                    *   Render and save SVG to `chart1_svg_path`.
            
                *   **Chart 2: Solvency Ratios Trend**
                    *   Define SVG path: `chart2_svg_path = os.path.join(graph_output_dir, 'solvency_ratios_graph.svg')`.
                    *   Define JSON path: `chart2_json_path = os.path.join(data_output_dir, 'solvency_ratios_data.json')`.
                    *   Create dict: `chart_type` ("line"), **`c_name` ("Solvency Ratios Trend")**, `financial_years`, `data_series` ('Debt-to-Equity Ratio', 'Interest Coverage Ratio').
                    *   Write dict to `chart2_json_path`.
                    *   Create `pygal.Line()`, apply styling/layout. Title: "Solvency Ratios Trend". X-labels: financial years.
                    *   Plot 'Debt-to-Equity Ratio', 'Interest Coverage Ratio'. Handle `None`.
                    *   Render and save SVG to `chart2_svg_path`.
            
                *   **Chart 3: Asset Management Ratios Trend**
                    *   Define SVG path: `chart3_svg_path = os.path.join(graph_output_dir, 'asset_management_ratios_graph.svg')`.
                    *   Define JSON path: `chart3_json_path = os.path.join(data_output_dir, 'asset_management_ratios_data.json')`.
                    *   Create dict: `chart_type` ("line"), **`c_name` ("Asset Management Ratios Trend")**, `financial_years`, `data_series` ('Return on Assets (ROA)', 'Fixed Asset Turnover').
                    *   Write dict to `chart3_json_path`.
                    *   Create `pygal.Line()`, apply styling/layout. Title: "Asset Management Ratios Trend". X-labels: financial years.
                    *   Plot 'Return on Assets (ROA)', 'Fixed Asset Turnover'. Handle `None`.
                    *   Render and save SVG to `chart3_svg_path`.
            
                *   **Chart 4: Profitability Ratios Trend**
                    *   Define SVG path: `chart4_svg_path = os.path.join(graph_output_dir, 'profitability_ratios_graph.svg')`.
                    *   Define JSON path: `chart4_json_path = os.path.join(data_output_dir, 'profitability_ratios_data.json')`.
                    *   Create dict: `chart_type` ("line"), **`c_name` ("Profitability Ratios Trend")**, `financial_years`, `data_series` ('Return on Equity (ROE)', 'Gross Profit Margin').
                    *   Write dict to `chart4_json_path`.
                    *   Create `pygal.Line()`, apply styling/layout. Title: "Profitability Ratios Trend". X-labels: financial years.
                    *   Plot 'Return on Equity (ROE)', 'Gross Profit Margin'. Handle `None`.
                    *   Render and save SVG to `chart4_svg_path`.
            
                *   **Chart 5: Capital Structure Ratios Trend**
                    *   Define SVG path: `chart5_svg_path = os.path.join(graph_output_dir, 'capital_structure_ratios_graph.svg')`.
                    *   Define JSON path: `chart5_json_path = os.path.join(data_output_dir, 'capital_structure_ratios_data.json')`.
                    *   Create dict: `chart_type` ("line"), **`c_name` ("Capital Structure Ratios Trend")**, `financial_years`, `data_series` ('Equity Ratio', 'Debt Ratio').
                    *   Write dict to `chart5_json_path`.
                    *   Create `pygal.Line()`, apply styling/layout. Title: "Capital Structure Ratios Trend". X-labels: financial years.
                    *   Plot 'Equity Ratio', 'Debt Ratio'. Handle `None`.
                    *   Render and save SVG to `chart5_svg_path`.
            
            8.  **Post-Process SVGs to Add Label (Bottom-Left):**
                *   After *all five* charts have been rendered and saved, include additional Python code to modify each SVG file.
                *   Define a Python function (e.g., `add_ai_label_to_svg(svg_filepath)`) that performs the SVG modification.
                *   **Inside this function:**
                    *   Register the default SVG namespace: `ET.register_namespace('', "http://www.w3.org/2000/svg")`.
                    *   Parse the SVG file using `ET.parse()`. Get the XML tree and the root element.
                    *   Create a new `<text>` element using `ET.Element('{{http://www.w3.org/2000/svg}}text')`.
                    *   Set attributes for bottom-left positioning: `x="10"`, `y="98%"`, `font-size="8px"`, `font-weight="bold"`, `fill="#555555"`, `text-anchor="start"`.
                    *   Set text content: "AI Generated Charts".
                    *   Append the new element to the root.
                    *   Write the modified tree back to the *same* `svg_filepath`. Use `tree.write(svg_filepath, encoding='utf-8', xml_declaration=True)`.
                *   **After defining the function**, create a list of the five generated SVG file paths (`chart1_svg_path`, ..., `chart5_svg_path`) and loop through it, calling the `add_ai_label_to_svg` function for each path.
            
            **Output Requirements:**
            
            *   The output MUST be **only** the complete Python script.
            *   The script should first define/calculate data (with ratio formula comments and division-by-zero handling), create the output directories (for graphs and data), define and randomly shuffle the darker colors, create the custom style.
            *   Then, for *each* chart, it should:
                *   Create the specific data dictionary for that chart (including `chart_type`, **`c_name` (the chart's title)**, `financial_years`, and relevant `data_series`).
                *   **Write that chart's data to its own separate JSON file** within the data directory.
                *   Generate the chart using Pygal (applying the specified randomized darker style, wider layout, font sizes, bottom legend, and no-truncation settings).
                *   Save the chart SVG to the graph directory.
            *   The script must *then* include the Python function and the calls to it (as described in Instruction #8) to perform the post-processing step, adding the "AI Generated Charts" text to the **bottom-left** of each saved SVG file by modifying the SVG XML.
            *   Do **not** include any introductory text, explanations, or comments *outside* the Python code itself, except for the requested comments explaining the ratio formulas and calculation notes as specified in Instruction #2.
            *   Do **not** use markdown formatting like ```python ... ``` around the code block.
        """,

            "profit & loss statement": """
            You are the Financial Trend Graph Generator Agent. Your task is to process financial data, calculate key financial metrics and a general CAGR, generate a Python script using Pygal to create line and bar graphs visualizing these trends with specific styling using randomly selected **darker pastel/muted** colors, save the underlying graph data (including chart type and **chart name**) for **each chart to a separate structured JSON file**, and then modify the resulting SVG files to add a label.

            **Input Data Assumptions:**
            
            You will need to structure the script assuming you have access to yearly data (replace placeholder values in the script with actual data when available) for the following, covering both historical and projected/estimated years:
            
            Date should be same format (yyyy-mm-dd).
            
            *   Data required to calculate:
                *   Net Sales (Revenue)
                *   Cost of Goods Sold (for Gross Margin)
                *   Components needed for EBITDA (e.g., Operating Profit, Depreciation, Amortization OR Net Profit, Taxes, Interest, Depreciation, Amortization - *State calculation basis in a comment*)
                *   Net Profit
            
            **Instructions:**
            
            Generate a *single*, complete Python script that performs the following tasks precisely:
            
            1.  **Imports:** Include necessary imports: `import pygal`, `from pygal.style import Style`, `import os`, `import xml.etree.ElementTree as ET`, `import random`, `import json`.
            2.  **Data Storage & Calculation:**
                *   Define a variable for the account name/identifier (e.g., `account_name = 'placeholder_account'`) to be used in file paths.
                *   Store the financial years (including indicators like '(E)', '(P)') in a list.
                *   Store the extracted yearly raw data needed for calculations within the script (e.g., lists for Revenue, COGS, Operating Profit, Depreciation, etc.). Use placeholder values if actual data isn't provided.
                *   Calculate the following metrics for each year and store them in lists:
                    *   Net Sales (usually same as Revenue)
                    *   Gross Margin (Comment: Net Sales - COGS)
                    *   EBITDA (Comment: State calculation method used, e.g., Op Profit + Depr + Amort)
                    *   Net Profit
                *   Calculate Past CAGR (last 3 actual years) and Expected CAGR (next 3 projected years) based on *one* of the primary metrics (e.g., Net Sales or EBITDA - *State which metric is used in a comment*). Store these two CAGR values and the metric name used for calculation. Handle potential errors (e.g., zero/negative starting value).
            3.  **Directory Creation:**
                *   Define the graph output directory path: `graph_output_dir = f'{output_path}/graphs/{sheet_directory}/'`.
                *   Define the data output directory path where **individual JSON files for each graph** will be stored: `data_output_dir = f'{output_path}/graph_data/{sheet_directory}/'`.
                *   Include logic to create both output directories if they don't exist: `os.makedirs(graph_output_dir, exist_ok=True)` and `os.makedirs(data_output_dir, exist_ok=True)`.
            4.  **Data Output (JSON):** *(This section is intentionally minimal - JSON writing happens in Instruction #7)*
                *(Ensure the `data_output_dir` is defined and created as per Instruction #3).*
            5.  **Custom Darker Color Style Definition (Randomized):**
                *   Define the list of **darker, more visible** pastel/muted hex color codes:
                    ```python
                    # Darker / More Saturated Pastel/Muted Palette
                    darker_colors = [
                        "#E57373", "#FFB74D", "#FFF176", "#81C784", "#64B5F6", "#BA68C8",
                        "#4DB6AC", "#FF8A65", "#9575CD", "#4DD0E1", "#A1887F", "#F06292",
                        "#7986CB", "#AED581", "#90A4AE", "#D81B60", "#1E88E5", "#43A047"
                     ]
                    ```
                *   **Shuffle the color list randomly:** Use `random.shuffle(darker_colors)` immediately after defining the list.
                *   Create a custom `Style` object using the *shuffled* list: `custom_darker_style = Style(colors=darker_colors)`.
            6.  **Chart Styling and Layout (Apply to BOTH charts):**
                *   **Apply Custom Style:** Ensure that *both* chart objects (Line and Bar) are initialized using the `custom_darker_style` defined above (e.g., `pygal.Line(style=custom_darker_style, ...)`).
                *   **Maximize Chart Width:** Configure charts for a wider plot area. Set `margin=40`. Explicitly set `width=1000`.
                *   **Prevent Label Truncation:** Configure all charts to *strictly avoid label truncation*. Set `truncate_label=-1` and `truncate_legend=-1`. Set `legend_at_bottom=True` (primarily affects the line chart).
                *   **Label Font Sizes:** Use reasonably small font sizes. Set `label_font_size=10`, `major_label_font_size=10`, and `legend_font_size=10`. Keep `title_font_size=14` or `16`.
                *   Enable tooltips for data points on all charts (`tooltip_border_radius=5`).
            7.  **Chart Generation (Pygal) and Individual JSON Data Output:** Use the `pygal` library to generate and save **two separate charts** and their corresponding data files:
            
                *   **Chart 1: P&L Statement Trend (Line Chart)**
                    *   Define the SVG output path: `chart1_svg_path = os.path.join(graph_output_dir, 'Pl_statement_trend.svg')`.
                    *   Define the JSON output path: `chart1_json_path = os.path.join(data_output_dir, 'pl_statement_trend_data.json')`.
                    *   Define the chart title: `chart1_title = "P&L Statement Trend"`.
                    *   Create a Python dictionary `chart1_data` containing the data for this specific chart. This dictionary must include:
                        *   A key `chart_type` with the value `"line"`.
                        *   A key `c_name` with the value `chart1_title`.
                        *   A key `financial_years` holding the list of financial years calculated in step 2.
                        *   A key `data_series` holding another dictionary. This inner dictionary should map the relevant metric names ('Net Sales', 'Gross Margin', 'EBITDA', 'Net Profit') to their corresponding data lists calculated in step 2.
                    *   Write this `chart1_data` dictionary to the `chart1_json_path` file using `json.dump(chart1_data, f, indent=4)`.
                    *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 5 & 6. Set `stroke=True`.
                    *   Set the title to `chart1_title`.
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the yearly data series for: 'Net Sales', 'Gross Margin', 'EBITDA', 'Net Profit'. Handle `None` values if necessary.
                    *   Render and save the chart to `chart1_svg_path`.
            
                *   **Chart 2: CAGR (Bar Chart)**
                    *   Define the SVG output path: `chart2_svg_path = os.path.join(graph_output_dir, 'cagr.svg')`.
                    *   Define the JSON output path: `chart2_json_path = os.path.join(data_output_dir, 'cagr_data.json')`.
                    *   Retrieve the metric name used for CAGR (`cagr_metric_name`) and the calculated CAGR values (`past_cagr`, `expected_cagr`) from step 2.
                    *   Define the chart title dynamically: `chart2_title = f"CAGR Comparison (Based on {{cagr_metric_name}})"`.
                    *   Create a Python dictionary `chart2_data` containing the data for this specific chart. This dictionary must include:
                        *   A key `chart_type` with the value `"bar"`.
                        *   A key `c_name` with the value `chart2_title`.
                        *   A key `cagr_metric` holding the `cagr_metric_name`.
                        *   A key `categories` holding the list `['Past 3Y Actual', 'Next 3Y Expected']`.
                        *   A key `data_series` holding another dictionary. This inner dictionary should map a series name (e.g., 'CAGR %') to a list containing the two calculated CAGR values (`past_cagr`, `expected_cagr`). Ensure values are suitable for direct plotting (e.g., percentages as numbers like 10.5 for 10.5%).
                    *   Write this `chart2_data` dictionary to the `chart2_json_path` file using `json.dump(chart2_data, f, indent=4)`.
                    *   Create a `pygal.Bar()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 5 & 6.
                    *   Set the title to `chart2_title`.
                    *   Set the X-axis labels to: `['Past 3Y Actual', 'Next 3Y Expected']`.
                    *   Add the single data series (e.g., 'CAGR %') containing the calculated Past CAGR and Expected CAGR values. Handle `None` values if necessary.
                    *   Render and save the chart to `chart2_svg_path`.
            
            8.  **Post-Process SVGs to Add Label (Bottom-Left):**
                *   After *both* charts have been rendered and saved, include additional Python code to modify each SVG file.
                *   Define a Python function (e.g., `add_ai_label_to_svg(svg_filepath)`) that performs the SVG modification.
                *   **Inside this function:**
                    *   Register the default SVG namespace: `ET.register_namespace('', "http://www.w3.org/2000/svg")`.
                    *   Parse the SVG file using `ET.parse()`. Get the XML tree and the root element.
                    *   Create a new `<text>` element using `ET.Element('{{http://www.w3.org/2000/svg}}text')`.
                    *   Set the following attributes for the new `<text>` element to position it at the **bottom-left**:
                        *   `x`: "10"
                        *   `y`: "98%"
                        *   `font-size`: "8px"
                        *   `font-weight`: "bold"
                        *   `fill`: "#555555"
                        *   `text-anchor`: "start"
                    *   Set the text content of the element to: "AI Generated Charts"
                    *   Append this new `<text>` element as a child to the SVG root element.
                    *   Write the modified XML tree back to the *same* `svg_filepath`, overwriting the original. Use `tree.write(svg_filepath, encoding='utf-8', xml_declaration=True)`.
                *   **After defining the function**, create a list of the two generated SVG file paths (`chart1_svg_path`, `chart2_svg_path`) and loop through it, calling the `add_ai_label_to_svg` function for each path.
            
            **Output Requirements:**
            
            *   The output MUST be **only** the complete Python script.
            *   The script should first define/calculate data, create the output directories (for graphs and data), define and randomly shuffle the darker colors, create the custom style.
            *   Then, for *each* chart, it should:
                *   Create the specific data dictionary for that chart (including `chart_type`, **`c_name` (the chart's title)**, and relevant data/labels/series).
                *   **Write that chart's data to its own separate JSON file** within the data directory.
                *   Generate the chart using Pygal (applying the specified randomized darker style, wider layout, font sizes, bottom legend (for line), and no-truncation settings).
                *   Save the chart SVG to the graph directory.
            *   The script must *then* include the Python function and the calls to it (as described in Instruction #8) to perform the post-processing step, adding the "AI Generated Charts" text to the **bottom-left** of each saved SVG file by modifying the SVG XML.
            *   Do **not** include any introductory text, explanations, or comments *outside* the Python code itself, except for the requested comments stating calculation bases (EBITDA, CAGR metric) as specified in Instruction #2.
            *   Do **not** use markdown formatting like ```python ... ``` around the code block.
            """,

            "fund flow": """
                You are the Fund Flow Graph Generator Agent. Your task is to process fund flow statement data and generate a Python script using Pygal to create line graphs, ensuring wide charts, full label visibility, the use of distinct **randomly selected darker pastel/muted** colors for lines, save the underlying graph data (including chart type and **chart name**) for **each chart to a separate structured JSON file**, and then modify the resulting SVG files to add a specific text label at the bottom.

                **Input Data Assumptions:**
                
                You will need to structure the script assuming you have access to yearly data (replace placeholder values in the script with actual data when available) for the following categories, covering both historical and projected/estimated years:
                
                Date should be same format (yyyy-mm-dd).
                
                *   **Source of Funds:**
                    *   A. Subtotal: Net Funds Generated
                    *   Increase in Capital
                    *   Increase in TL/Deb/DPG
                    *   Increase in ST Bank borrowings
                    *   Total Funds Available
                *   **Uses of Funds:**
                    *   Increase in Fixed Assets
                *   **Summary of Fund Flow Statement:**
                    *   LONG TERM SOURCES
                    *   LONG TERM USES
                    *   SURPLUS (+) / SHORTFALL (-) (Long Term - derived: LT Sources - LT Uses)
                    *   SHORT TERM SOURCES
                    *   SHORT TERM USES (*Assumption: You might need to explicitly define or derive this based on the full statement; state your assumption in a comment if necessary.*)
                    *   SURPLUS (+) / SHORTFALL (-) (Short Term - derived: ST Sources - ST Uses)
                
                **Instructions:**
                
                Generate a *single*, complete Python script that performs the following tasks precisely:
                
                1.  **Imports:** Include necessary imports: `import pygal`, `from pygal.style import Style`, `import os`, `import xml.etree.ElementTree as ET`, `import random`, `import json`.
                2.  **Data Storage:** Store the yearly data for all the categories listed above within the script using Python lists or similar structures. Use placeholder values if actual data isn't provided, but structure it correctly for the required years. Include comments showing how derived values (Surplus/Shortfall) are calculated. State any assumption for 'SHORT TERM USES' in a comment if needed. Define a variable for the account name/identifier (e.g., `account_name = 'placeholder_account'`) to be used in file paths. Define the list of financial years (e.g., `financial_years = ['FY20', 'FY21', 'FY22', 'FY23(E)', 'FY24(P)']`).
                3.  **Graph Directory Creation:** Define the graph output directory path: `graph_output_dir = f'{output_path}/graphs/{sheet_directory}/'`. Include logic to create the graph output directory if it doesn't exist: `os.makedirs(graph_output_dir, exist_ok=True)`.
                4.  **Data Directory Creation:**
                    *   Define the path for the data output directory where **individual JSON files for each graph** will be stored: `data_output_dir = f'{output_path}/graph_data/{sheet_directory}/'`.
                    *   Include logic to create this data output directory if it doesn't exist: `os.makedirs(data_output_dir, exist_ok=True)`.
                    *(Note: The actual writing of JSON files will happen within Instruction #7, alongside each chart's generation).*
                5.  **Custom Darker Color Style Definition (Randomized):**
                    *   Define the list of **darker, more visible** pastel/muted hex color codes:
                        ```python
                        # Darker / More Saturated Pastel/Muted Palette
                        darker_colors = [
                            "#E57373", "#FFB74D", "#FFF176", "#81C784", "#64B5F6", "#BA68C8",
                            "#4DB6AC", "#FF8A65", "#9575CD", "#4DD0E1", "#A1887F", "#F06292",
                            "#7986CB", "#AED581", "#90A4AE", "#D81B60", "#1E88E5", "#43A047"
                         ]
                        ```
                    *   **Shuffle the color list randomly:** Use `random.shuffle(darker_colors)` immediately after defining the list.
                    *   Create a custom `Style` object using the *shuffled* list: `custom_darker_style = Style(colors=darker_colors)`.
                6.  **Chart Styling and Layout:**
                    *   **Apply Custom Style:** Ensure that *all* chart objects created in the next step are initialized using the `custom_darker_style` defined above (e.g., `pygal.Line(style=custom_darker_style, ...)`).
                    *   **Maximize Chart Width:** Configure charts to use less surrounding margin. Set `margin=40`. Explicitly set `width=1000` (or another suitable large value).
                    *   **Prevent Label Truncation:** Configure all charts to *strictly avoid label truncation* by setting `truncate_label=-1` and `truncate_legend=-1`. Set `legend_at_bottom=True`.
                    *   **Label Font Sizes:** Use reasonably small font sizes. Set `label_font_size=10`, `major_label_font_size=10`, and `legend_font_size=10`. Keep `title_font_size=14` or `16`.
                    *   Enable tooltips for data points on all charts (`tooltip_border_radius=5`).
                7.  **Chart Generation (Pygal) and Individual JSON Data Output:** Use the `pygal` library to generate and save **three separate line charts** and their corresponding data files:
                
                    *   **Chart 1: Source of Funds Trend**
                        *   Define the SVG output path: `chart1_svg_path = os.path.join(graph_output_dir, 'source_of_funds_trend.svg')`.
                        *   Define the JSON output path: `chart1_json_path = os.path.join(data_output_dir, 'source_of_funds_trend_data.json')`.
                        *   Define the chart title: `chart1_title = "Source of Funds Trend"`.
                        *   Create a Python dictionary `chart1_data` containing the data for this specific chart. This dictionary must include:
                            *   A key `chart_type` with the value `"line"`.
                            *   A key `c_name` with the value `chart1_title`.
                            *   A key `financial_years` holding the list of financial years.
                            *   A key `data_series` holding another dictionary. This inner dictionary should map the relevant series names for this chart (e.g., "Net Funds Generated", "Increase in Capital", "Increase in TL/Deb/DPG", "Increase in ST Bank borrowings", "Total Funds Available") to their corresponding data lists.
                        *   Write this `chart1_data` dictionary to the `chart1_json_path` file using `json.dump(chart1_data, f, indent=4)`.
                        *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 5 & 6.
                        *   Set the title to `chart1_title`.
                        *   Set the X-axis labels using the `financial_years` list.
                        *   Plot the relevant data series (as listed under "Source of Funds"). Handle `None` values if necessary.
                        *   Render and save the chart to `chart1_svg_path`.
                
                    *   **Chart 2: Uses of Funds Trend**
                        *   Define the SVG output path: `chart2_svg_path = os.path.join(graph_output_dir, 'uses_of_funds_trend.svg')`.
                        *   Define the JSON output path: `chart2_json_path = os.path.join(data_output_dir, 'uses_of_funds_trend_data.json')`.
                        *   Define the chart title: `chart2_title = "Uses of Funds Trend"`.
                        *   Create a Python dictionary `chart2_data` containing the data for this specific chart. This dictionary must include:
                            *   A key `chart_type` with the value `"line"`.
                            *   A key `c_name` with the value `chart2_title`.
                            *   A key `financial_years` holding the list of financial years.
                            *   A key `data_series` holding another dictionary mapping the relevant series names for this chart (e.g., "Increase in Fixed Assets") to their corresponding data lists.
                        *   Write this `chart2_data` dictionary to the `chart2_json_path` file using `json.dump(chart2_data, f, indent=4)`.
                        *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings.
                        *   Set the title to `chart2_title`.
                        *   Set the X-axis labels using the `financial_years` list.
                        *   Plot the relevant data series (as listed under "Uses of Funds"). Handle `None` values if necessary.
                        *   Render and save the chart to `chart2_svg_path`.
                
                    *   **Chart 3: Fund Flow Summary Trend**
                        *   Define the SVG output path: `chart3_svg_path = os.path.join(graph_output_dir, 'fund_flow_summary_trend.svg')`.
                        *   Define the JSON output path: `chart3_json_path = os.path.join(data_output_dir, 'fund_flow_summary_trend_data.json')`.
                        *   Define the chart title: `chart3_title = "Fund Flow Summary Trend"`.
                        *   Create a Python dictionary `chart3_data` containing the data for this specific chart. This dictionary must include:
                            *   A key `chart_type` with the value `"line"`.
                            *   A key `c_name` with the value `chart3_title`.
                            *   A key `financial_years` holding the list of financial years.
                            *   A key `data_series` holding another dictionary mapping the relevant series names for this chart (e.g., "LONG TERM SOURCES", "LONG TERM USES", "SURPLUS (+) / SHORTFALL (-) (Long Term)", "SHORT TERM SOURCES", "SHORT TERM USES", "SURPLUS (+) / SHORTFALL (-) (Short Term)") to their corresponding data lists.
                        *   Write this `chart3_data` dictionary to the `chart3_json_path` file using `json.dump(chart3_data, f, indent=4)`.
                        *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings.
                        *   Set the title to `chart3_title`.
                        *   Set the X-axis labels using the `financial_years` list.
                        *   Plot the relevant data series (as listed under "Summary of Fund Flow Statement"). Handle `None` values if necessary.
                        *   Render and save the chart to `chart3_svg_path`.
                
                8.  **Post-Process SVGs to Add Label (Bottom-Right):**
                    *   After all three charts have been rendered and saved, include additional Python code to modify each SVG file.
                    *   Define a Python function (e.g., `add_ai_label_to_svg(svg_filepath)`) that performs the SVG modification.
                    *   **Inside this function:**
                        *   Register the default SVG namespace: `ET.register_namespace('', "http://www.w3.org/2000/svg")`.
                        *   Parse the SVG file using `ET.parse()`. Get the XML tree and the root element.
                        *   Create a new `<text>` element using `ET.Element('{{http://www.w3.org/2000/svg}}text')`.
                        *   Set the following attributes for the new `<text>` element to position it at the **bottom-right**:
                            *   `x`: "99%"
                            *   `y`: "98%"
                            *   `font-size`: "9px"
                            *   `font-weight`: "bold"
                            *   `fill`: "#555555"
                            *   `text-anchor`: "end"
                        *   Set the text content of the element to: "**AI Generated Charts**"
                        *   Append this new `<text>` element as a child to the SVG root element.
                        *   Write the modified XML tree back to the *same* `svg_filepath`, overwriting the original. Use `tree.write(svg_filepath, encoding='utf-8', xml_declaration=True)`.
                    *   **After defining the function**, create a list of the three generated SVG file paths (`chart1_svg_path`, `chart2_svg_path`, `chart3_svg_path`) and loop through it, calling the `add_ai_label_to_svg` function for each path.
                
                **Output Requirements:**
                
                *   The output MUST be **only** the complete Python script.
                *   The script should first define data, create the output directories (for graphs and data), define and randomly shuffle the darker colors, create the custom style.
                *   Then, for *each* chart, it should:
                    *   Create the specific data dictionary for that chart (including `chart_type`, **`c_name` (the chart's title)**, `financial_years`, and `data_series`).
                    *   **Write that chart's data to its own separate JSON file** within the data directory.
                    *   Generate the chart using Pygal (applying the specified randomized darker style, wider layout, font sizes, bottom legend, and no-truncation settings).
                    *   Save the chart SVG to the graph directory.
                *   The script must *then* include the Python function and the calls to it (as described in Instruction #8) to perform the post-processing step, adding the "**AI Generated Charts**" text to the bottom-right of each saved SVG file by modifying the SVG XML.
                *   Do **not** include any introductory text, explanations, or comments *outside* the Python code itself, except for explicitly stating assumptions or derivations for data points (like 'SHORT TERM USES' or SURPLUS/SHORTFALL calculations) as requested in Instruction #2.
                *   Do **not** use markdown formatting like ```python ... ``` around the code block.
            """
        }

    def get_sheet_specific_prompt(self, sheet_name: str, state: dict, account) -> str:
        """
        Generates a specific prompt based on the sheet type.

        Args:
            sheet_name (str): The name of the sheet.
            state (dict): A dictionary containing the current state of the analysis.

        Returns:
            str: The generated prompt.
        """
        self.logger.info(f"Generating graph prompt for sheet: {sheet_name}")
        prompt_template = self.prompts.get(sheet_name.lower(), None)
        if prompt_template is None:
            return None
        # prompt = prompt_template.format(account = account)
        # if sheet_name.lower() in self.prompts:
        prompt = prompt_template

        # self.logger.debug(f"Using prompt: {prompt}")
        return prompt