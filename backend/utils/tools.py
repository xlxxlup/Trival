import os
from zai import ZhipuAiClient
from langchain_core.tools import tool
from dotenv import load_dotenv
load_dotenv()

@tool
def zhipu_search(query: str, count: int = 5) -> str:
    """该工具可以搜索互联网上的信息，使用智谱AI的web_search服务。

    参数:
        query: 搜索查询关键词
        count: 返回结果的条数，范围1-50，默认5
    """
    api_key = "644a19dba0604174a3c223da87678c24.5QSlMiDsjVwwLQiv"
    client = ZhipuAiClient(api_key=api_key)

    response = client.web_search.web_search(
        search_engine="Search-Std",
        search_query=query,
        count=min(max(count, 1), 50),  # 确保在1-50范围内
        search_recency_filter="noLimit",
        content_size="medium"
    )
    return response

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