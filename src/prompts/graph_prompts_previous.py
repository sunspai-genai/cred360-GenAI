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
            "profit & loss statement": """
                You are the Financial Trend Graph Generator Agent. Your task is to process financial data, calculate key financial metrics and a general CAGR, generate a Python script using Pygal to create line and bar graphs visualizing these trends with specific styling using randomly selected **darker pastel/muted** colors, and then modify the resulting SVG files to add a label.

                **Input Data Assumptions:**
            
                You will need to structure the script assuming you have access to yearly data (replace placeholder values in the script with actual data when available) for the following, covering both historical and projected/estimated years:
            
                *   Data required to calculate:
                    *   Net Sales (Revenue)
                    *   Cost of Goods Sold (for Gross Margin)
                    *   Components needed for EBITDA (e.g., Operating Profit, Depreciation, Amortization OR Net Profit, Taxes, Interest, Depreciation, Amortization - *State calculation basis in a comment*)
                    *   Net Profit
            
                **Instructions:**
            
                Generate a *single*, complete Python script that performs the following tasks precisely:
            
                1.  **Imports:** Include necessary imports: `import pygal`, `from pygal.style import Style`, `import os`, `import xml.etree.ElementTree as ET`, `import random`.
                2.  **Data Storage & Calculation:**
                    *   Store the extracted yearly data needed for calculations within the script. Use placeholder values if actual data isn't provided.
                    *   Calculate the following metrics for each year and store them in lists:
                        *   Net Sales
                        *   Gross Margin (Comment: Net Sales - COGS)
                        *   EBITDA (Comment: State calculation method used, e.g., Op Profit + Depr + Amort)
                        *   Net Profit
                    *   Calculate Past CAGR (last 3 actual years) and Expected CAGR (next 3 projected years) based on *one* of the primary metrics (e.g., Net Sales or EBITDA - *State which metric is used in a comment*). Store these two CAGR values.
                3.  **Directory Creation:** Include logic to create the output directory if it doesn't exist: `os.makedirs('{output_path}/graphs/{sheet_directory}/', exist_ok=True)`.
                4.  **Custom Darker Color Style Definition (Randomized):**
                    *   Define the list of **darker, more visible** pastel/muted hex color codes:
                        ```python
                        # Darker / More Saturated Pastel/Muted Palette
                        darker_colors = [
                            "#E57373",  # Salmon Pink / Light Red
                            "#FFB74D",  # Orange / Peach
                            "#FFF176",  # Medium Yellow
                            "#81C784",  # Medium Green
                            "#64B5F6",  # Medium Blue
                            "#BA68C8",  # Lavender / Light Purple
                            "#4DB6AC",  # Teal / Aqua Green
                            "#FF8A65",  # Coral / Light Orange
                            "#9575CD",  # Deep Lavender / Medium Purple
                            "#4DD0E1",  # Bright Cyan / Turquoise
                            "#A1887F",  # Muted Brown / Taupe
                            "#F06292",  # Bright Pink / Magenta
                            "#7986CB",  # Indigo / Slate Blue
                            "#AED581",  # Lime / Light Olive Green
                            "#90A4AE",  # Blue Grey / Steel Blue
                            "#D81B60",  # Strong Pink (Use sparingly if needed)
                            "#1E88E5",  # Strong Blue (Use sparingly if needed)
                            "#43A047"   # Strong Green (Use sparingly if needed)
                        ]
                        ```
                    *   **Shuffle the color list randomly:** Use `random.shuffle(darker_colors)` immediately after defining the list.
                    *   Create a custom `Style` object using the *shuffled* list: `custom_darker_style = Style(colors=darker_colors)`.
                5.  **Chart Styling and Layout (Apply to BOTH charts):**
                    *   **Apply Custom Style:** Ensure that *both* chart objects (Line and Bar) are initialized using the `custom_darker_style` defined above (e.g., `pygal.Line(style=custom_darker_style, ...)`).
                    *   **Maximize Chart Width:** Configure charts for a wider plot area. Set `margin=40`. Explicitly set `width=1000`.
                    *   **Prevent Label Truncation:** Configure all charts to *strictly avoid label truncation*. Set `truncate_label=-1` and `truncate_legend=-1`. Set `legend_at_bottom=True` (primarily affects the line chart).
                    *   **Label Font Sizes:** Use reasonably small font sizes. Set `label_font_size=10`, `major_label_font_size=10`, and `legend_font_size=10`. Keep `title_font_size=14` or `16`.
                    *   Enable tooltips for data points on all charts (`tooltip_border_radius=5`).
                6.  **Chart Generation (Pygal):** Use the `pygal` library to generate and save **two separate charts**:
            
                    *   **Chart 1: P&L Statement Trend (Line Chart)**
                        *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 4 & 5. Set `stroke=True`.
                        *   Set the title to "P&L Statement Trend".
                        *   Set the X-axis labels to the list of financial years (including indicators like '(E)', '(P)').
                        *   Plot the yearly data series for: 'Net Sales', 'Gross Margin', 'EBITDA', 'Net Profit'.
                        *   Render and save the chart as `{output_path}/graphs/{sheet_directory}/Pl_statement_trend.svg`.
            
                    *   **Chart 2: CAGR (Bar Chart)**
                        *   Create a `pygal.Bar()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 4 & 5.
                        *   Set the title to "CAGR Comparison".
                        *   Set the X-axis labels to: `['Past 3Y Actual', 'Next 3Y Expected']`.
                        *   Add a single data series named 'CAGR %' (or similar) containing the calculated Past CAGR and Expected CAGR values (multiplied by 100 if representing percentage directly). Format tooltips if needed to show '%'.
                        *   Render and save the chart as `{output_path}/graphs/{sheet_directory}/cagr.svg`.
            
                7.  **Post-Process SVGs to Add Label (Bottom-Left):**
                    *   After *both* charts have been rendered and saved, include additional Python code to modify each SVG file.
                    *   Define a Python function (e.g., `add_ai_label_to_svg(svg_filepath)`) that performs the SVG modification.
                    *   **Inside this function:**
                        *   Register the default SVG namespace: `ET.register_namespace('', "http://www.w3.org/2000/svg")`.
                        *   Parse the SVG file using `ET.parse()`. Get the XML tree and the root element.
                        *   Create a new `<text>` element using `ET.Element('{{http://www.w3.org/2000/svg}}' text)`.
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
                    *   **After defining the function**, call this function for *each* of the two generated SVG file paths:
                        *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/Pl_statement_trend.svg')`
                        *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/cagr.svg')`
            
                **Output Requirements:**
            
                *   The output MUST be **only** the complete Python script.
                *   The script should first define/calculate data, create the output directory, define and **randomly shuffle** the **darker** colors, create the custom style, generate the two charts using Pygal (applying the specified randomized darker style, wider layout, font sizes, bottom legend, and no-truncation settings), and save them.
                *   The script must *then* include the Python function and the calls to it (as described in Instruction #7) to perform the post-processing step, adding the "AI Generated Charts" text to the **bottom-left** of each saved SVG file by modifying the SVG XML.
                *   Do **not** include any introductory text, explanations, or comments *outside* the Python code itself, except for the requested comments stating calculation bases (EBITDA, CAGR metric) as specified in Instruction #2.
                *   Do **not** use markdown formatting like ```python ... ``` around the code block.
            """,

            "balance sheet": """
            You are the Graph Data Generator Agent. Your task is to process financial data, calculate key financial ratios, generate a Python script using Pygal to create line graphs visualizing these ratio trends with specific styling using randomly selected **darker pastel/muted** colors, and then modify the resulting SVG files to add a label.
            
            **Input Data Assumptions:**
            
            You will need to structure the script assuming you have access to yearly data (replace placeholder values in the script with actual data when available) for the following, covering both historical and projected/estimated years.
            
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
            
            1.  **Imports:** Include necessary imports: `import pygal`, `from pygal.style import Style`, `import os`, `import xml.etree.ElementTree as ET`, `import random`.
            2.  **Data Storage & Calculation:**
                *   Store the extracted yearly data needed for calculations within the script. Use placeholder values if actual data isn't provided.
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
            3.  **Directory Creation:** Include logic to create the output directory if it doesn't exist: `os.makedirs('{output_path}/graphs/{sheet_directory}/', exist_ok=True)`.
            4.  **Custom Darker Color Style Definition (Randomized):**
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
            5.  **Chart Styling and Layout (Apply to ALL charts):**
                *   **Apply Custom Style:** Ensure that *all* chart objects created in the next step are initialized using the `custom_darker_style` defined above (e.g., `pygal.Line(style=custom_darker_style, ...)`).
                *   **Maximize Chart Width:** Configure charts for a wider plot area. Set `margin=40`. Explicitly set `width=1000`.
                *   **Prevent Label Truncation:** Configure all charts to *strictly avoid label truncation*. Set `truncate_label=-1` and `truncate_legend=-1`. Set `legend_at_bottom=True`.
                *   **Label Font Sizes:** Use reasonably small font sizes. Set `label_font_size=10`, `major_label_font_size=10`, and `legend_font_size=10`. Keep `title_font_size=14` or `16`.
                *   Enable tooltips for data points on all charts (`tooltip_border_radius=5`).
            6.  **Chart Generation (Pygal):** Use the `pygal` library to generate and save **five separate line charts**, one for each ratio category:
            
                *   **Chart 1: Liquidity Ratios Trend**
                    *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 4 & 5.
                    *   Set the title to "Liquidity Ratios Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the yearly data series for: 'Current Ratio', 'Quick Ratio'.
                    *   Render and save as `{output_path}/graphs/{sheet_directory}/liquidity_ratios_graph.svg`.
            
                *   **Chart 2: Solvency Ratios Trend**
                    *   Create a `pygal.Line()` chart object, applying the styling/layout from steps 4 & 5.
                    *   Set the title to "Solvency Ratios Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the yearly data series for: 'Debt-to-Equity Ratio', 'Interest Coverage Ratio'.
                    *   Render and save as `{output_path}/graphs/{sheet_directory}/solvency_ratios_graph.svg`.
            
                *   **Chart 3: Asset Management Ratios Trend**
                    *   Create a `pygal.Line()` chart object, applying the styling/layout from steps 4 & 5.
                    *   Set the title to "Asset Management Ratios Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the yearly data series for: 'Return on Assets (ROA)', 'Fixed Asset Turnover'.
                    *   Render and save as `{output_path}/graphs/{sheet_directory}/asset_management_ratios_graph.svg`.
            
                *   **Chart 4: Profitability Ratios Trend**
                    *   Create a `pygal.Line()` chart object, applying the styling/layout from steps 4 & 5.
                    *   Set the title to "Profitability Ratios Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the yearly data series for: 'Return on Equity (ROE)', 'Gross Profit Margin'.
                    *   Render and save as `{output_path}/graphs/{sheet_directory}/profitability_ratios_graph.svg`.
            
                *   **Chart 5: Capital Structure Ratios Trend**
                    *   Create a `pygal.Line()` chart object, applying the styling/layout from steps 4 & 5.
                    *   Set the title to "Capital Structure Ratios Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the yearly data series for: 'Equity Ratio', 'Debt Ratio'.
                    *   Render and save as `{output_path}/graphs/{sheet_directory}/capital_structure_ratios_graph.svg`.
            
            7.  **Post-Process SVGs to Add Label (Bottom-Left):**
                *   After *all five* charts have been rendered and saved, include additional Python code to modify each SVG file.
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
                *   **After defining the function**, call this function for *each* of the five generated SVG file paths:
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/liquidity_ratios_graph.svg')`
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/solvency_ratios_graph.svg')`
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/asset_management_ratios_graph.svg')`
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/profitability_ratios_graph.svg')`
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/capital_structure_ratios_graph.svg')`
            
            **Output Requirements:**
            
            *   The output MUST be **only** the complete Python script.
            *   The script should first define/calculate data (with ratio formula comments), create the output directory, define and **randomly shuffle** the **darker** colors, create the custom style, generate the five charts using Pygal (applying the specified randomized darker style, wider layout, font sizes, bottom legend, and no-truncation settings), and save them.
            *   The script must *then* include the Python function and the calls to it (as described in Instruction #7) to perform the post-processing step, adding the "AI Generated Charts" text to the **bottom-left** of each saved SVG file by modifying the SVG XML.
            *   Do **not** include any introductory text, explanations, or comments *outside* the Python code itself, except for the requested comments explaining the ratio formulas as specified in Instruction #2.
            *   Do **not** use markdown formatting like ```python ... ``` around the code block. 
            """,

            "fund flow": """
                You are the Fund Flow Graph Generator Agent. Your task is to process fund flow statement data and generate a Python script using Pygal to create line graphs, ensuring wide charts, full label visibility, the use of distinct **randomly selected darker pastel/muted** colors for lines, and then modify the resulting SVG files to add a specific text label at the bottom.

            **Input Data Assumptions:**
            
            You will need to structure the script assuming you have access to yearly data (replace placeholder values in the script with actual data when available) for the following categories, covering both historical and projected/estimated years:
            
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
            
            1.  **Imports:** Include necessary imports: `import pygal`, `from pygal.style import Style`, `import os`, `import xml.etree.ElementTree as ET`, `import random`. *(Added random)*
            2.  **Data Storage:** Store the yearly data for all the categories listed above within the script using Python lists or similar structures. Use placeholder values if actual data isn't provided, but structure it correctly for the required years. Include comments showing how derived values (Surplus/Shortfall) are calculated. State any assumption for 'SHORT TERM USES' in a comment if needed.
            3.  **Directory Creation:** Include logic to create the output directory if it doesn't exist: `os.makedirs('{output_path}/graphs/{sheet_directory}/', exist_ok=True)`.
            4.  **Custom Darker Color Style Definition (Randomized):**
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
                *   Create a custom `Style` object using the *shuffled* list: `custom_darker_style = Style(colors=darker_colors)`. *(Updated style creation)*
            5.  **Chart Styling and Layout:**
                *   **Apply Custom Style:** Ensure that *all* chart objects created in the next step are initialized using the `custom_darker_style` defined above (e.g., `pygal.Line(style=custom_darker_style, ...)`). *(Updated style usage)*
                *   **Maximize Chart Width:** Configure charts to use less surrounding margin. Set `margin=40`. Explicitly set `width=1000` (or another suitable large value).
                *   **Prevent Label Truncation:** Configure all charts to *strictly avoid label truncation* by setting `truncate_label=-1` and `truncate_legend=-1`. Set `legend_at_bottom=True`.
                *   **Label Font Sizes:** Use reasonably small font sizes. Set `label_font_size=10`, `major_label_font_size=10`, and `legend_font_size=10`. Keep `title_font_size=14` or `16`.
                *   Enable tooltips for data points on all charts (`tooltip_border_radius=5`).
            6.  **Chart Generation (Pygal):** Use the `pygal` library to generate and save **three separate line charts**:
            
                *   **Chart 1: Source of Funds Trend**
                    *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 4 & 5.
                    *   Set the title to "Source of Funds Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the data series (as listed in Input Data Assumptions).
                    *   Render and save the chart as `{output_path}/graphs/{sheet_directory}/source_of_funds_trend.svg`.
            
                *   **Chart 2: Uses of Funds Trend**
                    *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 4 & 5.
                    *   Set the title to "Uses of Funds Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the data series (as listed in Input Data Assumptions).
                    *   Render and save the chart as `{output_path}/graphs/{sheet_directory}/uses_of_funds_trend.svg`.
            
                *   **Chart 3: Fund Flow Summary Trend**
                    *   Create a `pygal.Line()` chart object, applying the `custom_darker_style` and other styling/layout settings defined in steps 4 & 5.
                    *   Set the title to "Fund Flow Summary Trend".
                    *   Set the X-axis labels to the list of financial years.
                    *   Plot the data series (as listed in Input Data Assumptions).
                    *   Render and save the chart as `{output_path}/graphs/{sheet_directory}/fund_flow_summary_trend.svg`.
            
            7.  **Post-Process SVGs to Add Label (Bottom-Left):**
                *   After all three charts have been rendered and saved, include additional Python code to modify each SVG file.
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
                *   **After defining the function**, call this function for each of the three generated SVG file paths:
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/source_of_funds_trend.svg')`
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/uses_of_funds_trend.svg')`
                    *   `add_ai_label_to_svg('{output_path}/graphs/{sheet_directory}/fund_flow_summary_trend.svg')`
            
            **Output Requirements:**
            
            *   The output MUST be **only** the complete Python script.
            *   The script should first define data, create the output directory, define and **randomly shuffle** the **darker** colors, create the custom style, generate the three charts using Pygal (applying the specified randomized darker style, wider layout, font sizes, bottom legend, and no-truncation settings), and save them. *(Updated output requirements)*
            *   The script must *then* include the Python function and the calls to it (as described in Instruction #7) to perform the post-processing step, adding the "AI Generated Charts" text to the **bottom-left** of each saved SVG file by modifying the SVG XML.
            *   Do **not** include any introductory text, explanations, or comments *outside* the Python code itself, except for explicitly stating assumptions or derivations for data points (like 'SHORT TERM USES' or SURPLUS/SHORTFALL calculations) as requested in Instruction #2.
            *   Do **not** use markdown formatting like ```python ... ``` around the code block.
        """
        }


    def get_sheet_specific_prompt(self, sheet_name: str, state: dict,account) -> str:
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