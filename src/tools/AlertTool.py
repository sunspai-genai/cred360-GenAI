import pandas as pd

attribute_rules = {
    "current ratio": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x < 1.0,
            "Medium": lambda x: 1.0 <= x < 1.2,
            "Low": lambda x: 1.2 <= x <= 1.33
        }
    },
    "net sales": {
        "type": "Dev",
        "thresholds": {
            "High": lambda x: x > 20,
            "Medium": lambda x: 15 <= x <= 20,
            "Low": lambda x: 10 <= x < 15
        }
    },
    "net cash accrual to net sales": {
        "type": "Dev",
        "thresholds": {
            "High": lambda x: x > 0.20,
            "Medium": lambda x: 0.10 < x <= 0.20,
            "Low": lambda x: 0.05 < x <= 0.10
        }
    },
    "net sales to total assets ratio": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x < 0.70,
            "Medium": lambda x: 0.70 < x <= 0.90,
            "Low": lambda x: 0.90 < x <= 1.00
        }
    },
    "roe %": {
        "type": "P",
        "thresholds": {
            "High": lambda x: x < 5,
            "Medium": lambda x: 5 <= x < 7,
            "Low": lambda x: 7 <= x <= 8
        }
    },
    "roce %": {
        "type": "P",
        "thresholds": {
            "High": lambda x: x < 12,
            "Medium": lambda x: 12 <= x < 14,
            "Low": lambda x: 10 <= x <= 14
        }
    },
    "ronw %": {
        "type": "P",
        "thresholds": {
            "High": lambda x: x < 10,
            "Medium": lambda x: 10 <= x < 14,
            "Low": lambda x: 14 <= x <= 15
        }
    },
    "quick ratio": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x < 1.0,
            "Medium": lambda x: 1.0 <= x < 1.25,
            "Low": lambda x: 1.25 <= x <= 1.33
        }
    },
    "debt to equity ratio": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x > 3.0,
            "Medium": lambda x: 2.0 <= x <= 2.5,
            "Low": lambda x: 1.5 <= x < 2.0
        }
    },
    "tol/tnw ratio": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x > 4.0,
            "Medium": lambda x: 2.50 <= x <= 3.00,
            "Low": lambda x: 1.50 <= x < 2.50
        }
    },
    "debt service coverage ratio (dscr)": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x < 1.0,
            "Medium": lambda x: 1.0 <= x <= 1.25,
            "Low": lambda x: 1.25 <= x < 1.5
        }
    },
    "adjusted tnw": {
        "type": "Dev",
        "thresholds": {
            "High": lambda x: x > 10,
            "Medium": lambda x: 10 <= x <= 7,
            "Low": lambda x: 7 <= x <= 5
        }
    },
    "interest coverage ratio (icr)": {
        "type": "Dev",
        "thresholds": {
            "High": lambda x: x < 1.5,
            "Medium": lambda x: 1.5 <= x <= 1.75,
            "Low": lambda x: 1.75 <= x <= 2.0
        }
    },
    "total debt to ebitda": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x > 2.0,
            "Medium": lambda x: 2.0 <= x <= 3.0,
            "Low": lambda x: 3.0 <= x <= 4.0
        }
    },
    "unhedged foreign currency exposure": {
        "type": "Dev",
        "thresholds": {
            "High": lambda x: x > 30,
            "Medium": lambda x: 20 <= x <= 30,
            "Low": lambda x: 10 <= x <= 20
        }
    },
    "net profit margin": {
        "type": "Dev",
        "thresholds": {
            "High": lambda x: x > 20,
            "Medium": lambda x: 10 <= x <= 20,
            "Low": lambda x: 5 <= x <= 10
        }
    },
    "fixed assets coverage ratio (facr)": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x < 1.5,
            "Medium": lambda x: 1.5 <= x <= 1.75,
            "Low": lambda x: 1.75 < x <= 2.0
        }
    },
    "assets coverage ratio (acr)": {
        "type": "R",
        "thresholds": {
            "High": lambda x: x < 1.5,
            "Medium": lambda x: 1.5 <= x <= 2.0,
            "Low": lambda x: 2.0 < x <= 2.5
        }
    }
}

# def classify_financial_attributes(df):
#     def classify(attribute, val):
#         attr = str(attribute).lower().strip()
#         if attr == "current ratio":
#             if val < 1.0:
#                 return "High"
#             elif 1.0 <= val <= 1.20:
#                 return "Medium"
#             elif 1.20 < val <= 1.33:
#                 return "Low"
#         elif attr == "debt to equity ratio":
#             if val > 3.0:
#                 return "High"
#             elif 2.00 <= val <= 2.50:
#                 return "Medium"
#             elif 1.50 <= val < 2.00:
#                 return "Low"
#         elif attr == "tol/tnw ratio":
#             if val > 4.0:
#                 return "High"
#             elif 2.50 <= val <= 3.00:
#                 return "Medium"
#             elif 1.50 <= val < 2.50:
#                 return "Low"
#         elif attr == "quick ratio":
#             if val < 1.0:
#                 return "High"
#             elif 1.0 <= val <= 1.25:
#                 return "Medium"
#             elif 1.25 < val <= 1.33:
#                 return "Low"
#         elif attr == "debt service coverage ratio (dscr)":
#             if val < 1.0:
#                 return "High"
#             elif 1.0 <= val <= 1.25:
#                 return "Medium"
#             elif 1.25 < val <= 1.5:
#                 return "Low"
#         elif attr == "adjusted tnw":
#             if val < -10:
#                 return "High"
#             elif -10 <= val <= -7:
#                 return "Medium"
#             elif -7 < val <= -5:
#                 return "Low"
#         elif attr == "interest coverage ratio (icr)":
#             if val < 1.5:
#                 return "High"
#             elif 1.5 <= val <= 1.75:
#                 return "Medium"
#             elif 1.75 < val <= 2.0:
#                 return "Low"
#         elif attr == "net sales":
#             if val > 20:
#                 return "High"
#             elif 15 <= val <= 20:
#                 return "Medium"
#             elif 10 <= val < 15:
#                 return "Low"
#         elif attr == "net sales to total assets ratio":
#             if val < 0.70:
#                 return "High"
#             elif 0.70 <= val <= 0.90:
#                 return "Medium"
#             elif 0.90 < val <= 1.00:
#                 return "Low"
#         elif attr == "total debt to ebidta":
#             if val > 2.0:
#                 return "High"
#             elif 2.0 <= val <= 3.0:
#                 return "Medium"
#             elif 3.0 < val <= 4.0:
#                 return "Low"
#         elif attr == "unhedged foreign currency exposure":
#             if val > 30:
#                 return "High"
#             elif 20 <= val <= 30:
#                 return "Medium"
#             elif 10 <= val < 20:
#                 return "Low"
#         elif attr == "roe %":
#             if val < 5:
#                 return "High"
#             elif 5 <= val <= 7:
#                 return "Medium"
#             elif 7 < val <= 8:
#                 return "Low"
#         elif attr == "roce %":
#             if val < 12:
#                 return "High"
#             elif 12 <= val <= 14:
#                 return "Medium"
#             elif 14 < val <= 15:
#                 return "Low"
#         elif attr == "ronw %":
#             if val < 10:
#                 return "High"
#             elif 10 <= val <= 14:
#                 return "Medium"
#             elif 14 < val <= 15:
#                 return "Low"
#         elif attr == "net cash accrual to net sales":
#             if val > 20 or val < 12:
#                 return "High"
#             elif 12 <= val <= 14 or 10 <= val <= 20:
#                 return "Medium"
#             elif 14 < val <= 15 or 5 <= val < 10:
#                 return "Low"
#         elif attr == "net profit margin":
#             if val > 20:
#                 return "High"
#             elif 10 <= val <= 20:
#                 return "Medium"
#             elif 5 <= val < 10:
#                 return "Low"
#         elif attr == "fixed assets coverage ratio (facr)":
#             if val < 1.5:
#                 return "High"
#             elif 1.5 <= val <= 1.75:
#                 return "Medium"
#             elif 1.75 < val <= 2.0:
#                 return "Low"
#         elif attr == "assets coverage ratio (acr)":
#             if val < 1.5:
#                 return "High"
#             elif 1.5 <= val <= 2.0:
#                 return "Medium"
#             elif 2.0 < val <= 2.5:
#                 return "Low"
#         # return ""
#
#     # Create a new DataFrame with category results
#     result = pd.DataFrame()
#     result["Attribute"] = df.columns
#     result["Value"] = [df[col].iloc[0] for col in df.columns]
#     # print(result)
#     result["Alert Type"] = result.apply(lambda row: classify(row["Attribute"], row["Value"]), axis=1)
#     return result
def classify_financial_attributes(df,year):
    def evaluate_attribute(attribute: str, value: float) -> str:
        rule = attribute_rules.get(attribute)
        if not rule:
            return f"No rating rule defined for {attribute}"

        attr_type = rule['type']
        thresholds = rule['thresholds']

        for rating, condition in thresholds.items():
            if condition(value):
                value = round(value,2)
                if attr_type == "R":
                    return f"{rating} Alert: {attribute} is {value} in last audited {year}."
                elif attr_type == "Dev":
                    return f"{rating} Alert: Deviation in {attribute} is {value}% in last audited {year}."
                elif attr_type == "P":
                    return f"{rating} Alert: {attribute} is {value}% in last audited {year}."
        return f"Unclassified Alert: {attribute} with value {round(value,2)} does not match any defined range."

    result = pd.DataFrame()
    result["Attribute"] = df.columns
    result["Value"] = [df[col].iloc[0] for col in df.columns]
    # print(result)
    result["Alert Message"] = result.apply(lambda row: evaluate_attribute(str(row["Attribute"]).lower().strip(),
                                                                          row["Value"]), axis=1)
    return result

def create_alerts_data(data):
    desired_attributes = [
        "Current Ratio",
        "Debt to Equity Ratio",
        "TOL/TNW Ratio",
        "Debt Service Coverage Ratio (DSCR)",
        "Adjusted TNW",
        "Net Sales",
        "Total Debt to EBITDA",
        "ROE %"
    ]

    # Map the desired attribute names to the actual keys in the input dictionary
    # This handles variations in naming, spacing, and symbols.
    key_mapping = {
        "Current Ratio": "Current Ratio",
        "Debt to Equity Ratio": "Debt/Equity Ratio",
        "TOL/TNW Ratio": "TOL/TNW Ratio",
        "Debt Service Coverage Ratio (DSCR)": "DSCR",
        # Assuming this is the intended DSCR
        "Adjusted TNW": "Adjusted TNW",
        "Net Sales": "Net Sales",
        "Total Debt to EBITDA": "Debt/EBIDTA %",  # Assuming this is the intended metric
        "ROE %": "Return on Equity %",
    }

    alert_kpi_data = {}

    for desired_name in desired_attributes:
        # Find the corresponding key in the input data using the mapping
        input_key = key_mapping.get(desired_name)

        # Initialize value to None
        extracted_value = None

        # If a mapping exists and the key is in the input data
        if input_key and input_key in data:
            value_list = data[input_key]
            if value_list:
                extracted_value = value_list[0]

        alert_kpi_data[desired_name] = [extracted_value]
    inventory = (data["a) R.M. Imported"][0] + data["b) R.M. Indigenous"][0]+
                 data["c) Stock in Process"][0] + data["d) Finished Goods"][0] + data["e) Other Consumables"][0])/100
    alert_kpi_data["Quick Ratio"] = [(data["Current Assets"][0] - inventory) / data["Current Liabilities"][0]]

    # total_revenue =
    alert_kpi_data["Interest Coverage Ratio (ICR)"] = [(((data["Gross Sales Local"][0] + data["Gross Sales Exports"][0])-
                                                       (data["Opening S.I.P."][0]+ data["Raw Materials Imported"][0]
                                                        +data["Raw Materials Indigeneous"][0] + data["Other Spares"][0]
                                                        + data["Power & Fuel"][0] + data["Direct Labour"][0]
                                                        + data["Repairs & Main"][0] + data["Other Operating Exp"][0]
                                                        + data["Depreciation"][0] - data["Closing S.I.P"][0]))
                                                       - data["SG&A Expenses"][0])/100]

    alert_kpi_data["Net Cash Accrual to Net Sales"] = [data["Cash Accruals"][0]/data["Net Sales"][0]]
    # print(alert_kpi_data)
    return pd.DataFrame(alert_kpi_data)

# extracted_data = {
#     "Date": ["31.03.2025"],
#     "Period_Type": ["Actuals"],
#     "Gross Sales Local": [1515.08],
#     "Gross Sales Exports": [0.0],
#     "Raw Materials Imported": [0.0],
#     "Raw Materials Indigeneous": [759.74],
#     "Other Spares": [3.31],
#     "Power & Fuel": [18.32],
#     "Direct Labour": [26.3],
#     "Repairs & Main": [3.31],
#     "Other Operating Exp": [39.71],
#     "Depreciation": [120.24],
#     "Opening S.I.P.": [60.83],
#     "Closing S.I.P": [62.84],
#     "SG&A Expenses": [22.73],
#     "Interest": [97.3],
#     "a) R.M. Imported": [0.0],
#     "b) R.M. Indigenous": [31.38],
#     "c) Stock in Process": [62.84],
#     "d) Finished Goods": [36.85],
#     "e) Other Consumables": [0.0],
#     "Current Ratio": [3.348059518331032],
#     "Debt/Equity Ratio": [0.6673455815113478],
#     "TOL/TNW Ratio": [0.938315736968992],
#     "Debt/EBIDTA %": [1.0930443662770908],
#     "Net Profit margin %": [11.537499146971179],
#     "Cash Accruals": [2.7239999999999993],
#     "Adjusted TNW": [7.217399999999997],
#     "Net Sales": [13.188299999999998],
#     "Return on Equity %": [21.082384238091283],
#     "FACR": [1.9001148985063196],
#     "Current Assets": [6.5478],
#     "Current Liabilities": [1.9557],
#     "DSCR": [1.8527246242468383]
# }
#
# extracted_year = extracted_data["Date"][0].split(".")[-1]
# financial_year = f"FY{extracted_year}-{int(extracted_year[2:])+1}"
# alert_data = create_alerts_data(extracted_data)
# print(alert_data)

# alert_type = classify_financial_attributes(alert_data,financial_year)
# print(alert_type.to_string())
