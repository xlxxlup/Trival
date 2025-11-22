import asyncio
import logging
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import trival_mcp_config

logger = logging.getLogger(__name__)

async def get_mcp_tools(mcp_config=trival_mcp_config, timeout=30):
    """
    获取MCP工具，带超时和错误处理

    Args:
        mcp_config: MCP配置字典
        timeout: 超时时间（秒），默认30秒

    Returns:
        list: 可用的MCP工具列表
    """
    available_tools = []

    # 逐个尝试连接每个MCP服务器，避免一个失败导致全部失败
    for server_name, server_config in mcp_config.items():
        try:
            logger.info(f"正在连接MCP服务器: {server_name}")
            logger.debug(f"服务器配置: {server_config}")

            # 为单个服务器创建客户端
            single_config = {server_name: server_config}
            client = MultiServerMCPClient(single_config)

            # 使用asyncio.wait_for添加超时控制
            tools = await asyncio.wait_for(
                client.get_tools(),
                timeout=timeout
            )

            available_tools.extend(tools)
            logger.info(f"✓ 成功连接 {server_name}，获取到 {len(tools)} 个工具")

        except asyncio.TimeoutError:
            logger.warning(f"⚠ 连接 {server_name} 超时（{timeout}秒），跳过此服务")
        except Exception as e:
            logger.error(f"✗ 连接 {server_name} 失败: {type(e).__name__}: {str(e)}")
            logger.debug(f"详细错误信息:", exc_info=True)

    if not available_tools:
        logger.warning("⚠ 所有MCP服务器连接失败，将仅使用本地工具")
    else:
        logger.info(f"✓ 总共获取到 {len(available_tools)} 个MCP工具")

    return available_tools
