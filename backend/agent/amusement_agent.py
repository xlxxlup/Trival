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
from formatters.amusement_format import AmusementFormat
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
    llm = await get_local_llm()
    trival_tools = await get_mcp_trival_tools()
    llm_with_tools = llm.bind_tools(trival_tools)
    parser = JsonOutputParser(pydantic_object = PlanFormat)
    prompt = PromptTemplate(
            template = AMUSEMENT_SYSTEM_PLAN_TEMPLATE,
            input_variables=["origin","destination","date","people","budget","preferences","plan","replan"],
            partial_variables={"json_format":parser.get_format_instructions()},
    )
    chain = prompt | llm_with_tools|parser
    response = await chain.ainvoke(state)
    logging.info(f'当前的旅行规划信息:{response}')
    return {"plan":response['plan']}

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
    last_message = state["messages"][-1]
    llm = await get_local_llm()
    trival_tools = await get_mcp_trival_tools()
    llm_with_tools = llm.bind_tools(trival_tools)
    parser = JsonOutputParser(pydantic_object = ReplanFormat)
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
    return {"replan":replan,"amusement_info":amusement_info}

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
async def get_graph() -> StateGraph:
    trival_tools = await get_mcp_trival_tools()
    tool_node = ToolNode(trival_tools)
    builder = StateGraph(state_schema = AmusementState)
    builder.add_node("plan",plan)
    builder.add_node("excute",excute)
    builder.add_node("tool_node",tool_node)
    builder.add_node("replan",replan)
    builder.add_node("observation",observation)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "excute")
    builder.add_conditional_edges(
        "excute",
        judge_tools,
        {"use_tools": "tool_node", "replan": "replan"}
    )
    builder.add_edge("tool_node","replan")

    builder.add_edge("replan", "observation")

    graph = builder.compile()
    return graph