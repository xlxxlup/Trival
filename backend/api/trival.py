import uuid
import logging
from typing import Dict
from fastapi.routing import APIRouter
from .model.trival_model import TrivalFormat, InterventionResponseModel, TravelResponse
from agent.amusement_agent import get_graph

trival_route = APIRouter(tags=["trival"])
logger = logging.getLogger(__name__)

# 简单的内存会话存储（生产环境应使用数据库或Redis）
session_store: Dict[str, dict] = {}

@trival_route.post("/travel", response_model=TravelResponse)
async def travel(data: TrivalFormat):
    """
    开始旅游规划流程
    如果需要人工介入，返回intervention_request并暂停
    否则返回完整的旅游规划结果
    """
    try:
        # 生成会话ID
        session_id = str(uuid.uuid4())
        logger.info(f"创建新会话: {session_id}")

        # 准备初始状态
        initial_state = {
            "origin": data.origin,
            "destination": data.destination,
            "date": data.date,
            "people": data.people,
            "budget": data.budget,
            "preferences": data.preferences,
            "messages": [],
            "plan": [],  # 初始为空列表
            "replan": [],  # 初始为空列表
            "amusement_info": None,  # 初始为None
            "need_intervention": False,
            "intervention_stage": "",
            "intervention_request": None,
            "intervention_response": None
        }

        # 获取并执行graph
        graph = await get_graph()
        logger.info("开始执行旅游规划流程...")
        final_state = await graph.ainvoke(initial_state)

        # 保存会话状态
        session_store[session_id] = final_state
        logger.info(f"会话 {session_id} 状态已保存")

        # 检查是否需要人工介入
        if final_state.get("need_intervention", False):
            logger.info(f"会话 {session_id} 需要人工介入")
            return TravelResponse(
                session_id=session_id,
                status="need_intervention",
                need_intervention=True,
                intervention_request=final_state.get("intervention_request")
            )
        else:
            logger.info(f"会话 {session_id} 已完成")
            # 转换amusement_info为dict
            amusement_info_dict = None
            if final_state.get("amusement_info"):
                amusement_info = final_state["amusement_info"]
                if hasattr(amusement_info, 'dict'):
                    amusement_info_dict = amusement_info.dict()
                elif hasattr(amusement_info, 'model_dump'):
                    amusement_info_dict = amusement_info.model_dump()

            return TravelResponse(
                session_id=session_id,
                status="completed",
                need_intervention=False,
                plan=final_state.get("plan"),
                replan=final_state.get("replan"),
                amusement_info=amusement_info_dict
            )

    except Exception as e:
        logger.error(f"执行旅游规划时出错: {str(e)}", exc_info=True)
        raise

@trival_route.post("/resume", response_model=TravelResponse)
async def resume_travel(data: InterventionResponseModel):
    """
    恢复被人工介入暂停的旅游规划流程
    接收用户的响应并继续执行
    """
    try:
        session_id = data.session_id
        logger.info(f"恢复会话: {session_id}")

        # 获取会话状态
        if session_id not in session_store:
            logger.error(f"会话 {session_id} 不存在")
            raise ValueError(f"会话 {session_id} 不存在或已过期")

        state = session_store[session_id]
        logger.info(f"找到会话 {session_id}，当前阶段: {state.get('intervention_stage')}")

        # 更新用户响应
        state["intervention_response"] = {
            "text_input": data.text_input,
            "selected_options": data.selected_options
        }
        state["need_intervention"] = False
        state["intervention_request"] = None

        # 根据之前的阶段，决定从哪里继续
        intervention_stage = state.get("intervention_stage", "")

        # 获取graph
        graph = await get_graph()

        # 重新执行（从plan或replan继续）
        logger.info(f"从 {intervention_stage} 阶段继续执行...")
        final_state = await graph.ainvoke(state)

        # 更新会话状态
        session_store[session_id] = final_state

        # 再次检查是否需要人工介入
        if final_state.get("need_intervention", False):
            logger.info(f"会话 {session_id} 再次需要人工介入")
            return TravelResponse(
                session_id=session_id,
                status="need_intervention",
                need_intervention=True,
                intervention_request=final_state.get("intervention_request")
            )
        else:
            logger.info(f"会话 {session_id} 已完成")
            # 转换amusement_info为dict
            amusement_info_dict = None
            if final_state.get("amusement_info"):
                amusement_info = final_state["amusement_info"]
                if hasattr(amusement_info, 'dict'):
                    amusement_info_dict = amusement_info.dict()
                elif hasattr(amusement_info, 'model_dump'):
                    amusement_info_dict = amusement_info.model_dump()

            return TravelResponse(
                session_id=session_id,
                status="completed",
                need_intervention=False,
                plan=final_state.get("plan"),
                replan=final_state.get("replan"),
                amusement_info=amusement_info_dict
            )

    except Exception as e:
        logger.error(f"恢复会话时出错: {str(e)}", exc_info=True)
        raise