"""
工具执行数据存储模块
按任务类型（transport、hotel、weather等）分类存储工具执行信息到JSON文件
用于后续RAG检索和数据分析
"""
import json
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("utils.tool_data_storage")


class ToolDataStorage:
    """
    工具数据存储管理器
    将工具执行信息按类型存储到JSON文件中
    """

    def __init__(self, storage_dir: str = "data/tool_executions"):
        """
        初始化存储管理器

        Args:
            storage_dir: 存储目录路径
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"工具数据存储目录: {self.storage_dir.absolute()}")

    def _get_file_path(self, category: str) -> Path:
        """
        获取指定类别的存储文件路径

        Args:
            category: 任务类别（如 transport、hotel、weather等）

        Returns:
            Path: 文件路径
        """
        # 清理文件名，确保安全
        safe_category = "".join(c for c in category if c.isalnum() or c in "-_")
        return self.storage_dir / f"{safe_category}.json"

    def _load_category_data(self, category: str) -> List[Dict[str, Any]]:
        """
        加载指定类别的现有数据

        Args:
            category: 任务类别

        Returns:
            List[Dict]: 现有数据列表
        """
        file_path = self._get_file_path(category)

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"加载 {category} 类别数据失败: {e}")
            return []

    def _save_category_data(self, category: str, data: List[Dict[str, Any]]) -> bool:
        """
        保存指定类别的数据到文件

        Args:
            category: 任务类别
            data: 要保存的数据列表

        Returns:
            bool: 是否保存成功
        """
        file_path = self._get_file_path(category)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存 {category} 类别数据失败: {e}")
            return False

    def save_tool_execution(
        self,
        category: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        保存单个工具执行记录

        Args:
            category: 任务类别（transport、hotel、weather等）
            tool_name: 工具名称
            tool_input: 工具输入参数
            tool_output: 工具输出结果
            context: 执行上下文（如出发地、目的地、日期等）
            metadata: 额外的元数据（如执行时间、任务ID等）

        Returns:
            bool: 是否保存成功
        """
        # 加载现有数据
        data = self._load_category_data(category)

        # 创建新记录
        record = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "context": context or {},
            "metadata": metadata or {}
        }

        # 添加到列表
        data.append(record)

        # 保存到文件
        success = self._save_category_data(category, data)

        if success:
            logger.info(f"✅ 成功保存工具执行记录: {category}/{tool_name}")
            logger.debug(f"记录详情: {json.dumps(record, ensure_ascii=False, indent=2)[:500]}...")
        else:
            logger.error(f"❌ 保存工具执行记录失败: {category}/{tool_name}")

        return success

    def save_batch_executions(
        self,
        category: str,
        executions: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        批量保存工具执行记录

        Args:
            category: 任务类别
            executions: 执行记录列表，每个记录应包含 tool_name、tool_input、tool_output
            context: 共同的执行上下文

        Returns:
            int: 成功保存的记录数
        """
        # 加载现有数据
        data = self._load_category_data(category)

        # 添加新记录
        timestamp = datetime.now().isoformat()
        success_count = 0

        for execution in executions:
            record = {
                "timestamp": timestamp,
                "category": category,
                "tool_name": execution.get("tool_name", "unknown"),
                "tool_input": execution.get("tool_input", {}),
                "tool_output": execution.get("tool_output", ""),
                "context": context or {},
                "metadata": execution.get("metadata", {})
            }
            data.append(record)
            success_count += 1

        # 保存到文件
        if self._save_category_data(category, data):
            logger.info(f"✅ 成功批量保存 {success_count} 条工具执行记录到 {category}")
            return success_count
        else:
            logger.error(f"❌ 批量保存工具执行记录失败: {category}")
            return 0

    def query_by_category(
        self,
        category: str,
        limit: Optional[int] = None,
        tool_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        查询指定类别的工具执行记录

        Args:
            category: 任务类别
            limit: 返回的最大记录数（None表示全部）
            tool_name: 可选的工具名称过滤

        Returns:
            List[Dict]: 匹配的记录列表
        """
        data = self._load_category_data(category)

        # 按工具名称过滤
        if tool_name:
            data = [record for record in data if record.get("tool_name") == tool_name]

        # 限制数量（返回最新的N条）
        if limit:
            data = data[-limit:]

        logger.info(f"查询 {category} 类别记录，找到 {len(data)} 条")
        return data

    def query_by_context(
        self,
        category: str,
        context_filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        根据上下文信息查询工具执行记录

        Args:
            category: 任务类别
            context_filters: 上下文过滤条件（如 {"destination": "北京", "date": "2025-09-22"}）

        Returns:
            List[Dict]: 匹配的记录列表
        """
        data = self._load_category_data(category)

        # 过滤匹配的记录
        filtered_data = []
        for record in data:
            context = record.get("context", {})
            # 检查是否所有过滤条件都匹配
            if all(context.get(key) == value for key, value in context_filters.items()):
                filtered_data.append(record)

        logger.info(f"根据上下文查询 {category} 类别，找到 {len(filtered_data)} 条匹配记录")
        return filtered_data

    def get_all_categories(self) -> List[str]:
        """
        获取所有存在的类别

        Returns:
            List[str]: 类别列表
        """
        categories = []
        for file_path in self.storage_dir.glob("*.json"):
            category = file_path.stem
            categories.append(category)

        return categories

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取存储统计信息

        Returns:
            Dict: 统计信息，包含每个类别的记录数
        """
        stats = {
            "total_categories": 0,
            "total_records": 0,
            "categories": {}
        }

        for category in self.get_all_categories():
            data = self._load_category_data(category)
            record_count = len(data)

            stats["categories"][category] = {
                "record_count": record_count,
                "file_path": str(self._get_file_path(category))
            }
            stats["total_records"] += record_count

        stats["total_categories"] = len(stats["categories"])

        return stats

    def find_cached_execution(
        self,
        category: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        require_exact_match: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        查找是否有匹配的缓存工具执行结果

        Args:
            category: 任务类别（transport、hotel、weather等）
            tool_name: 工具名称
            tool_input: 工具输入参数
            require_exact_match: 是否要求精确匹配（默认False，使用模糊匹配）

        Returns:
            Optional[Dict]: 如果找到匹配的缓存记录则返回，否则返回None
        """
        data = self._load_category_data(category)

        # 按工具名称过滤
        matching_records = [record for record in data if record.get("tool_name") == tool_name]

        if not matching_records:
            logger.debug(f"未找到工具 {tool_name} 的缓存记录（类别: {category}）")
            return None

        # 查找匹配的记录
        if require_exact_match:
            # 精确匹配：tool_input必须完全相同
            for record in reversed(matching_records):  # 从最新的开始查找
                if record.get("tool_input") == tool_input:
                    logger.info(f"✅ 找到精确匹配的缓存记录: {category}/{tool_name}")
                    return record
        else:
            # 模糊匹配：检查关键字段是否匹配
            # 对于大多数工具，主要参数（如city、keywords、address等）相同即可认为是重复调用
            for record in reversed(matching_records):  # 从最新的开始查找
                cached_input = record.get("tool_input", {})

                # 简单的匹配策略：所有非空参数都相同
                # 过滤掉值为None或空字符串的参数进行比较
                current_input_filtered = {k: v for k, v in tool_input.items() if v not in [None, "", []]}
                cached_input_filtered = {k: v for k, v in cached_input.items() if v not in [None, "", []]}

                if current_input_filtered == cached_input_filtered:
                    logger.info(f"✅ 找到模糊匹配的缓存记录: {category}/{tool_name}")
                    logger.debug(f"缓存输入: {cached_input}")
                    logger.debug(f"当前输入: {tool_input}")
                    return record

        logger.debug(f"未找到匹配的缓存记录: {category}/{tool_name}")
        return None


# 全局单例实例
_storage_instance: Optional[ToolDataStorage] = None


def get_tool_storage(storage_dir: str = "data/tool_executions") -> ToolDataStorage:
    """
    获取全局工具数据存储实例（单例模式）

    Args:
        storage_dir: 存储目录路径

    Returns:
        ToolDataStorage: 存储管理器实例
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ToolDataStorage(storage_dir=storage_dir)
    return _storage_instance
