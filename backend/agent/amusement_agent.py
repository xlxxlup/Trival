import asyncio
import uuid
import logging
import operator
import json
from typing import TypedDict, Annotated, Literal, Optional, List
from pydantic import Field

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage,ToolMessage,AnyMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

from utils import get_llm, get_mcp_tools
from utils.agent_tools import retry_llm_call
from utils.tools import tavily_search
from config import trival_mcp_config


from prompts import AMUSEMENT_SYSTEM_PLAN_TEMPLATE,AMUSEMENT_SYSYRM_REPLAN_TEMPLATE,AMUSEMENT_SYSTEM_JUDGE_TEMPLATE,AMUSEMENT_SUMMARY_PROMPT,AMUSEMENT_COORDINATOR_TASK_DISPATCH_TEMPLATE
from formatters import ReplanFormat,PlanFormat
from formatters.amusement_format import AmusementFormat, PlanWithIntervention, ReplanWithIntervention, InterventionResponse
from agent.sub_agents import create_sub_agents

# 使用agent专用的logger
logger = logging.getLogger("agent.amusement")
_mcp_trival_tools = None
_llm = None

class AmusementState(TypedDict):
    origin: Annotated[str, Field(description="出发地")]
    destination: Annotated[str, Field(description="目的地")]
    date: Annotated[str, Field(description="出发日期，格式为YYYY-MM-DD")]
    days: Annotated[int, Field(description="旅行天数")]
    people: Annotated[int, Field(description="出行人数")]
    budget: Annotated[float, Field(description="预算")]
    preferences: Annotated[str, Field(description="用户偏好")]
    messages: Annotated[list[BaseMessage], add_messages, Field("整个助手的上下文信息")]
    plan: Annotated[PlanFormat, Field(description="规划")]
    replan: Annotated[ReplanFormat, Field(description="优化后的规划")]
    amusement_info: Annotated[AmusementFormat, Field(description="旅游攻略信息")]
    # 人工介入相关状态
    need_intervention: Annotated[bool, Field(description="是否需要人工介入", default=False)]
    intervention_stage: Annotated[str, Field(description="介入阶段: plan/replan", default="")]
    intervention_request: Annotated[dict, Field(description="人工介入请求信息", default=None)]
    intervention_response: Annotated[dict, Field(description="用户的人工介入响应", default=None)]
    intervention_count: Annotated[int, Field(description="人工介入次数计数", default=0)]
    # 用户偏好收集追踪
    collected_info: Annotated[dict, Field(description="已收集的用户信息和偏好，避免重复提问", default={})]
    # Execute阶段任务追踪
    executed_tasks: Annotated[list[str], Field(description="已执行的任务列表，用于避免重复执行", default=[])]
    current_task_index: Annotated[int, Field(description="当前执行到第几条任务", default=0)]
    # Observation结果
    observation_result: Annotated[dict, Field(description="Observation阶段的判断结果，包含缺失项和建议", default=None)]
# 获取mcp工具
async def get_mcp_trival_tools():
    """
    获取 MCP 工具字典

    Returns:
        dict: {server_name: [tools]} 的字典结构
    """
    global _mcp_trival_tools
    if _mcp_trival_tools is None:
        # 只在第一次调用时执行
        logger.info("首次加载MCP工具...")
        try:
            _mcp_trival_tools = await get_mcp_tools(trival_mcp_config, timeout=30)
            total_count = sum(len(tools) for tools in _mcp_trival_tools.values())
            logger.info(f"MCP工具加载完成，获取到 {total_count} 个工具，来自 {len(_mcp_trival_tools)} 个服务器")
        except Exception as e:
            logger.error(f"加载MCP工具时出错: {type(e).__name__}: {str(e)}")
            logger.warning("将使用空的MCP工具字典，仅保留本地工具")
            _mcp_trival_tools = {}

    return _mcp_trival_tools
async def get_local_llm():
    global _llm
    if _llm is None:
        # 只在第一次调用时执行
        _llm = get_llm()
    return _llm

async def compress_messages(messages: list[BaseMessage], max_messages: int = 15) -> list[BaseMessage]:
    """
    智能压缩消息历史，避免上下文过长导致重要信息丢失

    策略：
    1. 保留所有ToolMessage（工具调用结果很重要，不能丢失）
    2. 保留最近的N条其他消息（HumanMessage、AIMessage等）
    3. 如果超过阈值，使用LLM总结早期的非工具消息

    Args:
        messages: 原始消息列表
        max_messages: 保留的最大消息数（不包括工具消息和总结）

    Returns:
        压缩后的消息列表
    """
    if not messages:
        return []

    if len(messages) <= max_messages:
        logger.debug(f"消息数量({len(messages)})未超过阈值({max_messages})，无需压缩")
        return messages

    logger.info(f"开始压缩消息历史：原始消息数={len(messages)}，阈值={max_messages}")

    # 分类消息：工具消息 vs 其他消息
    tool_messages = []
    other_messages = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_messages.append(msg)
        else:
            other_messages.append(msg)

    logger.debug(f"消息分类：ToolMessage={len(tool_messages)}，其他消息={len(other_messages)}")

    # 如果其他消息不多，直接返回所有消息
    if len(other_messages) <= max_messages:
        logger.debug("其他消息数量未超过阈值，保留所有消息")
        return messages

    # 保留最近的消息
    recent_count = max(5, max_messages // 2)  # 至少保留5条最近消息
    recent_other = other_messages[-recent_count:]
    old_other = other_messages[:-recent_count]

    logger.info(f"将总结{len(old_other)}条旧消息，保留{len(recent_other)}条最近消息")

    # 使用LLM总结旧消息
    try:
        llm = await get_local_llm()

        # 构建总结prompt
        old_messages_text = "\n\n".join([
            f"[{type(msg).__name__}] {msg.content[:500]}"
            for msg in old_other
        ])
        prompt = AMUSEMENT_SUMMARY_PROMPT.format(old_messages=old_messages_text)

        logger.debug(f"调用LLM总结消息，prompt长度={len(prompt)}")
        summary_response = await retry_llm_call(
            llm.ainvoke,
            [HumanMessage(content=prompt)],
            max_retries=1,
            error_context="消息总结"
        )

        if summary_response is None:
            logger.warning("消息总结失败，将使用原始消息")
            return messages  # 返回原始消息，不进行压缩

        summary_content = summary_response.content

        logger.info(f"✅ 消息总结完成，总结长度={len(summary_content)}")
        logger.debug(f"总结内容预览：{summary_content[:200]}...")

        # 创建总结消息
        summary_msg = SystemMessage(content=f"【历史对话总结】\n{summary_content}")

        # 组合消息：总结 + 所有工具消息 + 最近消息
        compressed = [summary_msg] + tool_messages + recent_other

        logger.info(f"✅ 消息压缩完成：{len(messages)} → {len(compressed)} (总结1条 + 工具{len(tool_messages)}条 + 最近{len(recent_other)}条)")

        return compressed

    except Exception as e:
        logger.error(f"消息总结失败: {type(e).__name__}: {str(e)}")
        logger.warning("将使用简单截断策略作为降级方案")
        # 降级方案：保留工具消息和最近的消息
        return tool_messages + other_messages[-max_messages:]
async def plan(state:AmusementState)->AmusementState:
    logger.info("=" * 80)
    logger.info("【PLAN阶段开始】旅游智能体开始规划...")
    logger.info(f"输入参数: 出发地={state['origin']}, 目的地={state['destination']}, 日期={state['date']}, 天数={state['days']}, 人数={state['people']}, 预算={state['budget']}")
    logger.debug(f"用户偏好: {state['preferences']}")
    logger.info(f"当前人工介入次数: {state.get('intervention_count', 0)}")

    # 获取当前已收集信息
    collected_info = state.get("collected_info", {})
    if "asked_questions" not in collected_info:
        collected_info["asked_questions"] = []
    logger.debug(f"当前已询问问题数: {len(collected_info['asked_questions'])}")

    # 如果有人工介入响应，将答案合并到最近的问题中
    if state.get("intervention_response") and collected_info.get("asked_questions"):
        intervention_resp = state["intervention_response"]
        logger.info("检测到人工介入响应，开始处理用户反馈...")
        logger.debug(f"人工介入响应内容: {json.dumps(intervention_resp, ensure_ascii=False, indent=2)}")

        # 找到最后一个未回答的问题
        last_question = None
        for q in reversed(collected_info["asked_questions"]):
            if "answer" not in q or q["answer"] is None:
                last_question = q
                break

        if last_question:
            # 保存用户的回答
            answer_parts = []
            if intervention_resp.get("text_input"):
                answer_parts.append(f"文本: {intervention_resp['text_input']}")
            if intervention_resp.get("selected_options"):
                answer_parts.append(f"选择: {', '.join(intervention_resp['selected_options'])}")

            last_question["answer"] = "; ".join(answer_parts) if answer_parts else "用户已确认"
            logger.info(f"✓ 已将用户回答记录到问题: {last_question['question'][:50]}...")
            logger.debug(f"完整答案: {last_question['answer']}")

            # 添加到messages
            human_msg = HumanMessage(content=f"用户回答了问题「{last_question['question'][:100]}」：{last_question['answer']}")
            state["messages"].append(human_msg)

    logger.info("正在初始化LLM...")
    llm = await get_local_llm()

    # Plan阶段不需要绑定工具，只需要生成结构化的规划
    # 工具调用在execute阶段进行
    logger.info("Plan阶段：不绑定工具，专注于生成结构化规划")

    # 使用PlanWithIntervention格式，让LLM自主判断是否需要人工介入
    parser = JsonOutputParser(pydantic_object = PlanWithIntervention)

    # 格式化已询问的问题列表，清晰展示给LLM
    if collected_info.get("asked_questions"):
        qa_list = []
        for idx, qa in enumerate(collected_info["asked_questions"], 1):
            answer = qa.get("answer", "【尚未回答】")
            qa_list.append(f"{idx}. 问题: {qa['question']}\n   回答: {answer}")
        collected_info_str = "已询问的问题和回答：\n" + "\n".join(qa_list)
        logger.debug(f"已格式化 {len(collected_info['asked_questions'])} 个问题传递给LLM")
    else:
        collected_info_str = "尚未询问任何问题"

    # 格式化observation反馈（如果有）
    observation_result = state.get("observation_result")
    if observation_result and not observation_result.get("satisfied", True):
        observation_feedback = "**上一轮执行存在以下问题：**\n\n"
        observation_feedback += "缺失项：\n"
        for item in observation_result.get("missing_items", []):
            observation_feedback += f"- {item}\n"
        observation_feedback += "\n建议：\n"
        for suggestion in observation_result.get("suggestions", []):
            observation_feedback += f"- {suggestion}\n"
        logger.info("检测到observation反馈，将传递给LLM进行增量规划")
        logger.debug(f"Observation反馈内容: {observation_feedback}")
    else:
        observation_feedback = "无（首次规划或上一轮已完成）"

    prompt = PromptTemplate(
            template = AMUSEMENT_SYSTEM_PLAN_TEMPLATE,
            input_variables=["origin","destination","date","days","people","budget","preferences","plan","replan","collected_info","observation_feedback","messages"],
            partial_variables={"json_format":parser.get_format_instructions()},
    )
    chain = prompt | llm | parser

    # 使用智能消息压缩，避免丢失重要信息
    logger.info("开始压缩消息历史...")
    recent_messages = await compress_messages(state.get("messages", []), max_messages=15)
    logger.info(f"消息压缩完成，最终消息数: {len(recent_messages)}")

    input_data = {
        "origin": state["origin"],
        "destination": state["destination"],
        "date": state["date"],
        "days": state["days"],
        "people": state["people"],
        "budget": state["budget"],
        "preferences": state["preferences"],
        "plan": state.get("plan", []),
        "replan": state.get("replan", []),
        "collected_info": collected_info_str,
        "observation_feedback": observation_feedback,
        "messages": recent_messages
    }

    logger.info("🤖 开始调用LLM生成规划...")
    logger.debug(f"Prompt模板变量: origin={state['origin']}, destination={state['destination']}, budget={state['budget']}")

    # 【新增】记录完整的输入信息到日志
    formatted_prompt = prompt.format(**input_data)
    logger.debug("=" * 80)
    logger.debug("【LLM输入信息 - Plan阶段】")
    logger.debug(f"完整Prompt:\n{formatted_prompt}")
    logger.debug("=" * 80)

    response = await retry_llm_call(
        chain.ainvoke,
        input_data,
        max_retries=1,
        error_context="Plan阶段生成规划"
    )

    if response is None:
        logger.error("Plan阶段LLM调用失败（重试后仍失败）")
        logger.warning("将请求人工介入以获取更多信息")
        response = {
            "overview": ["系统在生成规划时遇到问题"],
            "actionable_tasks": [],
            "need_intervention": True,
            "intervention_request": {
                "message": "系统在生成规划时遇到问题，请提供更详细的出行偏好和需求。",
                "question_type": "preferences",
                "options": ["文化历史游览", "自然风光", "美食体验", "休闲放松", "冒险刺激"],
                "allow_text_input": True
            }
        }
        logger.info("已生成默认的人工介入请求")

    logger.info("✅ LLM响应完成")
    logger.debug(f"Plan阶段LLM完整响应: {json.dumps(response, ensure_ascii=False, indent=2)}")

    # 处理新旧格式
    overview = response.get('overview', [])
    actionable_tasks = response.get('actionable_tasks', [])

    # 如果是旧格式（只有plan字段），将其全部视为overview
    if not overview and not actionable_tasks and 'plan' in response:
        logger.warning("检测到旧格式响应（只有plan字段），将其视为混合格式")
        old_plan = response['plan']
        # 简单判断：包含"Execute阶段"的视为actionable_tasks
        overview = [p for p in old_plan if "Execute阶段" not in p and "查询" not in p and "搜索" not in p]
        actionable_tasks = [p for p in old_plan if "Execute阶段" in p or "查询" in p or "搜索" in p]

    logger.info(f"生成的概述步骤数: {len(overview)}")
    logger.info(f"生成的可执行任务数: {len(actionable_tasks)}")
    logger.info(f"概述内容: {overview}")
    logger.info(f"可执行任务: {actionable_tasks}")
    logger.info(f"是否需要人工介入: {response.get('need_intervention', False)}")
    logger.info(f"人工介入请求: {response.get('intervention_request', None)}")
    # 如果需要人工介入，记录问题（不限制次数，让LLM自己判断）
    intervention_count = state.get("intervention_count", 0)
    if response.get('need_intervention', False):
        intervention_count += 1
        intervention_req = response.get('intervention_request')
        logger.warning(f"⚠️  LLM判断需要人工介入（第{intervention_count}次）")
        logger.info(f"介入原因: {intervention_req.get('message') if intervention_req else '未提供'}")
        logger.debug(f"完整介入请求: {json.dumps(intervention_req, ensure_ascii=False, indent=2) if intervention_req else 'None'}")

        # 将这个问题记录到asked_questions中
        if intervention_req:
            new_question = {
                "question": intervention_req.get('message', ''),
                "question_type": intervention_req.get('question_type', ''),
                "stage": "plan",
                "answer": None  # 尚未回答
            }
            collected_info["asked_questions"].append(new_question)
            logger.info(f"✓ 已记录新问题到历史，当前总问题数: {len(collected_info['asked_questions'])}")
    else:
        logger.info("✓ 不需要人工介入，流程将继续")

    # 重置人工介入状态，保留collected_info
    result = {
        "plan": {
            "overview": overview,
            "actionable_tasks": actionable_tasks
        },
        "need_intervention": response.get('need_intervention', False),
        "intervention_request": response.get('intervention_request'),
        "intervention_stage": "plan" if response.get('need_intervention', False) else "",
        "intervention_response": None,
        "intervention_count": intervention_count,
        "collected_info": collected_info,  # 保留已收集信息（包含问题历史）
        "executed_tasks": [],  # 重置已执行任务列表，因为plan重新规划了
        "current_task_index": 0  # 重置任务索引
    }

    logger.info("【PLAN阶段结束】")
    logger.info("=" * 80)
    return result

async def excute(state :AmusementState)->AmusementState:
    logger.info("=" * 80)
    logger.info("【EXECUTE阶段开始 - 多Agent系统】父Agent协调子Agent按类别执行任务...")

    # 从state中获取plan数据，兼容新旧格式
    plan_data = state.get("plan", [])

    # 判断plan是字典还是列表
    if isinstance(plan_data, dict):
        # 新格式：包含overview和actionable_tasks
        overview = plan_data.get("overview", [])
        actionable_tasks = plan_data.get("actionable_tasks", [])
        logger.info(f"新格式Plan - 概述: {len(overview)}条, 任务类别数: {len(actionable_tasks)}个")
        logger.debug(f"概述内容: {overview}")

        # 检查是否是分类格式
        if actionable_tasks and isinstance(actionable_tasks[0], dict) and "category" in actionable_tasks[0]:
            # 新的分类格式
            logger.info("检测到新的分类任务格式")
            task_categories = actionable_tasks
        else:
            # 旧的简单列表格式，转换为单一类别
            logger.warning("检测到旧的简单列表格式，转换为单一类别处理")
            task_categories = [{
                "category": "general",
                "tasks": actionable_tasks,
                "summary_task": None
            }]
    else:
        # 最旧格式：plan是列表，转换为单一类别
        logger.warning("检测到最旧格式Plan（列表），将全部作为单一类别处理")
        task_categories = [{
            "category": "general",
            "tasks": plan_data,
            "summary_task": None
        }]

    if not task_categories:
        logger.warning("⚠️  没有可执行任务类别，跳过Execute阶段")
        return {"messages": [AIMessage(content="没有需要执行的任务")]}

    # 获取已执行的任务列表，避免重复执行
    executed_tasks = state.get("executed_tasks", [])
    logger.info(f"已执行任务数: {len(executed_tasks)}")

    # 统计总任务数
    total_tasks = sum(len(cat.get("tasks", [])) + (1 if cat.get("summary_task") else 0) for cat in task_categories)
    logger.info(f"总任务数: {total_tasks}, 已执行: {len(executed_tasks)}")

    # 初始化工具和子Agent
    logger.info("正在初始化工具和子Agent...")
    tools_by_server = await get_mcp_trival_tools()

    total_mcp_tools = sum(len(tools) for tools in tools_by_server.values())
    logger.info(f"已获取 {total_mcp_tools} 个MCP工具，来自 {len(tools_by_server)} 个服务器")

    # 创建子Agent，传入 MCP 工具字典和本地工具列表
    logger.info("开始创建子Agent...")
    sub_agents = await create_sub_agents(
        tools_by_server=tools_by_server,
        local_tools=[tavily_search]  # 本地工具列表
    )
    logger.info(f"✓ 子Agent创建完成，共 {len(sub_agents)} 个")

    # 生成子Agent信息描述
    sub_agents_info_list = []
    for agent_type, agent in sub_agents.items():
        sub_agents_info_list.append(f"- **{agent_type}** ({agent.name}): {agent.description}")
    sub_agents_info = "\n".join(sub_agents_info_list)
    logger.debug(f"子Agent列表:\n{sub_agents_info}")

    # 初始化父Agent的LLM（用于任务分发）
    llm = await get_local_llm()

    # 准备上下文信息
    context = {
        "origin": state['origin'],
        "destination": state['destination'],
        "date": state['date'],
        "days": state['days'],
        "people": state['people'],
        "budget": state['budget'],
        "preferences": state['preferences']
    }

    # 按类别逐个执行任务（父Agent分发，子Agent执行）
    all_tool_messages = []  # 收集所有工具调用的结果
    new_executed_tasks = executed_tasks.copy()

    total_executed_count = 0  # 本轮实际执行的任务计数

    for category_idx, category in enumerate(task_categories, 1):
        category_name = category.get("category", f"category_{category_idx}")
        tasks = category.get("tasks", [])
        summary_task = category.get("summary_task")

        logger.info("=" * 80)
        logger.info(f"【类别 {category_idx}/{len(task_categories)}: {category_name}】")
        logger.info(f"查询任务数: {len(tasks)}, 总结任务: {'有' if summary_task else '无'}")
        logger.info("=" * 80)

        # 该类别的工具调用结果（用于传递给summary_task）
        category_tool_messages = []

        # 执行该类别的所有查询任务
        for task_idx, task in enumerate(tasks, 1):
            # 检查是否已执行
            if task in executed_tasks:
                logger.info(f"⏭ 任务{task_idx}/{len(tasks)}已执行，跳过: {task[:50]}...")
                continue

            logger.info("-" * 80)
            logger.info(f"【类别{category_name} - 查询任务 {task_idx}/{len(tasks)}】")
            logger.info(f"任务内容: {task}")
            logger.info("-" * 80)

            # 执行任务
            tool_messages = await _execute_single_task(
                task=task,
                context=context,
                sub_agents=sub_agents,
                sub_agents_info=sub_agents_info,
                llm=llm,
                previous_tool_results=None,  # 查询任务不需要之前的结果
                task_identifier=f"{category_name}-query-{task_idx}"
            )

            # 收集该任务的工具调用结果
            if tool_messages:
                category_tool_messages.extend(tool_messages)
                all_tool_messages.extend(tool_messages)
                logger.info(f"✓ 收集到 {len(tool_messages)} 个工具结果")

            # 标记任务已执行
            new_executed_tasks.append(task)
            total_executed_count += 1

        # 执行该类别的总结任务（如果有）
        if summary_task:
            # 检查是否已执行
            if summary_task in executed_tasks:
                logger.info(f"⏭ 总结任务已执行，跳过: {summary_task[:50]}...")
            else:
                logger.info("-" * 80)
                logger.info(f"【类别{category_name} - 总结任务】")
                logger.info(f"任务内容: {summary_task}")
                logger.info(f"可用上下文: 该类别的 {len(category_tool_messages)} 个工具调用结果")
                logger.info("-" * 80)

                # 总结任务可以访问该类别所有查询任务的工具调用结果
                tool_messages = await _execute_single_task(
                    task=summary_task,
                    context=context,
                    sub_agents=sub_agents,
                    sub_agents_info=sub_agents_info,
                    llm=llm,
                    previous_tool_results=category_tool_messages,  # 传递该类别的所有工具结果
                    task_identifier=f"{category_name}-summary"
                )

                # 收集总结任务的结果
                if tool_messages:
                    all_tool_messages.extend(tool_messages)
                    logger.info(f"✓ 收集到 {len(tool_messages)} 个工具结果")

                # 标记任务已执行
                new_executed_tasks.append(summary_task)
                total_executed_count += 1

        logger.info(f"【类别 {category_name} 完成】收集到该类别工具消息数: {len(category_tool_messages)}")

    logger.info("=" * 80)
    logger.info(f"【EXECUTE阶段结束 - 多Agent系统】")
    logger.info(f"  - 共执行任务类别数: {len(task_categories)}")
    logger.info(f"  - 本轮执行任务数: {total_executed_count}")
    logger.info(f"  - 累计已执行任务数: {len(new_executed_tasks)}")
    logger.info(f"  - 收集到工具消息数: {len(all_tool_messages)}")
    logger.info(f"  - 参与的子Agent数: {len(sub_agents)}")
    logger.info("=" * 80)

    # 返回所有工具消息和更新的executed_tasks
    return {
        "messages": all_tool_messages,  # 只返回工具消息，供replan使用
        "executed_tasks": new_executed_tasks
    }

async def _execute_single_task(
    task: str,
    context: dict,
    sub_agents: dict,
    sub_agents_info: str,
    llm,
    previous_tool_results: Optional[List[ToolMessage]],
    task_identifier: str
) -> List[ToolMessage]:
    """
    执行单个任务的辅助函数

    Args:
        task: 任务描述
        context: 上下文信息
        sub_agents: 子Agent字典
        sub_agents_info: 子Agent描述信息
        llm: LLM实例
        previous_tool_results: 之前的工具调用结果（用于总结任务）
        task_identifier: 任务标识符（用于日志）

    Returns:
        该任务执行产生的ToolMessage列表
    """
    logger.info(f"【父Agent】正在分析任务，决定分配给哪个子Agent...")

    dispatch_prompt = AMUSEMENT_COORDINATOR_TASK_DISPATCH_TEMPLATE.format(
        task=task,
        origin=context['origin'],
        destination=context['destination'],
        date=context['date'],
        days=context['days'],
        people=context['people'],
        budget=context['budget'],
        preferences=context['preferences'],
        sub_agents_info=sub_agents_info
    )

    logger.debug(f"任务分发Prompt:\n{dispatch_prompt}")

    # 调用LLM进行任务分发决策
    dispatch_response = await retry_llm_call(
        llm.ainvoke,
        [HumanMessage(content=dispatch_prompt)],
        max_retries=1,
        error_context=f"父Agent任务分发-{task_identifier}"
    )

    if dispatch_response is None:
        logger.error(f"【父Agent】任务分发失败，跳过任务: {task}")
        return []

    # 解析分发决策
    try:
        dispatch_text = dispatch_response.content.strip()
        logger.debug(f"【父Agent】分发决策原始响应: {dispatch_text}")

        # 尝试提取JSON
        if '```json' in dispatch_text:
            json_start = dispatch_text.find('```json') + 7
            json_end = dispatch_text.find('```', json_start)
            json_text = dispatch_text[json_start:json_end].strip()
        elif '```' in dispatch_text:
            json_start = dispatch_text.find('```') + 3
            json_end = dispatch_text.find('```', json_start)
            json_text = dispatch_text[json_start:json_end].strip()
        elif '{' in dispatch_text:
            json_start = dispatch_text.find('{')
            json_end = dispatch_text.rfind('}') + 1
            json_text = dispatch_text[json_start:json_end]
        else:
            json_text = dispatch_text

        dispatch_decision = json.loads(json_text)
        selected_agent_type = dispatch_decision.get('selected_agent', 'search')
        reason = dispatch_decision.get('reason', '未提供原因')

        logger.info(f"【父Agent】决定将任务分配给: {selected_agent_type}")
        logger.info(f"【父Agent】分配原因: {reason}")

    except Exception as e:
        logger.error(f"【父Agent】解析分发决策失败: {e}")
        logger.warning(f"【父Agent】使用默认策略：根据关键词分配")

        # 降级策略：基于关键词简单判断
        task_lower = task.lower()
        if any(keyword in task_lower for keyword in ['火车', '高铁', '动车', '机票', '航班', '车票', '交通']):
            selected_agent_type = 'transport'
        elif any(keyword in task_lower for keyword in ['天气', '气温', '降水', '降雨', '下雨', '晴天', '阴天', '气候', '温度']):
            selected_agent_type = 'weather'
        elif any(keyword in task_lower for keyword in ['酒店', '住宿', '宾馆', '旅馆', '民宿', '客栈', '入住']):
            selected_agent_type = 'hotel'
        elif any(keyword in task_lower for keyword in ['景点', 'poi', '地图', '路线', '餐厅', '酒吧', '周边']):
            selected_agent_type = 'map'
        elif any(keyword in task_lower for keyword in ['文件', '保存', '读取', '写入']):
            selected_agent_type = 'file'
        else:
            selected_agent_type = 'search'

        logger.info(f"【父Agent】降级策略选择: {selected_agent_type}")

    # 获取对应的子Agent并执行任务
    if selected_agent_type not in sub_agents:
        logger.warning(f"【父Agent】未找到子Agent类型 {selected_agent_type}，使用search作为默认")
        selected_agent_type = 'search' if 'search' in sub_agents else list(sub_agents.keys())[0]

    selected_sub_agent = sub_agents[selected_agent_type]
    logger.info(f"【子Agent: {selected_sub_agent.name}】开始执行任务...")

    # 调用子Agent执行任务
    try:
        result = await selected_sub_agent.execute_task(
            task=task,
            context=context,
            previous_tool_results=previous_tool_results,  # 传递之前的工具调用结果（仅总结任务有值）
            max_rounds=None  # 使用子Agent配置的默认max_rounds
        )

        if result['success']:
            logger.info(f"【子Agent: {selected_sub_agent.name}】✓ 任务执行成功")
            logger.info(f"【子Agent: {selected_sub_agent.name}】收集到 {len(result['tool_messages'])} 个工具结果")
            logger.debug(f"【子Agent: {selected_sub_agent.name}】总结: {result['summary']}")
            return result['tool_messages']
        else:
            logger.warning(f"【子Agent: {selected_sub_agent.name}】⚠️  任务执行未成功")
            return []

    except Exception as e:
        logger.error(f"【子Agent: {selected_sub_agent.name}】执行任务时出错: {e}")
        logger.exception(e)
        return []

async def replan(state:AmusementState)->AmusementState:
    logger.info("=" * 80)
    logger.info("【REPLAN阶段开始】旅游智能体重新规划并生成旅游攻略...")
    logger.info(f"输入参数: 目的地={state['destination']}, 天数={state['days']}, 预算={state['budget']}, 人数={state['people']}")

    # 处理plan格式（新旧兼容）
    plan_data = state.get('plan', [])
    if isinstance(plan_data, dict):
        # 新格式
        overview = plan_data.get('overview', [])
        actionable_tasks = plan_data.get('actionable_tasks', [])
        logger.debug(f"当前规划（新格式） - 概述: {overview}, 可执行任务: {actionable_tasks}")
        # 合并用于显示
        plan_for_display = overview + actionable_tasks
    else:
        # 旧格式
        plan_for_display = plan_data
        logger.debug(f"当前规划（旧格式）: {plan_for_display}")

    logger.info(f"当前人工介入次数: {state.get('intervention_count', 0)}")

    # 打印工具调用结果（仅ToolMessage）
    for msg in state.get("messages", []):
        if isinstance(msg, ToolMessage):
            logger.info(f"🔧 工具调用结果: {msg.content[:500]}..." if len(str(msg.content)) > 500 else f"🔧 工具调用结果: {msg.content}")

    # 获取当前已收集信息
    collected_info = state.get("collected_info", {})
    if "asked_questions" not in collected_info:
        collected_info["asked_questions"] = []
    logger.debug(f"当前已询问问题数: {len(collected_info['asked_questions'])}")

    # 如果有人工介入响应，将答案合并到最近的问题中
    if state.get("intervention_response") and collected_info.get("asked_questions"):
        intervention_resp = state["intervention_response"]
        logger.info("检测到人工介入响应，开始处理用户反馈...")
        logger.debug(f"人工介入响应内容: {json.dumps(intervention_resp, ensure_ascii=False, indent=2)}")

        # 找到最后一个未回答的问题
        last_question = None
        for q in reversed(collected_info["asked_questions"]):
            if "answer" not in q or q["answer"] is None:
                last_question = q
                break

        if last_question:
            # 保存用户的回答
            answer_parts = []
            if intervention_resp.get("text_input"):
                answer_parts.append(f"文本: {intervention_resp['text_input']}")
            if intervention_resp.get("selected_options"):
                answer_parts.append(f"选择: {', '.join(intervention_resp['selected_options'])}")

            last_question["answer"] = "; ".join(answer_parts) if answer_parts else "用户已确认"
            logger.info(f"✓ 已将用户回答记录到问题: {last_question['question'][:50]}...")
            logger.debug(f"完整答案: {last_question['answer']}")

            # 添加到messages
            human_msg = HumanMessage(content=f"用户回答了问题「{last_question['question'][:100]}」：{last_question['answer']}")
            state["messages"].append(human_msg)

    logger.info("正在初始化LLM...")
    llm = await get_local_llm()

    # Replan阶段不需要绑定工具，只需要生成结构化的规划和攻略
    # 工具调用在execute阶段已经完成
    logger.info("Replan阶段：不绑定工具，专注于生成优化后的规划和攻略")

    # 使用ReplanWithIntervention格式，让LLM自主判断是否需要人工介入
    parser = JsonOutputParser(pydantic_object = ReplanWithIntervention)

    # 格式化已询问的问题列表，清晰展示给LLM
    if collected_info.get("asked_questions"):
        qa_list = []
        for idx, qa in enumerate(collected_info["asked_questions"], 1):
            answer = qa.get("answer", "【尚未回答】")
            qa_list.append(f"{idx}. 问题: {qa['question']}\n   回答: {answer}")
        collected_info_str = "已询问的问题和回答：\n" + "\n".join(qa_list)
        logger.debug(f"已格式化 {len(collected_info['asked_questions'])} 个问题传递给LLM")
    else:
        collected_info_str = "尚未询问任何问题"

    prompt = PromptTemplate(
            template = AMUSEMENT_SYSYRM_REPLAN_TEMPLATE,
            input_variables=["origin","destination","date","days","people","budget","preferences","messages","plan","collected_info"],
            partial_variables={"json_format":parser.get_format_instructions()}
    )
    chain = prompt | llm | parser

    # 使用智能消息压缩，避免丢失重要信息（特别是工具调用结果）
    logger.info("开始压缩消息历史...")
    recent_messages = await compress_messages(state.get("messages", []), max_messages=15)
    logger.info(f"消息压缩完成，最终消息数: {len(recent_messages)}")

    input_data = {
        "origin": state["origin"],
        "destination": state["destination"],
        "date": state["date"],
        "days": state["days"],
        "people": state["people"],
        "budget": state["budget"],
        "preferences": state["preferences"],
        "messages": recent_messages,
        "plan": plan_for_display,  # 使用兼容格式的plan
        "collected_info": collected_info_str
    }

    logger.info("🤖 开始调用LLM生成优化后的规划和攻略...")
    logger.debug(f"Prompt模板变量: destination={state['destination']}, budget={state['budget']}")

    # 【新增】记录完整的输入信息到日志
    formatted_prompt = prompt.format(**input_data)
    logger.debug("=" * 80)
    logger.debug("【LLM输入信息 - Replan阶段】")
    logger.debug(f"完整Prompt:\n{formatted_prompt}")
    logger.debug("=" * 80)

    response = await retry_llm_call(
        chain.ainvoke,
        input_data,
        max_retries=1,
        error_context="Replan阶段生成优化规划"
    )

    # 如果重试后仍失败，提供默认响应
    if response is None or not isinstance(response, dict):
        logger.error(f"Replan阶段LLM调用失败（重试后仍失败），响应: {response}")
        logger.warning("将请求人工介入以获取更多信息")
        response = {
            "replan": state.get("plan", []),  # 使用原规划
            "amusement_info": {
                "destination": state.get("destination", ""),
                "summary": "由于系统错误，暂无详细攻略信息。",
                "highlights": [],
                "local_tips": [],
                "transportation": {},
                "budget_breakdown": {}
            },
            "need_intervention": True,
            "intervention_request": {
                "message": "系统在优化规划时遇到问题，请确认您的具体需求或偏好。",
                "question_type": "confirmation",
                "options": ["继续当前规划", "重新规划", "提供更多信息"],
                "allow_text_input": True
            }
        }
        logger.info("已生成默认的人工介入请求")

    logger.info("✅ LLM响应完成")
    replan = response["replan"]
    amusement_info = response["amusement_info"]
    logger.info(f"生成的优化规划步骤数: {len(replan)}")
    logger.info(f"优化规划内容: {replan}")
    logger.info(f"旅游攻略信息已生成")
    logger.debug(f"攻略详情: {amusement_info}")
    logger.info(f"是否需要人工介入: {response.get('need_intervention', False)}")

    # 如果需要人工介入，记录问题（不限制次数，让LLM自己判断）
    intervention_count = state.get("intervention_count", 0)
    if response.get('need_intervention', False):
        intervention_count += 1
        intervention_req = response.get('intervention_request')
        logger.warning(f"⚠️  LLM判断需要人工介入（第{intervention_count}次）")
        logger.info(f"介入原因: {intervention_req.get('message') if intervention_req else '未提供'}")
        logger.debug(f"完整介入请求: {json.dumps(intervention_req, ensure_ascii=False, indent=2) if intervention_req else 'None'}")

        # 将这个问题记录到asked_questions中
        if intervention_req:
            new_question = {
                "question": intervention_req.get('message', ''),
                "question_type": intervention_req.get('question_type', ''),
                "stage": "replan",
                "answer": None  # 尚未回答
            }
            collected_info["asked_questions"].append(new_question)
            logger.info(f"✓ 已记录新问题到历史，当前总问题数: {len(collected_info['asked_questions'])}")
    else:
        logger.info("✓ 不需要人工介入，流程将继续")

    # 重置人工介入状态，保留collected_info
    result = {
        "replan": replan,
        "amusement_info": amusement_info,
        "need_intervention": response.get('need_intervention', False),
        "intervention_request": response.get('intervention_request'),
        "intervention_stage": "replan" if response.get('need_intervention', False) else "",
        "intervention_response": None,
        "intervention_count": intervention_count,
        "collected_info": collected_info  # 保留已收集信息（包含问题历史）
    }

    logger.info("【REPLAN阶段结束】")
    logger.info("=" * 80)
    return result

async def observation(state:AmusementState) -> Command[Literal["__end__", "plan"]]:
    logger.info("=" * 80)
    logger.info("【OBSERVATION阶段开始】观察当前攻略并判断是否满足用户需求...")
    logger.debug(f"当前旅游攻略: {state.get('amusement_info')}")
    logger.info(f"出发地: {state['origin']}, 目的地: {state['destination']}, 预算: {state['budget']}")

    logger.info("正在初始化LLM...")
    llm = await get_local_llm()

    content = AMUSEMENT_SYSTEM_JUDGE_TEMPLATE.format(**state)
    human_message = HumanMessage(content=content)

    logger.info("🤖 开始调用LLM判断攻略质量...")
    logger.debug(f"判断提示词长度: {len(content)} 字符")

    response = await retry_llm_call(
        llm.ainvoke,
        [human_message],
        max_retries=1,
        error_context="Observation阶段判断攻略质量"
    )

    if response is None:
        logger.error("Observation阶段LLM调用失败（重试后仍失败）")
        logger.warning("默认判断为不满足需求，需要重新规划")
        # 提供默认的缺失原因
        update = {
            "observation_result": {
                "satisfied": False,
                "missing_items": ["系统判断失败，建议重新生成攻略"],
                "suggestions": ["重新执行完整流程"]
            }
        }
        goto = "plan"
        logger.info(f"下一步: {goto}")
        logger.info("【OBSERVATION阶段结束】")
        logger.info("=" * 80)
        return Command(goto=goto, update=update)

    logger.info("✅ LLM判断完成")
    logger.debug(f"Observation阶段LLM完整响应内容: {response.content}")
    logger.debug(f"Observation阶段LLM响应类型: {type(response).__name__}")

    goto = None
    update = None

    # 尝试解析响应
    response_text = response.content.strip()

    if '1' in response_text and len(response_text) < 10:
        # 简单的满足判断
        goto = "__end__"
        logger.info("✓ 判断结果: 攻略满足用户需求，流程结束")
    else:
        # 尝试解析JSON格式的详细反馈
        try:
            # 如果响应包含```json，提取JSON部分
            if '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            elif '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                json_text = response_text[json_start:json_end].strip()
            elif '{' in response_text:
                # 直接提取JSON对象
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                json_text = response_text[json_start:json_end]
            else:
                json_text = response_text

            observation_result = json.loads(json_text)
            logger.info("⚠️  判断结果: 攻略不满足需求")
            logger.info("缺失项:")
            for item in observation_result.get("missing_items", []):
                logger.info(f"  - {item}")
            logger.info("建议:")
            for suggestion in observation_result.get("suggestions", []):
                logger.info(f"  - {suggestion}")

            update = {"observation_result": observation_result}
            goto = "plan"
        except json.JSONDecodeError as e:
            logger.error(f"无法解析observation结果为JSON: {e}")
            logger.warning("使用默认判断：不满足需求")
            update = {
                "observation_result": {
                    "satisfied": False,
                    "missing_items": ["LLM返回格式错误，无法解析详细原因"],
                    "suggestions": ["重新生成攻略"]
                }
            }
            goto = "plan"

    logger.info(f"下一步: {goto}")
    logger.info("【OBSERVATION阶段结束】")
    logger.info("=" * 80)
    return Command(goto=goto, update=update)

async def resume_router(state: AmusementState) -> Command[Literal["plan", "replan"]]:
    """
    路由节点：决定从哪里开始或恢复执行

    逻辑：
    1. 如果intervention_stage为空 → 首次执行或正常循环 → 去plan
    2. 如果intervention_stage="plan" 且 有intervention_response → 用户已响应 → 重新执行plan（plan会处理用户响应）
    3. 如果intervention_stage="replan" 且 有intervention_response → 用户已响应 → 重新执行replan（replan会处理用户响应）

    重要：plan和replan函数内部会检查并处理intervention_response，所以恢复时需要重新执行它们
    """
    logger.info("=" * 80)
    logger.info("【RESUME_ROUTER阶段】决定从哪个节点开始/恢复执行...")

    intervention_stage = state.get("intervention_stage", "")
    has_response = state.get("intervention_response") is not None

    logger.info(f"当前介入阶段: {intervention_stage if intervention_stage else '无（首次执行或正常循环）'}")
    logger.info(f"是否有用户响应: {has_response}")

    if not intervention_stage:
        # 首次执行或正常循环，从plan开始
        logger.info("✓ 路由决策: 首次执行或正常循环，从plan节点开始")
        logger.info("=" * 80)
        return Command(goto="plan")

    elif intervention_stage == "plan" and has_response:
        # 从plan阶段恢复，用户已提供响应
        # 重新执行plan，让plan处理用户响应并生成新的规划
        logger.info("✓ 路由决策: 从plan阶段恢复，用户已提供响应")
        logger.info("准备重新执行plan节点以处理用户反馈")
        logger.debug("清除intervention_stage和need_intervention标志，避免无限循环")
        # 清除intervention_stage和need_intervention，避免无限循环
        logger.info("=" * 80)
        return Command(
            goto="plan",
            update={"intervention_stage": "", "need_intervention": False}
        )

    elif intervention_stage == "replan" and has_response:
        # 从replan阶段恢复，用户已提供响应
        # 重新执行replan，让replan处理用户响应并生成新的攻略
        logger.info("✓ 路由决策: 从replan阶段恢复，用户已提供响应")
        logger.info("准备重新执行replan节点以处理用户反馈")
        logger.debug("清除intervention_stage和need_intervention标志，避免无限循环")
        # 清除intervention_stage和need_intervention，避免无限循环
        logger.info("=" * 80)
        return Command(
            goto="replan",
            update={"intervention_stage": "", "need_intervention": False}
        )

    else:
        # 异常情况，默认从plan开始
        logger.warning(f"⚠️  未预期的状态：intervention_stage={intervention_stage}, has_response={has_response}")
        logger.warning("默认从plan节点开始")
        logger.info("=" * 80)
        return Command(goto="plan", update={"intervention_stage": ""})

async def check_intervention_after_plan(state: AmusementState) -> Command[Literal["wait_user_plan", "excute"]]:
    """
    在plan之后检查是否需要人工介入
    直接读取LLM在plan阶段的判断结果
    """
    logger.info("=" * 80)
    logger.info("【CHECK_INTERVENTION_AFTER_PLAN】检查plan阶段是否需要人工介入...")

    # 直接读取plan函数中LLM的判断结果
    need_intervention = state.get("need_intervention", False)
    intervention_request = state.get("intervention_request", {})

    logger.info(f"LLM判断结果: need_intervention={need_intervention}")

    if need_intervention:
        logger.warning("⚠️  需要人工介入")
        logger.info(f"介入原因: {intervention_request.get('message', '未提供')}")
        logger.debug(f"完整介入请求: {json.dumps(intervention_request, ensure_ascii=False, indent=2) if intervention_request else 'None'}")
        logger.info("下一步: 跳转到wait_user_plan节点，流程将暂停等待用户响应")
        logger.info("=" * 80)
        # 跳转到wait_user_plan节点，该节点会暂停并等待用户响应
        return Command(goto="wait_user_plan")
    else:
        logger.info("✓ 不需要人工介入，继续执行")
        logger.info("下一步: 跳转到excute节点")
        logger.info("=" * 80)
        return Command(goto="excute")

async def wait_user_plan(state: AmusementState) -> Command[Literal["__end__"]]:
    """
    等待用户在plan阶段提供响应
    这个节点会导致流程暂停，状态被保存
    """
    logger.info("=" * 80)
    logger.info("【WAIT_USER_PLAN】等待用户在plan阶段提供响应...")
    logger.info("流程暂停，状态已保存")
    logger.info("会话ID将返回给用户，用户提供响应后通过/resume接口恢复流程")
    logger.debug(f"当前介入请求: {state.get('intervention_request', {})}")
    logger.info("=" * 80)
    # 直接结束，状态已被保存，等待用户通过API恢复
    return Command(goto="__end__")

async def check_intervention_after_replan(state: AmusementState) -> Command[Literal["wait_user_replan", "observation"]]:
    """
    在replan之后检查是否需要人工介入
    直接读取LLM在replan阶段的判断结果
    """
    logger.info("=" * 80)
    logger.info("【CHECK_INTERVENTION_AFTER_REPLAN】检查replan阶段是否需要人工介入...")

    # 直接读取replan函数中LLM的判断结果
    need_intervention = state.get("need_intervention", False)
    intervention_request = state.get("intervention_request", {})

    logger.info(f"LLM判断结果: need_intervention={need_intervention}")

    if need_intervention:
        logger.warning("⚠️  需要人工介入")
        logger.info(f"介入原因: {intervention_request.get('message', '未提供')}")
        logger.debug(f"完整介入请求: {json.dumps(intervention_request, ensure_ascii=False, indent=2) if intervention_request else 'None'}")
        logger.info("下一步: 跳转到wait_user_replan节点，流程将暂停等待用户响应")
        logger.info("=" * 80)
        # 跳转到wait_user_replan节点，该节点会暂停并等待用户响应
        return Command(goto="wait_user_replan")
    else:
        logger.info("✓ 不需要人工介入，继续观察")
        logger.info("下一步: 跳转到observation节点")
        logger.info("=" * 80)
        return Command(goto="observation")

async def wait_user_replan(state: AmusementState) -> Command[Literal["__end__"]]:
    """
    等待用户在replan阶段提供响应
    这个节点会导致流程暂停，状态被保存
    """
    logger.info("=" * 80)
    logger.info("【WAIT_USER_REPLAN】等待用户在replan阶段提供响应...")
    logger.info("流程暂停，状态已保存")
    logger.info("会话ID将返回给用户，用户提供响应后通过/resume接口恢复流程")
    logger.debug(f"当前介入请求: {state.get('intervention_request', {})}")
    logger.info("=" * 80)
    # 直接结束，状态已被保存，等待用户通过API恢复
    return Command(goto="__end__")    
async def get_graph() -> StateGraph:
    """
    构建带人工介入功能的Agent工作流图

    工作流（支持暂停和恢复）：
    START → resume_router
        → (首次执行或普通循环) plan → check_intervention_after_plan
            → (需要介入) wait_user_plan → END
            → (不需要) excute → replan （工具调用在excute内部完成）
        → (从plan恢复) excute → ...
        → (从replan恢复) observation → ...

    恢复机制：
    - 用户响应后，API更新state的intervention_response
    - 重新调用graph.ainvoke(state)
    - resume_router根据intervention_stage决定从哪里继续

    注意：工具调用机制已改为在excute节点内部完成多轮对话，不再使用独立的tool_node
    """
    logger.info("=" * 80)
    logger.info("【GET_GRAPH】开始构建Agent工作流图...")

    # 注意：现在工具调用在excute节点内部完成，不再需要单独的tool_node
    logger.info("工作流采用新的execute内部多轮工具调用机制")

    builder = StateGraph(state_schema = AmusementState)

    # 添加所有节点
    logger.info("正在添加工作流节点...")
    nodes = [
        "resume_router",  # 路由节点，决定从哪里开始/恢复
        "plan",
        "check_intervention_after_plan",
        "wait_user_plan",  # 等待用户响应的节点
        "excute",  # execute节点内部完成工具调用
        "replan",
        "check_intervention_after_replan",
        "wait_user_replan",  # 等待用户响应的节点
        "observation"
    ]

    builder.add_node("resume_router", resume_router)
    builder.add_node("plan", plan)
    builder.add_node("check_intervention_after_plan", check_intervention_after_plan)
    builder.add_node("wait_user_plan", wait_user_plan)
    builder.add_node("excute", excute)
    builder.add_node("replan", replan)
    builder.add_node("check_intervention_after_replan", check_intervention_after_replan)
    builder.add_node("wait_user_replan", wait_user_replan)
    builder.add_node("observation", observation)

    logger.info(f"已添加 {len(nodes)} 个节点: {', '.join(nodes)}")

    # 构建工作流
    logger.info("正在构建工作流边...")
    # 1. 从START开始，总是先到resume_router
    builder.add_edge(START, "resume_router")
    logger.debug("  添加边: START → resume_router")
    # resume_router会根据intervention_stage决定跳转到plan/excute/observation
    # 这里不需要add_edge，因为resume_router使用Command返回值控制跳转

    # 2. plan的正常流程
    builder.add_edge("plan", "check_intervention_after_plan")
    logger.debug("  添加边: plan → check_intervention_after_plan")
    # check_intervention_after_plan根据need_intervention决定跳转

    # 3. 如果需要人工介入，跳转到wait_user节点，然后END
    builder.add_edge("wait_user_plan", END)
    logger.debug("  添加边: wait_user_plan → END")
    builder.add_edge("wait_user_replan", END)
    logger.debug("  添加边: wait_user_replan → END")

    # 4. excute的正常流程 - 直接到replan（工具调用在excute内部完成）
    builder.add_edge("excute", "replan")
    logger.debug("  添加边: excute → replan （工具调用在excute内部完成）")

    # 5. replan的正常流程
    builder.add_edge("replan", "check_intervention_after_replan")
    logger.debug("  添加边: replan → check_intervention_after_replan")
    # check_intervention_after_replan根据need_intervention决定跳转

    # 6. observation的判断流程会自动返回Command控制跳转到END或plan

    logger.info("工作流边构建完成")
    logger.info("正在编译工作流图...")
    graph = builder.compile()
    logger.info("✅ 工作流图编译成功")
    logger.info("=" * 80)
    return graph