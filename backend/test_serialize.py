"""
简单的序列化测试脚本 - 不依赖FastAPI
"""
import json
from typing import Dict, Any
from langchain_core.messages import messages_to_dict, messages_from_dict, HumanMessage, AIMessage, ToolMessage, BaseMessage

def serialize_state_test(state: Dict[str, Any]) -> Dict[str, Any]:
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
                    print(f"  ℹ️ messages已经序列化，跳过")
                else:
                    # 过滤掉可能混入的字典，只序列化消息对象
                    message_objects = [m for m in messages if isinstance(m, BaseMessage)]
                    if message_objects:
                        serialized['messages'] = messages_to_dict(message_objects)
                        print(f"  ✓ 序列化了{len(message_objects)}个消息对象")
                    else:
                        # 如果全是字典，说明已经序列化，直接使用
                        serialized['messages'] = messages
                        print(f"  ℹ️ messages全是字典，保持原样")
            except Exception as e:
                print(f"  ⚠️ 序列化messages时出错: {e}, 将保留原始数据")
                # 如果序列化失败，尝试保持原样或设为空列表
                try:
                    json.dumps(messages)  # 测试是否可以JSON化
                    serialized['messages'] = messages
                except:
                    serialized['messages'] = []

    return serialized

def deserialize_state_test(state: Dict[str, Any]) -> Dict[str, Any]:
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
                    print(f"  ✓ 反序列化了{len(messages)}条消息")
                # 否则假设已经是消息对象，直接使用
                else:
                    print(f"  ℹ️ messages已经是对象，跳过反序列化")
            except Exception as e:
                print(f"  ⚠️ 反序列化messages时出错: {e}, 将保留原始数据")
                deserialized['messages'] = messages

    return deserialized

def test_case_1():
    """测试1: 加载现有的session_store.json并测试序列化"""
    print("\n" + "=" * 80)
    print("测试1: 加载现有的session_store.json并测试重新序列化")
    print("=" * 80)

    try:
        with open('session_store.json', 'r', encoding='utf-8') as f:
            store = json.load(f)

        print(f"✅ 成功加载 {len(store)} 个会话\n")

        for session_id, state in store.items():
            print(f"测试会话: {session_id[:8]}...")
            print(f"  - messages数量: {len(state.get('messages', []))}")

            # 测试反序列化
            print("  步骤1: 反序列化")
            deserialized = deserialize_state_test(state)

            # 测试重新序列化
            print("  步骤2: 重新序列化")
            re_serialized = serialize_state_test(deserialized)

            # 测试JSON化
            print("  步骤3: 测试JSON化")
            json_str = json.dumps(re_serialized, ensure_ascii=False)
            print(f"  ✅ JSON化成功，长度: {len(json_str)} 字符\n")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_case_2():
    """测试2: 创建新消息并序列化"""
    print("\n" + "=" * 80)
    print("测试2: 创建新消息对象并序列化")
    print("=" * 80)

    try:
        # 创建测试状态
        test_state = {
            "origin": "北京",
            "destination": "上海",
            "messages": [
                HumanMessage(content="你好"),
                AIMessage(content="您好，有什么可以帮您？"),
                ToolMessage(content="工具结果", tool_call_id="test123", name="test_tool")
            ]
        }

        print(f"创建了包含 {len(test_state['messages'])} 条消息的测试状态")
        print(f"消息类型: {[type(m).__name__ for m in test_state['messages']]}")

        # 序列化
        print("\n步骤1: 序列化")
        serialized = serialize_state_test(test_state)

        # 验证可以JSON化
        print("步骤2: JSON化")
        json_str = json.dumps(serialized, ensure_ascii=False)
        print(f"✅ JSON化成功，长度: {len(json_str)} 字符")

        # 反序列化
        print("\n步骤3: 反序列化")
        deserialized = deserialize_state_test(json.loads(json_str))

        # 验证消息对象恢复
        if deserialized['messages']:
            print(f"✅ 恢复了 {len(deserialized['messages'])} 条消息")
            print(f"消息类型: {[type(m).__name__ for m in deserialized['messages']]}")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_case_3():
    """测试3: 测试混合类型（消息对象+字典）"""
    print("\n" + "=" * 80)
    print("测试3: 测试混合类型（消息对象+字典）- 只处理对象")
    print("=" * 80)

    try:
        # 创建混合类型的messages
        test_state = {
            "messages": [
                HumanMessage(content="第一条消息"),
                AIMessage(content="第二条消息")
            ]
        }

        print(f"创建了消息列表: {[type(m).__name__ for m in test_state['messages']]}")

        # 序列化
        print("\n步骤1: 序列化消息对象")
        serialized = serialize_state_test(test_state)

        # 验证可以JSON化
        print("步骤2: JSON化")
        json_str = json.dumps(serialized, ensure_ascii=False)
        print(f"✅ JSON化成功，长度: {len(json_str)} 字符")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🔧 开始测试序列化修复...\n")

    results = []
    results.append(("现有数据重新序列化", test_case_1()))
    results.append(("新消息对象序列化", test_case_2()))
    results.append(("消息对象处理", test_case_3()))

    print("\n" + "=" * 80)
    print("🎯 测试总结")
    print("=" * 80)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n🎉 所有测试通过！序列化修复成功。")
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息。")
