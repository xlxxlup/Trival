"""
子 Agent 定义
每个子 Agent 负责特定类型的工具调用，避免工具误调用
"""
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import PromptTemplate

from utils import get_llm
from utils.agent_tools import retry_llm_call, execute_tool_calls
from utils.tool_data_storage import get_tool_storage
from config import get_max_rounds
from prompts import (
    SUB_AGENT_SUMMARY_TASK_PROMPT,
    SUB_AGENT_QUERY_TASK_PROMPT,
    TASK_COMPLETION_CHECK_PROMPT,
    EXTRA_TOOL_CALL_GUIDANCE_PROMPT,
    TRANSPORT_AGENT_SUMMARY_TASK_PROMPT,
    TRANSPORT_AGENT_QUERY_TASK_PROMPT,
    MAP_AGENT_SUMMARY_TASK_PROMPT,
    MAP_AGENT_QUERY_TASK_PROMPT,
    SEARCH_AGENT_SUMMARY_TASK_PROMPT,
    SEARCH_AGENT_QUERY_TASK_PROMPT,
    FILE_AGENT_SUMMARY_TASK_PROMPT,
    FILE_AGENT_QUERY_TASK_PROMPT,
    WEATHER_AGENT_SUMMARY_TASK_PROMPT,
    WEATHER_AGENT_QUERY_TASK_PROMPT,
    HOTEL_AGENT_SUMMARY_TASK_PROMPT,
    HOTEL_AGENT_QUERY_TASK_PROMPT
)

logger = logging.getLogger("agent.sub_agents")


class BaseSubAgent:
    """子 Agent 基类"""

    def __init__(self, name: str, description: str, tools: List[Any], agent_type: str = "general"):
        self.name = name
        self.description = description
        self.tools = tools
        self.agent_type = agent_type
        self.llm = None
        self.llm_with_tools = None
        # 从配置获取该类型agent的默认max_rounds
        self.default_max_rounds = get_max_rounds(agent_type)
        logger.debug(f"子Agent [{self.name}] 类型: {agent_type}, 默认max_rounds: {self.default_max_rounds}")

    async def initialize(self):
        """初始化 LLM 和工具绑定"""
        if self.llm is None:
            self.llm = get_llm("plan")
            self.llm_with_tools = self.llm.bind_tools(self.tools)
            logger.info(f"子Agent [{self.name}] 初始化完成，绑定工具数: {len(self.tools)}")
            for tool in self.tools:
                tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                logger.debug(f"  - {tool_name}")

    async def execute_task(
        self,
        task: str,
        context: Dict[str, Any],
        previous_tool_results: Optional[List[ToolMessage]] = None,
        max_rounds: Optional[int] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述
            context: 上下文信息（包括 origin, destination, date 等）
            previous_tool_results: 之前任务执行的工具调用结果（用于提供上下文）
            max_rounds: 最大轮次（如果不指定，使用该agent类型的默认配置）
            category: 任务类别（用于存储工具执行数据，如transport、hotel、weather等）

        Returns:
            {
                "success": bool,
                "tool_messages": List[ToolMessage],
                "summary": str,
                "is_summary_task": bool,
                "final_response": str
            }
        """
        await self.initialize()

        # 获取工具数据存储实例
        storage = get_tool_storage()

        # 如果没有指定category，使用agent_type作为默认值
        if category is None:
            category = self.agent_type
            logger.debug(f"【子Agent: {self.name}】未指定category，使用agent_type: {category}")

        # 如果没有指定max_rounds，使用该agent类型的默认配置
        if max_rounds is None:
            max_rounds = self.default_max_rounds
            logger.debug(f"【子Agent: {self.name}】未指定max_rounds，使用默认值: {max_rounds}")
        else:
            logger.debug(f"【子Agent: {self.name}】使用指定的max_rounds: {max_rounds}")

        logger.info(f"【子Agent: {self.name}】开始执行任务")
        logger.info(f"任务: {task}")

        # 判断是否为总结任务：如果有previous_tool_results，说明是总结任务
        is_summary_task = previous_tool_results is not None and len(previous_tool_results) > 0

        # 如果有之前的工具调用结果，记录日志
        if previous_tool_results:
            logger.info(f"【子Agent: {self.name}】收到 {len(previous_tool_results)} 个之前的工具调用结果作为上下文")
            logger.info(f"【子Agent: {self.name}】识别为总结任务，不需要调用工具")
            for idx, msg in enumerate(previous_tool_results, 1):
                content_preview = str(msg.content)[:200]
                logger.debug(f"  上下文 {idx}: {content_preview}...")

        # 构建任务提示词
        prompt = self._build_prompt(task, context, previous_tool_results)

        # 多轮对话执行
        task_messages = []
        all_tool_messages = []
        final_response_content = ""

        for round_num in range(1, max_rounds + 1):
            logger.info(f"  [{self.name}] 第{round_num}轮")

            # 构建当前轮消息
            if round_num == 1:
                # 第一轮：构建初始消息
                # 如果有之前的工具结果，将内容提取为文本加入prompt，而不是直接添加ToolMessage
                if previous_tool_results:
                    # 将工具结果内容提取为文本
                    context_info = "\n\n**之前任务的查询结果**：\n"
                    for idx, tool_msg in enumerate(previous_tool_results, 1):
                        tool_name = tool_msg.name if hasattr(tool_msg, 'name') else '未知工具'
                        context_info += f"\n{idx}. [{tool_name}] 查询结果：\n{tool_msg.content}\n"

                    # 将工具结果作为上下文添加到prompt中
                    enhanced_prompt = prompt + context_info
                    current_messages = [HumanMessage(content=enhanced_prompt)]
                else:
                    current_messages = [HumanMessage(content=prompt)]
            else:
                current_messages = task_messages.copy()

            # 调用 LLM
            response = await retry_llm_call(
                self.llm_with_tools.ainvoke,
                current_messages,
                max_retries=1,
                error_context=f"{self.name} 第{round_num}轮"
            )

            if response is None:
                logger.error(f"  [{self.name}] LLM调用失败")
                break

            # 将响应加入历史
            task_messages = current_messages + [response]

            # 保存最后一次响应的内容（用于总结任务）
            if hasattr(response, 'content') and response.content:
                final_response_content = response.content
                logger.debug(f"  [{self.name}] 保存响应内容，长度: {len(final_response_content)}")

            # 检查是否有工具调用
            has_tool_calls = False
            if hasattr(response, 'tool_calls') and response.tool_calls:
                has_tool_calls = True
                logger.info(f"  [{self.name}] 检测到工具调用: {len(response.tool_calls)}个")
            elif "tool_calls" in response.additional_kwargs and response.additional_kwargs['tool_calls']:
                has_tool_calls = True
                logger.info(f"  [{self.name}] 检测到工具调用（旧格式）: {len(response.additional_kwargs['tool_calls'])}个")

            if not has_tool_calls:
                # 如果是总结任务，没有工具调用是正常的
                if is_summary_task:
                    logger.info(f"  [{self.name}] 第{round_num}轮未检测到工具调用（总结任务正常行为），任务完成")
                else:
                    logger.info(f"  [{self.name}] 第{round_num}轮未检测到工具调用，任务完成")
                break

            # 执行工具
            tool_messages = await execute_tool_calls(response, self.tools, logger, category, storage)

            if not tool_messages:
                logger.warning(f"  [{self.name}] 工具执行失败")
                break

            # 收集工具消息
            task_messages.extend(tool_messages)
            all_tool_messages.extend(tool_messages)

            # 保存工具执行结果到JSON文件
            for tool_msg in tool_messages:
                try:
                    tool_name = tool_msg.name if hasattr(tool_msg, 'name') else 'unknown'
                    # 尝试从tool_call_id解析工具输入
                    tool_input = {}
                    if hasattr(response, 'tool_calls'):
                        for tool_call in response.tool_calls:
                            if tool_call.get('id') == tool_msg.tool_call_id:
                                tool_input = tool_call.get('args', {})
                                break

                    storage.save_tool_execution(
                        category=category,
                        tool_name=tool_name,
                        tool_input=tool_input,
                        tool_output=tool_msg.content,
                        context=context,
                        metadata={
                            "task": task,
                            "agent_name": self.name,
                            "round": round_num
                        }
                    )
                except Exception as e:
                    logger.error(f"保存工具执行结果失败: {e}")

            logger.info(f"  [{self.name}] 第{round_num}轮完成，收集到{len(tool_messages)}个工具结果")

            if round_num == max_rounds:
                logger.warning(f"  [{self.name}] 达到最大轮次")
                break

        # 任务完成度检查和额外轮次（仅对查询任务）
        if not is_summary_task:
            logger.info(f"  [{self.name}] 主循环结束，开始检查任务完成度")

            extra_rounds = 2  # 最多额外2轮
            for extra_round in range(1, extra_rounds + 1):
                # 检查任务是否完成
                completion_result = await self._check_task_completion(task, context, all_tool_messages)
                completion_status = completion_result["completed"]
                completion_reason = completion_result["reason"]

                if completion_status == 1:
                    logger.info(f"  [{self.name}] ✓ 任务已完成，无需额外轮次")
                    logger.info(f"  [{self.name}] 完成原因: {completion_reason}")
                    break
                else:
                    logger.info(f"  [{self.name}] ✗ 任务未完成，开始第{extra_round}轮额外工具调用")
                    logger.info(f"  [{self.name}] 未完成原因: {completion_reason}")

                    # 执行额外的工具调用，并将未完成的原因告知LLM
                    current_messages = task_messages.copy()

                    # 添加一条包含未完成原因的提示消息，指导LLM进行补充查询
                    guidance_content = EXTRA_TOOL_CALL_GUIDANCE_PROMPT.format(
                        incomplete_reason=completion_reason
                    )
                    guidance_message = HumanMessage(content=guidance_content)
                    current_messages.append(guidance_message)

                    response = await retry_llm_call(
                        self.llm_with_tools.ainvoke,
                        current_messages,
                        max_retries=1,
                        error_context=f"{self.name} 额外第{extra_round}轮"
                    )

                    if response is None:
                        logger.error(f"  [{self.name}] 额外轮次LLM调用失败")
                        break

                    task_messages = current_messages + [response]

                    # 保存响应内容
                    if hasattr(response, 'content') and response.content:
                        final_response_content = response.content

                    # 检查是否有工具调用
                    has_tool_calls = False
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        has_tool_calls = True
                        logger.info(f"  [{self.name}] 额外第{extra_round}轮检测到工具调用: {len(response.tool_calls)}个")
                    elif "tool_calls" in response.additional_kwargs and response.additional_kwargs['tool_calls']:
                        has_tool_calls = True
                        logger.info(f"  [{self.name}] 额外第{extra_round}轮检测到工具调用（旧格式）: {len(response.additional_kwargs['tool_calls'])}个")

                    if not has_tool_calls:
                        logger.info(f"  [{self.name}] 额外第{extra_round}轮未检测到工具调用，结束额外轮次")
                        break

                    # 执行工具
                    tool_messages = await execute_tool_calls(response, self.tools, logger, category, storage)

                    if not tool_messages:
                        logger.warning(f"  [{self.name}] 额外第{extra_round}轮工具执行失败")
                        break

                    task_messages.extend(tool_messages)
                    all_tool_messages.extend(tool_messages)

                    # 保存工具执行结果到JSON文件
                    for tool_msg in tool_messages:
                        try:
                            tool_name = tool_msg.name if hasattr(tool_msg, 'name') else 'unknown'
                            # 尝试从tool_call_id解析工具输入
                            tool_input = {}
                            if hasattr(response, 'tool_calls'):
                                for tool_call in response.tool_calls:
                                    if tool_call.get('id') == tool_msg.tool_call_id:
                                        tool_input = tool_call.get('args', {})
                                        break

                            storage.save_tool_execution(
                                category=category,
                                tool_name=tool_name,
                                tool_input=tool_input,
                                tool_output=tool_msg.content,
                                context=context,
                                metadata={
                                    "task": task,
                                    "agent_name": self.name,
                                    "round": f"extra_{extra_round}"
                                }
                            )
                        except Exception as e:
                            logger.error(f"保存工具执行结果失败: {e}")

                    logger.info(f"  [{self.name}] 额外第{extra_round}轮完成，收集到{len(tool_messages)}个工具结果")

                    if extra_round == extra_rounds:
                        logger.warning(f"  [{self.name}] 达到额外轮次上限")

            # 两次额外轮次后，再次检查任务完成度
            final_completion_result = await self._check_task_completion(task, context, all_tool_messages)
            final_completion_status = final_completion_result["completed"]
            final_completion_reason = final_completion_result["reason"]

            if final_completion_status == 0:
                logger.warning(f"  [{self.name}] ⚠ 两次额外轮次后任务仍未完成，尝试使用zhipu_search补全信息")
                logger.warning(f"  [{self.name}] 未完成原因: {final_completion_reason}")

                # 构建搜索query（传入未完成的原因）
                search_query = await self._build_fallback_search_query(
                    task, context, all_tool_messages, final_completion_reason
                )
                logger.info(f"  [{self.name}] 构建搜索query: {search_query}")

                # 直接调用zhipu_search函数
                try:
                    from utils.tools import zhipu_search

                    # 调用zhipu_search（同步函数）
                    search_result = zhipu_search.invoke({"query": search_query})

                    # 创建ToolMessage
                    from langchain_core.messages import ToolMessage as LangChainToolMessage
                    search_tool_message = LangChainToolMessage(
                        content=str(search_result),
                        tool_call_id=f"fallback_search_{len(all_tool_messages)}",
                        name="zhipu_search"
                    )

                    all_tool_messages.append(search_tool_message)
                    logger.info(f"  [{self.name}] ✓ zhipu_search补全搜索完成，结果长度: {len(str(search_result))}")

                except Exception as e:
                    logger.error(f"  [{self.name}] ✗ zhipu_search补全搜索失败: {str(e)}")

        # 生成总结
        summary = self._generate_summary(all_tool_messages)

        # 判断任务是否成功：
        # - 查询任务（非总结任务）：需要有工具调用结果
        # - 总结任务：需要有文本响应内容
        if is_summary_task:
            success = bool(final_response_content and len(final_response_content.strip()) > 0)
            logger.info(f"【子Agent: {self.name}】总结任务完成，响应内容长度: {len(final_response_content) if final_response_content else 0}")
            if success:
                logger.info(f"【子Agent: {self.name}】✓ 总结任务成功")
            else:
                logger.warning(f"【子Agent: {self.name}】⚠ 总结任务失败：未生成有效响应内容")
        else:
            success = len(all_tool_messages) > 0
            logger.info(f"【子Agent: {self.name}】查询任务完成，共执行{len(all_tool_messages)}次工具调用")
            if success:
                logger.info(f"【子Agent: {self.name}】✓ 查询任务成功")
            else:
                logger.warning(f"【子Agent: {self.name}】⚠ 查询任务失败：未执行任何工具调用")

        return {
            "success": success,
            "tool_messages": all_tool_messages,
            "summary": summary,
            "agent_name": self.name,
            "is_summary_task": is_summary_task,
            "final_response": final_response_content
        }

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        """构建任务提示词（子类可重写）"""
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return SUB_AGENT_SUMMARY_TASK_PROMPT.format(
                description=self.description,
                task=task,
                origin=context.get('origin', '未知'),
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                people=context.get('people', '未知'),
                budget=context.get('budget', '未知'),
                preferences=context.get('preferences', '未知'),
                num_results=len(previous_tool_results)
            )
        else:
            # 查询任务
            return SUB_AGENT_QUERY_TASK_PROMPT.format(
                description=self.description,
                task=task,
                origin=context.get('origin', '未知'),
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                people=context.get('people', '未知'),
                budget=context.get('budget', '未知'),
                preferences=context.get('preferences', '未知'),
                tools_desc=tools_desc
            )

    async def _check_task_completion(
        self,
        task: str,
        context: Dict[str, Any],
        all_tool_messages: List[ToolMessage]
    ) -> Dict[str, Any]:
        """
        使用模型批判任务是否完成

        Returns:
            {
                "completed": int,  # 0: 未完成, 1: 已完成
                "reason": str      # 完成/未完成的原因
            }
        """
        # 构建工具结果摘要（返回完整内容，不截断）
        tool_results_summary = ""
        if all_tool_messages:
            tool_results_summary = "\n".join([
                f"{idx}. [{msg.name if hasattr(msg, 'name') else '工具'}] {str(msg.content)}"
                for idx, msg in enumerate(all_tool_messages, 1)
            ])
        else:
            tool_results_summary = "（暂无工具调用结果）"

        # 构建判断提示词
        check_prompt = TASK_COMPLETION_CHECK_PROMPT.format(
            task=task,
            origin=context.get('origin', '未知'),
            destination=context.get('destination', '未知'),
            date=context.get('date', '未知'),
            days=context.get('days', '未知'),
            people=context.get('people', '未知'),
            budget=context.get('budget', '未知'),
            preferences=context.get('preferences', '未知'),
            tool_results_summary=tool_results_summary
        )

        check_message = [HumanMessage(content=check_prompt)]

        try:
            response = await retry_llm_call(
                self.llm.ainvoke,
                check_message,
                max_retries=1,
                error_context=f"{self.name} 任务完成度检查"
            )

            if response is None:
                logger.error(f"  [{self.name}] 任务完成度检查失败，默认为已完成")
                return {"completed": 1, "reason": "LLM调用失败，默认为已完成"}

            # 提取响应内容
            result = response.content.strip()
            logger.debug(f"  [{self.name}] 任务完成度检查原始返回: {result}")

            # 解析返回值，格式为 "数字|原因"
            if '|' in result:
                parts = result.split('|', 1)
                status_str = parts[0].strip()
                reason = parts[1].strip() if len(parts) > 1 else ""

                if '0' in status_str:
                    return {"completed": 0, "reason": reason or "任务未完成"}
                elif '1' in status_str:
                    return {"completed": 1, "reason": reason or "任务已完成"}
                else:
                    logger.warning(f"  [{self.name}] 任务完成度检查返回异常状态: {status_str}，默认为已完成")
                    return {"completed": 1, "reason": "返回状态异常，默认为已完成"}
            else:
                # 兼容旧格式（只返回数字）
                if '0' in result:
                    return {"completed": 0, "reason": "任务未完成（未提供详细原因）"}
                elif '1' in result:
                    return {"completed": 1, "reason": "任务已完成"}
                else:
                    logger.warning(f"  [{self.name}] 任务完成度检查返回异常结果: {result}，默认为已完成")
                    return {"completed": 1, "reason": "返回格式异常，默认为已完成"}

        except Exception as e:
            logger.error(f"  [{self.name}] 任务完成度检查异常: {str(e)}，默认为已完成")
            return {"completed": 1, "reason": f"检查异常: {str(e)}，默认为已完成"}

    async def _build_fallback_search_query(
        self,
        task: str,
        context: Dict[str, Any],
        all_tool_messages: List[ToolMessage],
        incomplete_reason: str = ""
    ) -> str:
        """
        构建补全搜索的query

        基于任务描述、上下文、已有的工具调用结果和未完成原因，构建一个合适的搜索query

        Args:
            task: 任务描述
            context: 上下文信息
            all_tool_messages: 已有的工具调用结果
            incomplete_reason: 任务未完成的原因，用于构建更精准的搜索query
        """
        # 提取上下文关键信息
        origin = context.get('origin', '')
        destination = context.get('destination', '')
        date = context.get('date', '')
        budget = context.get('budget', '')

        # 分析任务类型，构建针对性的搜索query
        task_lower = task.lower()
        reason_lower = incomplete_reason.lower() if incomplete_reason else ''

        # 构建基础query部分
        query_parts = []

        # 添加地点信息
        if destination:
            query_parts.append(destination)

        # 根据任务类型添加特定关键词
        if '机票' in task or '航班' in task or 'flight' in task_lower:
            query_parts.extend([origin, '机票', date if date else '2025'])
            # 根据未完成原因添加针对性关键词
            if '价格' in reason_lower:
                query_parts.extend(['价格', '票价', '费用'])
            elif '航班' in reason_lower or '航班号' in reason_lower:
                query_parts.extend(['航班号', '班次'])
            elif '时间' in reason_lower:
                query_parts.extend(['起飞时间', '航班时刻表'])
            else:
                query_parts.extend(['价格', '航班', '时间'])
        elif '火车' in task or '高铁' in task or 'train' in task_lower:
            query_parts.extend([origin, '火车票', '高铁', date if date else '2025'])
            # 根据未完成原因添加针对性关键词
            if '价格' in reason_lower:
                query_parts.extend(['票价', '价格'])
            elif '车次' in reason_lower:
                query_parts.extend(['车次', '班次'])
            elif '时间' in reason_lower:
                query_parts.extend(['发车时间', '列车时刻表'])
            else:
                query_parts.extend(['车次', '价格', '时间'])
        elif '酒店' in task or 'hotel' in task_lower or '住宿' in task:
            query_parts.extend(['酒店', '住宿', date if date else '2025'])
            # 根据未完成原因添加针对性关键词
            if '价格' in reason_lower:
                query_parts.extend(['价格', '房价'])
            elif '位置' in reason_lower or '地址' in reason_lower:
                query_parts.extend(['位置', '地址', '交通'])
            elif '名称' in reason_lower:
                query_parts.extend(['推荐', '酒店名称'])
            else:
                query_parts.extend(['价格', '推荐'])
        elif '天气' in task or 'weather' in task_lower:
            query_parts.extend(['天气', date if date else '2025'])
            # 根据未完成原因添加针对性关键词
            if '温度' in reason_lower:
                query_parts.extend(['温度', '气温'])
            elif '天气状况' in reason_lower or '状况' in reason_lower:
                query_parts.extend(['天气状况', '晴雨'])
            else:
                query_parts.extend(['温度', '天气预报'])
        elif '景点' in task or '旅游' in task or '游览' in task:
            query_parts.extend(['旅游景点', '2025'])
            # 根据未完成原因添加针对性关键词
            if '门票' in reason_lower or '价格' in reason_lower:
                query_parts.extend(['门票价格'])
            elif '时间' in reason_lower or '营业' in reason_lower:
                query_parts.extend(['开放时间', '营业时间'])
            elif '位置' in reason_lower or '地址' in reason_lower:
                query_parts.extend(['位置', '地址'])
            else:
                query_parts.extend(['门票', '开放时间', '推荐'])
        elif '美食' in task or '餐厅' in task or '吃' in task:
            query_parts.extend(['美食', '餐厅', '2025'])
            # 根据未完成原因添加针对性关键词
            if '推荐' in reason_lower:
                query_parts.extend(['推荐', '特色'])
            elif '位置' in reason_lower or '地址' in reason_lower:
                query_parts.extend(['位置', '地址'])
            else:
                query_parts.extend(['推荐', '特色'])
        else:
            # 默认通用搜索
            query_parts.extend(['信息', '推荐', '攻略', '2025'])

        # 添加预算信息
        if budget:
            query_parts.append(f'预算{budget}')

        # 如果未完成原因中有其他有用的关键词，也加入搜索
        if incomplete_reason:
            # 提取未完成原因中的关键信息词
            reason_keywords = []
            if '缺少' in reason_lower:
                # 尝试提取"缺少XX信息"中的XX
                import re
                match = re.search(r'缺少(.{1,10}?)(?:信息|数据|资料)', reason_lower)
                if match:
                    keyword = match.group(1).strip()
                    if keyword and keyword not in ' '.join(query_parts):
                        reason_keywords.append(keyword)

            if reason_keywords:
                query_parts.extend(reason_keywords)
                logger.debug(f"  [{self.name}] 从未完成原因中提取关键词: {reason_keywords}")

        # 组合成搜索query
        search_query = ' '.join([part for part in query_parts if part])

        # 确保query不为空
        if not search_query:
            search_query = f"{destination} {task} 2025"

        logger.debug(f"  [{self.name}] 构建的补全搜索query: {search_query}")
        if incomplete_reason:
            logger.debug(f"  [{self.name}] 基于未完成原因: {incomplete_reason}")
        return search_query

    def _generate_summary(self, tool_messages: List[ToolMessage]) -> str:
        """生成工具调用总结"""
        if not tool_messages:
            return f"{self.name}未执行任何工具调用"

        summary_parts = [f"{self.name}执行了{len(tool_messages)}次工具调用:"]
        for idx, msg in enumerate(tool_messages, 1):
            content_preview = str(msg.content)[:100]
            summary_parts.append(f"  {idx}. {content_preview}...")

        return "\n".join(summary_parts)


class TransportSubAgent(BaseSubAgent):
    """交通子Agent：负责机票、火车票查询"""

    def __init__(self, tools: List[Any]):
        super().__init__(
            name="交通助手",
            description="查询机票、火车票等长距离交通工具",
            tools=tools,
            agent_type="transport"
        )

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        if previous_tool_results:
            return TRANSPORT_AGENT_SUMMARY_TASK_PROMPT.format(
                task=task,
                origin=context.get('origin', '未知'),
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                people=context.get('people', '未知'),
                num_results=len(previous_tool_results)
            )
        else:
            return TRANSPORT_AGENT_QUERY_TASK_PROMPT.format(
                task=task,
                origin=context.get('origin', '未知'),
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                people=context.get('people', '未知'),
                tools_desc=tools_desc
            )


class MapSubAgent(BaseSubAgent):
    """地图子Agent：负责高德地图相关查询"""

    def __init__(self, tools: List[Any]):
        super().__init__(
            name="地图助手",
            description="使用高德地图查询景点、路线、周边信息",
            tools=tools,
            agent_type="map"
        )

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        if previous_tool_results:
            return MAP_AGENT_SUMMARY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                preferences=context.get('preferences', '未知'),
                num_results=len(previous_tool_results)
            )
        else:
            return MAP_AGENT_QUERY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                preferences=context.get('preferences', '未知'),
                tools_desc=tools_desc
            )


class SearchSubAgent(BaseSubAgent):
    """搜索子Agent：负责互联网搜索"""

    def __init__(self, tools: List[Any]):
        super().__init__(
            name="搜索助手",
            description="使用互联网搜索获取最新信息",
            tools=tools,
            agent_type="search"
        )

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        if previous_tool_results:
            return SEARCH_AGENT_SUMMARY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                preferences=context.get('preferences', '未知'),
                num_results=len(previous_tool_results)
            )
        else:
            return SEARCH_AGENT_QUERY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                origin=context.get('origin', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                people=context.get('people', '未知'),
                budget=context.get('budget', '未知'),
                preferences=context.get('preferences', '未知'),
                tools_desc=tools_desc
            )


class FileSubAgent(BaseSubAgent):
    """文件子Agent：负责文件读写操作"""

    def __init__(self, tools: List[Any]):
        super().__init__(
            name="文件助手",
            description="处理文件读写操作",
            tools=tools,
            agent_type="file"
        )

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        if previous_tool_results:
            return FILE_AGENT_SUMMARY_TASK_PROMPT.format(
                task=task,
                num_results=len(previous_tool_results)
            )
        else:
            return FILE_AGENT_QUERY_TASK_PROMPT.format(
                task=task,
                tools_desc=tools_desc
            )


class WeatherSubAgent(BaseSubAgent):
    """天气子Agent：负责天气查询"""

    def __init__(self, tools: List[Any]):
        super().__init__(
            name="天气助手",
            description="查询目的地天气信息",
            tools=tools,
            agent_type="weather"
        )

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        if previous_tool_results:
            return WEATHER_AGENT_SUMMARY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                num_results=len(previous_tool_results)
            )
        else:
            return WEATHER_AGENT_QUERY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                tools_desc=tools_desc
            )


class HotelSubAgent(BaseSubAgent):
    """酒店子Agent：负责酒店查询"""

    def __init__(self, tools: List[Any]):
        super().__init__(
            name="酒店助手",
            description="查询目的地酒店信息",
            tools=tools,
            agent_type="hotel"
        )

    def _build_prompt(self, task: str, context: Dict[str, Any], previous_tool_results: Optional[List[ToolMessage]] = None) -> str:
        tools_desc = "\n".join([
            f"- {tool.name if hasattr(tool, 'name') else str(tool)}: "
            f"{tool.description if hasattr(tool, 'description') else '无描述'}"
            for tool in self.tools
        ])

        if previous_tool_results:
            return HOTEL_AGENT_SUMMARY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                people=context.get('people', '未知'),
                budget=context.get('budget', '未知'),
                num_results=len(previous_tool_results)
            )
        else:
            return HOTEL_AGENT_QUERY_TASK_PROMPT.format(
                task=task,
                destination=context.get('destination', '未知'),
                date=context.get('date', '未知'),
                days=context.get('days', '未知'),
                people=context.get('people', '未知'),
                budget=context.get('budget', '未知'),
                tools_desc=tools_desc
            )


# 子 Agent 工厂函数
async def create_sub_agents(
    tools_by_server: Dict[str, List[Any]],
    local_tools: List[Any] = None
) -> Dict[str, BaseSubAgent]:
    """
    根据 MCP 服务器名称创建对应的子 Agent

    不再使用硬编码的工具名称匹配，而是直接根据 MCP 服务器类型来分类工具。
    例如：12306-mcp 和 flight-ticket-mcp 的所有工具直接绑定给交通助手。

    Args:
        tools_by_server: {server_name: [tools]} 的字典结构
        local_tools: 本地工具列表（如 zhipu_search），默认绑定给搜索助手

    Returns:
        Dict[agent_type, SubAgent实例]
    """
    from config import mcp_to_agent_mapping

    logger.info("开始创建子 Agent...")
    logger.info(f"接收到 {len(tools_by_server)} 个 MCP 服务器的工具")

    # 按 agent 类型分类工具
    tools_by_agent_type = {
        'transport': [],
        'map': [],
        'search': [],
        'file': [],
        'weather': [],
        'hotel': []
    }

    # 根据配置映射，将 MCP 服务器的工具分配给对应的 agent
    for server_name, tools in tools_by_server.items():
        agent_types = mcp_to_agent_mapping.get(server_name)

        if agent_types:
            # 如果是列表，说明一个MCP服务器映射到多个agent
            if isinstance(agent_types, list):
                for agent_type in agent_types:
                    tools_by_agent_type[agent_type].extend(tools)
                    logger.info(f"✓ MCP服务器 [{server_name}] 的 {len(tools)} 个工具 → {agent_type} 助手")
                    for tool in tools:
                        tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                        logger.debug(f"    - {tool_name}")
            else:
                # 单个映射
                tools_by_agent_type[agent_types].extend(tools)
                logger.info(f"✓ MCP服务器 [{server_name}] 的 {len(tools)} 个工具 → {agent_types} 助手")
                for tool in tools:
                    tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                    logger.debug(f"    - {tool_name}")
        else:
            # 未配置映射的 MCP 服务器，默认放到搜索助手
            tools_by_agent_type['search'].extend(tools)
            logger.warning(f"⚠ MCP服务器 [{server_name}] 未配置映射，默认 {len(tools)} 个工具 → search 助手")

    # 将本地工具（如 zhipu_search）添加到搜索助手和交通助手（作为fallback）
    if local_tools:
        tools_by_agent_type['search'].extend(local_tools)
        tools_by_agent_type['transport'].extend(local_tools)
        logger.info(f"✓ 添加 {len(local_tools)} 个本地工具 → search 助手 和 transport 助手（作为fallback）")

    # 创建子 Agent
    sub_agents = {}

    if tools_by_agent_type['transport']:
        sub_agents['transport'] = TransportSubAgent(tools_by_agent_type['transport'])
        logger.info(f"✓ 创建交通助手，绑定工具数: {len(tools_by_agent_type['transport'])}")

    if tools_by_agent_type['map']:
        sub_agents['map'] = MapSubAgent(tools_by_agent_type['map'])
        logger.info(f"✓ 创建地图助手，绑定工具数: {len(tools_by_agent_type['map'])}")

    if tools_by_agent_type['search']:
        sub_agents['search'] = SearchSubAgent(tools_by_agent_type['search'])
        logger.info(f"✓ 创建搜索助手，绑定工具数: {len(tools_by_agent_type['search'])}")

    if tools_by_agent_type['file']:
        sub_agents['file'] = FileSubAgent(tools_by_agent_type['file'])
        logger.info(f"✓ 创建文件助手，绑定工具数: {len(tools_by_agent_type['file'])}")

    if tools_by_agent_type['weather']:
        sub_agents['weather'] = WeatherSubAgent(tools_by_agent_type['weather'])
        logger.info(f"✓ 创建天气助手，绑定工具数: {len(tools_by_agent_type['weather'])}")

    if tools_by_agent_type['hotel']:
        sub_agents['hotel'] = HotelSubAgent(tools_by_agent_type['hotel'])
        logger.info(f"✓ 创建酒店助手，绑定工具数: {len(tools_by_agent_type['hotel'])}")

    logger.info(f"子 Agent 创建完成，共{len(sub_agents)}个")

    return sub_agents
