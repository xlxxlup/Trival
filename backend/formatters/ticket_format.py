from pydantic import BaseModel, Field
from typing import List
class TicketPlanFormat(BaseModel):
    plan: List[str] = Field(description="规划获取车票信息的计划")

class TrainInfoFormat(BaseModel):
    train_type: str = Field(description="车次类型:火车、动车、高铁")
    train_number: str = Field(description="车次编号")
    start_time: str = Field(description="出发时间")
    arrive_time: str = Field(description="到达时间")
    duration: str = Field(description="时长")
    price: str = Field(description="价格")
    seat_type: str = Field(description="座位类型")
class AirplaneInfoFormat(BaseModel):
    flight_type: str = Field(description="航班类型")
    start_time: str = Field(description="出发时间")
    arrive_time: str = Field(description="到达时间")
    duration: str = Field(description="时长")
    price: str = Field(description="价格")
    seat_type: str = Field(description="座位类型")
class TicketFormat(BaseModel):
    train_info: List[TrainInfoFormat] = Field(description="火车信息")
    airplane_info: List[AirplaneInfoFormat] = Field(description="飞机信息")