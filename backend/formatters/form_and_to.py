from pydantic import BaseModel, Field

class FromAndToFormat(BaseModel):
    origin: str = Field(..., description="旅游的出发地")
    destination: str = Field(..., description="旅游的目的地")