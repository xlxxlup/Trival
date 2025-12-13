trival_mcp_config = {
    # 高德地图 - POI搜索、路线规划（不再包含天气和酒店查询）
    "amap-maps": {
      "transport": "streamable_http",
      "url": "https://mcp.api-inference.modelscope.net/c2c9f72900af4b/mcp"
    },
    # 12306火车票查询 - 提供详细的火车票信息
    "12306-mcp": {
      "transport": "streamable_http",
      "url": "https://mcp.api-inference.modelscope.net/17d96fdf3db846/mcp"
    },
    # 机票查询 - 提供详细的航班信息
    "flight-ticket-mcp": {
        "transport": "streamable_http",
        "url": "https://mcp.api-inference.modelscope.net/88db201fc7b448/mcp"
    },
    # 浏览器搜索
    "fetch": {
      "transport": "streamable_http",
      "url": "https://mcp.api-inference.modelscope.net/5ad4894744a64b/mcp"
    },
    # 天气查询 MCP - 专门的天气服务
    "MCP_WEATHER_MCP_Agent_Challenge": {
      "transport": "streamable_http",
      "url": "https://mcp.api-inference.modelscope.net/de3453c8463949/mcp"
    },
    # 酒店查询 MCP - 专门的酒店服务（本地部署，使用npx启动） npx jinko-mcp-dev@latest
    "jinkocx-jinko-mcp": {
        "command": "npx",
        "args": ["jinko-mcp-dev@latest"]
    },
}

# MCP 服务器到 Agent 类型的映射配置
# 直接将整个 MCP 服务器的所有工具绑定到对应的 agent
# 而不是根据工具名称硬编码绑定
mcp_to_agent_mapping = {
    "12306-mcp": "transport",      # 12306的所有工具 → 交通助手
    "flight-ticket-mcp": "transport",  # 机票的所有工具 → 交通助手
    "amap-maps": "map",            # 高德地图的所有工具 → 地图助手
    "fetch": ["search", "transport"],  # fetch工具同时给搜索助手和交通助手（作为fallback）
    "MCP_WEATHER_MCP_Agent_Challenge": "weather",
    "jinkocx-jinko-mcp": "hotel"
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
        "url": "https://mcp.api-inference.modelscope.net/88db201fc7b448/mcp"
    }
}