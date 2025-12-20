import asyncio
import logging
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import trival_mcp_config

logger = logging.getLogger(__name__)

async def get_mcp_tools(mcp_config=trival_mcp_config, timeout=30):
    """
    获取MCP工具，带超时和错误处理

    现在返回一个字典，保留每个工具所属的MCP服务器信息，
    这样可以根据MCP服务器类型直接绑定到对应的agent，
    而不是根据工具名称硬编码绑定

    Args:
        mcp_config: MCP配置字典
        timeout: 超时时间（秒），默认30秒

    Returns:
        dict: {server_name: [tools]} 的字典结构
    """
    tools_by_server = {}

    # 逐个尝试连接每个MCP服务器，避免一个失败导致全部失败
    for server_name, server_config in mcp_config.items():
        try:
            logger.info(f"正在连接MCP服务器: {server_name}")
            logger.debug(f"服务器配置: {server_config}")

            # 获取禁用工具列表（在创建客户端之前提取）
            disabled_tools = server_config.get('disabled_tools', [])

            # 创建一个不包含 disabled_tools 的配置副本传递给客户端
            # 因为 MultiServerMCPClient 不认识这个自定义字段
            clean_config = {k: v for k, v in server_config.items() if k != 'disabled_tools'}
            single_config = {server_name: clean_config}
            client = MultiServerMCPClient(single_config)

            # 使用asyncio.wait_for添加超时控制
            tools = await asyncio.wait_for(
                client.get_tools(),
                timeout=timeout
            )

            # 过滤掉禁用的工具
            if disabled_tools:
                original_count = len(tools)
                tools = [tool for tool in tools if tool.name not in disabled_tools]
                filtered_count = original_count - len(tools)

                if filtered_count > 0:
                    logger.info(f"✓ 已过滤 {server_name} 的 {filtered_count} 个禁用工具: {disabled_tools}")

            tools_by_server[server_name] = tools
            logger.info(f"✓ 成功连接 {server_name}，获取到 {len(tools)} 个工具")

        except asyncio.TimeoutError:
            logger.warning(f"⚠ 连接 {server_name} 超时（{timeout}秒），跳过此服务")
        except Exception as e:
            logger.error(f"✗ 连接 {server_name} 失败: {type(e).__name__}: {str(e)}")
            logger.debug(f"详细错误信息:", exc_info=True)

    if not tools_by_server:
        logger.warning("⚠ 所有MCP服务器连接失败，将仅使用本地工具")
    else:
        total_tools = sum(len(tools) for tools in tools_by_server.values())
        logger.info(f"✓ 总共获取到 {total_tools} 个MCP工具，来自 {len(tools_by_server)} 个服务器")

    return tools_by_server
