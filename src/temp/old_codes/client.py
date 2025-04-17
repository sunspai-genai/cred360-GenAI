import asyncio
from mcp import ClientSession, StdioServerParameters
from langchain_openai import AzureChatOpenAI
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp.client.stdio import stdio_client
from langgraph.prebuilt import create_react_agent
import os
from dotenv import load_dotenv
from textwrap import dedent

# Load environment variables
load_dotenv()
os.environ["AZURE_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
os.environ["AZURE_ENDPOINT"] = os.getenv("AZURE_ENDPOINT")
os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_OPENAI_API_VERSION")
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

server_params = StdioServerParameters(
    command="python",
    args=[r"C:\Users\10829459\OneDrive - LTIMindtree\LTIM\cred360\src\mcp_tools.py"],
)

model = AzureChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    api_version=os.getenv("AZURE_API_VERSION"),
    temperature=0
)

async def run_agent():
    async with stdio_client(server_params) as (read, write):
        # Open an MCP session to interact with the math_server.py tool.
        async with ClientSession(read, write) as session:
            # Initialize the session.
            await session.initialize()
            # Load tools
            tools = await load_mcp_tools(session)
            # Create a ReAct agent.
            agent = create_react_agent(model, tools)
            # Run the agent.
            agent_response = await agent.ainvoke({"messages": dedent("""what is 2+2""")})
            print(agent_response)
            # Return the response.
            return agent_response["messages"]

if __name__ == "__main__":
    result = asyncio.run(run_agent())
    print(result[-1])