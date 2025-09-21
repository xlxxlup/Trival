from pydantic import BaseModel, Field
from typing import List, Optional   
class HotelFormat(BaseModel):
    category: str = Field(..., description="酒店类别，如经济型、豪华型等")
    price: float = Field(..., description="酒店的价格")
    location: str = Field(..., description="酒店的位置")
    rating: float = Field(..., description="酒店的评分")
    facilities: List[str] = Field(..., description="酒店的设施，如 WiFi、停车场等")