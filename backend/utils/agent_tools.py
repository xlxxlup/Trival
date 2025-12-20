import os
import logging
import asyncio
from typing import Any, Callable, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

async def retry_llm_call(
    llm_func: Callable,
    *args,
    max_retries: int = 1,
    retry_delay: float = 0.5,
    error_context: str = "LLM调用",
    fallback_model: Optional[list[str]] = None,
    **kwargs
) -> Optional[Any]:
    """
    通用的LLM调用重试包装函数，支持模型降级

    Args:
        llm_func: LLM调用函数（如 llm.ainvoke 或 chain.ainvoke）
        *args: 传递给llm_func的位置参数
        max_retries: 最大重试次数（默认1次）
        retry_delay: 重试间隔秒数（默认1秒）
        error_context: 错误上下文描述，用于日志
        fallback_model: 降级模型列表（按顺序依次尝试），如果为None则使用默认列表["gemini-3-flash-preview", "gpt-4o-mini"]
        **kwargs: 传递给llm_func的关键字参数

    Returns:
        LLM响应结果，如果所有重试都失败则返回None
    """
    # 如果未提供fallback_model，使用默认列表
    if fallback_model is None:
        fallback_model = ["gemini-3-flash-preview", "gemini-2.5-flash-preview-09-2025-thinking-*"]

    consecutive_429_errors = 0  # 连续429错误计数  貌似是因为token太长了
    current_fallback_index = -1  # 当前使用的后备模型索引，-1表示未降级

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"{error_context}: 第 {attempt + 1}/{max_retries + 1} 次尝试")
            response = await llm_func(*args, **kwargs)

            # 检查响应是否有效
            if response is None:
                raise ValueError("LLM返回了None响应")

            logger.info(f"{error_context}: 调用成功（尝试 {attempt + 1}/{max_retries + 1}）")
            return response

        except Exception as e:
            is_last_attempt = (attempt == max_retries)
            error_str = str(e)

            # 检测429错误（负载饱和）
            is_429_error = "429" in error_str or "负载已饱和" in error_str or "负载饱和" in error_str

            if is_429_error:
                consecutive_429_errors += 1
                logger.warning(f"{error_context}: 检测到429错误（负载饱和），连续第 {consecutive_429_errors} 次")

                # 如果连续遇到2次429错误且还有可用的降级模型，尝试切换
                if consecutive_429_errors >= 2 and fallback_model and current_fallback_index < len(fallback_model) - 1:
                    current_fallback_index += 1
                    target_model = fallback_model[current_fallback_index]
                    logger.warning(f"{error_context}: 连续遇到 {consecutive_429_errors} 次429错误，尝试降级到模型 [{current_fallback_index + 1}/{len(fallback_model)}]: {target_model}")
                    try:
                        # 尝试获取 config 参数并修改模型
                        if 'config' in kwargs and hasattr(kwargs['config'], 'get'):
                            # 如果config是字典类型
                            if 'configurable' not in kwargs['config']:
                                kwargs['config']['configurable'] = {}
                            kwargs['config']['configurable']['model_name'] = target_model
                        elif hasattr(llm_func, '__self__') and hasattr(llm_func.__self__, 'model_name'):
                            # 如果llm_func是绑定方法，尝试修改实例的model_name
                            original_model = llm_func.__self__.model_name
                            logger.info(f"{error_context}: 将LLM实例的model_name从 {original_model} 修改为 {target_model}")
                            llm_func.__self__.model_name = target_model

                        consecutive_429_errors = 0  # 重置计数器
                        logger.info(f"{error_context}: 已切换到降级模型 {target_model}，将继续重试")
                        continue  # 立即重试，不等待
                    except Exception as degrade_error:
                        logger.error(f"{error_context}: 模型降级失败: {str(degrade_error)}")
            else:
                # 非429错误，重置计数器
                consecutive_429_errors = 0

            if is_last_attempt:
                logger.error(f"{error_context}: 所有重试均失败（{max_retries + 1}次尝试）")
                logger.error(f"最后一次错误: {str(e)}")
                logger.error(f"错误类型: {type(e).__name__}")
                if current_fallback_index >= 0:
                    logger.error(f"注意: 已尝试降级到模型 {fallback_model[:current_fallback_index + 1]} 但仍然失败")
                return None
            else:
                logger.warning(f"{error_context}: 第 {attempt + 1} 次尝试失败: {str(e)}")
                logger.info(f"将在 {retry_delay} 秒后重试...")
                await asyncio.sleep(retry_delay)

    return None

def get_llm():
    model = os.getenv("MODEL_NAME")
    api_key = os.getenv("MODEL_API_KEY")
    base_url = os.getenv("MODEL_BASE_URL")

    llm = ChatOpenAI(model_name=model,openai_api_key=api_key,openai_api_base=base_url,temperature=0)
    return llm

async def execute_tool_calls(ai_message, tools: list, logger_instance=None) -> list:
    """
    自定义工具调用函数，替代内置的ToolNode

    Args:
        ai_message: LLM返回的包含工具调用的消息
        tools: 可用工具列表
        logger_instance: 日志记录器实例

    Returns:
        包含ToolMessage的列表
    """
    from langchain_core.messages import ToolMessage
    import json

    log = logger_instance if logger_instance else logger
    tool_messages = []

    # 创建工具名称到工具对象的映射
    tool_map = {tool.name: tool for tool in tools}

    # 兼容新旧版本的tool_calls格式
    tool_calls = []
    if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
        tool_calls = ai_message.tool_calls
        log.info(f"检测到工具调用（新版本格式），数量: {len(tool_calls)}")
    elif hasattr(ai_message, 'additional_kwargs') and "tool_calls" in ai_message.additional_kwargs:
        # 旧版本格式
        raw_tool_calls = ai_message.additional_kwargs['tool_calls']
        for tc in raw_tool_calls:
            tool_calls.append({
                'name': tc.get('function', {}).get('name'),
                'args': json.loads(tc.get('function', {}).get('arguments', '{}')),
                'id': tc.get('id', '')
            })
        log.info(f"检测到工具调用（旧版本格式），数量: {len(tool_calls)}")

    if not tool_calls:
        log.warning("未检测到任何工具调用")
        return []

    # 逐个执行工具调用
    for idx, tool_call in enumerate(tool_calls, 1):
        tool_name = tool_call.get('name', 'unknown')
        tool_args = tool_call.get('args', {})
        tool_id = tool_call.get('id', '')

        log.info(f"=" * 60)
        log.info(f"【执行工具 {idx}/{len(tool_calls)}】")
        log.info(f"工具名称: {tool_name}")
        log.info(f"工具参数: {json.dumps(tool_args, ensure_ascii=False, indent=2)}")
        log.info(f"=" * 60)

        # 查找对应的工具
        if tool_name not in tool_map:
            error_msg = f"工具 '{tool_name}' 不存在"
            log.error(error_msg)
            tool_messages.append(
                ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name
                )
            )
            continue

        # 执行工具
        tool = tool_map[tool_name]
        try:
            log.info(f"🔧 开始执行工具: {tool_name}")

            # 调用工具（始终使用异步调用）
            result = await tool.ainvoke(tool_args)

            log.info(f"✅ 工具执行成功")
            log.info(f"工具返回结果（前500字符）: {str(result)[:500]}")

            # 创建ToolMessage
            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                    name=tool_name
                )
            )

        except Exception as e:
            error_msg = f"工具执行失败: {type(e).__name__}: {str(e)}"
            log.error(error_msg)
            tool_messages.append(
                ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_id,
                    name=tool_name
                )
            )

    log.info(f"=" * 60)
    log.info(f"所有工具执行完成，共执行 {len(tool_messages)} 个工具")
    log.info(f"=" * 60)

    return tool_messages