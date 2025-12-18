"""
MCP管理器 - 全局单例模式管理MCP工具和子Agent的初始化
在项目启动时初始化，避免每次流程开始时重复初始化
"""
import logging
from typing import Dict, Any, Optional
from utils import get_mcp_tools
from utils.tools import zhipu_search
from config import trival_mcp_config
from agent.sub_agents import create_sub_agents

logger = logging.getLogger("utils.mcp_manager")

class MCPManager:
    """
    MCP管理器单例类
    负责在项目启动时初始化MCP工具和子Agent，并在整个项目生命周期内复用
    """
    _instance: Optional['MCPManager'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化管理器（但不立即初始化MCP工具）"""
        if not self._initialized:
            self._tools_by_server: Dict[str, list] = {}
            self._sub_agents: Dict[str, Any] = {}
            self._initialization_error: Optional[Exception] = None

    async def initialize(self, timeout: int = 30) -> bool:
        """
        初始化MCP工具和子Agent（应在项目启动时调用一次）

        Args:
            timeout: MCP连接超时时间（秒）

        Returns:
            bool: 初始化是否成功
        """
        if self._initialized:
            logger.info("MCP管理器已初始化，跳过重复初始化")
            return True

        logger.info("=" * 80)
        logger.info("【MCP管理器】开始初始化MCP工具和子Agent...")
        logger.info("=" * 80)

        try:
            # 1. 初始化MCP工具
            logger.info("【步骤1/2】正在连接MCP服务器并获取工具...")
            self._tools_by_server = await get_mcp_tools(trival_mcp_config, timeout=timeout)

            total_mcp_tools = sum(len(tools) for tools in self._tools_by_server.values())
            logger.info(f"✅ MCP工具获取成功：共 {total_mcp_tools} 个工具，来自 {len(self._tools_by_server)} 个服务器")

            # 打印每个服务器的工具统计
            for server_name, tools in self._tools_by_server.items():
                logger.info(f"  - {server_name}: {len(tools)} 个工具")

            # 2. 创建子Agent
            logger.info("【步骤2/2】正在创建子Agent...")
            self._sub_agents = await create_sub_agents(
                tools_by_server=self._tools_by_server,
                local_tools=[zhipu_search]
            )

            logger.info(f"✅ 子Agent创建成功：共 {len(self._sub_agents)} 个子Agent")

            # 打印每个子Agent的信息
            for agent_type, agent in self._sub_agents.items():
                logger.info(f"  - {agent_type}: {agent.name} ({agent.description})")

            self._initialized = True
            logger.info("=" * 80)
            logger.info("【MCP管理器】初始化完成！")
            logger.info("=" * 80)
            return True

        except Exception as e:
            self._initialization_error = e
            logger.error(f"【MCP管理器】初始化失败: {type(e).__name__}: {str(e)}")
            logger.exception(e)
            logger.warning("将使用空的MCP工具字典和子Agent字典")

            # 设置为空字典，允许系统继续运行（但没有MCP工具）
            self._tools_by_server = {}
            self._sub_agents = {}
            self._initialized = True  # 标记为已初始化（虽然失败了）

            logger.info("=" * 80)
            return False

    def get_tools_by_server(self) -> Dict[str, list]:
        """
        获取MCP工具字典

        Returns:
            Dict[str, list]: {server_name: [tools]} 的字典结构
        """
        if not self._initialized:
            logger.warning("MCP管理器尚未初始化，返回空工具字典")
            return {}
        return self._tools_by_server

    def get_sub_agents(self) -> Dict[str, Any]:
        """
        获取子Agent字典

        Returns:
            Dict[str, Any]: {agent_type: agent_instance} 的字典结构
        """
        if not self._initialized:
            logger.warning("MCP管理器尚未初始化，返回空子Agent字典")
            return {}
        return self._sub_agents

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    def get_initialization_error(self) -> Optional[Exception]:
        """获取初始化过程中的错误（如果有）"""
        return self._initialization_error


# 全局单例实例
_mcp_manager = MCPManager()


async def initialize_mcp_manager(timeout: int = 30) -> bool:
    """
    初始化全局MCP管理器（应在项目启动时调用）

    Args:
        timeout: MCP连接超时时间（秒）

    Returns:
        bool: 初始化是否成功
    """
    return await _mcp_manager.initialize(timeout=timeout)


def get_mcp_manager() -> MCPManager:
    """
    获取全局MCP管理器实例

    Returns:
        MCPManager: MCP管理器实例
    """
    return _mcp_manager
