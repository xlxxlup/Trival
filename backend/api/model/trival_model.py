from pydantic import BaseModel, Field
from typing import Annotated, Optional, List, Dict, Any

class TrivalFormat(BaseModel):
    date :Annotated[str,Field(description="用户的出发日期")]
    origin :Annotated[str,Field(description="用户的出发地")]
    destination :Annotated[str,Field(description="用户目的地")]
    days:Annotated[int,Field(description="用户计划的旅行天数")]
    budget:Annotated[float,Field(description="用户的预算")]
    preferences:Annotated[str,Field(description="用户的兴趣偏好")]
    people:Annotated[int,Field(description="用户的出行人数")]

class InterventionResponseModel(BaseModel):
    """用户对人工介入的响应"""
    session_id: str = Field(description="会话ID")
    text_input: Optional[str] = Field(default=None, description="用户的文本输入")
    selected_options: Optional[List[str]] = Field(default=None, description="用户选择的选项ID列表")

class TravelResponse(BaseModel):
    """旅游规划API响应"""
    session_id: str = Field(description="会话ID，用于后续恢复")
    status: str = Field(description="状态: completed/need_intervention")

    # 如果需要人工介入
    need_intervention: bool = Field(default=False, description="是否需要人工介入")
    intervention_request: Optional[Dict[str, Any]] = Field(default=None, description="人工介入请求")

    # 如果完成
    plan: Optional[List[str]] = Field(default=None, description="初始规划")
    replan: Optional[List[str]] = Field(default=None, description="优化后的规划")
    amusement_info: Optional[Dict[str, Any]] = Field(default=None, description="旅游攻略信息")