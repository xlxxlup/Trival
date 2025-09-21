# main.py
import uuid
from logging_config import setup_logging
from langgraph.types import RunnableConfig
import logging
import asyncio
from agent.amusement_agent import get_graph
setup_logging()  # 全局只需要调用一次

logger = logging.getLogger(__name__)
logger.info("旅游助手启动完成")

# async def main():
#     state = {
#         "query": "我在郑州，我想去北京旅游，帮我指定旅游计划",
#         "messages":[],
#         "plan":None
#     }
#     graph =await get_graph()
#     thread_id =  str(uuid.uuid4())
#     config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
#     res = await graph.ainvoke(state,config=config)
#     # logger.info(res["__interrupt__"])
#     logger.info("旅行助手运行结束")
async def main():
    state = {
    "origin": "郑州",
    "destination": "北京",
    "date": "2025-09-22",
    "people": 1,
    "budget": 3000.0,
    "preferences": "靠窗, 不换乘",
    "messages": [],
    "plan":[],
    "replan":[],
    "amusement_info":None
    }
    graph = await get_graph()
    response = await graph.ainvoke(state)
    print(response)
if __name__ == "__main__":


    asyncio.run(main())