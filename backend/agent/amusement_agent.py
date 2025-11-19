import asyncio
import uuid
import logging
import operator
from typing import TypedDict, Annotated,Literal
from pydantic import Field

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage,ToolMessage,AnyMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

from utils import get_llm,get_mcp_tools
from utils.tools import tavily_search
from config import trival_mcp_config


from prompts import AMUSEMENT_SYSTEM_PLAN_TEMPLATE,AMUSEMENT_SYSYRM_REPLAN_TEMPLATE,AMUSEMENT_SYSTEM_JUDGE_TEMPLATE
from formatters import ReplanFormat,PlanFormat
from formatters.amusement_format import AmusementFormat, PlanWithIntervention, ReplanWithIntervention, InterventionResponse
logger = logging.getLogger(__name__) 
_mcp_trival_tools = None
_llm = None

class AmusementState(TypedDict):
    origin: Annotated[str, Field(description="出发地")]
    destination: Annotated[str, Field(description="目的地")]
    date: Annotated[str, Field(description="出发日期，格式为YYYY-MM-DD")]
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
# 获取mcp工具
async def get_mcp_trival_tools():
    global _mcp_trival_tools
    if _mcp_trival_tools is None:
        # 只在第一次调用时执行
        _mcp_trival_tools = await get_mcp_tools(trival_mcp_config)
    return _mcp_trival_tools+[tavily_search]
async def get_local_llm():
    global _llm
    if _llm is None:
        # 只在第一次调用时执行
        _llm = get_llm()
    return _llm
async def plan(state:AmusementState)->AmusementState:
    logging.info(f"娱乐智能体开始规划...")

    # 如果有人工介入响应，将其合并到用户偏好中
    if state.get("intervention_response"):
        intervention_resp = state["intervention_response"]
        additional_info = ""
        if intervention_resp.get("text_input"):
            additional_info = f"\n用户补充信息: {intervention_resp['text_input']}"
        if intervention_resp.get("selected_options"):
            additional_info += f"\n用户选择: {', '.join(intervention_resp['selected_options'])}"

        # 将人工介入的信息添加到messages中
        if additional_info:
            human_msg = HumanMessage(content=f"用户提供了额外信息：{additional_info}")
            state["messages"].append(human_msg)

    llm = await get_local_llm()
    trival_tools = await get_mcp_trival_tools()
    llm_with_tools = llm.bind_tools(trival_tools)

    # 使用PlanWithIntervention格式，让LLM自主判断是否需要人工介入
    parser = JsonOutputParser(pydantic_object = PlanWithIntervention)
    prompt = PromptTemplate(
            template = AMUSEMENT_SYSTEM_PLAN_TEMPLATE,
            input_variables=["origin","destination","date","people","budget","preferences","plan","replan"],
            partial_variables={"json_format":parser.get_format_instructions()},
    )
    chain = prompt | llm_with_tools|parser
    response = await chain.ainvoke(state)
    logging.info(f'当前的旅行规划信息:{response}')

    # 重置人工介入状态
    return {
        "plan": response['plan'],
        "need_intervention": response.get('need_intervention', False),
        "intervention_request": response.get('intervention_request'),
        "intervention_stage": "plan" if response.get('need_intervention', False) else "",
        "intervention_response": None
    }

async def excute(state :AmusementState)->AmusementState:
    logging.info(f"娱乐智能体开始执行计划")
    logging.info(f'当前的旅行规划信息:{state["plan"]}')
    plan = state["plan"]
    trival_tools = await get_mcp_trival_tools()
    llm = await get_local_llm()
    
    llm_with_tools = llm.bind_tools(trival_tools)
    human_message = HumanMessage(content=plan[0])
    response = await llm_with_tools.ainvoke([human_message])
    logging.info(f"娱乐智能体执行计划是：{response}")
    return {"messages":[response]}
async def judge_tools(state:AmusementState)->AmusementState:
    """
    判断是否需要使用工具
    """
    ai_message = state["messages"][-1]
    if "tool_calls" in ai_message.additional_kwargs.keys()  and len(ai_message.additional_kwargs['tool_calls']) > 0:
        logger.info("行动---执行工具")
        return "use_tools"
    logger.info("不执行工具 ---- 观察")
    return "replan"
    
async def replan(state:AmusementState)->AmusementState:
    logging.info(f"娱乐智能体 重新规划计划、并根据目前信息生成旅游攻略")

    # 如果有人工介入响应，将其合并到消息中
    if state.get("intervention_response"):
        intervention_resp = state["intervention_response"]
        additional_info = ""
        if intervention_resp.get("text_input"):
            additional_info = f"\n用户补充信息: {intervention_resp['text_input']}"
        if intervention_resp.get("selected_options"):
            additional_info += f"\n用户选择: {', '.join(intervention_resp['selected_options'])}"

        if additional_info:
            human_msg = HumanMessage(content=f"用户提供了额外信息：{additional_info}")
            state["messages"].append(human_msg)

    last_message = state["messages"][-1]
    llm = await get_local_llm()
    trival_tools = await get_mcp_trival_tools()
    llm_with_tools = llm.bind_tools(trival_tools)

    # 使用ReplanWithIntervention格式，让LLM自主判断是否需要人工介入
    parser = JsonOutputParser(pydantic_object = ReplanWithIntervention)
    prompt = PromptTemplate(
            template = AMUSEMENT_SYSYRM_REPLAN_TEMPLATE,
            input_variables=["origin","destination","date","people","budget","preferences","messages","plan"],
            partial_variables={"json_format":parser.get_format_instructions()}
    )
    chain = prompt | llm_with_tools|parser
    state["messages"] = last_message
    response = await chain.ainvoke(state)
    replan = response["replan"]
    amusement_info = response["amusement_info"]

    # 重置人工介入状态
    return {
        "replan": replan,
        "amusement_info": amusement_info,
        "need_intervention": response.get('need_intervention', False),
        "intervention_request": response.get('intervention_request'),
        "intervention_stage": "replan" if response.get('need_intervention', False) else "",
        "intervention_response": None
    }

async def observation(state:AmusementState) -> Command[Literal["__end__", "plan"]]:
    logging.info(f"娱乐智能体观察目前的攻略信息：{state['amusement_info']}，来判断能否满足用户的需求")
    llm = await get_local_llm()

    content = AMUSEMENT_SYSTEM_JUDGE_TEMPLATE.format(**state)
    human_message = HumanMessage(content=content)
    response = await llm.ainvoke([human_message])
    goto = None
    update = None
    if '1' in response.content:
        goto = "__end__"

    else:
        goto = "plan"
    return Command(goto=goto,update=update)

async def resume_router(state: AmusementState) -> Command[Literal["plan", "replan"]]:
    """
    路由节点：决定从哪里开始或恢复执行

    逻辑：
    1. 如果intervention_stage为空 → 首次执行或正常循环 → 去plan
    2. 如果intervention_stage="plan" 且 有intervention_response → 用户已响应 → 重新执行plan（plan会处理用户响应）
    3. 如果intervention_stage="replan" 且 有intervention_response → 用户已响应 → 重新执行replan（replan会处理用户响应）

    重要：plan和replan函数内部会检查并处理intervention_response，所以恢复时需要重新执行它们
    """
    intervention_stage = state.get("intervention_stage", "")
    has_response = state.get("intervention_response") is not None

    if not intervention_stage:
        # 首次执行或正常循环，从plan开始
        logging.info("首次执行或正常循环，从plan节点开始")
        return Command(goto="plan")

    elif intervention_stage == "plan" and has_response:
        # 从plan阶段恢复，用户已提供响应
        # 重新执行plan，让plan处理用户响应并生成新的规划
        logging.info("从plan阶段恢复，用户已提供响应，重新执行plan")
        # 清除intervention_stage和need_intervention，避免无限循环
        return Command(
            goto="plan",
            update={"intervention_stage": "", "need_intervention": False}
        )

    elif intervention_stage == "replan" and has_response:
        # 从replan阶段恢复，用户已提供响应
        # 重新执行replan，让replan处理用户响应并生成新的攻略
        logging.info("从replan阶段恢复，用户已提供响应，重新执行replan")
        # 清除intervention_stage和need_intervention，避免无限循环
        return Command(
            goto="replan",
            update={"intervention_stage": "", "need_intervention": False}
        )

    else:
        # 异常情况，默认从plan开始
        logging.warning(f"未预期的状态：intervention_stage={intervention_stage}, has_response={has_response}，默认从plan开始")
        return Command(goto="plan", update={"intervention_stage": ""})

async def check_intervention_after_plan(state: AmusementState) -> Command[Literal["wait_user_plan", "excute"]]:
    """
    在plan之后检查是否需要人工介入
    直接读取LLM在plan阶段的判断结果
    """
    logging.info("检查plan阶段是否需要人工介入...")

    # 直接读取plan函数中LLM的判断结果
    need_intervention = state.get("need_intervention", False)

    if need_intervention:
        logging.info(f"LLM判断需要人工介入，原因：{state.get('intervention_request', {}).get('message', '未提供')}")
        # 跳转到wait_user_plan节点，该节点会暂停并等待用户响应
        return Command(goto="wait_user_plan")
    else:
        logging.info("LLM判断不需要人工介入，继续执行")
        return Command(goto="excute")

async def wait_user_plan(state: AmusementState) -> Command[Literal["__end__"]]:
    """
    等待用户在plan阶段提供响应
    这个节点会导致流程暂停，状态被保存
    """
    logging.info("等待用户在plan阶段提供响应，流程暂停")
    # 直接结束，状态已被保存，等待用户通过API恢复
    return Command(goto="__end__")

async def check_intervention_after_replan(state: AmusementState) -> Command[Literal["wait_user_replan", "observation"]]:
    """
    在replan之后检查是否需要人工介入
    直接读取LLM在replan阶段的判断结果
    """
    logging.info("检查replan阶段是否需要人工介入...")

    # 直接读取replan函数中LLM的判断结果
    need_intervention = state.get("need_intervention", False)

    if need_intervention:
        logging.info(f"LLM判断需要人工介入，原因：{state.get('intervention_request', {}).get('message', '未提供')}")
        # 跳转到wait_user_replan节点，该节点会暂停并等待用户响应
        return Command(goto="wait_user_replan")
    else:
        logging.info("LLM判断不需要人工介入，继续观察")
        return Command(goto="observation")

async def wait_user_replan(state: AmusementState) -> Command[Literal["__end__"]]:
    """
    等待用户在replan阶段提供响应
    这个节点会导致流程暂停，状态被保存
    """
    logging.info("等待用户在replan阶段提供响应，流程暂停")
    # 直接结束，状态已被保存，等待用户通过API恢复
    return Command(goto="__end__")    
async def get_graph() -> StateGraph:
    """
    构建带人工介入功能的Agent工作流图

    工作流（支持暂停和恢复）：
    START → resume_router
        → (首次执行或普通循环) plan → check_intervention_after_plan
            → (需要介入) wait_user_plan → END
            → (不需要) excute → judge_tools → tool_node/replan
        → (从plan恢复) excute → ...
        → (从replan恢复) observation → ...

    恢复机制：
    - 用户响应后，API更新state的intervention_response
    - 重新调用graph.ainvoke(state)
    - resume_router根据intervention_stage决定从哪里继续
    """
    trival_tools = await get_mcp_trival_tools()
    tool_node = ToolNode(trival_tools)
    builder = StateGraph(state_schema = AmusementState)

    # 添加所有节点
    builder.add_node("resume_router", resume_router)  # 路由节点，决定从哪里开始/恢复
    builder.add_node("plan", plan)
    builder.add_node("check_intervention_after_plan", check_intervention_after_plan)
    builder.add_node("wait_user_plan", wait_user_plan)  # 等待用户响应的节点
    builder.add_node("excute", excute)
    builder.add_node("tool_node", tool_node)
    builder.add_node("replan", replan)
    builder.add_node("check_intervention_after_replan", check_intervention_after_replan)
    builder.add_node("wait_user_replan", wait_user_replan)  # 等待用户响应的节点
    builder.add_node("observation", observation)

    # 构建工作流
    # 1. 从START开始，总是先到resume_router
    builder.add_edge(START, "resume_router")
    # resume_router会根据intervention_stage决定跳转到plan/excute/observation
    # 这里不需要add_edge，因为resume_router使用Command返回值控制跳转

    # 2. plan的正常流程
    builder.add_edge("plan", "check_intervention_after_plan")
    # check_intervention_after_plan根据need_intervention决定跳转

    # 3. 如果需要人工介入，跳转到wait_user节点，然后END
    builder.add_edge("wait_user_plan", END)
    builder.add_edge("wait_user_replan", END)

    # 4. excute的正常流程
    builder.add_conditional_edges(
        "excute",
        judge_tools,
        {"use_tools": "tool_node", "replan": "replan"}
    )
    builder.add_edge("tool_node", "replan")

    # 5. replan的正常流程
    builder.add_edge("replan", "check_intervention_after_replan")
    # check_intervention_after_replan根据need_intervention决定跳转

    # 6. observation的判断流程会自动返回Command控制跳转到END或plan

    graph = builder.compile()
    return graph