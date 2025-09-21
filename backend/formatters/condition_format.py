from pydantic import BaseModel,Field
from typing import  List, Annotated

class ConditionFormat(BaseModel):
    days: Annotated[int, Field(description="旅行天数")]
    budget: Annotated[float, Field(description="预算")]
    preferences: Annotated[List[str], Field(description="兴趣偏好")]
    people: Annotated[int, Field(description="出行人数")]