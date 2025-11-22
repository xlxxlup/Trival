from pydantic import BaseModel, Field
from typing import List, Annotated, Optional

# 交通相关
class TrainTicketFormat(BaseModel):
    """火车票信息"""
    train_no: str = Field(description="车次号，如G1234")
    from_station: str = Field(description="出发站")
    to_station: str = Field(description="到达站")
    departure_time: str = Field(description="出发时间")
    arrival_time: str = Field(description="到达时间")
    duration: str = Field(description="历时")
    second_class_price: Optional[str] = Field(default=None, description="二等座价格")
    first_class_price: Optional[str] = Field(default=None, description="一等座价格")
    business_class_price: Optional[str] = Field(default=None, description="商务座价格")
    second_class_available: Optional[str] = Field(default=None, description="二等座余票")
    first_class_available: Optional[str] = Field(default=None, description="一等座余票")
    business_class_available: Optional[str] = Field(default=None, description="商务座余票")

class FlightTicketFormat(BaseModel):
    """机票信息"""
    flight_no: str = Field(description="航班号")
    from_airport: str = Field(description="出发机场")
    to_airport: str = Field(description="到达机场")
    departure_time: str = Field(description="出发时间")
    arrival_time: str = Field(description="到达时间")
    duration: str = Field(description="飞行时长")
    price: Optional[str] = Field(default=None, description="票价")
    seat_type: Optional[str] = Field(default=None, description="舱位类型")

class TransportationFormat(BaseModel):
    """交通信息"""
    outbound: Optional[List[TrainTicketFormat]] = Field(default=None, description="去程火车票选项")
    return_trip: Optional[List[TrainTicketFormat]] = Field(default=None, description="返程火车票选项")
    outbound_flights: Optional[List[FlightTicketFormat]] = Field(default=None, description="去程航班选项")
    return_flights: Optional[List[FlightTicketFormat]] = Field(default=None, description="返程航班选项")
    local_transport: Optional[str] = Field(default=None, description="当地交通建议")

# 住宿相关
class HotelFormat(BaseModel):
    """酒店信息"""
    hotel_name: str = Field(description="酒店名称")
    hotel_star: Optional[str] = Field(default=None, description="酒店星级")
    address: Optional[str] = Field(default=None, description="酒店地址")
    price_per_night: Optional[str] = Field(default=None, description="每晚价格")
    rating: Optional[str] = Field(default=None, description="评分")
    facilities: Optional[List[str]] = Field(default=None, description="设施")
    distance_to_center: Optional[str] = Field(default=None, description="距离市中心距离")

# 景点与POI相关
class POIFormat(BaseModel):
    """景点或POI信息"""
    name: str = Field(description="名称")
    type: str = Field(description="类型：景点/餐厅/酒吧/购物等")
    address: Optional[str] = Field(default=None, description="地址")
    opening_hours: Optional[str] = Field(default=None, description="营业时间")
    rating: Optional[str] = Field(default=None, description="评分")
    avg_cost: Optional[str] = Field(default=None, description="人均消费")
    description: Optional[str] = Field(default=None, description="描述")
    distance_from_hotel: Optional[str] = Field(default=None, description="距离酒店距离")
    transport_time: Optional[str] = Field(default=None, description="从酒店到达时间")
    transport_cost: Optional[str] = Field(default=None, description="从酒店到达费用")

# 天气相关
class WeatherFormat(BaseModel):
    """天气信息"""
    date: str = Field(description="日期")
    weather_desc: str = Field(description="天气描述")
    temperature_high: Optional[str] = Field(default=None, description="最高温度")
    temperature_low: Optional[str] = Field(default=None, description="最低温度")
    wind: Optional[str] = Field(default=None, description="风力")

# 每日行程相关
class DailyItineraryFormat(BaseModel):
    """每日行程"""
    day: int = Field(description="第几天")
    date: str = Field(description="日期")
    morning: Optional[str] = Field(default=None, description="上午安排")
    afternoon: Optional[str] = Field(default=None, description="下午安排")
    evening: Optional[str] = Field(default=None, description="晚上安排")
    meals: Optional[List[str]] = Field(default=None, description="餐饮安排")
    pois: Optional[List[POIFormat]] = Field(default=None, description="当天涉及的POI")

# 预算相关
class BudgetBreakdownFormat(BaseModel):
    """预算明细"""
    transportation: Optional[str] = Field(default=None, description="交通费用")
    accommodation: Optional[str] = Field(default=None, description="住宿费用")
    meals: Optional[str] = Field(default=None, description="餐饮费用")
    attractions: Optional[str] = Field(default=None, description="景点门票费用")
    entertainment: Optional[str] = Field(default=None, description="娱乐费用")
    shopping: Optional[str] = Field(default=None, description="购物预算")
    contingency: Optional[str] = Field(default=None, description="预备金")
    total: str = Field(description="总计")

class PathWayFormat(BaseModel):
    path_type: str = Field(description="路径规划方式，例如：骑行、步行、驾车、公交车")
    path_way: str = Field(description="旅游路线")
class PathFormat(BaseModel):
    path_way: Annotated[List[PathWayFormat] , Field(description="旅游路线")]
class AroundFormat(BaseModel):
    around: str = Field(description="周边信息")

# 完整旅游攻略信息
class AmusementFormat(BaseModel):
    """完整旅游攻略信息"""
    destination: str = Field(description="目的地")
    travel_dates: str = Field(description="出行日期范围")
    duration: int = Field(description="行程天数")
    summary: str = Field(description="行程概要")

    # 交通信息
    transportation: TransportationFormat = Field(description="交通信息")

    # 住宿信息
    accommodation: List[HotelFormat] = Field(description="住宿选项")

    # 天气信息
    weather: List[WeatherFormat] = Field(description="天气预报")

    # 景点与POI
    attractions: List[POIFormat] = Field(description="主要景点")
    restaurants: Optional[List[POIFormat]] = Field(default=None, description="推荐餐厅")
    bars_nightlife: Optional[List[POIFormat]] = Field(default=None, description="酒吧和夜生活")
    shopping: Optional[List[POIFormat]] = Field(default=None, description="购物地点")

    # 每日行程
    daily_itinerary: List[DailyItineraryFormat] = Field(description="每日详细行程")

    # 预算明细
    budget_breakdown: BudgetBreakdownFormat = Field(description="预算明细")

    # 其他建议
    tips: Optional[List[str]] = Field(default=None, description="旅行贴士")
    emergency_contacts: Optional[List[str]] = Field(default=None, description="紧急联系方式")

    # 保留原有字段以兼容
    around: Optional[List[AroundFormat]] = Field(default=None, description="周边信息")
    path: Optional[PathFormat] = Field(default=None, description="旅游路线")
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