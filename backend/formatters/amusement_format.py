from pydantic import BaseModel, Field
from typing import List, Annotated, Optional

class HotelFormat(BaseModel):
    hotel_name: str = Field(description="酒店名称")
    hotel_star: str = Field(description="酒店星级")
class WeatherFormat(BaseModel):
    weather: str = Field(description="天气信息")
class PathWayFormat(BaseModel):
    path_type: str = Field(description="路径规划方式，例如：骑行、步行、驾车、公交车")
    path_way: str = Field(description="旅游路线")
class PathFormat(BaseModel):
    path_way: Annotated[List[PathWayFormat] , Field(description="旅游路线")]
class AroundFormat(BaseModel):
    around: str = Field(description="周边信息")
class AmusementFormat(BaseModel):
    around: Annotated[List[AroundFormat] , Field(description="周边信息")]
    path: PathFormat = Field(description="旅游路线")
    weather: WeatherFormat = Field(description="天气信息")
class PlanFormat(BaseModel):
    plan: List[str] = Field(description="旅游规划")
class ReplanFormat(BaseModel):
    replan: List[str] = Field(description="重新规划")
    amusement_info : Annotated[AmusementFormat, Field(description="旅游攻略信息")]

# 人工介入相关格式
class InterventionOption(BaseModel):
    """人工介入选项"""
    id: str = Field(description="选项ID")
    text: str = Field(description="选项文本")

class InterventionRequest(BaseModel):
    """人工介入请求"""
    stage: str = Field(description="介入阶段: plan 或 replan")
    message: str = Field(description="向用户展示的提示信息")
    question_type: str = Field(description="问题类型: text(文本输入) / single_choice(单选) / multiple_choice(多选)")
    options: Optional[List[InterventionOption]] = Field(default=None, description="选项列表(仅用于选择类型)")
    current_plan: Optional[List[str]] = Field(default=None, description="当前规划内容，供用户参考")

class InterventionResponse(BaseModel):
    """人工介入响应"""
    text_input: Optional[str] = Field(default=None, description="用户的文本输入")
    selected_options: Optional[List[str]] = Field(default=None, description="用户选择的选项ID列表")

class PlanWithIntervention(BaseModel):
    """带人工介入标识的规划"""
    plan: List[str] = Field(description="旅游规划")
    need_intervention: bool = Field(default=False, description="是否需要人工介入")
    intervention_request: Optional[InterventionRequest] = Field(default=None, description="人工介入请求")

class ReplanWithIntervention(BaseModel):
    """带人工介入标识的重新规划"""
    replan: List[str] = Field(description="重新规划")
    amusement_info: Annotated[AmusementFormat, Field(description="旅游攻略信息")]
    need_intervention: bool = Field(default=False, description="是否需要人工介入")
    intervention_request: Optional[InterventionRequest] = Field(default=None, description="人工介入请求")