"""
工具数据存储测试和使用示例
演示如何使用tool_data_storage模块查询和分析已存储的工具执行数据
"""
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.tool_data_storage import get_tool_storage


def main():
    """测试和演示工具数据存储功能"""
    print("=" * 80)
    print("工具数据存储测试")
    print("=" * 80)

    # 获取存储实例
    storage = get_tool_storage()

    # 1. 获取统计信息
    print("\n【1. 存储统计信息】")
    stats = storage.get_statistics()
    print(f"总类别数: {stats['total_categories']}")
    print(f"总记录数: {stats['total_records']}")
    print("\n各类别详情:")
    for category, info in stats['categories'].items():
        print(f"  - {category}: {info['record_count']} 条记录")
        print(f"    文件路径: {info['file_path']}")

    # 2. 查询指定类别的记录
    print("\n【2. 查询transport类别的最新5条记录】")
    transport_records = storage.query_by_category("transport", limit=5)
    for idx, record in enumerate(transport_records, 1):
        print(f"\n记录 {idx}:")
        print(f"  时间: {record['timestamp']}")
        print(f"  工具: {record['tool_name']}")
        print(f"  输入: {json.dumps(record['tool_input'], ensure_ascii=False)}")
        print(f"  输出: {str(record['tool_output'])[:100]}...")

    # 3. 根据上下文查询
    print("\n【3. 查询特定目的地的记录】")
    # 示例：查询目的地为北京的记录
    beijing_records = storage.query_by_context(
        category="transport",
        context_filters={"destination": "北京"}
    )
    print(f"找到 {len(beijing_records)} 条关于北京的记录")

    # 4. 查询weather类别的记录
    print("\n【4. 查询weather类别的记录】")
    weather_records = storage.query_by_category("weather", limit=3)
    for idx, record in enumerate(weather_records, 1):
        print(f"\n记录 {idx}:")
        print(f"  时间: {record['timestamp']}")
        print(f"  工具: {record['tool_name']}")
        print(f"  上下文: {json.dumps(record['context'], ensure_ascii=False)}")

    # 5. 查询hotel类别的记录
    print("\n【5. 查询hotel类别的记录】")
    hotel_records = storage.query_by_category("hotel", limit=3)
    for idx, record in enumerate(hotel_records, 1):
        print(f"\n记录 {idx}:")
        print(f"  时间: {record['timestamp']}")
        print(f"  工具: {record['tool_name']}")
        print(f"  任务: {record['metadata'].get('task', 'N/A')}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
