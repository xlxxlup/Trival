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
    retry_delay: float = 1.0,
    error_context: str = "LLM调用",
    **kwargs
) -> Optional[Any]:
    """
    通用的LLM调用重试包装函数

    Args:
        llm_func: LLM调用函数（如 llm.ainvoke 或 chain.ainvoke）
        *args: 传递给llm_func的位置参数
        max_retries: 最大重试次数（默认1次）
        retry_delay: 重试间隔秒数（默认1秒）
        error_context: 错误上下文描述，用于日志
        **kwargs: 传递给llm_func的关键字参数

    Returns:
        LLM响应结果，如果所有重试都失败则返回None
    """
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

            if is_last_attempt:
                logger.error(f"{error_context}: 所有重试均失败（{max_retries + 1}次尝试）")
                logger.error(f"最后一次错误: {str(e)}")
                logger.error(f"错误类型: {type(e).__name__}")
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