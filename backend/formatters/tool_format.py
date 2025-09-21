from pydantic import BaseModel,Field
from typing import Dict,Annotated,List
import uuid
class MyTool(BaseModel):
    name: str = Field(description="工具名称")
    arguments: dict = Annotated[Dict,Field(description="工具参数")]
class ToolFormat(BaseModel):
    tools: List[MyTool] = Field(description="工具列表")