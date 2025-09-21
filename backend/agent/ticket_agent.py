"""
车票智能体
"""
import asyncio
import uuid
import logging
import operator
from typing import TypedDict, Annotated,Literal
from pydantic import Field

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage,ToolMessage,AnyMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
# from langchain_core.memory import InMemorySaver
from utils import get_llm,get_mcp_tools
from config import train_mcp_config
from prompts import TICKET_OBSEVATION_TEMPLATE,TICKET_REASON_TEMPLATE,TICKET_JUDGE_REASON_TEMPLATE,TICKET_CONTENT_TO_TOOL_TEMPLATE
from formatters import TicketFormat
from formatters.tool_format import ToolFormat
logger = logging.getLogger(__name__) 

_mcp_train_tools = None  # 全局缓存
_llm = None
# 获取mcp工具
async def get_mcp_train_tools():
    global _mcp_train_tools
    if _mcp_train_tools is None:
        # 只在第一次调用时执行
        _mcp_train_tools = await get_mcp_tools(train_mcp_config)
    return _mcp_train_tools
async def get_local_llm():
    global _llm
    if _llm is None:
        # 只在第一次调用时执行
        _llm = get_llm()
    return _llm
class InputState(TypedDict):
    origin: Annotated[str, Field(description="出发地")]
    destination: Annotated[str, Field(description="目的地")]
    date: Annotated[str, Field(description="出发日期，格式为YYYY-MM-DD")]
    people: Annotated[int, Field(description="出行人数")]
    budget: Annotated[float, Field(description="预算")]
    preferences: Annotated[str, Field(description="用户偏好")]
    messages: Annotated[list[BaseMessage], add_messages, Field("整个助手的上下文信息")]
class OutputState(InputState):
    ticket_info :Annotated[TicketFormat,Field(description="车票信息")]
class TrivalState(TypedDict):
    origin: Annotated[str, Field(description="出发地")]
    destination: Annotated[str, Field(description="目的地")]
    date: Annotated[str, Field(description="出发日期，格式为YYYY-MM-DD")]
    people: Annotated[int, Field(description="出行人数")]
    budget: Annotated[float, Field(description="预算")]
    preferences: Annotated[str, Field(description="用户偏好")]
    messages: Annotated[list[AnyMessage], add_messages]
    ticket_info :Annotated[TicketFormat,Field(description="车票信息")]
async def create_tool_message(tool_format:list) -> AIMessage:
    """
    创建工具消息
    """
    
    tool_calls = []
    for tool_data in tool_format:
        name = tool_data.get('name',None)
        arguments = tool_data.get('arguments',None) or tool_data.get('args',None)
        id = str(uuid.uuid4())
        if name and arguments:
            tool_calls.append({
                "id":id,
                "function":{
                    "arguments": arguments,
                    "name": name,
                },
                "type": "function"
            })
    
    ai_message = AIMessage(
        content='',
        additional_kwargs={"tool_calls": tool_calls}
    )
    return ai_message
async def reason(state: TrivalState) :
    logging.info(f"模型思考中....")
    logging.info(f"上下文信息：{state['messages']}")
    llm = await get_local_llm()
    train_tools = await get_mcp_train_tools()
    llm_with_tools = llm.bind_tools(train_tools)
    
    prompt = PromptTemplate(
            template = TICKET_REASON_TEMPLATE,
            input_variables=["origin","destination","date","people","budget","preferences","messages","ticket_info"],
    )
    chain = prompt | llm_with_tools
    response = await chain.ainvoke(state)
    logging.info(f'==模型思考后的结果:{response}==')
    #==========================================
    if len(response.content) > 0:
        tool_parser = JsonOutputParser(schema=ToolFormat)
        prompt = PromptTemplate(
            template = TICKET_CONTENT_TO_TOOL_TEMPLATE,
            input_variables=["content"],
            partial_variables={"tool_format":tool_parser.get_format_instructions()}
        )
        tool_chain = prompt|llm_with_tools|tool_parser
        tool_format = await tool_chain.ainvoke({"content":response})
        logging.info(f"工具信息：{tool_format},工具类型为：{type(tool_format)}")
        response = await create_tool_message(tool_format)
        logging.info(f"当前模型思考后，做出的行动：{response}")
    print(type(response))
    return {"messages":[response]}
async def observation(state:TrivalState) :
    """
    模型观察
    """
    logging.info(f"模型观察中....")
    llm = await get_local_llm()
    parser = JsonOutputParser(schema=TicketFormat)
    prompt = PromptTemplate(
            template = TICKET_OBSEVATION_TEMPLATE,
            input_variables=["messages"],
            partial_variables={"ticket_format":parser.get_format_instructions()}
    )
    chain = prompt | llm | parser
    
    ticket_info = await chain.ainvoke(state['messages'])
    logging.info(f'==观察当前的旅行车票信息:{ticket_info}==')
    return {'ticket_info':ticket_info}
    
async def judge_tools(state:TrivalState) -> Literal["tools", "observation"]:
    """
    判断是否需要使用工具
    """
    ai_message = state["messages"][-1]
    if "tool_calls" in ai_message.additional_kwargs.keys()  and len(ai_message.additional_kwargs['tool_calls']) > 0:
        logger.info("行动---执行工具")
        return "tools"
    logger.info("不执行工具 ---- 观察")
    return "observation"

async def judge_reason(state:TrivalState) -> Literal["end", "reason"]:
    """
    判断是否需要思考
    """
    llm = await get_local_llm()
    prompt = PromptTemplate(
            template = TICKET_JUDGE_REASON_TEMPLATE,
            input_variables=["origin","destination","date","people","budget","preferences","ticket_info"],
    )
    chain = prompt | llm
    response = await chain.ainvoke(state)
    if  '1' in response.content:
        return "reason"
    return "end"




async def get_graph() -> StateGraph:
    # checkpointer  = InMemorySaver()
    train_tools = await get_mcp_train_tools()
    tool_node = ToolNode(train_tools)
    builder = StateGraph(TrivalState)  
    builder.add_node("reason",reason)
    builder.add_node("tool_node", tool_node)
    builder.add_node("observation",observation)
    builder.add_edge(START, "reason")
    builder.add_conditional_edges(
        "reason",
        judge_tools,
        {"observation": "observation","tools": "tool_node"}
    )
    builder.add_edge("tool_node", "observation")
    builder.add_conditional_edges("observation", 
                                  judge_reason,
                                  {"end": END, "reason": "reason"})
    

    graph = builder.compile()
 
    
    return graph