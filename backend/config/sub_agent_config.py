"""
子 Agent 配置文件
用于配置每个子Agent的max_rounds超参数
"""

# 子Agent的最大轮次配置
SUB_AGENT_MAX_ROUNDS = {
    # 交通助手：查询火车票、机票等  机票一般设置1 火车高铁设置2 节约成本
    "transport": 1,

    # 地图助手：查询景点、路线、周边信息
    "map": 2,

    # 搜索助手：互联网搜索
    "search": 2,

    # 文件助手：文件读写操作
    "file": 2,

    # 天气助手：查询天气信息
    "weather": 1,

    # 酒店助手：查询酒店信息
    "hotel": 2,
}

# 默认最大轮次（当某个agent类型未在上面配置时使用）
DEFAULT_MAX_ROUNDS = 3


def get_max_rounds(agent_type: str) -> int:
    """
    获取指定类型子Agent的最大轮次数

    Args:
        agent_type: 子Agent类型 (transport/map/search/file)

    Returns:
        该Agent类型配置的最大轮次数
    """
    return SUB_AGENT_MAX_ROUNDS.get(agent_type, DEFAULT_MAX_ROUNDS)
