from fastapi.routing import APIRouter
from .model.trival_model import TrivalFormat
trival_route = APIRouter(tags=["trival"])

@trival_route.post("/travel")
async def travel(data:TrivalFormat):
    # graph.invoke(data)
    return {"message": "获取旅游攻略"}