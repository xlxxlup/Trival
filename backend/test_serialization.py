"""
测试序列化和反序列化功能
"""
import json
import sys
import os

# 添加backend目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from api.trival import serialize_state, deserialize_state, load_session_store, save_session_store

def test_existing_session_store():
    """测试加载现有的session_store.json"""
    print("=" * 80)
    print("测试1: 加载现有的session_store.json")
    print("=" * 80)

    try:
        store = load_session_store()
        print(f"✅ 成功加载 {len(store)} 个会话")

        for session_id, state in store.items():
            print(f"\n会话ID: {session_id[:8]}...")
            print(f"  - origin: {state.get('origin')}")
            print(f"  - destination: {state.get('destination')}")
            print(f"  - messages数量: {len(state.get('messages', []))}")
            print(f"  - need_intervention: {state.get('need_intervention')}")

    except Exception as e:
        print(f"❌ 加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def test_serialize_deserialize():
    """测试序列化和反序列化"""
    print("\n" + "=" * 80)
    print("测试2: 测试序列化和反序列化")
    print("=" * 80)

    try:
        # 加载现有数据
        store = load_session_store()

        if not store:
            print("⚠️ 没有现有会话数据，跳过测试")
            return True

        # 获取第一个会话进行测试
        session_id = list(store.keys())[0]
        original_state = store[session_id]

        print(f"\n测试会话: {session_id[:8]}...")

        # 测试反序列化
        print("\n1. 测试反序列化...")
        deserialized = deserialize_state(original_state)
        print(f"  ✅ 反序列化成功")
        print(f"  - messages类型: {type(deserialized.get('messages', []))}")
        if deserialized.get('messages'):
            print(f"  - 第一条message类型: {type(deserialized['messages'][0])}")

        # 测试重新序列化
        print("\n2. 测试重新序列化...")
        re_serialized = serialize_state(deserialized)
        print(f"  ✅ 重新序列化成功")

        # 验证可以JSON化
        print("\n3. 测试JSON化...")
        json_str = json.dumps(re_serialized, ensure_ascii=False, indent=2)
        print(f"  ✅ JSON化成功，长度: {len(json_str)} 字符")

        # 测试保存
        print("\n4. 测试保存到文件...")
        test_store = {session_id: deserialized}
        save_session_store(test_store)
        print(f"  ✅ 保存成功")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 80)
    print("测试3: 测试边界情况")
    print("=" * 80)

    test_cases = [
        ("空状态", {}),
        ("空messages", {"messages": []}),
        ("None messages", {"messages": None}),
        ("只有字符串字段", {"origin": "北京", "destination": "上海"}),
    ]

    for name, state in test_cases:
        try:
            print(f"\n测试: {name}")
            serialized = serialize_state(state)
            json.dumps(serialized)  # 验证可以JSON化
            deserialized = deserialize_state(serialized)
            print(f"  ✅ {name} 测试通过")
        except Exception as e:
            print(f"  ❌ {name} 测试失败: {e}")
            return False

    return True

if __name__ == "__main__":
    print("\n开始测试序列化修复...\n")

    results = []
    results.append(("加载现有session store", test_existing_session_store()))
    results.append(("序列化/反序列化", test_serialize_deserialize()))
    results.append(("边界情况", test_edge_cases()))

    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n🎉 所有测试通过！序列化修复成功。")
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息。")

    sys.exit(0 if all_passed else 1)
