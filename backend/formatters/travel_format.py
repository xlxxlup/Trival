from pydantic import BaseModel, Field
from typing import List, Optional   
class TravelFormat(BaseModel):
    category: str = Field(..., description="交通工具类别，如飞机、火车、汽车等")
    price: float = Field(..., description="交通工具的价格")
    duration: str = Field(..., description="交通工具的行程时间")
    departure_time: str = Field(..., description="交通工具的出发时间")
    arrival_time: str = Field(..., description="交通工具的到达时间")

