import os
from tavily import TavilyClient
from langchain_core.tools import tool
from dotenv import load_dotenv
load_dotenv()

@tool
def tavily_search(query: str,limit_k:int=5) -> str:
    """该工具可以搜索互联网上的信息."""
    api_key = "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"
    tavily_client = TavilyClient(api_key = api_key)
    results = tavily_client.search(query)
    return results

@tool
def write_file(file_path: str, content: str) -> str:
    """该工具可以写入文件."""
    with open(file_path, 'w') as f:
        f.write(content)
    return f"写入文件成功，文件路径为：{file_path}"
@tool
def read_file(file_path: str) -> str:
    """该工具可以读取文件."""
    if not os.path.exists(file_path):
        return f"文件不存在，文件路径为：{file_path}"
    with open(file_path, 'r') as f:
        content = f.read()
    return content