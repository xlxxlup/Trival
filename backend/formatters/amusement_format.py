from pydantic import BaseModel, Field
from typing import List,Annotated

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