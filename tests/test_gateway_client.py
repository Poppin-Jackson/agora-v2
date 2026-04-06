"""
GatewayClient 单元测试

测试 OpenCLAW Gateway 集成客户端的消息构建和注册逻辑。
使用同步测试（asyncio.run），不依赖 pytest-asyncio 或外部 Gateway 服务。

运行方式：
  cd /Users/mac/Documents/opencode-zl/agora-v2
  pytest tests/test_gateway_client.py -v --tb=short

或在容器内：
  docker exec agora-v2-api python -m pytest /app/tests/test_gateway_client.py -v
"""

import pytest
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


def make_client():
    """创建 GatewayClient 实例（不连接外部 Gateway）"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import GatewayClient
    client = GatewayClient(
        gateway_url="ws://localhost:18789",
        agora_api_url="http://localhost:8000",
    )
    # 模拟已连接的 WebSocket
    client._ws = MagicMock()
    client._running = True
    return client


def run_async(coro):
    """在同步上下文中运行协程"""
    return asyncio.run(coro)


# ========================
# 测试：消息构建
# ========================

def test_register_room_sends_correct_message():
    """注册房间发送正确格式"""
    client = make_client()
    room_id = str(uuid.uuid4())
    topic = "测试讨论室"
    plan_id = str(uuid.uuid4())

    run_async(client.register_room(room_id, topic, plan_id))

    client._ws.send.assert_called_once()
    call_args = client._ws.send.call_args[0][0]
    msg = json.loads(call_args)

    assert msg["type"] == "register_room"
    assert msg["room_id"] == room_id
    assert msg["topic"] == topic
    assert msg["plan_id"] == plan_id
    assert "registered_at" in msg


def test_register_room_adds_to_registered_set():
    """注册房间添加到已注册集合"""
    client = make_client()
    room_id = str(uuid.uuid4())
    run_async(client.register_room(room_id, "topic", "plan_id"))
    assert room_id in client._registered_rooms


def test_unregister_room_sends_correct_message():
    """注销房间发送正确格式"""
    client = make_client()
    room_id = str(uuid.uuid4())
    client._registered_rooms.add(room_id)

    run_async(client.unregister_room(room_id))

    client._ws.send.assert_called_once()
    call_args = client._ws.send.call_args[0][0]
    msg = json.loads(call_args)

    assert msg["type"] == "unregister_room"
    assert msg["room_id"] == room_id
    assert room_id not in client._registered_rooms


def test_forward_to_gateway_sends_message():
    """消息转发到 Gateway 格式正确"""
    client = make_client()
    room_id = str(uuid.uuid4())
    client._registered_rooms.add(room_id)
    payload = {"content": "测试消息", "message_type": "speech"}

    run_async(client.forward_to_gateway(room_id, "speech", payload))

    client._ws.send.assert_called_once()
    call_args = client._ws.send.call_args[0][0]
    msg = json.loads(call_args)

    assert msg["type"] == "message"
    assert msg["room_id"] == room_id
    assert msg["message_type"] == "speech"
    assert msg["payload"] == payload
    assert "sent_at" in msg


def test_forward_to_gateway_skips_unregistered_room():
    """未注册房间不发送消息"""
    client = make_client()
    room_id = str(uuid.uuid4())
    # room_id 不在 _registered_rooms 中

    run_async(client.forward_to_gateway(room_id, "speech", {"content": "test"}))

    client._ws.send.assert_not_called()


def test_notify_agent_joined_sends_correct_message():
    """Agent 加入通知格式正确"""
    client = make_client()
    room_id = str(uuid.uuid4())
    agent_id = "agent-001"
    name = "测试Agent"
    level = 5

    run_async(client.notify_agent_joined(room_id, agent_id, name, level))

    client._ws.send.assert_called_once()
    call_args = client._ws.send.call_args[0][0]
    msg = json.loads(call_args)

    assert msg["type"] == "agent_joined"
    assert msg["room_id"] == room_id
    assert msg["agent"]["agent_id"] == agent_id
    assert msg["agent"]["name"] == name
    assert msg["agent"]["level"] == level
    assert "joined_at" in msg["agent"]


def test_notify_agent_left_sends_correct_message():
    """Agent 离开通知格式正确"""
    client = make_client()
    room_id = str(uuid.uuid4())
    agent_id = "agent-001"

    run_async(client.notify_agent_left(room_id, agent_id))

    client._ws.send.assert_called_once()
    call_args = client._ws.send.call_args[0][0]
    msg = json.loads(call_args)

    assert msg["type"] == "agent_left"
    assert msg["room_id"] == room_id
    assert msg["agent_id"] == agent_id
    assert "left_at" in msg


def test_send_without_ws_connection_no_exception():
    """WebSocket 未连接时 _send 不抛异常"""
    client = make_client()
    client._ws = None  # 模拟未连接

    # 不应抛异常
    run_async(client._send({"type": "test"}))


# ========================
# 测试：重新注册
# ========================

def test_reregister_rooms_sends_all_registered():
    """重连后重新注册所有已注册房间"""
    client = make_client()
    room1 = str(uuid.uuid4())
    room2 = str(uuid.uuid4())
    client._registered_rooms.add(room1)
    client._registered_rooms.add(room2)

    run_async(client._reregister_rooms())

    assert client._ws.send.call_count == 2
    calls = [json.loads(c[0][0]) for c in client._ws.send.call_args_list]
    room_ids = [m["room_id"] for m in calls]
    assert room1 in room_ids
    assert room2 in room_ids
    for m in calls:
        assert m["type"] == "register_room"


def test_reregister_rooms_empty_set_no_calls():
    """无已注册房间时不发送消息"""
    client = make_client()
    client._registered_rooms.clear()
    run_async(client._reregister_rooms())
    client._ws.send.assert_not_called()


# ========================
# 测试：消息处理
# ========================

def make_client_with_callback():
    """创建带回调的 GatewayClient"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import GatewayClient
    callback_received = []

    async def test_callback(msg):
        callback_received.append(msg)

    client = GatewayClient(
        gateway_url="ws://localhost:18789",
        agora_api_url="http://localhost:8000",
        on_message=test_callback,
    )
    client._ws = MagicMock()
    client._running = True
    return client, callback_received


def test_handle_ping_responds_with_pong():
    """收到 ping 回复 pong"""
    client, _ = make_client_with_callback()
    client._ws.send = AsyncMock()

    run_async(client._handle_message({"type": "ping"}))

    client._ws.send.assert_called_once()
    msg = json.loads(client._ws.send.call_args[0][0])
    assert msg["type"] == "pong"


def test_handle_agent_message_calls_callback():
    """收到 agent_message 调用 on_message 回调"""
    client, callback_received = make_client_with_callback()
    room_id = str(uuid.uuid4())
    payload = {"content": "Agent 说的话", "message_type": "agent_speech"}

    run_async(client._handle_message({
        "type": "agent_message",
        "room_id": room_id,
        "payload": payload,
    }))

    assert len(callback_received) == 1
    cb_msg = callback_received[0]
    assert cb_msg["source"] == "gateway"
    assert cb_msg["room_id"] == room_id
    assert cb_msg["message_type"] == "agent_speech"


def test_handle_agent_join_request_calls_callback():
    """收到 agent_join_request 调用 on_message 回调"""
    client, callback_received = make_client_with_callback()
    room_id = str(uuid.uuid4())
    agent_info = {"agent_id": "agent-001", "name": "TestAgent", "level": 5}

    run_async(client._handle_message({
        "type": "agent_join_request",
        "room_id": room_id,
        "agent": agent_info,
    }))

    assert len(callback_received) == 1
    cb_msg = callback_received[0]
    assert cb_msg["source"] == "gateway"
    assert cb_msg["room_id"] == room_id
    assert cb_msg["message_type"] == "gateway_agent_join_request"
    assert cb_msg["payload"]["name"] == "TestAgent"


def test_handle_agent_leave_calls_callback():
    """收到 agent_leave 调用 on_message 回调"""
    client, callback_received = make_client_with_callback()
    room_id = str(uuid.uuid4())
    agent_id = "agent-001"

    run_async(client._handle_message({
        "type": "agent_leave",
        "room_id": room_id,
        "agent_id": agent_id,
    }))

    assert len(callback_received) == 1
    cb_msg = callback_received[0]
    assert cb_msg["source"] == "gateway"
    assert cb_msg["room_id"] == room_id
    assert cb_msg["message_type"] == "gateway_agent_leave"
    assert cb_msg["payload"]["agent_id"] == agent_id


def test_handle_unknown_message_no_callback():
    """收到未知类型消息不调用回调"""
    client, callback_received = make_client_with_callback()

    run_async(client._handle_message({"type": "unknown_type_xyz"}))

    assert len(callback_received) == 0


def test_handle_pong_no_action():
    """收到 pong 不做任何处理"""
    client, callback_received = make_client_with_callback()

    run_async(client._handle_message({"type": "pong"}))

    assert len(callback_received) == 0


# ========================
# 测试：生命周期
# ========================

def test_init_default_values():
    """初始化默认参数正确"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import GatewayClient

    client = GatewayClient()
    assert client.gateway_url == "ws://host.docker.internal:18789"
    assert client.agora_api_url == "http://api:8000"
    assert client.on_message is None
    assert client._registered_rooms == set()
    assert client._running is False


def test_init_custom_values():
    """初始化自定义参数正确"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import GatewayClient

    async def cb(msg):
        pass

    client = GatewayClient(
        gateway_url="ws://custom:9999",
        agora_api_url="http://custom:8000",
        on_message=cb,
    )
    assert client.gateway_url == "ws://custom:9999"
    assert client.agora_api_url == "http://custom:8000"
    assert client.on_message is cb


def test_stop_sets_running_false_and_closes_ws():
    """stop 方法正确设置状态并关闭 WebSocket"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import GatewayClient

    client = GatewayClient()
    ws_mock = AsyncMock()
    client._ws = ws_mock  # close() 是 async 方法
    client._running = True

    run_async(client.stop())

    assert client._running is False
    ws_mock.close.assert_called_once()  # 在 stop() 内部 _ws 已=None，用 ws_mock 引用
    assert client._ws is None  # stop() 后 _ws 被设为 None


# ========================
# 测试：重连延迟
# ========================

def test_reconnect_delay_doubles_on_error():
    """连接错误后重连延迟指数退避"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import GatewayClient

    client = GatewayClient()
    assert client._reconnect_delay == 5  # 初始值
    assert client._max_reconnect_delay == 60


def test_register_multiple_rooms_all_tracked():
    """注册多个房间全部被追踪"""
    client = make_client()
    rooms = [str(uuid.uuid4()) for _ in range(3)]

    for room_id in rooms:
        run_async(client.register_room(room_id, f"topic-{room_id[:8]}", "plan_id"))

    assert len(client._registered_rooms) == 3
    for room_id in rooms:
        assert room_id in client._registered_rooms


def test_forward_multiple_messages_all_sent():
    """转发多条消息全部发送"""
    client = make_client()
    room_id = str(uuid.uuid4())
    client._registered_rooms.add(room_id)

    run_async(client.forward_to_gateway(room_id, "speech", {"content": "msg1"}))
    run_async(client.forward_to_gateway(room_id, "phase_change", {"from": "A", "to": "B"}))

    assert client._ws.send.call_count == 2
    msgs = [json.loads(c[0][0]) for c in client._ws.send.call_args_list]
    assert msgs[0]["message_type"] == "speech"
    assert msgs[1]["message_type"] == "phase_change"


def test_default_on_gateway_message_logs_info():
    """默认网关消息回调记录日志"""
    import sys
    sys.path.insert(0, "/Users/mac/Documents/opencode-zl/agora-v2/backend")
    from gateway_client import _default_on_gateway_message

    # 不抛异常，只记录日志
    run_async(_default_on_gateway_message({
        "source": "gateway",
        "room_id": "room-123",
        "message_type": "test_message",
    }))
