# Define the AgentState class for BalanceSheet Analyzer
import os
from textwrap import dedent
from typing import TypedDict
import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

from dotenv import find_dotenv, load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph
from typer.cli import state

load_dotenv(find_dotenv(), verbose=True, override=True)

AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


class AgentState(TypedDict):
    data: str
    result: str


def graph_data_agent(state: AgentState):
    """
    The Graph Data Generator Agent processes cleaned data from a .md file, analyzes it,
    and determines the most suitable type of graph for the data. Additionally, it provides the necessary graph data.

    Returns:
    dict: The response from the Language Learning Model (LLM), containing the analyzed data and the recommended graph type.
    """
    try:

        with open(
                r"/src/output/nvidia\audit_data\fund flow_20250327_175539.md",
                "r") as f:
            state['data'] = f.read()
    except FileNotFoundError:
        return {"error": "File not found. Please ensure the .md file is available."}

    data = state['data']

    if not data:
        return {"error": "Failed to extract text from the file."}

    system = dedent("""
    You are the Graph Data Generator Agent. Your task is to process data, analyze it, and determine the most suitable type of graph for the data.
    Additionally, you will provide the necessary graph data.

    Your responsibilities include:
        1. Reading and understanding the data. Modify the date in same format.
        2. Analyzing the data to identify key patterns, trends, and insights.
        3. Determining the most appropriate type of graph (e.g., bar chart, line graph, pie chart, etc.) to represent the data effectively.
        4. Generating the data required to create the recommended graph.
        5. Returning a dictionary containing the analyzed data and the graph type.
    
    
    Returns:
        Only the extracted graph data
    """)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", f"Data: {data}")
        ]
    )

    # Initialize the LLM
    llm = AzureChatOpenAI(
        model="gpt-4o-mini",
        api_key=AZURE_API_KEY,
        azure_endpoint=AZURE_ENDPOINT,
        api_version=AZURE_API_VERSION,
        temperature=0
    )

    graph_data = prompt | llm | StrOutputParser()

    result = graph_data.invoke({"data": data})
    print(result)
    state["result"] = result
    return state

def create_charts_with_seaborn(state: AgentState):  # Changed AgentState to dict for simplicity
    """
    Generates charts using Seaborn based on the provided data.

    Args:
        state (dict): A dictionary containing the data and graph type.  The 'result' key
                      should contain a JSON string representing the data.  The 'graph_type'
                      key specifies the type of chart to generate (line or bar).
    """
    try:
        data_string = str(state["result"]).replace("```", "").replace("json", "").replace("python", "")
        data = json.loads(data_string)

        print(data)
        exit()
        # Extract data
        years = data['data']['Date']
        net_profit = data['data']['Depreciation']
        operating_profit = data['data']['Operating Cash Flow']
        graph_type = data['graph_type']

        # Create a Pandas DataFrame for easier handling with Seaborn
        df = pd.DataFrame({'Year': years, 'Depreciation': net_profit, 'Operating Cash Flow': operating_profit})
        df = df.melt(id_vars='Year', var_name='Category', value_name='Fund Flow')  # Reshape for Seaborn

        # Create the plot using Seaborn
        plt.figure(figsize=(10, 6))  # Adjust figure size

        if str(graph_type).__contains__('line'):
            sns.lineplot(x='Year', y='Fund Flow', hue='Category', data=df, marker='o')
        elif graph_type == 'bar':
            sns.barplot(x='Year', y='Fund Flow', hue='Category', data=df)
        else:
            print(f"Unsupported graph type: {graph_type}.  Using line chart as default.")
            sns.lineplot(x='Year', y='Amount', hue='Category', data=df, marker='o')


        plt.xlabel('Year')
        plt.ylabel('Fund Flow')
        plt.title('Depreciation vs Operating Cash Flow')
        plt.xticks(rotation=45, ha='right')  # Rotate x-axis labels for readability
        plt.tight_layout()  # Adjust layout to prevent labels from overlapping

        # Save the plot
        plt.savefig('../charts/fund_flow_fig1.png')

        # Show the plot
        plt.show()

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except KeyError as e:
        print(f"KeyError: Missing key in data: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def create_charts(state: AgentState):
    data = json.loads(str(state["result"]).replace("```", "").replace("json", "")
                      .replace("python", ""))

    print(data)
    # Extract data for plotting
    years = data['data']['Date']
    net_profit = data['data']['Net Income']
    operating_profit = data['data']['Total Revenue']
    graph_type = data['graph_type']

    # Create the plot
    plt.figure(figsize=(9, 6))

    if str(graph_type).__contains__('line'):
        plt.plot(years, net_profit, label='Net Income', marker='o')
        plt.plot(years, operating_profit, label='Total Revenue', marker='o')
    elif graph_type == 'bar':
        width = 0.35
        x = range(len(years))
        plt.bar(x, net_profit, width=width, label='Net Income')
        plt.bar([p + width for p in x], operating_profit, width=width, label='Total Revenue')

    plt.xlabel('Years')
    plt.ylabel('Amount')
    plt.title('Total Revenue VS Net Income')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save the plot as an image file
    plt.savefig('profit_&_loss statement_fig1.png')

    # Show the plot
    plt.show()


workflow = StateGraph(AgentState)

workflow.add_node("graph_data_node", graph_data_agent)
workflow.add_node("prepare_chart_with_seaborn", create_charts_with_seaborn)
# workflow.add_node("prepare_chart", create_charts)

# workflow.add_edge("graph_data_node","prepare_chart")
workflow.add_edge("graph_data_node","prepare_chart_with_seaborn")
workflow.set_entry_point("graph_data_node")

app = workflow.compile()


# Invoke the app without data
initial_state = {"data": "", "result": ""}
output = app.invoke(initial_state)

