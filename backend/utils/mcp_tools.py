from langchain_mcp_adapters.client import MultiServerMCPClient
from config import trival_mcp_config
async def get_mcp_tools(mcp_config=trival_mcp_config):
    client = MultiServerMCPClient(mcp_config)
    mcp_tools = await client.get_tools()
    return mcp_tools
