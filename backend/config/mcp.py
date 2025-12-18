trival_mcp_config = {
    # 高德地图 - POI搜索、路线规划（不再包含天气和酒店查询）
    "amap-maps": {
        "transport": "sse",
        "url": "https://mcp.api-inference.modelscope.net/b48cb908811b44/sse"
    },
    # 12306火车票查询 - 提供详细的火车票信息
    "12306-mcp": {
      "transport": "streamable_http",
      "url": "https://mcp.api-inference.modelscope.net/17d96fdf3db846/mcp"
    },
    # 机票查询 - 提供详细的航班信息（本地部署，需先启动 flight-ticket-mcp-server）
    "flight-ticket-mcp": {
        "transport": "sse",
        "url": "http://127.0.0.1:8080/sse"
    },
    # "variflight-mcp": {
    #   "transport": "sse",
    #   "url": "https://mcp.api-inference.modelscope.net/520f938ab0a546/sse"
    # },
    # 天气查询 MCP - 专门的天气服务
    "mcp_tool": {
      "transport": "sse",
      "url": "https://mcp.api-inference.modelscope.net/662f8555dfe746/sse"
    },
    # fetch 搜索 MCP - 远程部署（已禁用 robots.txt 限制）
    # "fetch": {
    #     "transport": "sse",
    #     "url": "https://mcp.api-inference.modelscope.net/727fbcd746ee4c/sse"
    # },
    # "fetch": {
    #     "transport": "stdio",
    #     "command": "uvx",
    #     "args": [
    #         "mcp-server-fetch",
    #         "--ignore-robots-txt"
    #     ]
    # }
    # 酒店查询 MCP - 专门的酒店服务（本地部署，使用npx启动） npx jinko-mcp-dev@latest  这个mcp生产环境好像要钱
    # "jinkocx-jinko-mcp": {
    #     "transport": "stdio",
    #     "command": "npx.cmd",
    #     "args": ["jinko-mcp-dev@latest"]
    # },
}

# MCP 服务器到 Agent 类型的映射配置
# 直接将整个 MCP 服务器的所有工具绑定到对应的 agent
# 而不是根据工具名称硬编码绑定
mcp_to_agent_mapping = {
    "12306-mcp": "transport",      # 12306的所有工具 → 交通助手
    "flight-ticket-mcp": "transport",  # 机票的所有工具 → 交通助手
    # "fetch": ["search", "transport"],  # mcp-server-fetch 工具（已禁用，使用 zhipu_search 替代）
    "mcp_tool": "weather",
    "amap-maps": ["hotel","map"] # 高德地图的所有工具 → 酒店助手、地图助手
    # 未来可以添加更多映射：
    # "tavily-search-mcp": "search",
    # "file-operations-mcp": "file",
}

# 保留单独的配置供其他用途
train_mcp_config = {
    "12306-mcp": {
        "transport": "streamable_http",
        "url": "https://mcp.api-inference.modelscope.net/1183ae8a54974b/mcp"
    }
}

flight_mcp_config = {
    "flight-ticket-mcp": {
        "transport": "streamable_http",
        "url": "http://127.0.0.1:8080/mcp"
    }
}