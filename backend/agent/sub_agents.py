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
from config import get_max_rounds

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
            self.llm = get_llm()
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
        max_rounds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        执行任务

        Args:
            task: 任务描述
            context: 上下文信息（包括 origin, destination, date 等）
            previous_tool_results: 之前任务执行的工具调用结果（用于提供上下文）
            max_rounds: 最大轮次（如果不指定，使用该agent类型的默认配置）

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
            tool_messages = await execute_tool_calls(response, self.tools, logger)

            if not tool_messages:
                logger.warning(f"  [{self.name}] 工具执行失败")
                break

            # 收集工具消息
            task_messages.extend(tool_messages)
            all_tool_messages.extend(tool_messages)

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
                completion_status = await self._check_task_completion(task, context, all_tool_messages)

                if completion_status == 1:
                    logger.info(f"  [{self.name}] ✓ 任务已完成，无需额外轮次")
                    break
                else:
                    logger.info(f"  [{self.name}] ✗ 任务未完成，开始第{extra_round}轮额外工具调用")

                    # 执行额外的工具调用
                    current_messages = task_messages.copy()

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
                    tool_messages = await execute_tool_calls(response, self.tools, logger)

                    if not tool_messages:
                        logger.warning(f"  [{self.name}] 额外第{extra_round}轮工具执行失败")
                        break

                    task_messages.extend(tool_messages)
                    all_tool_messages.extend(tool_messages)

                    logger.info(f"  [{self.name}] 额外第{extra_round}轮完成，收集到{len(tool_messages)}个工具结果")

                    if extra_round == extra_rounds:
                        logger.warning(f"  [{self.name}] 达到额外轮次上限")

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
            return f"""你是一个专门负责{self.description}的助手。

**这是一个总结任务**，你需要基于之前查询任务获得的数据，进行分析、比对、计算或总结。

**任务**: {task}

**上下文信息**:
- 出发地: {context.get('origin', '未知')}
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}
- 人数: {context.get('people', '未知')}
- 预算: {context.get('budget', '未知')}
- 偏好: {context.get('preferences', '未知')}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的原始数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、总结即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责{self.description}的助手。

**任务**: {task}

**上下文信息**:
- 出发地: {context.get('origin', '未知')}
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}
- 人数: {context.get('people', '未知')}
- 预算: {context.get('budget', '未知')}
- 偏好: {context.get('preferences', '未知')}

**可用工具**:
{tools_desc}

**【通用搜索工具使用指导】（如果可用工具有搜索功能）**：
1. **构建具体的搜索关键词**：
   - 使用明确的地点、时间、描述
   - 加入年份获取最新信息
   - 避免模糊表述，使用精确词汇

2. **多维度信息组合**：
   - 价格相关信息：加入"价格"、"费用"、"门票"、"收费"
   - 时间相关信息：加入"开放时间"、"营业时间"、"时长"
   - 评价相关信息：加入"评价"、"评分"、"推荐"、"体验"

3. **搜索结果验证**：
   - 优先选择官方信息和权威来源
   - 注意信息的时效性
   - 多个来源交叉验证

请使用合适的工具完成任务，并返回详细的结果。注意：
1. 仔细选择正确的工具
2. 提供完整的工具参数
3. 如果使用搜索工具，按照上述指导构建精确的query
4. 如果需要多个步骤，请按顺序执行
"""

    async def _check_task_completion(
        self,
        task: str,
        context: Dict[str, Any],
        all_tool_messages: List[ToolMessage]
    ) -> int:
        """
        使用模型批判任务是否完成

        Returns:
            0: 未完成
            1: 已完成
        """
        # 构建工具结果摘要
        tool_results_summary = ""
        if all_tool_messages:
            tool_results_summary = "\n".join([
                f"{idx}. [{msg.name if hasattr(msg, 'name') else '工具'}] {str(msg.content)[:200]}..."
                for idx, msg in enumerate(all_tool_messages, 1)
            ])
        else:
            tool_results_summary = "（暂无工具调用结果）"

        # 构建判断提示词
        check_prompt = f"""请判断以下任务是否已经完成：

**任务**: {task}

**上下文信息**:
- 出发地: {context.get('origin', '未知')}
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}
- 人数: {context.get('people', '未知')}
- 预算: {context.get('budget', '未知')}
- 偏好: {context.get('preferences', '未知')}

**已执行的工具调用结果**:
{tool_results_summary}

请仔细分析任务要求和已有的工具调用结果，判断任务是否完成。

**判断标准**:
1. 任务要求的所有必要信息是否都已经查询到
2. 工具调用返回的结果是否有效（不是错误或空结果）
3. 是否需要更多信息才能完成任务

**重要**：只返回一个数字：
- 返回 0：任务未完成，还需要继续查询或操作
- 返回 1：任务已完成，所有必要信息已获取

请只回复0或1，不要有任何其他内容。"""

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
                return 1

            # 提取响应内容
            result = response.content.strip()
            logger.debug(f"  [{self.name}] 任务完成度检查原始返回: {result}")

            # 解析返回值
            if '0' in result:
                return 0
            elif '1' in result:
                return 1
            else:
                logger.warning(f"  [{self.name}] 任务完成度检查返回异常结果: {result}，默认为已完成")
                return 1

        except Exception as e:
            logger.error(f"  [{self.name}] 任务完成度检查异常: {str(e)}，默认为已完成")
            return 1

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

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return f"""你是一个专门负责【交通查询】的助手，擅长查询机票、火车票等长距离交通工具。

**这是一个总结任务**，你需要基于之前查询任务获得的交通数据，进行分析、比对、计算或总结。

**任务**: {task}

**上下文信息**:
- 出发地: {context.get('origin', '未知')}
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 人数: {context.get('people', '未知')}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的交通数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、推荐即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的交通数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责【交通查询】的助手，擅长查询机票、火车票等长距离交通工具。

**任务**: {task}

**上下文信息**:
- 出发地: {context.get('origin', '未知')}
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 人数: {context.get('people', '未知')}

**可用工具**:
{tools_desc}

**重要的工具使用优先级规则**:
1. **优先使用专用交通工具**：优先使用12306、机票查询等专用工具来查询火车票和机票
2. **搜索工具仅作为fallback**：只有在以下情况下才能使用搜索工具（如fetch、zhipu_search）：
   - 当任务涉及市内接驳交通（地铁、公交、出租车、网约车）时
   - 当任务需要查询车站之间的接驳方案时
   - 当专用工具无法满足查询需求时
3. **禁止滥用搜索工具**：不要用搜索工具来查询火车票或机票信息，这些必须使用专用工具

**【重要】市内交通搜索Query构建指导**：
1. **精确描述接驳需求**：
   - 避免"车站怎么去市区" → 改为"北京南站到天安门广场 地铁路线 时间票价"
   - 避免"机场交通" → 改为"上海浦东国际机场到人民广场 地铁2号线 磁悬浮 对比"

2. **包含具体地点信息**：
   - 起点和终点都要明确（具体车站、机场、景点名称）
   - 加入城市名确保搜索准确性
   - 例如："成都东站到春熙路 地铁 公交 出租车 时间费用对比"

3. **关注实用信息**：
   - 营业时间：首末班车时间
   - 票价：具体费用、优惠政策
   - 时间：路程时长、等车时间
   - 便利性：换乘次数、步行距离

4. **根据人群优化搜索**：
   - 大件行李：查询"行李托运 电梯 无障碍通道"
   - 赶时间：查询"最快路线 高峰期避堵"
   - 预算有限：查询"最便宜路线 经济出行方式"

请使用合适的工具完成交通查询任务。注意：
1. 优先查询火车票（12306工具）
2. 如果没有合适的火车，再查询机票
3. 对于市内接驳交通，使用搜索工具并按照上述指导构建详细query
4. 提供详细的班次、时间、价格信息
5. 考虑用户的预算和出行人数
6. 多种交通方案对比推荐
"""


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

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return f"""你是一个专门负责【地图查询】的助手，擅长使用高德地图查询景点、路线、周边设施等信息。

**这是一个总结任务**，你需要基于之前查询任务获得的地图数据，进行分析、比对、计算或总结。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 偏好: {context.get('preferences', '未知')}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的地图数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、推荐即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的地图数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责【地图查询】的助手，擅长使用高德地图查询景点、路线、周边设施等信息。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 偏好: {context.get('preferences', '未知')}

**可用工具**:
{tools_desc}

请使用高德地图工具完成查询任务。注意：
1. 查询景点信息时提供详细的地址、评分、简介
2. 查询路线时考虑距离和时间
3. 查询周边设施（餐饮、住宿等）时提供多个选项
4. 结合用户偏好推荐合适的地点
"""


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

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return f"""你是一个专门负责【互联网搜索】的助手，擅长查找最新的旅游资讯、攻略、评价等信息。

**这是一个总结任务**，你需要基于之前查询任务获得的搜索数据，进行分析、比对、计算或总结。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 偏好: {context.get('preferences', '未知')}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的搜索数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、总结即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的搜索数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责【互联网搜索】的助手，擅长查找最新的旅游资讯、攻略、评价等信息。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 出发地: {context.get('origin', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}
- 人数: {context.get('people', '未知')}
- 预算: {context.get('budget', '未知')}
- 偏好: {context.get('preferences', '未知')}

**可用工具**:
{tools_desc}

**【重要】搜索Query构建指导**：
1. **使用具体、明确的关键词**：
   - 避免"好玩的地方" → 改为"北京必去景点排名2024"
   - 避免"好吃的" → 改为"上海本地特色餐厅推荐"

2. **结合时间和地点**：
   - 加入年份"2024"、"2025"获取最新信息
   - 明确具体城市名称，不用模糊表述
   - 例如："2024年成都最佳旅游景点排行榜"

3. **使用搜索优化技巧**：
   - 使用引号精确匹配："成都火锅"
   - 使用限定词：成都景点 门票价格 开放时间
   - 组合多个关键词：北京故宫 预约方式 游玩攻略

4. **针对不同信息类型优化搜索**：
   - 攻略类："目的地 + 自由行攻略 + 注意事项"
   - 评价类："景点/餐厅 + 真实评价 + 2024最新"
   - 价格类："门票价格 + 官方价格 + 优惠政策"
   - 路线类："景点之间 + 交通路线 + 时间费用"

5. **结合用户具体需求**：
   - 预算有限：加入"经济型"、"平价"、"性价比高"
   - 家庭出游：加入"亲子"、"适合带小孩"
   - 美食偏好：加入"特色菜"、"正宗"、"本地人推荐"

**搜索策略**：
1. 如果第一次搜索结果不够详细，尝试不同的关键词组合
2. 对于复杂查询，可以分多次搜索不同维度的信息
3. 优先搜索官方信息源和权威旅游网站内容
4. 注意信息的时效性，优先选择最新内容

请使用搜索工具完成信息查询任务，严格按照上述指导构建详细的搜索query。
"""


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

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return f"""你是一个专门负责【文件操作】的助手，擅长读取和写入文件。

**这是一个总结任务**，你需要基于之前查询任务获得的文件数据，进行分析、比对、计算或总结。

**任务**: {task}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的文件数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、总结即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的文件数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责【文件操作】的助手，擅长读取和写入文件。

**任务**: {task}

**可用工具**:
{tools_desc}

请使用文件工具完成任务。注意：
1. 读取文件时检查文件是否存在
2. 写入文件时使用合适的格式
3. 处理可能的文件错误
"""


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

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return f"""你是一个专门负责【天气查询】的助手，擅长查询目的地的天气信息。

**这是一个总结任务**，你需要基于之前查询任务获得的天气数据，进行分析、比对、计算或总结。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的天气数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、总结即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的天气数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责【天气查询】的助手，擅长查询目的地的天气信息。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}

**可用工具**:
{tools_desc}

请使用天气查询工具完成任务。注意：
1. 提供准确的天气预报信息（温度、湿度、降水等）
2. 查询旅行期间多天的天气情况
3. 提供穿衣建议和出行提醒
4. 关注极端天气预警
"""


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

        # 如果有之前的工具调用结果，说明这是总结任务
        if previous_tool_results:
            return f"""你是一个专门负责【酒店查询】的助手，擅长查询目的地的酒店住宿信息。

**这是一个总结任务**，你需要基于之前查询任务获得的酒店数据，进行分析、比对、计算或总结。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}
- 人数: {context.get('people', '未知')}
- 预算: {context.get('budget', '未知')}

**重要说明**：
1. 这是一个总结任务，**不需要调用任何工具**
2. 之前的查询任务已经获取了所需的酒店数据（共{len(previous_tool_results)}个结果）
3. 你只需要基于这些数据进行分析、比对、推荐即可
4. 直接用文字回答即可，无需调用工具

请基于之前查询的酒店数据，完成总结任务。
"""
        else:
            # 查询任务
            return f"""你是一个专门负责【酒店查询】的助手，擅长查询目的地的酒店住宿信息。

**任务**: {task}

**上下文信息**:
- 目的地: {context.get('destination', '未知')}
- 日期: {context.get('date', '未知')}
- 天数: {context.get('days', '未知')}
- 人数: {context.get('people', '未知')}
- 预算: {context.get('budget', '未知')}

**可用工具**:
{tools_desc}

请使用酒店查询工具完成任务。注意：
1. 提供详细的酒店信息（位置、价格、评分、设施等）
2. 考虑用户的预算和人数需求
3. 推荐多个不同档次的酒店选项
4. 提供酒店周边的交通和景点信息
5. 考虑入住日期和天数计算总费用
"""


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
