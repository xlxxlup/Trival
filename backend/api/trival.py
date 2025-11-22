import uuid
import logging
import json
import os
from typing import Dict, Any
from fastapi.routing import APIRouter
from .model.trival_model import TrivalFormat, InterventionResponseModel, TravelResponse
from agent.amusement_agent import get_graph
from logging_config import setup_session_logging, cleanup_session_logging
from langchain_core.messages import messages_to_dict, messages_from_dict, BaseMessage

trival_route = APIRouter(tags=["trival"])
logger = logging.getLogger(__name__)

# 使用JSON文件持久化会话存储
SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", "session_store.json")

def load_session_store() -> Dict[str, dict]:
    """从文件加载会话存储"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """将状态对象序列化为可JSON化的格式"""
    if not state:
        return {}

    serialized = state.copy()

    # 将messages字段转换为可序列化的字典
    if 'messages' in serialized and serialized['messages']:
        messages = serialized['messages']
        # 检查messages是否已经是字典列表（已序列化）
        if messages and isinstance(messages, list) and len(messages) > 0:
            try:
                # 如果第一个元素是字典且包含'type'和'data'键，说明已经序列化过了
                if isinstance(messages[0], dict) and 'type' in messages[0] and 'data' in messages[0]:
                    # 已经序列化，直接使用
                    serialized['messages'] = messages
                else:
                    # 过滤掉可能混入的字典，只序列化消息对象
                    message_objects = [m for m in messages if isinstance(m, BaseMessage)]
                    if message_objects:
                        serialized['messages'] = messages_to_dict(message_objects)
                    else:
                        # 如果全是字典，说明已经序列化，直接使用
                        serialized['messages'] = messages
            except Exception as e:
                logger.warning(f"序列化messages时出错: {e}, 将保留原始数据")
                # 如果序列化失败，尝试保持原样或设为空列表
                try:
                    json.dumps(messages)  # 测试是否可以JSON化
                    serialized['messages'] = messages
                except:
                    serialized['messages'] = []

    # 处理amusement_info对象
    if 'amusement_info' in serialized and serialized['amusement_info']:
        amusement_info = serialized['amusement_info']
        try:
            if isinstance(amusement_info, dict):
                # 已经是字典，保持不变
                serialized['amusement_info'] = amusement_info
            elif hasattr(amusement_info, 'model_dump'):
                serialized['amusement_info'] = amusement_info.model_dump()
            elif hasattr(amusement_info, 'dict'):
                serialized['amusement_info'] = amusement_info.dict()
            else:
                serialized['amusement_info'] = None
        except Exception as e:
            logger.warning(f"序列化amusement_info时出错: {e}")
            serialized['amusement_info'] = None

    # 处理ticket_info对象（如果存在）
    if 'ticket_info' in serialized and serialized['ticket_info']:
        ticket_info = serialized['ticket_info']
        try:
            if isinstance(ticket_info, dict):
                serialized['ticket_info'] = ticket_info
            elif hasattr(ticket_info, 'model_dump'):
                serialized['ticket_info'] = ticket_info.model_dump()
            elif hasattr(ticket_info, 'dict'):
                serialized['ticket_info'] = ticket_info.dict()
            else:
                serialized['ticket_info'] = None
        except Exception as e:
            logger.warning(f"序列化ticket_info时出错: {e}")
            serialized['ticket_info'] = None

    # 处理hotel_info对象（如果存在）
    if 'hotel_info' in serialized and serialized['hotel_info']:
        hotel_info = serialized['hotel_info']
        try:
            if isinstance(hotel_info, dict):
                serialized['hotel_info'] = hotel_info
            elif hasattr(hotel_info, 'model_dump'):
                serialized['hotel_info'] = hotel_info.model_dump()
            elif hasattr(hotel_info, 'dict'):
                serialized['hotel_info'] = hotel_info.dict()
            else:
                serialized['hotel_info'] = None
        except Exception as e:
            logger.warning(f"序列化hotel_info时出错: {e}")
            serialized['hotel_info'] = None

    return serialized

def deserialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """将JSON化的状态反序列化为原始格式"""
    if not state:
        return {}

    deserialized = state.copy()

    # 将messages字段从字典转换回消息对象
    if 'messages' in deserialized and deserialized['messages']:
        messages = deserialized['messages']
        # 检查是否需要反序列化
        if messages and isinstance(messages, list) and len(messages) > 0:
            try:
                # 如果第一个元素是字典且包含'type'和'data'键，需要反序列化
                if isinstance(messages[0], dict) and 'type' in messages[0] and 'data' in messages[0]:
                    deserialized['messages'] = messages_from_dict(messages)
                # 否则假设已经是消息对象，直接使用
            except Exception as e:
                logger.warning(f"反序列化messages时出错: {e}, 将保留原始数据")
                deserialized['messages'] = messages

    return deserialized

def save_session_store(store: Dict[str, dict]):
    """保存会话存储到文件"""
    try:
        serialized_store = {}
        for session_id, state in store.items():
            try:
                serialized_store[session_id] = serialize_state(state)
            except Exception as e:
                logger.error(f"序列化会话 {session_id} 时出错: {e}")
                # 跳过有问题的会话，继续处理其他会话
                continue

        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(serialized_store, f, ensure_ascii=False, indent=2)

        logger.debug(f"成功保存 {len(serialized_store)} 个会话到文件")
    except Exception as e:
        logger.error(f"保存会话存储到文件时出错: {e}")
        raise

@trival_route.post("/travel", response_model=TravelResponse)
async def travel(data: TrivalFormat):
    """
    开始旅游规划流程
    如果需要人工介入，返回intervention_request并暂停
    否则返回完整的旅游规划结果
    """
    logger.info("=" * 80)
    logger.info("【API /travel】收到新的旅游规划请求")
    logger.info(f"请求参数: 出发地={data.origin}, 目的地={data.destination}, 日期={data.date}")
    logger.info(f"           人数={data.people}, 预算={data.budget}")
    logger.debug(f"用户偏好: {data.preferences}")

    try:
        # 生成会话ID
        session_id = str(uuid.uuid4())
        logger.info(f"✓ 创建新会话: {session_id}")

        # 为该会话创建独立的日志文件
        log_file = setup_session_logging(session_id)
        logger.info(f"📁 会话日志文件: {log_file}")

        # 准备初始状态
        initial_state = {
            "origin": data.origin,
            "destination": data.destination,
            "date": data.date,
            "days": data.days,
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
            "intervention_response": None,
            "intervention_count": 0,  # 初始介入次数为0
            "collected_info": {}  # 初始已收集信息为空字典
        }
        logger.debug(f"初始状态已构建")

        # 获取并执行graph
        logger.info("正在获取工作流图...")
        graph = await get_graph()
        logger.info("🚀 开始执行旅游规划流程...")
        final_state = await graph.ainvoke(initial_state)
        logger.info("✅ 工作流执行完成")

        # 保存会话状态
        store = load_session_store()
        store[session_id] = final_state
        save_session_store(store)
        logger.info(f"会话 {session_id} 状态已保存到文件")
        logger.debug(f"当前会话总数: {len(store)}")

        # 检查是否需要人工介入
        if final_state.get("need_intervention", False):
            logger.warning(f"⚠️  会话 {session_id} 需要人工介入")
            intervention_req = final_state.get("intervention_request", {})
            logger.info(f"介入阶段: {final_state.get('intervention_stage')}")
            logger.info(f"介入原因: {intervention_req.get('message', '未提供')}")
            logger.debug(f"完整介入请求: {intervention_req}")

            response = TravelResponse(
                session_id=session_id,
                status="need_intervention",
                need_intervention=True,
                intervention_request=final_state.get("intervention_request")
            )
            logger.info(f"✓ 返回人工介入响应，等待用户通过/resume接口继续")
            logger.info("=" * 80)
            return response
        else:
            logger.info(f"✓ 会话 {session_id} 已完成，无需人工介入")
            # 转换amusement_info为dict
            amusement_info_dict = None
            if final_state.get("amusement_info"):
                amusement_info = final_state["amusement_info"]
                if hasattr(amusement_info, 'dict'):
                    amusement_info_dict = amusement_info.dict()
                elif hasattr(amusement_info, 'model_dump'):
                    amusement_info_dict = amusement_info.model_dump()
                elif isinstance(amusement_info, dict):
                    amusement_info_dict = amusement_info
                logger.debug(f"攻略信息已转换为字典")

            logger.info(f"规划步骤数: {len(final_state.get('plan', []))}")
            logger.info(f"优化规划步骤数: {len(final_state.get('replan', []))}")
            logger.info(f"攻略信息: {'已生成' if amusement_info_dict else '未生成'}")

            response = TravelResponse(
                session_id=session_id,
                status="completed",
                need_intervention=False,
                plan=final_state.get("plan"),
                replan=final_state.get("replan"),
                amusement_info=amusement_info_dict
            )
            logger.info("✓ 返回完整旅游规划结果")
            logger.info("=" * 80)
            return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ 执行旅游规划时出错: {str(e)}")
        logger.error(f"错误类型: {type(e).__name__}")
        logger.exception("完整错误堆栈:")
        logger.error("=" * 80)
        raise

@trival_route.post("/resume", response_model=TravelResponse)
async def resume_travel(data: InterventionResponseModel):
    """
    恢复被人工介入暂停的旅游规划流程
    接收用户的响应并继续执行
    """
    logger.info("=" * 80)
    logger.info("【API /resume】收到恢复请求")
    logger.info(f"会话ID: {data.session_id}")
    logger.debug(f"用户文本输入: {data.text_input}")
    logger.debug(f"用户选择: {data.selected_options}")

    try:
        session_id = data.session_id
        logger.info(f"正在查找会话 {session_id}...")

        # 获取会话状态
        store = load_session_store()
        if session_id not in store:
            logger.error(f"❌ 会话 {session_id} 不存在或已过期")
            logger.error(f"当前存储的会话ID列表: {list(store.keys())}")
            raise ValueError(f"会话 {session_id} 不存在或已过期")

        # 反序列化状态（将messages从字典转回消息对象）
        state = deserialize_state(store[session_id])
        logger.info(f"✓ 找到会话 {session_id}")
        logger.info(f"当前介入阶段: {state.get('intervention_stage')}")
        logger.debug(f"会话状态概览: need_intervention={state.get('need_intervention')}, intervention_request={state.get('intervention_request', {}).get('message', 'None')}")

        # 更新用户响应
        state["intervention_response"] = {
            "text_input": data.text_input,
            "selected_options": data.selected_options
        }
        state["need_intervention"] = False
        state["intervention_request"] = None
        logger.info("✓ 用户响应已更新到会话状态")

        # 根据之前的阶段，决定从哪里继续
        intervention_stage = state.get("intervention_stage", "")
        logger.info(f"将从 {intervention_stage if intervention_stage else '未知'} 阶段继续执行")

        # 获取graph
        logger.info("正在获取工作流图...")
        graph = await get_graph()

        # 重新执行（从plan或replan继续）
        logger.info(f"🚀 从 {intervention_stage} 阶段恢复执行...")
        final_state = await graph.ainvoke(state)
        logger.info("✅ 恢复执行完成")

        # 更新会话状态
        store = load_session_store()
        store[session_id] = final_state
        save_session_store(store)
        logger.info(f"会话 {session_id} 状态已更新")

        # 再次检查是否需要人工介入
        if final_state.get("need_intervention", False):
            logger.warning(f"⚠️  会话 {session_id} 再次需要人工介入")
            intervention_req = final_state.get("intervention_request", {})
            logger.info(f"介入阶段: {final_state.get('intervention_stage')}")
            logger.info(f"介入原因: {intervention_req.get('message', '未提供')}")
            logger.debug(f"完整介入请求: {intervention_req}")

            response = TravelResponse(
                session_id=session_id,
                status="need_intervention",
                need_intervention=True,
                intervention_request=final_state.get("intervention_request")
            )
            logger.info(f"✓ 返回人工介入响应，等待用户再次通过/resume接口继续")
            logger.info("=" * 80)
            return response
        else:
            logger.info(f"✓ 会话 {session_id} 已完成，无需人工介入")
            # 转换amusement_info为dict
            amusement_info_dict = None
            if final_state.get("amusement_info"):
                amusement_info = final_state["amusement_info"]
                if hasattr(amusement_info, 'dict'):
                    amusement_info_dict = amusement_info.dict()
                elif hasattr(amusement_info, 'model_dump'):
                    amusement_info_dict = amusement_info.model_dump()
                elif isinstance(amusement_info, dict):
                    amusement_info_dict = amusement_info
                logger.debug(f"攻略信息已转换为字典")

            logger.info(f"规划步骤数: {len(final_state.get('plan', []))}")
            logger.info(f"优化规划步骤数: {len(final_state.get('replan', []))}")
            logger.info(f"攻略信息: {'已生成' if amusement_info_dict else '未生成'}")

            response = TravelResponse(
                session_id=session_id,
                status="completed",
                need_intervention=False,
                plan=final_state.get("plan"),
                replan=final_state.get("replan"),
                amusement_info=amusement_info_dict
            )
            logger.info("✓ 返回完整旅游规划结果")
            logger.info("=" * 80)
            return response

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ 恢复会话时出错: {str(e)}")
        logger.error(f"错误类型: {type(e).__name__}")
        logger.exception("完整错误堆栈:")
        logger.error("=" * 80)
        raise