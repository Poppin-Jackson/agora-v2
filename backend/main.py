"""
Agora-V2 主入口
去中心化多Agent讨论协调系统
"""
import uuid
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum


# ========================
# 枚举定义
# ========================

class PlanStatus(str, Enum):
    DRAFT = "draft"
    INITIATED = "initiated"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RoomPhase(str, Enum):
    INITIATED = "initiated"
    SELECTING = "selecting"
    THINKING = "thinking"
    SHARING = "sharing"
    DEBATE = "debate"
    CONVERGING = "converging"
    HIERARCHICAL_REVIEW = "hierarchical_review"
    DECISION = "decision"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PROBLEM_DETECTED = "problem_detected"


# ========================
# Pydantic 模型
# ========================

class PlanCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(..., min_length=1)
    requirements: List[str] = Field(default_factory=list)
    hierarchy_id: Optional[str] = "default"


class ParticipantAdd(BaseModel):
    agent_id: str
    name: str
    level: int = Field(default=5, ge=1, le=7)
    role: str = "Member"


class SpeechAdd(BaseModel):
    agent_id: str
    content: str


# ========================
# 内存存储（起步）
# ========================

_plans: dict = {}
_rooms: dict = {}
_participants: dict = {}  # room_id -> list[Participant]


# ========================
# FastAPI 应用
# ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Agora-V2 启动")
    yield
    print("Agora-V2 关闭")


app = FastAPI(
    title="Agora-V2",
    version="0.1",
    description="去中心化多Agent讨论协调系统",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================
# WebSocket 管理器
# ========================

class ConnectionManager:
    def __init__(self):
        self.active: dict = {}  # room_id -> list[WebSocket]

    async def connect(self, ws: WebSocket, room_id: str):
        await ws.accept()
        if room_id not in self.active:
            self.active[room_id] = []
        self.active[room_id].append(ws)

    def disconnect(self, ws: WebSocket, room_id: str):
        if room_id in self.active:
            self.active[room_id].remove(ws)
            if not self.active[room_id]:
                del self.active[room_id]

    async def broadcast(self, room_id: str, message: dict):
        if room_id in self.active:
            for ws in self.active[room_id]:
                await ws.send_json(message)


ws_manager = ConnectionManager()


# ========================
# HTTP 端点
# ========================

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/plans", status_code=201)
async def create_plan(data: PlanCreate):
    plan_id = str(uuid.uuid4())
    plan = {
        "plan_id": plan_id,
        "title": data.title,
        "topic": data.topic,
        "requirements": data.requirements,
        "status": PlanStatus.INITIATED,
        "hierarchy_id": data.hierarchy_id,
        "created_at": datetime.now().isoformat(),
        "current_version": "v1.0",
        "versions": ["v1.0"],
    }
    _plans[plan_id] = plan

    # 自动创建讨论室
    room_id = str(uuid.uuid4())
    room = {
        "room_id": room_id,
        "plan_id": plan_id,
        "topic": data.topic,
        "phase": RoomPhase.SELECTING,
        "coordinator_id": "coordinator",
        "created_at": datetime.now().isoformat(),
    }
    _rooms[room_id] = room
    _participants[room_id] = []

    return {"plan": plan, "room": room}


@app.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plans[plan_id]


@app.get("/plans")
async def list_plans():
    return list(_plans.values())


@app.get("/rooms/{room_id}")
async def get_room(room_id: str):
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = _rooms[room_id].copy()
    room["participants"] = _participants.get(room_id, [])
    return room


@app.post("/rooms/{room_id}/participants")
async def add_participant(room_id: str, data: ParticipantAdd):
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    if room_id not in _participants:
        _participants[room_id] = []

    p = {
        "participant_id": str(uuid.uuid4()),
        "agent_id": data.agent_id,
        "name": data.name,
        "level": data.level,
        "role": data.role,
        "joined_at": datetime.now().isoformat(),
        "is_active": True,
    }
    _participants[room_id].append(p)

    await ws_manager.broadcast(room_id, {
        "type": "participant_joined",
        "participant": p,
    })
    return p


@app.post("/rooms/{room_id}/speech")
async def add_speech(room_id: str, data: SpeechAdd):
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "agent_id": data.agent_id,
        "content": data.content,
        "timestamp": datetime.now().isoformat(),
    }

    await ws_manager.broadcast(room_id, {
        "type": "speech",
        **msg,
    })
    return msg


# ========================
# WebSocket 端点
# ========================

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(ws: WebSocket, room_id: str):
    await ws_manager.connect(ws, room_id)
    try:
        await ws.send_json({
            "type": "welcome",
            "room_id": room_id,
            "message": "欢迎加入讨论"
        })

        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await ws.send_json({"type": "pong"})

            elif msg_type == "phase_change":
                if room_id in _rooms:
                    old = _rooms[room_id]["phase"]
                    new = data.get("to_phase")
                    _rooms[room_id]["phase"] = new
                    await ws_manager.broadcast(room_id, {
                        "type": "phase_change",
                        "from_phase": old,
                        "to_phase": new,
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(ws, room_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
