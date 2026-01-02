import os

trival_mcp_config = {
    # 高德地图 - POI搜索、路线规划（不再包含天气和酒店查询）
    "amap-maps": {
        "transport": "sse",
        "url": os.getenv("MCP_AMAP_URL"),
        "disabled_tools": []  # 禁用的工具列表，例如: ["tool_name1", "tool_name2"]
    },
    # 12306火车票查询 - 提供详细的火车票信息
    "12306-mcp": {
      "transport": "streamable_http",
      "url": os.getenv("MCP_12306_URL"),
      "disabled_tools": []  # 禁用的工具列表
    },
    # 机票查询 - 提供详细的航班信息（本地部署，需先启动 flight-ticket-mcp-server）
    # "flight-ticket-mcp": {
    #     "transport": "sse",
    #     "url": "http://127.0.0.1:8080/sse",
    #     "disabled_tools": []
    # },
    "variflight-mcp": {
      "transport": "sse",
      "url": os.getenv("MCP_VARIFLIGHT_URL"),
      "disabled_tools": ["flightHappinessIndex","searchFlightsByNumber"]  # 禁用的工具列表
    },
    # 天气查询 MCP - 专门的天气服务
    "mcp_tool": {
      "transport": "sse",
      "url": os.getenv("MCP_WEATHER_URL"),
      "disabled_tools": []  # 禁用的工具列表
    },
    "aigohotel-mcp": {
      "url": "https://mcp.aigohotel.com/mcp",
      "transport": "streamable_http",
      "headers": {
        "Authorization": os.getenv("AIGOHOTEL-MCP-KEY"),
        "Content-Type": "application/json"
      },
      "disabled_tools": []  # 禁用的工具列表
    }
    # "fetch": {
    #     "transport": "stdio",
    #     "command": "uvx",
    #     "args": [
    #         "mcp-server-fetch",
    #         "--ignore-robots-txt"
    #     ],
    #     "disabled_tools": []
    # }
    # 酒店查询 MCP - 专门的酒店服务（本地部署，使用npx启动） npx jinko-mcp-dev@latest  这个mcp生产环境好像要钱
    # "jinkocx-jinko-mcp": {
    #     "transport": "stdio",
    #     "command": "npx.cmd",
    #     "args": ["jinko-mcp-dev@latest"],
    #     "disabled_tools": []
    # },
}

# MCP 服务器到 Agent 类型的映射配置
# 直接将整个 MCP 服务器的所有工具绑定到对应的 agent
# 而不是根据工具名称硬编码绑定
mcp_to_agent_mapping = {
    "12306-mcp": "transport",      # 12306的所有工具 → 交通助手
    "variflight-mcp": "transport",  # 机票的所有工具 → 交通助手
    # "fetch": ["search", "transport"],  # mcp-server-fetch 工具（已禁用，使用 zhipu_search 替代）
    "mcp_tool": "weather",
    "amap-maps": ["map"], # 高德地图的所有工具 → 酒店助手、地图助手
    "aigohotel-mcp":["hotel"]
    # 未来可以添加更多映射：
    # "tavily-search-mcp": "search",
    # "file-operations-mcp": "file",
}

