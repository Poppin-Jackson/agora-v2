"""
OpenCLAW Gateway 集成客户端

功能：
- 连接 ws://gateway:18789
- 向 Gateway 注册讨论室，外部 Agent 可发现并加入
- 双向转发消息：Gateway↔Agora Room
- 心跳保活

协议（Gateway标准格式）：
  注册房间:  { "type": "register_room", "room_id": "xxx", "topic": "...", "participants": [...] }
  消息转发:  { "type": "message", "room_id": "xxx", "payload": {...} }
  心跳:      { "type": "ping" } / { "type": "pong" }
  Agent加入: { "type": "agent_joined", "room_id": "xxx", "agent": {...} }
  Agent离开: { "type": "agent_left", "room_id": "xxx", "agent_id": "..." }
"""
import asyncio
import json
import logging
from typing import Optional, Callable, Awaitable
from datetime import datetime

import httpx
import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger("gateway_client")


class GatewayClient:
    """
    OpenCLAW Gateway 客户端
    """

    def __init__(
        self,
        gateway_url: str = "ws://host.docker.internal:18789",
        agora_api_url: str = "http://api:8000",
        on_message: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        self.gateway_url = gateway_url
        self.agora_api_url = agora_api_url
        self.on_message = on_message  # 外部回调：处理来自Gateway的消息

        self._ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_delay = 5  # 秒
        self._max_reconnect_delay = 60
        self._registered_rooms: set = set()
        self._heartbeat_interval = 30  # 秒

    # ----------------------
    # 公开 API
    # ----------------------

    async def start(self):
        """启动 Gateway 客户端（异步）"""
        self._running = True
        logger.info(f"[Gateway] 启动，连接 {self.gateway_url}")
        asyncio.create_task(self._run_loop())

    async def stop(self):
        """停止 Gateway 客户端"""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("[Gateway] 已停止")

    async def register_room(self, room_id: str, topic: str, plan_id: str):
        """
        向 Gateway 注册讨论室
        外部 Agent 可通过 Gateway 发现此房间并加入
        """
        msg = {
            "type": "register_room",
            "room_id": room_id,
            "topic": topic,
            "plan_id": plan_id,
            "registered_at": datetime.now().isoformat(),
        }
        self._registered_rooms.add(room_id)
        await self._send(msg)
        logger.info(f"[Gateway] 注册房间: {room_id} - {topic}")

    async def unregister_room(self, room_id: str):
        """从 Gateway 注销讨论室"""
        msg = {
            "type": "unregister_room",
            "room_id": room_id,
        }
        self._registered_rooms.discard(room_id)
        await self._send(msg)
        logger.info(f"[Gateway] 注销房间: {room_id}")

    async def forward_to_gateway(
        self, room_id: str, message_type: str, payload: dict
    ):
        """
        将 Agora 消息转发给 Gateway（再分发给外部 Agent）
        """
        if room_id not in self._registered_rooms:
            logger.warning(f"[Gateway] 房间未注册，跳过转发: {room_id}")
            return

        msg = {
            "type": "message",
            "room_id": room_id,
            "message_type": message_type,  # 如: speech/phase_change/participant_joined
            "payload": payload,
            "sent_at": datetime.now().isoformat(),
        }
        await self._send(msg)

    async def notify_agent_joined(
        self, room_id: str, agent_id: str, name: str, level: int
    ):
        """通知 Gateway：Agent 加入房间"""
        msg = {
            "type": "agent_joined",
            "room_id": room_id,
            "agent": {
                "agent_id": agent_id,
                "name": name,
                "level": level,
                "joined_at": datetime.now().isoformat(),
            },
        }
        await self._send(msg)

    async def notify_agent_left(self, room_id: str, agent_id: str):
        """通知 Gateway：Agent 离开房间"""
        msg = {
            "type": "agent_left",
            "room_id": room_id,
            "agent_id": agent_id,
            "left_at": datetime.now().isoformat(),
        }
        await self._send(msg)

    # ----------------------
    # 内部方法
    # ----------------------

    async def _send(self, msg: dict):
        """发送 JSON 消息到 Gateway"""
        if self._ws:
            try:
                await self._ws.send(json.dumps(msg))
            except Exception as e:
                logger.error(f"[Gateway] 发送失败: {e}")
        else:
            logger.warning("[Gateway] WebSocket未连接，消息未发送")

    async def _run_loop(self):
        """主循环：连接 → 心跳 → 监听消息"""
        while self._running:
            try:
                async with websockets.connect(
                    self.gateway_url,
                    ping_interval=None,  # 我们自己发心跳
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._ws = ws
                    logger.info("[Gateway] WebSocket已连接")

                    # 连接成功后立即发送注册的所有房间
                    await self._reregister_rooms()

                    # 同时启动心跳和监听任务
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                    listener_task = asyncio.create_task(self._listener_loop())

                    # 等待任一任务结束
                    done, pending = await asyncio.wait(
                        [heartbeat_task, listener_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"[Gateway] 连接关闭: {e}")
            except Exception as e:
                logger.error(f"[Gateway] 连接错误: {e}")

            if self._running:
                logger.info(f"[Gateway] {self._reconnect_delay}s 后重连...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

    async def _listener_loop(self):
        """监听来自 Gateway 的消息"""
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
                await self._handle_message(msg)
            except json.JSONDecodeError:
                logger.warning(f"[Gateway] 收到无效JSON: {raw[:100]}")
            except Exception as e:
                logger.error(f"[Gateway] 处理消息异常: {e}")

    async def _handle_message(self, msg: dict):
        """处理来自 Gateway 的消息"""
        msg_type = msg.get("type", "unknown")

        if msg_type == "ping":
            await self._send({"type": "pong"})
            return

        if msg_type == "pong":
            return  # 心跳响应，无需处理

        # 外部 Agent 发来的消息 → 转发给 Agora Room
        if msg_type == "agent_message":
            room_id = msg.get("room_id")
            payload = msg.get("payload", {})
            logger.info(f"[Gateway] 收到Agent消息 room={room_id}: {payload.get('content', '')[:50]}")

            # 回调给 main.py 处理
            if self.on_message:
                await self.on_message({
                    "source": "gateway",
                    "room_id": room_id,
                    "message_type": payload.get("message_type", "agent_speech"),
                    "payload": payload,
                })

        elif msg_type == "agent_join_request":
            # 外部 Agent 请求加入房间
            room_id = msg.get("room_id")
            agent_info = msg.get("agent", {})
            logger.info(f"[Gateway] Agent加入请求: {agent_info.get('name')} → room={room_id}")
            if self.on_message:
                await self.on_message({
                    "source": "gateway",
                    "room_id": room_id,
                    "message_type": "gateway_agent_join_request",
                    "payload": agent_info,
                })

        elif msg_type == "agent_leave":
            room_id = msg.get("room_id")
            agent_id = msg.get("agent_id")
            logger.info(f"[Gateway] Agent离开: {agent_id} ← room={room_id}")
            if self.on_message:
                await self.on_message({
                    "source": "gateway",
                    "room_id": room_id,
                    "message_type": "gateway_agent_leave",
                    "payload": {"agent_id": agent_id},
                })

        else:
            logger.debug(f"[Gateway] 收到未知消息类型: {msg_type}")

    async def _heartbeat_loop(self):
        """心跳保活"""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            try:
                await self._send({"type": "ping"})
            except Exception:
                break

    async def _reregister_rooms(self):
        """重连后重新注册所有房间"""
        for room_id in list(self._registered_rooms):
            msg = {
                "type": "register_room",
                "room_id": room_id,
                "registered_at": datetime.now().isoformat(),
            }
            await self._send(msg)
        if self._registered_rooms:
            logger.info(f"[Gateway] 重连后重新注册 {len(self._registered_rooms)} 个房间")


# ----------------------
# 全局单例
# ----------------------

_gateway_client: Optional[GatewayClient] = None


def get_gateway_client() -> Optional[GatewayClient]:
    return _gateway_client


async def init_gateway_client(gateway_url: str, agora_api_url: str) -> GatewayClient:
    """
    初始化并启动 Gateway 客户端
    在 main.py lifespan 中调用
    """
    global _gateway_client
    _gateway_client = GatewayClient(
        gateway_url=gateway_url,
        agora_api_url=agora_api_url,
        on_message=_default_on_gateway_message,
    )
    await _gateway_client.start()
    return _gateway_client


async def _default_on_gateway_message(msg: dict):
    """
    默认的 Gateway 消息处理回调
    可被 main.py 覆盖
    """
    # 打印日志，不做业务处理（业务由 main.py 通过 on_message 回调处理）
    logger.info(f"[Gateway→Agora] {msg.get('message_type')} from {msg.get('source')}")
