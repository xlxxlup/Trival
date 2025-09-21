from pydantic import BaseModel, Field
from typing import Annotated

class TrivalFormat(BaseModel):
    date :Annotated[str,Field(description="用户的出发日期")]
    origin :Annotated[str,Field(description="用户的出发地")]
    destination :Annotated[str,Field(description="用户目的地")]
    days:Annotated[int,Field(description="用户计划的旅行天数")]
    budget:Annotated[float,Field(description="用户的预算")]
    preferences:Annotated[str,Field(description="用户的兴趣偏好")]
    people:Annotated[int,Field(description="用户的出行人数")]