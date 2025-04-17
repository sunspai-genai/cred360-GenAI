# import os
# from typing import List, Dict, Any, TypedDict
# import glob
#
# from debugpy import configure
# from dotenv import load_dotenv, find_dotenv
# from langchain_core.messages import HumanMessage, AIMessage
# from langchain_openai import ChatOpenAI, AzureChatOpenAI
# from langgraph.graph import StateGraph, END
# from langgraph.prebuilt import ToolNode
# from openai import AzureOpenAI
#
# # Load environment variables
# load_dotenv(find_dotenv(), verbose=True, override=True)
#
# # Set environment variables for Azure OpenAI
# os.environ["AZURE_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
# os.environ["AZURE_ENDPOINT"] = os.getenv("AZURE_ENDPOINT")
# os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")
#
# # Define state structure
# class AgentState(TypedDict):
#     files: List[str]
#     current_file: str
#     file_contents: Dict[str, str]
#     analyses: Dict[str, str]
#     final_report: str
#
#
# # Function to read markdown files
# def read_markdown_files(state: AgentState) -> AgentState:
#     """Read all markdown files from the reports directory."""
#     markdown_files = glob.glob(f"../output/{account}/reports/*.md")
#     print(markdown_files)
#     # exit()
#     state["files"] = markdown_files
#     state["file_contents"] = {}
#     file_contents = ""
#     for file_path in markdown_files:
#         file_name = file_path.split("\\")[1]
#         try:
#             with open(file_path, "r", encoding="utf-8") as file:
#                 content = file.read()
#                 # state["file_contents"][file_path] = content
#                 file_contents = file_contents+"\n"+ file_name+"\n"+content+"\n"
#         except Exception as e:
#             print(f"Error reading {file_path}: {e}")
#     # print(file_contents)
#     state["file_contents"] = file_contents
#     return state
#
# # Function to generate the final report
# def generate_report(state: AgentState) -> AgentState:
#     """Generate the final cumulative report."""
#     llm = AzureChatOpenAI(
#             model="gpt-4o",
#             api_key=os.getenv("AZURE_OPENAI_API_KEY"),
#             azure_endpoint=os.getenv("AZURE_ENDPOINT"),
#             api_version=os.getenv("AZURE_API_VERSION"),
#             temperature=0,
#         )
#
#     messages = [
#         HumanMessage(content=f"""You are a Markdown analysis and reporting tool. Your task is to analyze a collection of Markdown files provided as input
#         and generate a single, comprehensive report summarizing key aspects of the content.
#
#         Here are the individual analyses by section:
#
#         {state["file_contents"]}
#
#         Please format the final report with appropriate headings and ensuring a cohesive narrative throughout.
#
#         Output format:
#             Introduction: Summary of all the sheets
#             ##Name of Sheet
#                - Analysis of the respective Sheet
#             Conclusion: Based on analysis of all sheets
#         """)
#     ]
#
#     response = llm.invoke(messages)
#
#     # Store the final report
#     state["final_report"] = response.content
#
#     return state
#
#
# # Define the workflow
# def create_markdown_analysis_agent():
#     """Create the LangGraph workflow for markdown file analysis."""
#     workflow = StateGraph(AgentState)
#
#     # Add nodes
#     workflow.add_node("read_files", read_markdown_files)
#     # workflow.add_node("analyze_file", analyze_file)
#     workflow.add_node("generate_report", generate_report)
#
#     # Add edges
#     workflow.add_edge("read_files", "generate_report")
#
#     # workflow.add_edge("analyze_file", "generate_report")
#     workflow.add_edge("generate_report", END)
#
#     # Set entry point
#     workflow.set_entry_point("read_files")
#
#     # Compile the graph
#     return workflow.compile()
#
#
# # Function to run the agent and get the report
# def run_markdown_analysis():
#     """Run the markdown analysis agent and return the final report."""
#     agent = create_markdown_analysis_agent()
#
#     # Run the agent
#     result = agent.invoke({})
#
#     # Return the final report
#     return result.get("final_report", "No report generated.")
#
#
# # Sample usage
# if __name__ == "__main__":
#     account = "walmart"
#     if not os.path.exists(f"../output/{account}/reports"):
#         print("Reports folder not exist")
#         exit(1)
#
#     final_report = run_markdown_analysis()
#     print("\n\n--- FINAL REPORT ---\n\n")
#     print(final_report)
#
#     # Optionally save the report
#     with open(f"../output/{account}/cumulative_report.md", "w") as f:
#         f.write(final_report)

import os
import glob
from typing import List, Dict, Any, TypedDict

from dotenv import load_dotenv, find_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END


# Define state structure
class AgentState(TypedDict):
    files: List[str]
    current_file: str
    file_contents: Dict[str, str]
    analyses: Dict[str, str]
    final_report: str


class MarkdownAnalysisAgent:
    """
    A class for analyzing markdown files and generating a cumulative report using LangGraph.
    """

    def __init__(self, account):
        """
        Initializes the MarkdownAnalysisAgent.

        Args:
            account (str): The account name used for file paths.  Defaults to "tesla".
        """
        self.account = account
        # self.load_environment_variables()
        # self.llm = AzureChatOpenAI(
        #     model="gpt-4o",
        #     api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        #     azure_endpoint=os.getenv("AZURE_ENDPOINT"),
        #     api_version=os.getenv("AZURE_API_VERSION"),
        #     temperature=0,
        # )

    # def load_environment_variables(self):
    #     """Loads environment variables from .env file."""
    #     load_dotenv(find_dotenv(), verbose=True, override=True)
    #
    #     # Set environment variables for Azure OpenAI
    #     os.environ["AZURE_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
    #     os.environ["AZURE_ENDPOINT"] = os.getenv("AZURE_ENDPOINT")
    #     os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")
    #
    # def read_markdown_files(self, state: AgentState) -> AgentState:
    #     """Reads all markdown files from the reports directory."""
    #     markdown_files = glob.glob(f"../output/{self.account}/reports/*.md")
    #     print(markdown_files)
    #     state["files"] = markdown_files
    #     state["file_contents"] = {}
    #     file_contents = ""
    #     for file_path in markdown_files:
    #         file_name = os.path.basename(file_path)  # Use os.path.basename for filename
    #         try:
    #             with open(file_path, "r", encoding="utf-8") as file:
    #                 content = file.read()
    #                 file_contents = file_contents + "\n" + file_name + "\n" + content + "\n"
    #         except Exception as e:
    #             print(f"Error reading {file_path}: {e}")
    #     state["file_contents"] = file_contents
    #     return state

    def generate_report(self, state: AgentState) -> AgentState:
        """Generates the final cumulative report."""

        messages = [
            HumanMessage(
                content=f"""You are a Markdown analysis and reporting tool. Your task is to analyze a collection of Markdown files provided as input 
            and generate a single, comprehensive report summarizing key aspects of the content.

            Here are the individual analyses by section:

            {state["file_contents"]}

            Please format the final report with appropriate headings and ensuring a cohesive narrative throughout.

            Output format:
                Introduction: Summary of all the sheets
                ##Name of Sheet
                   - Analysis of the respective Sheet
                Conclusion: Based on analysis of all sheets
            """
            )
        ]

        response = self.llm.invoke(messages)

        # Store the final report
        state["final_report"] = response.content

        return state

    def create_langgraph_workflow(self):
        """Creates the LangGraph workflow for markdown file analysis."""
        workflow = StateGraph(AgentState)

        # Add nodes
        # workflow.add_node("read_files", self.read_markdown_files)
        workflow.add_node("generate_report", self.generate_report)

        # Add edges
        workflow.add_edge("read_files", "generate_report")
        workflow.add_edge("generate_report", END)

        # Set entry point
        workflow.set_entry_point("read_files")

        # Compile the graph
        return workflow.compile()

    def run_analysis(self) -> str:
        """Runs the markdown analysis and returns the final report."""
        agent = self.create_langgraph_workflow()
        result = agent.invoke({})
        return result.get("final_report", "No report generated.")


def analyze_markdown_files(account: str = "tesla") -> str:
    """
    Analyzes markdown files for a given account and returns the final report.

    Args:
        account (str): The account name. Defaults to "tesla".

    Returns:
        str: The final cumulative report.
    """
    agent = MarkdownAnalysisAgent(account=account)
    return agent.run_analysis()


if __name__ == "__main__":
    account = "walmart"
    if not os.path.exists(f"../output/{account}/reports"):
        print("Reports folder does not exist")
        exit(1)

    final_report = analyze_markdown_files(account)
    print("\n\n--- FINAL REPORT ---\n\n")
    print(final_report)

    # Optionally save the report
    with open(f"../output/{account}/cumulative_report.md", "w") as f:
        f.write(final_report)