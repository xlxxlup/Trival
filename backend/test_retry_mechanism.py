"""
测试重试机制
这个脚本用于验证retry_llm_call函数的重试功能
"""
import asyncio
import logging
import sys
import os

# 添加backend目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.agent_tools import retry_llm_call

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 模拟LLM调用的测试函数
call_count = 0

async def mock_llm_success(*args, **kwargs):
    """模拟成功的LLM调用"""
    global call_count
    call_count += 1
    logger.info(f"Mock LLM调用 #{call_count}: 成功")
    return {"content": "成功响应"}

async def mock_llm_fail_once(*args, **kwargs):
    """模拟第一次失败，第二次成功的LLM调用"""
    global call_count
    call_count += 1
    if call_count == 1:
        logger.info(f"Mock LLM调用 #{call_count}: 失败")
        raise Exception("第一次调用失败")
    logger.info(f"Mock LLM调用 #{call_count}: 成功")
    return {"content": "重试后成功响应"}

async def mock_llm_always_fail(*args, **kwargs):
    """模拟总是失败的LLM调用"""
    global call_count
    call_count += 1
    logger.info(f"Mock LLM调用 #{call_count}: 失败")
    raise Exception(f"第{call_count}次调用失败")

async def mock_llm_return_none(*args, **kwargs):
    """模拟返回None的LLM调用"""
    global call_count
    call_count += 1
    logger.info(f"Mock LLM调用 #{call_count}: 返回None")
    return None

async def test_retry_mechanism():
    """测试重试机制的各种场景"""
    global call_count

    print("\n" + "="*80)
    print("测试1: 成功的LLM调用（无需重试）")
    print("="*80)
    call_count = 0
    result = await retry_llm_call(
        mock_llm_success,
        max_retries=1,
        retry_delay=0.5,
        error_context="测试成功场景"
    )
    print(f"✓ 结果: {result}")
    print(f"✓ 调用次数: {call_count} (预期: 1)")
    assert call_count == 1, f"调用次数应为1，实际为{call_count}"
    assert result is not None, "结果不应为None"

    print("\n" + "="*80)
    print("测试2: 第一次失败，重试后成功")
    print("="*80)
    call_count = 0
    result = await retry_llm_call(
        mock_llm_fail_once,
        max_retries=1,
        retry_delay=0.5,
        error_context="测试重试场景"
    )
    print(f"✓ 结果: {result}")
    print(f"✓ 调用次数: {call_count} (预期: 2)")
    assert call_count == 2, f"调用次数应为2，实际为{call_count}"
    assert result is not None, "结果不应为None"

    print("\n" + "="*80)
    print("测试3: 所有重试都失败")
    print("="*80)
    call_count = 0
    result = await retry_llm_call(
        mock_llm_always_fail,
        max_retries=1,
        retry_delay=0.5,
        error_context="测试失败场景"
    )
    print(f"✓ 结果: {result}")
    print(f"✓ 调用次数: {call_count} (预期: 2)")
    assert call_count == 2, f"调用次数应为2，实际为{call_count}"
    assert result is None, "结果应为None"

    print("\n" + "="*80)
    print("测试4: LLM返回None（应触发重试）")
    print("="*80)
    call_count = 0
    result = await retry_llm_call(
        mock_llm_return_none,
        max_retries=1,
        retry_delay=0.5,
        error_context="测试None响应场景"
    )
    print(f"✓ 结果: {result}")
    print(f"✓ 调用次数: {call_count} (预期: 2)")
    assert call_count == 2, f"调用次数应为2，实际为{call_count}"
    assert result is None, "结果应为None"

    print("\n" + "="*80)
    print("✅ 所有测试通过！")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_retry_mechanism())
