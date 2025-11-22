trival_mcp_config = {
    # 高德地图 - 路线规划、POI搜索
    "amap-maps": {
        "transport": "streamable_http",
        "url": "https://mcp.api-inference.modelscope.net/8b394c88c8bc4f/mcp"
    },
    # 12306火车票查询 - 提供详细的火车票信息
    "12306-mcp": {
        "transport": "streamable_http",
        "url": "https://mcp.api-inference.modelscope.net/1183ae8a54974b/mcp"
    },
    # 机票查询 - 提供详细的航班信息
    "flight-ticket-mcp": {
        "transport": "streamable_http",
        "url": "https://mcp.api-inference.modelscope.net/88db201fc7b448/mcp"
    }
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