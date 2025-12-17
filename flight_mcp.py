'''
机票mcp启动流程
1、cmd切换到虚拟环境mineru
2、set MCP_PORT=8080 # 可以修改端口
3、set MCP_TRANSPORT=sse # 可以修改通信方式
4、切换到虚拟环境mineru后,在终端输入flight-ticket-mcp-server启动机票mcp服务
'''

import requests
import json
import time

MCP_URL = "http://127.0.0.1:8080/mcp"
SESSION_ID = None


# ============================================================
#  解析流式 JSON（SSE）
# ============================================================

def parse_complete_json_from_stream(stream_lines):
    """
    从流式响应中提取 JSON
    """
    full_text = ""
    json_objects = []

    for line in stream_lines:
        if not line:
            continue

        if line.startswith("event:") or line.startswith(": ping"):
            continue

        if line.startswith("data: "):
            line = line[6:]

        full_text += line

        stack = []
        json_start = -1

        for i, c in enumerate(full_text):
            if c == "{":
                if not stack:
                    json_start = i
                stack.append(c)
            elif c == "}":
                if stack:
                    stack.pop()
                    if not stack and json_start != -1:
                        json_str = full_text[json_start:i+1]
                        try:
                            obj = json.loads(json_str)
                            json_objects.append(obj)
                            full_text = full_text[i+1:]
                            json_start = -1
                        except json.JSONDecodeError:
                            pass

    for obj in reversed(json_objects):
        if "jsonrpc" in obj and ("result" in obj or "error" in obj):
            return obj

    return None


# ============================================================
#  初始化 MCP 会话
# ============================================================

def initialize_session():
    """
    初始化 MCP 会话
    """
    global SESSION_ID

    print("正在使用 MCP 协议初始化会话...\n")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "resources": {"subscribe": True},
                "tools": {"listChanged": True},
                "prompts": {"listChanged": True}
            },
            "clientInfo": {
                "name": "mcp-client-python",
                "version": "1.0.0"
            }
        }
    }

    try:
        response = requests.post(
            MCP_URL,
            headers=headers,
            json=payload,
            timeout=30,
            stream=True
        )
        response.raise_for_status()

        # 强制 UTF-8（防止 requests 误解码）
        response.encoding = "utf-8"

        if "mcp-session-id" not in response.headers:
            print("❌ 错误：响应头中没有 mcp-session-id")
            print("响应头：", dict(response.headers))
            return False

        SESSION_ID = response.headers["mcp-session-id"]
        print(f"✅ Session ID 获取成功：{SESSION_ID}")

        # 解析响应内容
        lines = []
        for raw in response.iter_lines(decode_unicode=False):
            if raw:
                line = raw.decode("utf-8", errors="replace")
                lines.append(line)

        result = parse_complete_json_from_stream(lines)
        if result:
            print("初始化响应：")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("⚠️ 未找到有效 JSON 响应")

        return True

    except Exception as e:
        print("初始化失败：", e)
        return False


# ============================================================
#  工具调用
# ============================================================

def call_tool(tool_name, arguments):
    global SESSION_ID

    if not SESSION_ID:
        if not initialize_session():
            return None

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": SESSION_ID
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    try:
        print(f"\n=== 调用工具：{tool_name} ===")
        print("参数：", json.dumps(arguments, ensure_ascii=False))

        response = requests.post(
            MCP_URL,
            headers=headers,
            json=payload,
            timeout=120,
            stream=True
        )
        response.raise_for_status()

        response.encoding = "utf-8"

        lines = []
        for raw in response.iter_lines(decode_unicode=False):
            if raw:
                line = raw.decode("utf-8", errors="replace")
                lines.append(line)

        result = parse_complete_json_from_stream(lines)

        print("工具响应：")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result and "result" in result:
            return result["result"]

        return None

    except Exception as e:
        print("工具调用失败：", e)
        return None


# ============================================================
#  业务 API 封装
# ============================================================

def get_current_date():
    return call_tool("getCurrentDate", {})


def search_flight_routes(departure_city, destination_city, departure_date):
    return call_tool("searchFlightRoutes", {
        "departure_city": departure_city,
        "destination_city": destination_city,
        "departure_date": departure_date
    })


def getTransferFlightsByThreePlace(from_place, transfer_place, to_place, min_transfer_time, max_transfer_time):
    return call_tool("getTransferFlightsByThreePlace", {
        "from_place": from_place,
        "transfer_place": transfer_place,
        "to_place": to_place,
        "min_transfer_time": min_transfer_time,
        "max_transfer_time": max_transfer_time
    })

def getFlightInfo(flight_number):
    return call_tool("getFlightInfo", {
        "flight_number": flight_number
    })

# ============================================================
#  显示结果
# ============================================================

def display_flight_result(result):
    if not result:
        print("❌ 未返回结果")
        return

    if "structuredContent" in result:
        sc = result["structuredContent"]
        print("\n=== 航班查询结果 ===")
        print(json.dumps(sc, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


# ============================================================
#  主程序
# ============================================================

if __name__ == "__main__":
    print("\n=== MCP 客户端测试开始 ===\n")

    if not initialize_session():
        exit(1)

    time.sleep(1)

    # print("\n=== 测试 getCurrentDate ===")
    # date_result = get_current_date()

    # print(json.dumps(date_result, indent=2, ensure_ascii=False))

    # time.sleep(1)

    # print("\n=== 测试 searchFlightRoutes ===")
    # flight = search_flight_routes("沈阳", "长沙", "2025-11-25")
    # display_flight_result(flight)

    # time.sleep(1)

    # print("\n=== 测试 getTransferFlightsByThreePlace ===")
    # date_result = getTransferFlightsByThreePlace("北京", "香港", "纽约", 2.0, 5.0)
    # display_flight_result(date_result)

    time.sleep(1)

    print("\n=== 测试 getFlightInfo ===")
    date_result = getFlightInfo("NH955")  # 根据航班号查询详细航班信息
    display_flight_result(date_result)

    print("\n=== 测试结束 ===")
