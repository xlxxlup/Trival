"""
文件操作智能体
"""
import logging
from typing import TypedDict,Annotated
from pydantic import Field
from typing import Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
class FileState(TypedDict):
    file_path:Annotated[str,Field(description="文件路径")]
    file_name:Annotated[str,Field(description="文件名称")]
    operation:Annotated[Literal["read","write","delete"],Field(description="操作类型，支持读取、写入、删除")]
    content:Annotated[str|None,Field(description="写入内容，仅在操作为写入时需要提供")]

    messages: Annotated[list[BaseMessage], add_messages, Field("整个助手的上下文信息")]
