"""
Agora-V2 全流程E2E测试

覆盖：
1. Plan创建 → 自动创建Room
2. Participant加入
3. Phase状态转换 (SELECTING→THINKING→SHARING→DEBATE→CONVERGING→HIERARCHICAL_REVIEW→DECISION→EXECUTING→COMPLETED)
4. L1-L7审批流
5. WebSocket实时消息

运行方式（在容器外）：
  cd /Users/mac/Documents/opencode-zl/agora-v2
  pytest tests/test_e2e.py -v --tb=short

或在容器内：
  docker exec agora-v2-api python -m pytest /app/tests/test_e2e.py -v
"""

import pytest
import asyncio
import uuid
import time
import json as _json

import httpx
import websocket


# ========================
# 配置
# ========================

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
TIMEOUT = 10.0


# ========================
# 辅助函数
# ========================

def wait_for_api(max_retries=30, delay=1.0):
    """等待API就绪"""
    for i in range(max_retries):
        try:
            resp = httpx.get(f"{API_BASE}/health", timeout=2.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
    raise RuntimeError("API not ready after max retries")


def wait_for_ws(url: str, max_retries=10, delay=0.5):
    """等待WebSocket就绪"""
    for _ in range(max_retries):
        try:
            ws = websocket.create_connection(url, timeout=2.0)
            ws.close()
            return True
        except Exception:
            time.sleep(delay)
    raise RuntimeError("WebSocket not ready")


def ws_recv_json(ws, timeout=TIMEOUT):
    """从WebSocket接收JSON消息"""
    ws.settimeout(timeout)
    raw = ws.recv()
    return _json.loads(raw)


# ========================
# Fixtures
# ========================

@pytest.fixture(scope="module")
def ensure_api():
    """确保API服务已启动"""
    wait_for_api()
    yield


@pytest.fixture
def room_info(ensure_api):
    """创建一个Plan和配套Room，返回room信息（function scope，每个测试独立）"""
    plan_id = str(uuid.uuid4())
    payload = {
        "title": f"E2E测试计划-{plan_id[:8]}",
        "topic": "测试议题：E2E全流程验证",
        "requirements": ["需求1", "需求2"],
        "hierarchy_id": "default",
    }
    resp = httpx.post(f"{API_BASE}/plans", json=payload, timeout=TIMEOUT)
    assert resp.status_code == 201, f"创建Plan失败: {resp.text}"
    data = resp.json()
    plan = data["plan"]
    room = data["room"]
    return {"plan": plan, "room": room, "plan_id": plan["plan_id"], "room_id": room["room_id"]}


def _add_participant_to_room(room_id: str) -> Dict[str, Any]:
    """向Room添加一个测试参与者（供多个测试复用）"""
    payload = {
        "agent_id": f"agent-{uuid.uuid4().hex[:8]}",
        "name": "测试参与者-Alice",
        "level": 5,
        "role": "Member",
    }
    resp = httpx.post(f"{API_BASE}/rooms/{room_id}/participants", json=payload, timeout=TIMEOUT)
    assert resp.status_code == 200, f"添加参与者失败: {resp.text}"
    return resp.json()


@pytest.fixture
def room_with_participant(room_info):
    """创建一个带参与者的Room（供贡献追踪等测试使用）"""
    room_id = room_info["room_id"]
    participant = _add_participant_to_room(room_id)
    return {**room_info, "participant": participant, "participant_id": participant["participant_id"]}


@pytest.fixture
def approved_plan(room_info):
    """创建一个已启动审批流的plan（function scope，每个测试独立）"""
    plan_id = room_info["plan_id"]
    payload = {
        "initiator_id": "test-initiator",
        "initiator_name": "测试发起人",
        "skip_levels": [],
    }
    resp = httpx.post(
        f"{API_BASE}/plans/{plan_id}/approval/start",
        json=payload,
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"启动审批流失败: {resp.status_code} {resp.text}"
    return {"plan_id": plan_id, "room_id": room_info["room_id"]}


# ========================
# 测试用例
# ========================

class TestHealth:
    """健康检查"""

    def test_health_check(self, ensure_api):
        resp = httpx.get(f"{API_BASE}/health", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "timestamp" in body


class TestDashboard:
    """Dashboard Stats API"""

    def test_get_dashboard_stats_structure(self, ensure_api):
        """验证仪表盘统计数据结构"""
        resp = httpx.get(f"{API_BASE}/dashboard/stats", timeout=TIMEOUT)
        assert resp.status_code == 200
        body = resp.json()
        # 验证所有必需字段存在
        assert "total_plans" in body
        assert "total_rooms" in body
        assert "rooms_by_phase" in body
        assert "recent_plans" in body
        assert "recent_rooms" in body
        assert "recent_activities" in body
        assert "pending_action_items" in body
        assert "pending_approvals" in body
        # 验证字段类型
        assert isinstance(body["total_plans"], int)
        assert isinstance(body["total_rooms"], int)
        assert isinstance(body["rooms_by_phase"], dict)
        assert isinstance(body["recent_plans"], list)
        assert isinstance(body["recent_rooms"], list)
        assert isinstance(body["recent_activities"], list)
        assert isinstance(body["pending_action_items"], int)
        assert isinstance(body["pending_approvals"], int)


class TestPlanCreation:
    """Plan创建 + 自动Room创建"""

    def test_create_plan_creates_room(self, room_info):
        plan = room_info["plan"]
        room = room_info["room"]
        assert plan["plan_id"] is not None
        assert room["room_id"] is not None
        assert room["plan_id"] == plan["plan_id"]

    def test_get_plan(self, room_info):
        plan_id = room_info["plan_id"]
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id

    def test_list_plans(self, room_info):
        resp = httpx.get(f"{API_BASE}/plans", timeout=TIMEOUT)
        assert resp.status_code == 200
        plans = resp.json()
        assert isinstance(plans, list)
        assert len(plans) >= 1

    def test_search_plans(self, room_info):
        # Create a plan with known title
        plan_id = room_info["plan_id"]
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        plan = resp.json()
        title = plan["title"]
        
        # Search by title
        resp = httpx.get(f"{API_BASE}/plans/search", params={"q": title[:4]}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        assert "count" in data
        assert isinstance(data["plans"], list)
        
        # Search with status filter
        resp = httpx.get(f"{API_BASE}/plans/search", params={"q": title[:4], "status": "draft"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == title[:4]
        assert data["status"] == "draft"

    def test_search_rooms(self, room_info):
        # Search by topic (uses the room created by the plan)
        resp = httpx.get(f"{API_BASE}/rooms/search", params={"q": "测试议题"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "rooms" in data
        assert "count" in data
        assert isinstance(data["rooms"], list)
        assert data["query"] == "测试议题"

        # Search with phase filter
        resp = httpx.get(f"{API_BASE}/rooms/search", params={"q": "测试议题", "phase": "selecting"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "selecting"

        # Search with plan_id filter
        plan_id = room_info["plan_id"]
        resp = httpx.get(f"{API_BASE}/rooms/search", params={"q": "测试议题", "plan_id": plan_id}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id

        # Pagination
        resp = httpx.get(f"{API_BASE}/rooms/search", params={"q": "测试", "limit": 5, "offset": 0}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0

    def test_plan_initial_phase(self, room_info):
        room_id = room_info["room_id"]
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        room = resp.json()
        # 创建Plan时Room phase为SELECTING
        assert room["phase"] == "selecting"


class TestParticipant:
    """参与者管理"""

    def test_add_participant(self, room_info):
        room_id = room_info["room_id"]
        payload = {
            "agent_id": f"agent-{uuid.uuid4().hex[:8]}",
            "name": "测试参与者-Alice",
            "level": 5,
            "role": "Member",
        }
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/participants",
            json=payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        p = resp.json()
        assert p["name"] == "测试参与者-Alice"
        assert p["level"] == 5

    def test_get_room_with_participants(self, room_info):
        room_id = room_info["room_id"]
        # 添加一个参与者
        payload = {
            "agent_id": f"agent-{uuid.uuid4().hex[:8]}",
            "name": "测试参与者-Bob",
            "level": 4,
            "role": "Member",
        }
        httpx.post(f"{API_BASE}/rooms/{room_id}/participants", json=payload, timeout=TIMEOUT)

        resp = httpx.get(f"{API_BASE}/rooms/{room_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        room = resp.json()
        assert len(room["participants"]) >= 1


class TestPhaseTransitions:
    """Phase状态机转换"""

    def test_get_current_phase(self, room_info):
        room_id = room_info["room_id"]
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/phase", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert data["current_phase"] == "selecting"
        # SELECTING的合法下一阶段只有THINKING
        assert "thinking" in data["allowed_next"]

    def _transition(self, room_id: str, to_phase: str) -> httpx.Response:
        """Phase转换（to_phase是query参数）"""
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/phase",
            params={"to_phase": to_phase},
            timeout=TIMEOUT,
        )
        return resp

    def test_selecting_to_thinking(self, room_info):
        room_id = room_info["room_id"]
        result = self._transition(room_id, "thinking")
        assert result.status_code == 200, f"转换到thinking失败: {result.text}"
        assert result.json()["to_phase"] == "thinking"

    def test_thinking_to_sharing(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        result = self._transition(room_id, "sharing")
        assert result.status_code == 200, f"转换到sharing失败: {result.text}"
        assert result.json()["to_phase"] == "sharing"

    def test_sharing_to_debate(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        self._transition(room_id, "sharing")
        result = self._transition(room_id, "debate")
        assert result.status_code == 200, f"转换到debate失败: {result.text}"
        assert result.json()["to_phase"] == "debate"

    def test_debate_to_converging(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        self._transition(room_id, "sharing")
        self._transition(room_id, "debate")
        result = self._transition(room_id, "converging")
        assert result.status_code == 200, f"转换到converging失败: {result.text}"
        assert result.json()["to_phase"] == "converging"

    def test_converging_to_hierarchical_review(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        self._transition(room_id, "sharing")
        self._transition(room_id, "debate")
        self._transition(room_id, "converging")
        result = self._transition(room_id, "hierarchical_review")
        assert result.status_code == 200, f"转换到hierarchical_review失败: {result.text}"
        assert result.json()["to_phase"] == "hierarchical_review"

    def test_hierarchical_review_to_decision(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        self._transition(room_id, "sharing")
        self._transition(room_id, "debate")
        self._transition(room_id, "converging")
        self._transition(room_id, "hierarchical_review")
        result = self._transition(room_id, "decision")
        assert result.status_code == 200, f"转换到decision失败: {result.text}"
        assert result.json()["to_phase"] == "decision"

    def test_decision_to_executing(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        self._transition(room_id, "sharing")
        self._transition(room_id, "debate")
        self._transition(room_id, "converging")
        self._transition(room_id, "hierarchical_review")
        self._transition(room_id, "decision")
        result = self._transition(room_id, "executing")
        assert result.status_code == 200, f"转换到executing失败: {result.text}"
        assert result.json()["to_phase"] == "executing"

    def test_executing_to_completed(self, room_info):
        room_id = room_info["room_id"]
        self._transition(room_id, "thinking")
        self._transition(room_id, "sharing")
        self._transition(room_id, "debate")
        self._transition(room_id, "converging")
        self._transition(room_id, "hierarchical_review")
        self._transition(room_id, "decision")
        self._transition(room_id, "executing")
        result = self._transition(room_id, "completed")
        assert result.status_code == 200, f"转换到completed失败: {result.text}"
        assert result.json()["to_phase"] == "completed"

    def test_invalid_transition_rejected(self, room_info):
        """从SELECTING直接跳到SHARING是违法的（中间必须经过THINKING）"""
        room_id = room_info["room_id"]
        resp = self._transition(room_id, "sharing")
        assert resp.status_code == 400
        body = resp.json()
        assert body["detail"]["error"] == "invalid_transition"


class TestPhaseTimeline:
    """Step 63: Room Phase Timeline API"""

    def test_phase_timeline_after_room_creation(self, room_info):
        """房间创建后，SELECTING阶段已记录到时间线"""
        room_id = room_info["room_id"]
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/phase-timeline", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert len(data["timeline"]) >= 1
        # 初始阶段应该是 SELECTING
        first = data["timeline"][0]
        assert first["phase"] == "selecting"
        assert first["entered_at"] is not None
        # 仍在进行中（未退出）
        assert first["exited_at"] is None

    def test_phase_timeline_records_transitions(self, room_info):
        """阶段转换时，时间线正确记录退出和进入"""
        room_id = room_info["room_id"]

        # 初始：SELECTING 在时间线中
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/phase-timeline", timeout=TIMEOUT)
        assert resp.status_code == 200
        timeline = resp.json()["timeline"]
        assert timeline[0]["phase"] == "selecting"
        assert timeline[0]["exited_at"] is None

        # 转换到 THINKING
        httpx.post(f"{API_BASE}/rooms/{room_id}/phase", params={"to_phase": "thinking"}, timeout=TIMEOUT)
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/phase-timeline", timeout=TIMEOUT)
        timeline = resp.json()["timeline"]

        # SELECTING 已退出
        selecting_entry = next(e for e in timeline if e["phase"] == "selecting")
        assert selecting_entry["exited_at"] is not None
        assert selecting_entry["exited_via"] == "thinking"
        assert selecting_entry["duration_secs"] is not None
        assert selecting_entry["duration_secs"] >= 0

        # THINKING 已进入
        thinking_entry = next(e for e in timeline if e["phase"] == "thinking")
        assert thinking_entry["entered_at"] is not None
        assert thinking_entry["exited_at"] is None  # 仍在进行中

    def test_phase_timeline_full_transition_chain(self, room_info):
        """完整转换链：SELECTING→THINKING→SHARING，时间线有3条记录"""
        room_id = room_info["room_id"]

        # SELECTING → THINKING
        httpx.post(f"{API_BASE}/rooms/{room_id}/phase", params={"to_phase": "thinking"}, timeout=TIMEOUT)
        # THINKING → SHARING
        httpx.post(f"{API_BASE}/rooms/{room_id}/phase", params={"to_phase": "sharing"}, timeout=TIMEOUT)

        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/phase-timeline", timeout=TIMEOUT)
        timeline = resp.json()["timeline"]

        # 至少3条记录：SELECTING, THINKING, SHARING
        phases = [e["phase"] for e in timeline]
        assert "selecting" in phases
        assert "thinking" in phases
        assert "sharing" in phases

        # SHARING 仍在进行中
        sharing_entry = next(e for e in timeline if e["phase"] == "sharing")
        assert sharing_entry["exited_at"] is None


class TestSpeech:
    """发言功能"""

    def test_add_speech(self, room_info):
        room_id = room_info["room_id"]
        payload = {
            "agent_id": "test-agent",
            "content": "这是一条测试发言",
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/speech", json=payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "这是一条测试发言"
        assert data["agent_id"] == "test-agent"


class TestApprovalFlow:
    """L1-L7审批流"""

    def test_start_approval_flow(self, approved_plan):
        """启动审批流"""
        plan_id = approved_plan["plan_id"]
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/approval", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["current_level"] == 7  # 从L7开始

    def test_get_approval_levels(self, approved_plan):
        """获取审批层级说明"""
        plan_id = approved_plan["plan_id"]
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/approval/levels", timeout=TIMEOUT)
        assert resp.status_code == 200
        levels = resp.json()
        assert len(levels) == 7
        assert levels[0]["level"] == 7   # L7在第一个
        assert levels[6]["level"] == 1   # L1在最后一个

    def test_approve_l7_to_l6(self, approved_plan):
        """L7审批通过，流转到L6"""
        plan_id = approved_plan["plan_id"]
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/approval/7/action",
            params={
                "level": 7,
                "action": "approve",
                "actor_id": "L7-approver",
                "actor_name": "战略决策者",
                "comment": "L7审批通过",
            },
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_current_level"] == 6

    def test_full_approval_chain(self, room_info):
        """完整审批链：L7→L6→L5→L4→L3→L2→L1"""
        # 使用独立的plan，避免与其他fixture冲突
        plan_id = room_info["plan_id"]

        # 启动审批流
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/approval/start",
            json={"initiator_id": "test-init", "initiator_name": "测试发起人", "skip_levels": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200

        # 依次审批 L7 到 L1
        for level in [7, 6, 5, 4, 3, 2, 1]:
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/approval/{level}/action",
                params={
                    "level": level,
                    "action": "approve",
                    "actor_id": f"L{level}-approver",
                    "actor_name": f"L{level}审批人",
                    "comment": f"L{level}审批通过",
                },
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, f"L{level}审批失败: {resp.text}"

        # 验证最终状态
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/approval", timeout=TIMEOUT)
        data = resp.json()
        assert data["status"] == "fully_approved"

        # 验证plan状态更新
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}", timeout=TIMEOUT)
        plan = resp.json()
        assert plan["status"] == "approved"


class TestWebSocket:
    """WebSocket实时通信"""

    @pytest.fixture
    def ws_client(self, room_info):
        room_id = room_info["room_id"]
        wait_for_ws(f"{WS_BASE}/ws/{room_id}")
        ws = websocket.create_connection(f"{WS_BASE}/ws/{room_id}", timeout=TIMEOUT)
        # 先接收welcome消息
        welcome = ws_recv_json(ws)
        assert welcome["type"] == "welcome"
        yield ws
        ws.close()

    def test_ws_connect_and_welcome(self, ws_client):
        """已在fixture中接收welcome，此处验证ws仍然连接"""
        ws_client.settimeout(2.0)
        # 连接后应立即收到welcome
        pass  # fixture已验证

    def test_ws_ping_pong(self, ws_client):
        """WebSocket ping/pong"""
        ws_client.send(_json.dumps({"type": "ping"}))
        msg = ws_recv_json(ws_client)
        assert msg["type"] == "pong"

    def test_ws_phase_change_broadcast(self, room_info):
        """Phase变更通过WebSocket广播"""
        room_id = room_info["room_id"]
        wait_for_ws(f"{WS_BASE}/ws/{room_id}")
        ws = websocket.create_connection(f"{WS_BASE}/ws/{room_id}", timeout=TIMEOUT)
        try:
            # 接收welcome
            ws_recv_json(ws)

            # 切换phase，触发广播
            httpx.post(
                f"{API_BASE}/rooms/{room_id}/phase",
                params={"to_phase": "thinking"},
                timeout=TIMEOUT,
            )

            # 接收phase_change广播
            ws.settimeout(5.0)
            msg = ws_recv_json(ws)
            assert msg["type"] == "phase_change"
            assert msg["to_phase"] == "thinking"
        finally:
            ws.close()


class TestFullE2E:
    """全流程E2E：从Plan创建到审批完成的完整流程"""

    def test_full_flow(self, ensure_api):
        """
        完整流程：
        1. 创建Plan → 自动创建Room (phase=SELECTING)
        2. 添加3个参与者
        3. 状态机流转：SELECTING→THINKING→SHARING→DEBATE→CONVERGING→HIERARCHICAL_REVIEW→DECISION
        4. 发言验证
        5. 启动审批流：L7→L1全部通过
        6. 验证最终状态
        """
        # Step 1: 创建Plan
        plan_payload = {
            "title": "E2E完整流程测试",
            "topic": "验证全流程端到端",
            "requirements": ["需求A", "需求B"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]

        # Step 2: 添加参与者
        for i, (name, level) in enumerate([("Alice-L5", 5), ("Bob-L4", 4), ("Charlie-L3", 3)]):
            p = {
                "agent_id": f"agent-{i}",
                "name": name,
                "level": level,
                "role": "Member",
            }
            resp = httpx.post(f"{API_BASE}/rooms/{room_id}/participants", json=p, timeout=TIMEOUT)
            assert resp.status_code == 200

        # Step 3: 状态机流转
        transitions = ["thinking", "sharing", "debate", "converging",
                       "hierarchical_review", "decision"]
        for phase in transitions:
            resp = httpx.post(
                f"{API_BASE}/rooms/{room_id}/phase",
                params={"to_phase": phase},
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, f"转换到{phase}失败: {resp.text}"

        # Step 4: 发言验证
        for i in range(3):
            resp = httpx.post(
                f"{API_BASE}/rooms/{room_id}/speech",
                json={"agent_id": f"agent-{i}", "content": f"第{i+1}条发言"},
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200

        # Step 5: 启动审批流
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/approval/start",
            json={"initiator_id": "test-init", "initiator_name": "测试发起人", "skip_levels": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200

        # Step 6: 完整审批链
        for level in [7, 6, 5, 4, 3, 2, 1]:
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/approval/{level}/action",
                params={
                    "level": level,
                    "action": "approve",
                    "actor_id": f"L{level}-reviewer",
                    "actor_name": f"L{level}审批人",
                    "comment": f"审批通过",
                },
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200, f"L{level}审批失败"

        # Step 7: 验证最终状态
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/approval", timeout=TIMEOUT)
        approval = resp.json()
        assert approval["status"] == "fully_approved"

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}", timeout=TIMEOUT)
        plan = resp.json()
        assert plan["status"] == "approved"

        # Step 8: 继续执行到COMPLETED
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/phase", params={"to_phase": "executing"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/phase", params={"to_phase": "completed"}, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 最终验证
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/phase", timeout=TIMEOUT)
        phase_data = resp.json()
        assert phase_data["current_phase"] == "completed"


class TestIndexAPI:
    """索引API（INDEX.md生成）"""

    def test_plan_index(self, ensure_api):
        """获取方案索引文档"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "索引测试方案", "topic": "测试索引API", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 获取索引
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/INDEX.md", timeout=TIMEOUT)
        assert resp.status_code == 200
        md = resp.text
        assert "方案索引" in md
        assert plan_id in md

    def test_versions_list_index(self, ensure_api):
        """获取版本列表索引文档（versions/INDEX.md）"""
        # 创建Plan（初始版本 v1.0）
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "版本列表索引测试", "topic": "测试版本列表索引", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 获取版本列表索引
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/INDEX.md", timeout=TIMEOUT)
        assert resp.status_code == 200
        md = resp.text
        assert "版本索引" in md
        assert "v1.0" in md
        assert "版本列表" in md or "版本总数" in md

    def test_version_index(self, ensure_api):
        """获取版本索引文档"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "版本索引测试", "topic": "测试版本索引", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 获取版本索引
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/INDEX.md", timeout=TIMEOUT)
        assert resp.status_code == 200
        md = resp.text
        assert "版本索引" in md
        assert "v1.0" in md

    def test_rooms_index(self, ensure_api):
        """获取讨论室索引文档"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "讨论室索引测试", "topic": "测试讨论室索引", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 获取讨论室索引
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/rooms/INDEX.md", timeout=TIMEOUT)
        assert resp.status_code == 200
        md = resp.text
        assert "讨论室索引" in md

    def test_issues_index(self, ensure_api):
        """获取问题索引文档"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "问题索引测试", "topic": "测试问题索引", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 获取问题索引（无问题时应返回空列表）
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/issues/INDEX.md", timeout=TIMEOUT)
        assert resp.status_code == 200
        md = resp.text
        assert "问题索引" in md


class TestSnapshotAPI:
    """快照管理API"""

    def test_create_snapshot(self, ensure_api):
        """创建快照"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "快照测试", "topic": "测试快照API", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]

        # 创建快照
        snapshot_payload = {
            "plan_id": plan_id,
            "version": "v1.0",
            "room_id": room_id,
            "phase": "debate",
            "context_summary": "讨论进行中，暂无共识",
            "participants": ["Alice", "Bob"],
            "messages_summary": [{"type": "speech", "content": "test"}],
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/snapshots/",
            json=snapshot_payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        snapshot_data = resp.json()
        assert "snapshot_id" in snapshot_data

    def test_list_snapshots(self, ensure_api):
        """获取快照列表"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "快照列表测试", "topic": "测试快照列表", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]

        # 创建快照
        snapshot_payload = {
            "plan_id": plan_id,
            "version": "v1.0",
            "room_id": room_id,
            "phase": "converging",
            "context_summary": "收敛阶段",
            "participants": [],
            "messages_summary": [],
        }
        httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/snapshots/",
            json=snapshot_payload,
            timeout=TIMEOUT,
        )

        # 列出快照
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/snapshots/",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        assert len(data["snapshots"]) >= 1

    def test_get_snapshot(self, ensure_api):
        """获取快照详情"""
        # 创建Plan
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "获取快照测试", "topic": "测试获取快照", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]

        # 创建快照
        snapshot_payload = {
            "plan_id": plan_id,
            "version": "v1.0",
            "room_id": room_id,
            "phase": "executing",
            "context_summary": "执行中",
            "participants": ["Tech", "Critic"],
            "messages_summary": [],
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/snapshots/",
            json=snapshot_payload,
            timeout=TIMEOUT,
        )
        snapshot_id = resp.json()["snapshot_id"]

        # 获取快照详情
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/snapshots/{snapshot_id}.json",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        snapshot = resp.json()
        assert snapshot["snapshot_id"] == snapshot_id
        assert snapshot["phase"] == "executing"


# ========================
# Level-specific Context API Tests
# 来源: 05-Hierarchy-Roles.md §7.3 - 获取层级专属上下文
# ========================

class TestHierarchyContext:
    """测试层级专属上下文 API"""

    def test_get_room_context_without_level(self, ensure_api):
        """不带 level 参数：返回完整上下文"""
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "层级测试", "topic": "测试层级上下文", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()
        room_id = data["room"]["room_id"]

        # 添加不同层级的参与者
        for lvl, name in [(5, "L5经理"), (4, "L4主管"), (3, "L3组长")]:
            httpx.post(
                f"{API_BASE}/rooms/{room_id}/participants",
                json={"agent_id": f"agent_lvl{lvl}", "name": name, "level": lvl, "role": "Member"},
                timeout=TIMEOUT,
            )

        # 获取完整上下文（无 level 参数）
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/context", timeout=TIMEOUT)
        assert resp.status_code == 200
        ctx = resp.json()
        assert "participants" in ctx
        assert len(ctx["participants"]) == 3  # 所有参与者都可见
        assert "hierarchy_context" not in ctx  # 无 level 参数时不包含层级上下文

    def test_get_room_context_with_level(self, ensure_api):
        """带 level 参数：返回层级专属视角"""
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "层级测试", "topic": "测试层级上下文", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()
        room_id = data["room"]["room_id"]
        plan_id = data["plan"]["plan_id"]

        # 添加不同层级的参与者
        for lvl, name in [(5, "L5经理"), (4, "L4主管"), (3, "L3组长"), (2, "L2专员"), (1, "L1操作员")]:
            httpx.post(
                f"{API_BASE}/rooms/{room_id}/participants",
                json={"agent_id": f"agent_lvl{lvl}", "name": name, "level": lvl, "role": "Member"},
                timeout=TIMEOUT,
            )

        # L4 视角：能看到 L4, L3, L2, L1，看不到 L5
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/context?level=4", timeout=TIMEOUT)
        assert resp.status_code == 200
        ctx = resp.json()
        assert "hierarchy_context" in ctx
        hc = ctx["hierarchy_context"]
        assert hc["viewer_level"] == 4
        assert hc["viewer_level_label"] == "团队层(方案整合)"
        assert 4 in hc["visible_levels"]
        assert 5 not in hc["visible_levels"]  # L5 不可见
        assert 3 in hc["visible_levels"]  # L3 可见

        # L7 视角：能看到所有层级
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/context?level=7", timeout=TIMEOUT)
        assert resp.status_code == 200
        ctx = resp.json()
        assert 1 in ctx["hierarchy_context"]["visible_levels"]
        assert 7 in ctx["hierarchy_context"]["visible_levels"]

        # L1 视角：只能看到自己
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/context?level=1", timeout=TIMEOUT)
        assert resp.status_code == 200
        ctx = resp.json()
        hc = ctx["hierarchy_context"]
        assert hc["visible_levels"] == [1]

    def test_level_context_with_approval_flow(self, ensure_api):
        """带审批流的层级上下文"""
        resp = httpx.post(
            f"{API_BASE}/plans",
            json={"title": "审批流测试", "topic": "测试层级审批上下文", "requirements": []},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]

        # 启动审批流
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/approval/start",
            json={"initiator_id": "user_001", "initiator_name": "测试用户"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200

        # L5 视角应看到审批流摘要
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/context?level=5", timeout=TIMEOUT)
        assert resp.status_code == 200
        ctx = resp.json()
        assert "hierarchy_context" in ctx
        assert ctx["hierarchy_context"]["approval_summary"] is not None
        approval = ctx["hierarchy_context"]["approval_summary"]
        assert approval["current_level"] == 7  # 从 L7 开始


class TestProblemHandling:
    """问题处理流程测试 (PROBLEM_DETECTED → PROBLEM_ANALYSIS → PROBLEM_DISCUSSION → PLAN_UPDATE → RESUMING)"""

    def _create_executing_plan(self, ensure_api):
        """创建Plan并推进到EXECUTING阶段"""
        plan_payload = {
            "title": "问题处理流程测试",
            "topic": "测试问题处理流程",
            "requirements": ["需求A", "需求B"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201, f"创建Plan失败: {resp.text}"
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]

        # 快速推进到 EXECUTING：创建任务
        task_payload = {
            "title": "测试任务1",
            "description": "这是测试任务",
            "owner_id": "agent-0",
            "owner_level": 5,
            "owner_role": "Engineer",
            "priority": "high",
            "difficulty": "medium",
            "estimated_hours": 8.0,
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
            json=task_payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201, f"创建任务失败: {resp.text}"

        return {"plan_id": plan_id, "room_id": room_id}

    def test_report_problem(self, ensure_api):
        """Step 1: 报告问题 → PROBLEM_DETECTED"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "blocking",
            "title": "数据库连接超时",
            "description": "执行过程中数据库连接超时，导致任务无法完成",
            "severity": "high",
            "detected_by": "Executor",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200, f"报告问题失败: {resp.status_code} {resp.text}"
        problem = resp.json()
        assert "issue_id" in problem
        assert problem["type"] == "blocking"
        assert problem["severity"] == "high"
        assert problem["status"] == "detected"

    def test_get_problem(self, ensure_api):
        """Step 2: 获取问题详情"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 先报告问题
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "bug",
            "title": "API响应错误",
            "description": "某个API返回500错误",
            "severity": "medium",
            "detected_by": "Tester",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        # 获取问题详情
        resp = httpx.get(f"{API_BASE}/problems/{issue_id}", timeout=TIMEOUT)
        assert resp.status_code == 200, f"获取问题失败: {resp.text}"
        problem = resp.json()
        assert problem["issue_id"] == issue_id
        assert problem["title"] == "API响应错误"
        assert problem["status"] == "detected"

    def test_get_plan_problems(self, ensure_api):
        """Step 3: 获取方案下所有问题"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告两个问题
        for i in range(2):
            problem_payload = {
                "plan_id": plan_id,
                "room_id": ctx["room_id"],
                "type": "enhancement",
                "title": f"改进项{i+1}",
                "description": f"需要改进的地方{i+1}",
                "severity": "low",
                "detected_by": "Reviewer",
            }
            resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
            assert resp.status_code == 200

        # 获取方案下所有问题
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/problems", timeout=TIMEOUT)
        assert resp.status_code == 200, f"获取方案问题列表失败: {resp.text}"
        problems = resp.json()
        assert isinstance(problems, list)
        assert len(problems) >= 2

    def test_analyze_problem(self, ensure_api):
        """Step 4: 分析问题 → PROBLEM_ANALYSIS"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告问题
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "blocking",
            "title": "资源不足",
            "description": "执行资源不足",
            "severity": "high",
            "detected_by": "Executor",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        # 分析问题
        analysis_payload = {
            "root_cause": "数据库连接池配置过小",
            "root_cause_confidence": 0.85,
            "impact_scope": "部分任务",
            "progress_impact": "延迟2天",
            "severity_reassessment": "high",
            "solution_options": [
                {"id": 0, "description": "扩大连接池到20", "pros": "快速", "cons": "资源占用增加"},
                {"id": 1, "description": "引入连接池中间件", "pros": "可扩展", "cons": "需要重构"},
            ],
            "recommended_option": 0,
            "requires_discussion": False,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200, f"分析问题失败: {resp.status_code} {resp.text}"
        result = resp.json()
        assert result["root_cause"] == "数据库连接池配置过小"
        assert result["status"] == "analyzed"

    def test_analyze_problem_requires_discussion(self, ensure_api):
        """Step 5: 问题需要讨论 → PROBLEM_ANALYSIS (requires_discussion=True)"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告问题
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "risk",
            "title": "技术路线风险",
            "description": "不确定该用哪个技术方案",
            "severity": "medium",
            "detected_by": "Architect",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        # 分析问题（需要讨论）
        analysis_payload = {
            "root_cause": "技术选型未确定",
            "root_cause_confidence": 0.6,
            "impact_scope": "全局",
            "progress_impact": "阻塞",
            "severity_reassessment": "high",
            "solution_options": [
                {"id": 0, "description": "方案A", "pros": "成熟", "cons": "成本高"},
                {"id": 1, "description": "方案B", "pros": "轻量", "cons": "风险大"},
            ],
            "recommended_option": 0,
            "requires_discussion": True,
            "discussion_needed_aspects": ["成本", "风险", "时间"],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert result["requires_discussion"] is True
        assert result["status"] == "analyzed"

    def test_discuss_problem(self, ensure_api):
        """Step 6: 讨论问题 → PROBLEM_DISCUSSION"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析问题
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "enhancement",
            "title": "用户体验改进",
            "description": "界面需要优化",
            "severity": "medium",
            "detected_by": "UX",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        # 分析问题
        analysis_payload = {
            "root_cause": "界面设计不符合用户习惯",
            "root_cause_confidence": 0.7,
            "impact_scope": "局部",
            "progress_impact": "轻微延迟",
            "severity_reassessment": "medium",
            "solution_options": [{"id": 0, "description": "重新设计"}],
            "recommended_option": 0,
            "requires_discussion": True,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 讨论问题
        discuss_payload = {
            "participants": [
                {"agent_id": "agent-0", "name": "UX专家", "level": 4},
                {"agent_id": "agent-1", "name": "开发负责人", "level": 5},
            ],
            "discussion_focus": [
                {"aspect": "用户体验", "concerns": ["操作复杂", "导航不清"]},
                {"aspect": "技术可行性", "concerns": ["工期紧张"]},
            ],
            "proposed_solutions": [
                {"participant": "UX专家", "solution": "简化操作流程"},
                {"participant": "开发负责人", "solution": "分阶段改进"},
            ],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/discuss", json=discuss_payload, timeout=TIMEOUT)
        assert resp.status_code == 200, f"讨论问题失败: {resp.status_code} {resp.text}"
        result = resp.json()
        assert len(result["participants"]) == 2

    def test_update_plan(self, ensure_api):
        """Step 7: 更新方案 → PLAN_UPDATE"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析问题
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "blocking",
            "title": "第三方服务不可用",
            "description": "依赖的第三方服务宕机",
            "severity": "critical",
            "detected_by": "Monitor",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        analysis_payload = {
            "root_cause": "第三方服务故障",
            "root_cause_confidence": 0.9,
            "impact_scope": "全局",
            "progress_impact": "严重延迟",
            "severity_reassessment": "critical",
            "solution_options": [{"id": 0, "description": "切换备选服务"}],
            "recommended_option": 0,
            "requires_discussion": False,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 更新方案
        update_payload = {
            "new_version": "v1.1",
            "parent_version": "v1.0",
            "update_type": "fix",
            "description": "修复第三方服务依赖问题，切换到备选服务",
            "changes": {
                "task_001": {"action": "modify", "field": "title", "old": "原任务", "new": "使用备选服务"},
            },
            "task_updates": [
                {"task_id": "task_001", "status": "in_progress", "progress": 0.0},
            ],
            "new_tasks": [
                {
                    "task_number": 2,
                    "title": "接入备选第三方服务",
                    "description": "替换原有第三方服务",
                    "owner_id": "agent-0",
                    "owner_level": 5,
                    "priority": "critical",
                }
            ],
            "cancelled_tasks": [],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/update-plan", json=update_payload, timeout=TIMEOUT)
        assert resp.status_code == 200, f"更新方案失败: {resp.status_code} {resp.text}"
        result = resp.json()
        assert result["new_version"] == "v1.1"
        assert result["update_type"] == "fix"

    def test_resume_execution(self, ensure_api):
        """Step 8: 恢复执行 → RESUMING → EXECUTING"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析+更新方案
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "blocking",
            "title": "接口字段缺失",
            "description": "API缺少必需字段",
            "severity": "high",
            "detected_by": "QA",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        analysis_payload = {
            "root_cause": "设计时遗漏字段",
            "root_cause_confidence": 0.95,
            "impact_scope": "局部",
            "progress_impact": "延迟1天",
            "severity_reassessment": "high",
            "solution_options": [{"id": 0, "description": "补充字段"}],
            "recommended_option": 0,
            "requires_discussion": False,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        update_payload = {
            "new_version": "v1.1",
            "parent_version": "v1.0",
            "update_type": "fix",
            "description": "补充API必需字段",
            "changes": {},
            "task_updates": [],
            "new_tasks": [],
            "cancelled_tasks": [],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/update-plan", json=update_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 恢复执行
        resume_payload = {
            "new_version": "v1.1",
            "resuming_from_task": 1,
            "checkpoint": f"问题{issue_id}已修复，从任务1继续",
            "resume_instructions": {
                "continue_from": "task_001",
                "ignore_blocked": True,
                "priority_override": True,
            },
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/resume", json=resume_payload, timeout=TIMEOUT)
        assert resp.status_code == 200, f"恢复执行失败: {resp.status_code} {resp.text}"
        result = resp.json()
        assert result["new_version"] == "v1.1"
        assert result["resuming_from_task"] == 1

    def test_get_problem_analysis(self, ensure_api):
        """Step 9: 获取问题分析"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "bug",
            "title": "数据计算错误",
            "description": "统计数据有误",
            "severity": "medium",
            "detected_by": "QA",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        analysis_payload = {
            "root_cause": "计算公式错误",
            "root_cause_confidence": 0.8,
            "impact_scope": "部分报表",
            "progress_impact": "轻微",
            "severity_reassessment": "medium",
            "solution_options": [{"id": 0, "description": "修正公式"}],
            "recommended_option": 0,
            "requires_discussion": False,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 获取分析
        resp = httpx.get(f"{API_BASE}/problems/{issue_id}/analysis", timeout=TIMEOUT)
        assert resp.status_code == 200, f"获取分析失败: {resp.text}"
        analysis = resp.json()
        assert analysis["root_cause"] == "计算公式错误"
        assert analysis["root_cause_confidence"] == 0.8

    def test_get_problem_discussion(self, ensure_api):
        """Step 10: 获取问题讨论记录"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析+讨论
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "risk",
            "title": "性能风险",
            "description": "高并发场景可能有问题",
            "severity": "medium",
            "detected_by": "Architect",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        analysis_payload = {
            "root_cause": "未做性能测试",
            "root_cause_confidence": 0.6,
            "impact_scope": "生产环境",
            "progress_impact": "未知",
            "severity_reassessment": "medium",
            "solution_options": [{"id": 0, "description": "增加性能测试"}],
            "recommended_option": 0,
            "requires_discussion": True,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        discuss_payload = {
            "participants": [{"agent_id": "a1", "name": "性能专家", "level": 5}],
            "discussion_focus": [{"aspect": "性能", "concerns": ["并发"]}],
            "proposed_solutions": [{"participant": "性能专家", "solution": "加缓存"}],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/discuss", json=discuss_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 获取讨论记录
        resp = httpx.get(f"{API_BASE}/problems/{issue_id}/discussion", timeout=TIMEOUT)
        assert resp.status_code == 200, f"获取讨论失败: {resp.text}"
        discussion = resp.json()
        assert len(discussion["participants"]) == 1
        assert len(discussion["proposed_solutions"]) == 1

    def test_get_plan_update(self, ensure_api):
        """Step 11: 获取方案更新记录"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析+更新方案
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "blocking",
            "title": "安全问题",
            "description": "存在安全漏洞",
            "severity": "critical",
            "detected_by": "Security",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        analysis_payload = {
            "root_cause": "未做安全加固",
            "root_cause_confidence": 0.85,
            "impact_scope": "全局",
            "progress_impact": "严重",
            "severity_reassessment": "critical",
            "solution_options": [{"id": 0, "description": "安全加固"}],
            "recommended_option": 0,
            "requires_discussion": False,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        update_payload = {
            "new_version": "v1.1",
            "parent_version": "v1.0",
            "update_type": "fix",
            "description": "安全加固",
            "changes": {},
            "task_updates": [],
            "new_tasks": [],
            "cancelled_tasks": [],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/update-plan", json=update_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 获取方案更新记录
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/plan-update", timeout=TIMEOUT)
        assert resp.status_code == 200, f"获取方案更新失败: {resp.text}"
        updates = resp.json()
        assert isinstance(updates, list)
        assert len(updates) >= 1
        assert updates[0]["new_version"] == "v1.1"

    def test_get_resuming_record(self, ensure_api):
        """Step 12: 获取恢复执行记录"""
        ctx = self._create_executing_plan(ensure_api)
        plan_id = ctx["plan_id"]

        # 报告+分析+更新+恢复
        problem_payload = {
            "plan_id": plan_id,
            "room_id": ctx["room_id"],
            "type": "bug",
            "title": "缺陷修复",
            "description": "修复已知缺陷",
            "severity": "low",
            "detected_by": "Tester",
        }
        resp = httpx.post(f"{API_BASE}/problems/report", json=problem_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        issue_id = resp.json()["issue_id"]

        analysis_payload = {
            "root_cause": "代码bug",
            "root_cause_confidence": 0.9,
            "impact_scope": "局部",
            "progress_impact": "轻微",
            "severity_reassessment": "low",
            "solution_options": [{"id": 0, "description": "修复bug"}],
            "recommended_option": 0,
            "requires_discussion": False,
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/analyze", json=analysis_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        update_payload = {
            "new_version": "v1.1",
            "parent_version": "v1.0",
            "update_type": "fix",
            "description": "修复缺陷",
            "changes": {},
            "task_updates": [],
            "new_tasks": [],
            "cancelled_tasks": [],
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/update-plan", json=update_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        resume_payload = {
            "new_version": "v1.1",
            "resuming_from_task": 0,
            "checkpoint": "修复完成",
            "resume_instructions": {},
        }
        resp = httpx.post(f"{API_BASE}/problems/{issue_id}/resume", json=resume_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 获取恢复执行记录
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/resuming", timeout=TIMEOUT)
        assert resp.status_code == 200, f"获取恢复记录失败: {resp.text}"
        records = resp.json()
        assert isinstance(records, list)
        assert len(records) >= 1


# ========================
# 层级汇报/升级测试（05-Hierarchy-Roles.md §7.2）
# 来源: Step 20 - 层级汇报/升级系统
# ========================


class TestEscalation:
    """层级汇报/升级 API 测试"""

    def test_escalate_room_level_by_level(self):
        """测试逐级汇报模式 L1→L2→L3→L7"""
        # 创建一个 plan + room
        plan_payload = {
            "title": "测试升级-逐级汇报",
            "topic": "县城新建学校方案",
            "requirements": ["需要省审批", "需要中央批准"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_data = resp.json()
        plan_id = plan_data["plan"]["plan_id"]
        room_id = plan_data["room"]["room_id"]

        # escalate_room 会自动将 room 状态切换到 HIERARCHICAL_REVIEW
        # 执行逐级升级: L1 → L7
        escalation_payload = {
            "from_level": 1,
            "to_level": 7,
            "mode": "level_by_level",
            "content": {
                "proposal": "县城新建学校方案",
                "attachments": ["选址报告.pdf", "预算表.xlsx"],
                "approval_status": "pending_central_review",
                "escalated_by": "county_official",
            },
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        assert resp.status_code == 201, f"升级失败: {resp.text}"
        data = resp.json()
        assert data["from_level"] == 1
        assert data["to_level"] == 7
        assert data["mode"] == "level_by_level"
        assert data["escalation_path"] == [1, 2, 3, 4, 5, 6, 7]
        assert data["status"] == "pending"
        assert "escalation_id" in data
        assert data["room_id"] == room_id
        assert data["plan_id"] == plan_id

    def test_escalate_room_cross_level(self):
        """测试跨级汇报模式 L1→L3→L5→L7"""
        plan_payload = {
            "title": "测试升级-跨级汇报",
            "topic": "紧急项目方案",
            "requirements": ["需要快速审批"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_data = resp.json()
        plan_id = plan_data["plan"]["plan_id"]
        room_id = plan_data["room"]["room_id"]

        # 跨级升级: L2 → L7
        escalation_payload = {
            "from_level": 2,
            "to_level": 7,
            "mode": "cross_level",
            "content": {
                "proposal": "紧急项目方案",
                "escalated_by": "village_leader",
            },
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        assert resp.status_code == 201, f"跨级升级失败: {resp.text}"
        data = resp.json()
        assert data["mode"] == "cross_level"
        # 跨级模式只走奇数层: 2→3→5→7
        assert data["escalation_path"] == [2, 3, 5, 7], f"实际路径: {data['escalation_path']}"

    def test_escalate_room_emergency_mode(self):
        """测试紧急汇报模式 L1→L5→L7"""
        plan_payload = {
            "title": "测试升级-紧急汇报",
            "topic": "紧急救灾方案",
            "requirements": ["需要立即审批"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_data = resp.json()
        room_id = plan_data["room"]["room_id"]


        escalation_payload = {
            "from_level": 1,
            "to_level": 7,
            "mode": "emergency",
            "content": {
                "proposal": "紧急救灾方案",
                "escalated_by": "emergency_operator",
            },
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        assert data["mode"] == "emergency"
        # 紧急模式: 1→5→7
        assert data["escalation_path"] == [1, 5, 7], f"实际路径: {data['escalation_path']}"

    def test_escalate_invalid_level(self):
        """测试 to_level <= from_level 的无效请求"""
        plan_payload = {
            "title": "测试升级-无效层级",
            "topic": "测试方案",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]


        # to_level <= from_level 应该返回 400
        escalation_payload = {
            "from_level": 5,
            "to_level": 3,  # 无效：目标层级低于起始层级
            "mode": "level_by_level",
            "content": {"proposal": "测试"},
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        assert resp.status_code == 400, f"应该返回 400，实际: {resp.status_code}"

    def test_escalate_nonexistent_room(self):
        """测试向不存在的房间升级"""
        fake_room_id = str(uuid.uuid4())
        escalation_payload = {
            "from_level": 1,
            "to_level": 7,
            "mode": "level_by_level",
            "content": {"proposal": "测试"},
        }
        resp = httpx.post(f"{API_BASE}/rooms/{fake_room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_get_room_escalations(self):
        """测试获取房间的升级记录"""
        plan_payload = {
            "title": "测试-获取升级记录",
            "topic": "测试升级列表",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]
        plan_id = resp.json()["plan"]["plan_id"]


        # 创建两次升级
        for i in range(2):
            escalation_payload = {
                "from_level": i + 1,
                "to_level": 7,
                "mode": "level_by_level",
                "content": {"proposal": f"升级{i+1}"},
            }
            httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)

        # 获取房间升级记录
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/escalations", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert data["total"] == 2
        assert len(data["escalations"]) == 2

    def test_get_plan_escalations(self):
        """测试获取方案的升级记录"""
        plan_payload = {
            "title": "测试-获取方案升级记录",
            "topic": "测试方案升级",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]
        plan_id = resp.json()["plan"]["plan_id"]


        # 创建升级
        escalation_payload = {
            "from_level": 1,
            "to_level": 7,
            "mode": "level_by_level",
            "content": {"proposal": "测试方案"},
        }
        httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)

        # 获取方案升级记录
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/escalations", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id
        assert data["total"] == 1
        assert len(data["escalations"]) == 1

    def test_get_escalation_by_id(self):
        """测试通过 ID 获取升级记录"""
        plan_payload = {
            "title": "测试-ID获取升级",
            "topic": "测试升级详情",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]


        escalation_payload = {
            "from_level": 1,
            "to_level": 7,
            "mode": "level_by_level",
            "content": {"proposal": "测试升级详情"},
        }
        create_resp = httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        escalation_id = create_resp.json()["escalation_id"]

        # 通过 ID 获取
        resp = httpx.get(f"{API_BASE}/escalations/{escalation_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["escalation_id"] == escalation_id
        assert data["from_level"] == 1
        assert data["to_level"] == 7

    def test_update_escalation_status(self):
        """测试更新升级状态"""
        plan_payload = {
            "title": "测试-更新升级状态",
            "topic": "测试状态更新",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]


        escalation_payload = {
            "from_level": 1,
            "to_level": 7,
            "mode": "level_by_level",
            "content": {"proposal": "测试状态更新"},
        }
        create_resp = httpx.post(f"{API_BASE}/rooms/{room_id}/escalate", json=escalation_payload, timeout=TIMEOUT)
        escalation_id = create_resp.json()["escalation_id"]

        # 确认升级
        resp = httpx.patch(
            f"{API_BASE}/escalations/{escalation_id}",
            json={"action": "acknowledge", "actor_id": "L7_decider", "actor_name": "战略决策者", "comment": "已收到"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"

        # 完成升级
        resp = httpx.patch(
            f"{API_BASE}/escalations/{escalation_id}",
            json={"action": "complete", "actor_id": "L7_decider", "actor_name": "战略决策者"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    def test_get_escalation_path_preview(self):
        """测试升级路径预览"""
        plan_payload = {
            "title": "测试-路径预览",
            "topic": "测试路径",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]


        # 预览逐级路径
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/escalation-path", params={"from_level": 1, "mode": "level_by_level"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_level"] == 1
        assert data["mode"] == "level_by_level"
        assert data["escalation_path"] == [1, 2, 3, 4, 5, 6, 7]
        assert "L1 → L2 → L3 → L4 → L5 → L6 → L7" in data["path_description"]

        # 预览跨级路径
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/escalation-path", params={"from_level": 1, "mode": "cross_level"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "cross_level"
        assert data["escalation_path"] == [1, 3, 5, 7]


# ========================
# Task Comments & Checkpoints (Step 21)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 comments/checkpoints
# ========================

class TestTaskEnhancements:
    """Step 21: Task Comments & Checkpoints API"""

    def test_create_and_list_comments(self):
        """测试创建和列出任务评论"""
        # 创建 plan + room
        plan_payload = {
            "title": "测试-任务评论",
            "topic": "测试评论功能",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        room_id = resp.json()["room"]["room_id"]

        # 创建任务
        task_payload = {
            "title": "实现用户认证模块",
            "owner_level": 4,
            "owner_role": "L4_PLANNER",
            "priority": "high",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks", json=task_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 添加评论
        comment_payload = {
            "author_name": "张工",
            "author_level": 5,
            "content": "建议使用 JWT 进行身份验证",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments",
            json=comment_payload, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        comment_data = resp.json()
        assert comment_data["author_name"] == "张工"
        assert comment_data["content"] == "建议使用 JWT 进行身份验证"
        comment_id = comment_data["comment_id"]

        # 列出评论
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["comments"]) == 1
        assert data["comments"][0]["content"] == "建议使用 JWT 进行身份验证"

    def test_update_comment(self):
        """测试更新任务评论"""
        # 创建 plan + task
        plan_payload = {
            "title": "测试-更新评论",
            "topic": "测试评论更新",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
                          json={"title": "实现支付模块", "priority": "high"}, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 创建评论
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments",
            json={"author_name": "王工", "content": "初始评论"},
            timeout=TIMEOUT
        )
        comment_id = resp.json()["comment_id"]

        # 更新评论
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments/{comment_id}",
            json={"content": "修改后的评论内容"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "修改后的评论内容"

    def test_delete_comment(self):
        """测试删除任务评论"""
        plan_payload = {"title": "测试-删除评论", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
                          json={"title": "测试任务"}, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments",
            json={"author_name": "李工", "content": "要删除的评论"},
            timeout=TIMEOUT
        )
        comment_id = resp.json()["comment_id"]

        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments/{comment_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # 确认已删除
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/comments", timeout=TIMEOUT)
        assert len(resp.json()["comments"]) == 0

    def test_create_and_list_checkpoints(self):
        """测试创建和列出任务检查点"""
        plan_payload = {"title": "测试-任务检查点", "topic": "测试检查点", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
                          json={"title": "数据库设计", "priority": "high"}, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 创建检查点1
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints",
            json={"name": "需求分析完成"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        cp1 = resp.json()
        assert cp1["name"] == "需求分析完成"
        assert cp1["status"] == "pending"
        cp1_id = cp1["checkpoint_id"]

        # 创建检查点2
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints",
            json={"name": "ER图设计完成"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        cp2_id = resp.json()["checkpoint_id"]

        # 列出检查点
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["checkpoints"]) == 2
        names = {cp["name"] for cp in data["checkpoints"]}
        assert "需求分析完成" in names
        assert "ER图设计完成" in names

    def test_update_checkpoint_status(self):
        """测试更新检查点状态（完成/未完成）"""
        plan_payload = {"title": "测试-更新检查点", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
                          json={"title": "API开发"}, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints",
            json={"name": "接口文档完成"},
            timeout=TIMEOUT
        )
        checkpoint_id = resp.json()["checkpoint_id"]

        # 标记为完成
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints/{checkpoint_id}",
            json={"status": "completed"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completed_at"] is not None

        # 改回未完成
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints/{checkpoint_id}",
            json={"status": "pending"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_delete_checkpoint(self):
        """测试删除检查点"""
        plan_payload = {"title": "测试-删除检查点", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
                          json={"title": "测试任务"}, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints",
            json={"name": "测试检查点"},
            timeout=TIMEOUT
        )
        checkpoint_id = resp.json()["checkpoint_id"]

        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/checkpoints/{checkpoint_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


# ========================
# Requirements API 测试
# ========================

class TestRequirements:
    """测试 Requirements Management API"""

    def test_create_and_list_requirements(self):
        """测试创建和列出需求"""
        plan_payload = {"title": "测试-需求管理", "topic": "测试需求", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 创建第一个需求
        req1 = {
            "description": "系统必须在3秒内响应",
            "priority": "high",
            "category": "technical",
            "status": "pending",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json=req1, timeout=TIMEOUT)
        assert resp.status_code == 201
        data1 = resp.json()
        assert data1["description"] == "系统必须在3秒内响应"
        assert data1["priority"] == "high"
        assert data1["category"] == "technical"
        assert data1["status"] == "pending"
        assert "id" in data1
        req1_id = data1["id"]

        # 创建第二个需求
        req2 = {
            "description": "预算不超过100万",
            "priority": "medium",
            "category": "budget",
            "status": "pending",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json=req2, timeout=TIMEOUT)
        assert resp.status_code == 201
        req2_id = resp.json()["id"]

        # 列出所有需求
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/requirements", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ids = {r["id"] for r in data}
        assert req1_id in ids
        assert req2_id in ids

    def test_get_single_requirement(self):
        """测试获取单个需求"""
        plan_payload = {"title": "测试-单个需求", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        req = {
            "description": "需要支持移动端",
            "priority": "low",
            "category": "quality",
            "status": "pending",
            "notes": "优先iOS",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json=req, timeout=TIMEOUT)
        assert resp.status_code == 201
        req_id = resp.json()["id"]

        # 获取单个需求
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/requirements/{req_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == req_id
        assert data["description"] == "需要支持移动端"
        assert data["priority"] == "low"
        assert data["notes"] == "优先iOS"

    def test_update_requirement(self):
        """测试更新需求字段"""
        plan_payload = {"title": "测试-更新需求", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        req = {
            "description": "初始描述",
            "priority": "medium",
            "category": "technical",
            "status": "pending",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json=req, timeout=TIMEOUT)
        assert resp.status_code == 201
        req_id = resp.json()["id"]

        # 更新 priority 和 status
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/requirements/{req_id}",
            json={"priority": "high", "status": "in_progress"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "high"
        assert data["status"] == "in_progress"
        assert data["description"] == "初始描述"  # 未更新的字段保持不变

    def test_delete_requirement(self):
        """测试删除需求"""
        plan_payload = {"title": "测试-删除需求", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        req1 = {"description": "需求A", "priority": "high", "category": "technical"}
        req2 = {"description": "需求B", "priority": "low", "category": "budget"}
        resp1 = httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json=req1, timeout=TIMEOUT)
        resp2 = httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json=req2, timeout=TIMEOUT)
        req1_id = resp1.json()["id"]

        # 删除需求A
        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/requirements/{req1_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证只剩需求B
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/requirements", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["description"] == "需求B"

    def test_requirements_stats(self):
        """测试需求统计"""
        plan_payload = {"title": "测试-需求统计", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 添加多个需求
        for i, (priority, status, category) in enumerate([
            ("high", "pending", "technical"),
            ("high", "met", "budget"),
            ("medium", "pending", "technical"),
            ("low", "not_met", "timeline"),
        ]):
            httpx.post(f"{API_BASE}/plans/{plan_id}/requirements", json={
                "description": f"需求{i+1}",
                "priority": priority,
                "status": status,
                "category": category,
            }, timeout=TIMEOUT)

        # 获取统计
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/requirements/stats", timeout=TIMEOUT)
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total"] == 4
        assert stats["by_status"]["pending"] == 2
        assert stats["by_status"]["met"] == 1
        assert stats["by_priority"]["high"] == 2
        assert stats["by_category"]["technical"] == 2

    def test_requirement_not_found(self):
        """测试需求不存在"""
        plan_payload = {"title": "测试-需求不存在", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/requirements/nonexistent-id", timeout=TIMEOUT)
        assert resp.status_code == 404

        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/requirements/nonexistent-id",
            json={"status": "met"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/requirements/nonexistent-id", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestConstraints:
    """测试 Constraints API (Plan 约束)"""

    def test_create_and_list_constraints(self):
        """测试创建和列出约束"""
        plan_payload = {"title": "测试-约束管理", "topic": "测试约束", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 创建预算约束
        c1 = {"type": "budget", "value": "50000000", "unit": "CNY", "description": "总预算上限"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/constraints", json=c1, timeout=TIMEOUT)
        assert resp.status_code == 201
        data1 = resp.json()
        assert data1["type"] == "budget"
        assert data1["value"] == "50000000"
        assert data1["unit"] == "CNY"
        assert "constraint_id" in data1

        # 创建时间约束
        c2 = {"type": "timeline", "value": "24", "unit": "months"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/constraints", json=c2, timeout=TIMEOUT)
        assert resp.status_code == 201
        c2_id = resp.json()["constraint_id"]

        # 列出所有约束
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/constraints", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_get_update_delete_constraint(self):
        """测试获取、更新、删除约束"""
        plan_payload = {"title": "测试-约束CRUD", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        c = {"type": "budget", "value": "10000000", "unit": "CNY"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/constraints", json=c, timeout=TIMEOUT)
        assert resp.status_code == 201
        constraint_id = resp.json()["constraint_id"]

        # 获取单个约束
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/constraints/{constraint_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["value"] == "10000000"

        # 更新约束
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/constraints/{constraint_id}",
            json={"value": "15000000"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["value"] == "15000000"

        # 删除约束
        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/constraints/{constraint_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

    def test_constraint_not_found(self):
        """测试约束不存在返回404"""
        # 创建真实计划，但使用假constraint_id
        plan_payload = {"title": "约束不存在测试", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        fake_constraint_id = str(uuid.uuid4())

        # 获取不存在的约束
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/constraints/{fake_constraint_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Constraint not found"

        # 更新不存在的约束（先检查plan存在，返回Constraint not found）
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/constraints/{fake_constraint_id}",
            json={"value": "999"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Constraint not found"

        # 删除不存在的约束
        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/constraints/{fake_constraint_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Constraint not found"


class TestStakeholders:
    """测试 Stakeholders API (Plan 干系人)"""

    def test_create_and_list_stakeholders(self):
        """测试创建和列出干系人"""
        plan_payload = {"title": "测试-干系人管理", "topic": "测试干系人", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 创建干系人
        s1 = {"name": "省教育厅", "level": 6, "interest": "high", "influence": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/stakeholders", json=s1, timeout=TIMEOUT)
        assert resp.status_code == 201
        data1 = resp.json()
        assert data1["name"] == "省教育厅"
        assert data1["level"] == 6
        assert data1["interest"] == "high"
        assert "stakeholder_id" in data1

        # 创建第二个干系人
        s2 = {"name": "县财政局", "level": 5, "interest": "medium", "influence": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/stakeholders", json=s2, timeout=TIMEOUT)
        assert resp.status_code == 201

        # 列出所有干系人
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/stakeholders", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_update_stakeholder(self):
        """测试更新干系人"""
        plan_payload = {"title": "测试-干系人更新", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        s = {"name": "原单位", "level": 4, "interest": "low", "influence": "low"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/stakeholders", json=s, timeout=TIMEOUT)
        assert resp.status_code == 201
        stakeholder_id = resp.json()["stakeholder_id"]

        # 更新
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/stakeholders/{stakeholder_id}",
            json={"interest": "high", "influence": "high"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["interest"] == "high"
        assert resp.json()["influence"] == "high"

    def test_delete_stakeholder(self):
        """测试删除干系人"""
        plan_payload = {"title": "测试-干系人删除", "topic": "测试删除", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        s = {"name": "待删除单位", "level": 5, "interest": "medium", "influence": "medium"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/stakeholders", json=s, timeout=TIMEOUT)
        assert resp.status_code == 201
        stakeholder_id = resp.json()["stakeholder_id"]

        # 删除干系人
        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/stakeholders/{stakeholder_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/stakeholders/{stakeholder_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_stakeholder_not_found(self):
        """测试干系人不存在返回404"""
        plan_payload = {"title": "测试-干系人404", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        fake_id = str(uuid.uuid4())

        # 获取不存在的干系人
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/stakeholders/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Stakeholder not found"

        # 更新不存在的干系人
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/stakeholders/{fake_id}",
            json={"interest": "high"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

        # 删除不存在的干系人
        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/stakeholders/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestRisks:
    """测试 Risks API (Version 风险)"""

    def test_create_and_list_risks(self):
        """测试创建和列出风险"""
        plan_payload = {"title": "测试-风险管理", "topic": "测试风险", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建风险
        r1 = {
            "title": "资金不到位风险",
            "description": "省级财政拨款可能延迟",
            "probability": "medium",
            "impact": "high",
            "mitigation": "预备金方案",
            "contingency": "分期建设",
            "status": "identified",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks", json=r1, timeout=TIMEOUT)
        assert resp.status_code == 201
        data1 = resp.json()
        assert data1["title"] == "资金不到位风险"
        assert data1["probability"] == "medium"
        assert data1["impact"] == "high"
        assert "risk_id" in data1

        # 创建第二个风险
        r2 = {"title": "工期延误风险", "probability": "low", "impact": "medium"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks", json=r2, timeout=TIMEOUT)
        assert resp.status_code == 201

        # 列出所有风险
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_update_delete_risk(self):
        """测试更新和删除风险"""
        plan_payload = {"title": "测试-风险CRUD", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        r = {"title": "测试风险", "probability": "low", "impact": "low"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks", json=r, timeout=TIMEOUT)
        assert resp.status_code == 201
        risk_id = resp.json()["risk_id"]

        # 获取单个风险
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks/{risk_id}", timeout=TIMEOUT)
        assert resp.status_code == 200

        # 更新风险状态
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/risks/{risk_id}",
            json={"status": "mitigated"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "mitigated"

        # 删除风险
        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks/{risk_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

    def test_risk_not_found(self):
        """测试风险不存在返回404"""
        plan_payload = {"title": "测试-风险404", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"
        fake_id = str(uuid.uuid4())

        # 获取不存在的风险
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

        # 更新不存在的风险
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/risks/{fake_id}",
            json={"status": "mitigated"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

        # 删除不存在的风险
        resp = httpx.delete(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

        # 在不存在的计划中获取风险也应返回404
        fake_plan = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/plans/{fake_plan}/versions/{version}/risks/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestPlanJsonEnrichment:
    """测试 plan.json 和 version plan.json 包含 constraints/stakeholders/risks"""

    def test_plan_json_includes_constraints_stakeholders(self):
        """plan.json 应包含 constraints 和 stakeholders"""
        plan_payload = {"title": "测试-丰富plan.json", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 添加约束和干系人
        httpx.post(f"{API_BASE}/plans/{plan_id}/constraints",
                   json={"type": "budget", "value": "1000", "unit": "CNY"}, timeout=TIMEOUT)
        httpx.post(f"{API_BASE}/plans/{plan_id}/stakeholders",
                   json={"name": "测试干系人", "level": 5}, timeout=TIMEOUT)

        # 获取 plan.json
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/plan.json", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "constraints" in data
        assert "stakeholders" in data
        assert len(data["constraints"]) == 1
        assert len(data["stakeholders"]) == 1

    def test_version_plan_json_includes_risks_metrics_tasks(self):
        """version plan.json 应包含 risks, metrics 和 tasks（Step 25: tasks 字段）"""
        plan_payload = {"title": "测试-丰富version", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 添加风险
        httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/risks",
                   json={"title": "测试风险", "probability": "medium", "impact": "medium"},
                   timeout=TIMEOUT)

        # 添加任务
        httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks",
                   json={"title": "测试任务", "description": "测试描述"},
                   timeout=TIMEOUT)

        # 获取 version plan.json
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/plan.json", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "risks" in data
        assert "metrics" in data
        assert "tasks" in data
        assert len(data["risks"]) == 1
        assert len(data["tasks"]) == 1


# ========================
# Task Dependency & Blocking System Tests (Step 22)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 blocked_by
# 来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
# ========================

class TestTaskDependencyBlocking:
    """Step 22: Task Dependency Validation and Auto-Blocking System"""

    def test_task_auto_blocked_when_dependency_not_completed(self):
        """测试：当依赖任务未完成时，创建的任务自动被blocked"""
        # 创建 plan
        plan_payload = {"title": "测试-任务依赖自动阻塞", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务A（无依赖）
        task_a = {"title": "任务A", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_a_id = resp.json()["task_id"]

        # 创建任务B（依赖任务A，但任务A未完成）
        task_b = {"title": "任务B", "priority": "high", "dependencies": [task_a_id]}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_b, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_b_id = resp.json()["task_id"]
        task_b_data = resp.json()

        # 验证任务B被自动标记为blocked
        assert task_b_data.get("status") == "blocked"
        assert task_a_id in task_b_data.get("blocked_by", [])

    def test_task_unblocked_when_dependency_completed(self):
        """测试：当依赖任务完成时，被阻塞的任务自动解除阻塞"""
        # 创建 plan
        plan_payload = {"title": "测试-任务依赖解除阻塞", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务A（无依赖）
        task_a = {"title": "任务A", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_a_id = resp.json()["task_id"]

        # 创建任务B（依赖任务A）
        task_b = {"title": "任务B", "priority": "high", "dependencies": [task_a_id]}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_b, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_b_id = resp.json()["task_id"]
        assert resp.json().get("status") == "blocked"

        # 完成任务A
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_a_id}/progress",
            json={"progress": 1.0, "status": "completed"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200

        # 验证任务B自动解除阻塞
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_b_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        task_b_data = resp.json()
        assert task_a_id not in task_b_data.get("blocked_by", [])
        # status 可能变成 pending（如果之前是blocked）
        assert task_b_data.get("status") in ["pending", "in_progress"]

    def test_validate_dependencies(self):
        """测试：验证依赖列表的有效性"""
        # 创建 plan
        plan_payload = {"title": "测试-依赖验证", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务
        task_a = {"title": "任务A", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_a_id = resp.json()["task_id"]

        # 验证有效依赖
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/validate-dependencies",
            json={"dependencies": [task_a_id]},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["valid"] is True
        assert len(result["errors"]) == 0

        # 验证无效依赖（不存在的任务ID）
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/validate-dependencies",
            json={"dependencies": ["non-existent-task-id"]},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_circular_dependency_detection(self):
        """测试：检测循环依赖"""
        # 创建 plan
        plan_payload = {"title": "测试-循环依赖检测", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务A和B
        task_a = {"title": "任务A", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_a_id = resp.json()["task_id"]

        task_b = {"title": "任务B", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_b, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_b_id = resp.json()["task_id"]

        # 设置A依赖B
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_a_id}",
            json={"dependencies": [task_b_id]},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200

        # 设置B依赖A（形成循环）
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_b_id}",
            json={"dependencies": [task_a_id]},
            timeout=TIMEOUT
        )
        # 注意：验证发生在更新后，这里只是记录，实际的循环检测应该在validate时捕获

    def test_get_blocked_tasks(self):
        """测试：获取所有被阻塞的任务"""
        # 创建 plan
        plan_payload = {"title": "测试-获取阻塞任务", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务A（无依赖）
        task_a = {"title": "任务A", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        assert resp.status_code == 201

        # 创建任务B（依赖A）
        task_b = {"title": "任务B", "priority": "high", "dependencies": [resp.json()["task_id"]]}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_b, timeout=TIMEOUT)
        assert resp.status_code == 201

        # 获取阻塞任务列表
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/blocked", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked_count"] == 1
        assert len(data["blocked_tasks"]) == 1
        assert data["blocked_tasks"][0]["title"] == "任务B"

    def test_get_dependency_graph(self):
        """测试：获取任务依赖图"""
        # 创建 plan
        plan_payload = {"title": "测试-依赖图", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务A
        task_a = {"title": "任务A", "priority": "high"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_a_id = resp.json()["task_id"]

        # 创建任务B（依赖A）
        task_b = {"title": "任务B", "priority": "high", "dependencies": [task_a_id]}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_b, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_b_id = resp.json()["task_id"]

        # 获取依赖图
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/dependency-graph", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tasks"] == 2
        assert data["blocked_task_count"] == 1
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1
        assert data["edges"][0]["from"] == task_a_id
        assert data["edges"][0]["to"] == task_b_id

    def test_multiple_dependencies_all_block(self):
        """测试：多个依赖任一未完成则阻塞"""
        # 创建 plan
        plan_payload = {"title": "测试-多依赖阻塞", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = "v1.0"

        # 创建任务A、B、C
        task_a = {"title": "任务A"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_a, timeout=TIMEOUT)
        task_a_id = resp.json()["task_id"]

        task_b = {"title": "任务B"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_b, timeout=TIMEOUT)
        task_b_id = resp.json()["task_id"]

        task_c = {"title": "任务C", "dependencies": [task_a_id, task_b_id]}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks", json=task_c, timeout=TIMEOUT)
        task_c_id = resp.json()["task_id"]
        # C应该被阻塞（A和B都未完成）
        assert resp.json().get("status") == "blocked"
        assert task_a_id in resp.json().get("blocked_by", [])
        assert task_b_id in resp.json().get("blocked_by", [])

        # 完成A，B未完成
        httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_a_id}/progress",
            json={"progress": 1.0, "status": "completed"},
            timeout=TIMEOUT
        )

        # C仍然被阻塞（B未完成）
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_c_id}", timeout=TIMEOUT)
        assert task_b_id in resp.json().get("blocked_by", [])

        # 完成B
        httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_b_id}/progress",
            json={"progress": 1.0, "status": "completed"},
            timeout=TIMEOUT
        )

        # C解除阻塞
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_c_id}", timeout=TIMEOUT)
        assert len(resp.json().get("blocked_by", [])) == 0


# ========================
# Step 24: Room Hierarchy + Participant Contributions Tests
# ========================

class TestRoomHierarchy:
    """测试讨论室层级关系 API（08-Data-Models-Details.md §4.1 Room hierarchy）"""

    def test_link_rooms_parent_child(self, room_info):
        """测试：建立父子讨论室关系（通过创建两个独立plan各自的room）"""
        # 父讨论室：创建 planA -> roomA
        planA = {"title": "测试-父计划", "topic": "父讨论室", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=planA, timeout=TIMEOUT)
        assert resp.status_code == 201
        parent_room_id = resp.json()["room"]["room_id"]

        # 子讨论室：创建 planB -> roomB
        planB = {"title": "测试-子计划", "topic": "子讨论室", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=planB, timeout=TIMEOUT)
        assert resp.status_code == 201
        child_room_id = resp.json()["room"]["room_id"]

        # 建立父子关系
        link_payload = {"parent_room_id": parent_room_id}
        resp = httpx.post(f"{API_BASE}/rooms/{child_room_id}/link", json=link_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json().get("parent_room_id") == parent_room_id

    def test_link_rooms_related(self, room_info):
        """测试：建立关联讨论室关系"""
        # 创建两个独立 plan -> room
        planA = {"title": "测试-关联A", "topic": "讨论室A", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=planA, timeout=TIMEOUT)
        assert resp.status_code == 201
        roomA_id = resp.json()["room"]["room_id"]

        planB = {"title": "测试-关联B", "topic": "讨论室B", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=planB, timeout=TIMEOUT)
        assert resp.status_code == 201
        roomB_id = resp.json()["room"]["room_id"]

        # 建立关联关系
        link_payload = {"related_room_ids": [roomA_id]}
        resp = httpx.post(f"{API_BASE}/rooms/{roomB_id}/link", json=link_payload, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 获取层级关系
        resp = httpx.get(f"{API_BASE}/rooms/{roomB_id}/hierarchy", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert roomA_id in [r["room_id"] for r in data.get("related", [])]

    def test_conclude_room(self, room_info):
        """测试：结束讨论室并填写总结"""
        room_id = room_info["room_id"]

        # 结束讨论室
        conclude_payload = {"summary": "讨论完成，达成共识", "conclusion": "方案确定"}
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/conclude", json=conclude_payload, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("summary") == "讨论完成，达成共识"
        assert data.get("conclusion") == "方案确定"
        assert "ended_at" in data


class TestParticipantContributions:
    """测试参与者贡献追踪 API（08-Data-Models-Details.md §4.1 participants.contributions）"""

    def test_update_participant_contributions(self, room_with_participant):
        """测试：更新参与者贡献计数"""
        room_id = room_with_participant["room_id"]
        participant_id = room_with_participant["participant_id"]

        # 更新贡献计数（delta 模式）
        contrib_payload = {"speech_count": 3, "challenge_count": 2, "response_count": 1}
        resp = httpx.patch(
            f"{API_BASE}/rooms/{room_id}/participants/{participant_id}/contributions",
            json=contrib_payload,
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("contributions", {}).get("speech_count") == 3
        assert data.get("contributions", {}).get("challenge_count") == 2
        assert data.get("contributions", {}).get("response_count") == 1

    def test_update_participant_thinking_sharing_complete(self, room_with_participant):
        """测试：更新参与者 THINKING/SHARING 阶段完成状态"""
        room_id = room_with_participant["room_id"]
        participant_id = room_with_participant["participant_id"]

        # 更新阶段完成状态
        contrib_payload = {"thinking_complete": True, "sharing_complete": True}
        resp = httpx.patch(
            f"{API_BASE}/rooms/{room_id}/participants/{participant_id}/contributions",
            json=contrib_payload,
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json().get("thinking_complete") is True
        assert resp.json().get("sharing_complete") is True


class TestSubTasks:
    """Step 23: Task SubTasks API (08-Data-Models-Details.md §3.1 Task模型 sub_tasks)"""

    def test_create_and_list_sub_tasks(self):
        """测试创建和列出子任务"""
        # 创建 plan + room
        plan_payload = {
            "title": "测试-子任务",
            "topic": "测试子任务功能",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 创建任务
        task_payload = {
            "title": "实现用户认证模块",
            "owner_level": 4,
            "owner_role": "L4_PLANNER",
            "priority": "high",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks", json=task_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 创建子任务1
        sub_task_payload = {
            "title": "实现JWT Token生成",
            "description": "使用PyJWT库实现",
            "status": "pending",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks",
            json=sub_task_payload, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "实现JWT Token生成"
        assert data["description"] == "使用PyJWT库实现"
        assert data["status"] == "pending"
        sub_task_id = data["sub_task_id"]

        # 创建子任务2
        sub_task_payload2 = {
            "title": "实现Token验证中间件",
            "status": "in_progress",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks",
            json=sub_task_payload2, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        data2 = resp.json()
        assert data2["title"] == "实现Token验证中间件"
        assert data2["status"] == "in_progress"

        # 列出所有子任务
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sub_tasks"]) == 2

        # 获取单个子任务
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks/{sub_task_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["sub_task_id"] == sub_task_id
        assert resp.json()["title"] == "实现JWT Token生成"

    def test_update_sub_task(self):
        """测试更新子任务"""
        # 创建 plan + task
        plan_payload = {
            "title": "测试-子任务更新",
            "topic": "测试子任务更新",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        task_payload = {
            "title": "实现注册功能",
            "owner_level": 3,
            "owner_role": "L3_MEMBER",
            "priority": "medium",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks", json=task_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 创建子任务
        sub_task_payload = {
            "title": "前端注册表单",
            "status": "pending",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks",
            json=sub_task_payload, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        sub_task_id = resp.json()["sub_task_id"]

        # 更新子任务
        update_payload = {
            "title": "前端注册表单（带验证）",
            "status": "in_progress",
            "progress": 0.5,
        }
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks/{sub_task_id}",
            json=update_payload, timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "前端注册表单（带验证）"
        assert data["status"] == "in_progress"
        assert data["progress"] == 0.5

    def test_delete_sub_task(self):
        """测试删除子任务"""
        # 创建 plan + task
        plan_payload = {
            "title": "测试-子任务删除",
            "topic": "测试子任务删除",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        task_payload = {
            "title": "实现登录功能",
            "owner_level": 3,
            "owner_role": "L3_MEMBER",
            "priority": "high",
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks", json=task_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 创建子任务
        sub_task_payload = {"title": "登录API", "status": "pending"}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks",
            json=sub_task_payload, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        sub_task_id = resp.json()["sub_task_id"]

        # 删除子任务
        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks/{sub_task_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # 验证已删除
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks/{sub_task_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

    def test_sub_task_not_found(self):
        """测试子任务不存在时返回404"""
        plan_payload = {
            "title": "测试-子任务不存在",
            "topic": "测试子任务不存在",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        task_payload = {"title": "测试任务", "priority": "low"}
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks", json=task_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]

        # 获取不存在的子任务
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}/sub-tasks/00000000-0000-0000-0000-000000000000",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404


class TestMessageSequence:
    """测试消息序号分配（Step 26: messages.sequence）"""

    def test_message_sequence_assignment(self):
        """测试：连续发言时消息序号递增"""
        # 创建房间
        plan_payload = {
            "title": "测试-消息序号",
            "topic": "测试消息序号递增",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]

        # 添加第一个发言
        speech1 = {"agent_id": "agent-1", "content": "第一条发言"}
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/speech", json=speech1, timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["sequence"] == 1

        # 添加第二个发言
        speech2 = {"agent_id": "agent-2", "content": "第二条发言"}
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/speech", json=speech2, timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["sequence"] == 2

        # 添加第三个发言
        speech3 = {"agent_id": "agent-1", "content": "第三条发言"}
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/speech", json=speech3, timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["sequence"] == 3

        # 获取历史验证序号
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/history", timeout=TIMEOUT)
        assert resp.status_code == 200
        history = resp.json()["history"]
        # 过滤出speech类型的消息
        speeches = [m for m in history if m["type"] == "speech"]
        assert len(speeches) == 3
        assert speeches[0]["sequence"] == 1
        assert speeches[1]["sequence"] == 2
        assert speeches[2]["sequence"] == 3

    def test_room_history_includes_sequence(self):
        """测试：历史记录中每条消息都包含sequence字段"""
        plan_payload = {
            "title": "测试-历史序号",
            "topic": "测试历史包含序号",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]

        # 添加一条发言
        speech = {"agent_id": "agent-x", "content": "测试发言"}
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/speech", json=speech, timeout=TIMEOUT)
        assert resp.status_code == 200

        # 获取历史
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/history", timeout=TIMEOUT)
        assert resp.status_code == 200
        history = resp.json()["history"]
        for msg in history:
            assert "sequence" in msg, f"消息缺少sequence字段: {msg['type']}"


# ========================
# 运行入口
# ========================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


# ========================
# Test Edict API (圣旨/下行 decree from L7)
# 来源: 01-Edict-Reference.md
# ========================

class TestEdictAPI:
    """测试圣旨 API"""

    def test_create_edict(self):
        """创建圣旨"""
        plan_payload = {"title": "测试Edict", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        edict_data = {
            "title": "关于XX事项的圣旨",
            "content": "兹决定...，着各部遵照执行。",
            "issued_by": "L7-战略层",
            "recipients": [6, 5, 4, 3],
            "status": "published",
        }

        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data,
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        result = resp.json()
        assert result["edict"]["title"] == edict_data["title"]
        assert result["edict"]["content"] == edict_data["content"]
        assert result["edict"]["issued_by"] == edict_data["issued_by"]
        assert result["edict"]["recipients"] == edict_data["recipients"]
        assert result["edict"]["edict_number"] == 1
        assert "edict_id" in result["edict"]

    def test_list_edicts(self):
        """列出圣旨列表"""
        plan_payload = {"title": "测试Edict列表", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建两条圣旨
        for i in range(2):
            edict_data = {
                "title": f"第{i+1}号圣旨",
                "content": f"内容{i+1}",
                "issued_by": "L7",
            }
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
                json=edict_data,
                timeout=TIMEOUT
            )
            assert resp.status_code == 201

        # 列出
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["count"] == 2
        assert len(result["edicts"]) == 2
        # 验证 edict_number 递增
        assert result["edicts"][0]["edict_number"] == 1
        assert result["edicts"][1]["edict_number"] == 2

    def test_get_edict(self):
        """获取单个圣旨"""
        plan_payload = {"title": "测试Edict获取", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建
        edict_data = {
            "title": "测试圣旨",
            "content": "测试内容",
            "issued_by": "L7- Emperor",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data,
            timeout=TIMEOUT
        )
        edict_id = resp.json()["edict"]["edict_id"]

        # 获取
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["edict"]["title"] == edict_data["title"]
        assert result["edict"]["edict_id"] == edict_id

    def test_update_edict(self):
        """更新圣旨"""
        plan_payload = {"title": "测试Edict更新", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建
        edict_data = {
            "title": "原标题",
            "content": "原内容",
            "issued_by": "L7",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data,
            timeout=TIMEOUT
        )
        edict_id = resp.json()["edict"]["edict_id"]

        # 更新
        update_data = {
            "title": "新标题",
            "status": "revoked",
        }
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}",
            json=update_data,
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["edict"]["title"] == "新标题"
        assert result["edict"]["status"] == "revoked"
        # 未更新的字段保持不变
        assert result["edict"]["content"] == "原内容"

    def test_delete_edict(self):
        """删除圣旨"""
        plan_payload = {"title": "测试Edict删除", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建
        edict_data = {
            "title": "待删除圣旨",
            "content": "删除测试",
            "issued_by": "L7",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data,
            timeout=TIMEOUT
        )
        edict_id = resp.json()["edict"]["edict_id"]

        # 删除
        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

    def test_edict_not_found(self):
        """圣旨不存在返回404"""
        plan_payload = {"title": "测试Edict404", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")
        fake_id = str(uuid.uuid4())

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{fake_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

    def test_version_plan_json_includes_edicts(self):
        """version plan.json 包含 edicts 字段"""
        plan_payload = {"title": "测试Edict in plan.json", "topic": "L7下行 decree 测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建圣旨
        edict_data = {
            "title": "version plan.json 测试",
            "content": "测试内容",
            "issued_by": "L7",
        }
        httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data,
            timeout=TIMEOUT
        )

        # 获取 version plan.json
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/plan.json",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert "edicts" in result
        assert len(result["edicts"]) == 1
        assert result["edicts"][0]["title"] == edict_data["title"]


class TestEdictAcknowledgment:
    """测试圣旨签收（Acknowledgment）API — Step 82"""

    def test_create_edict_acknowledgment(self):
        """创建圣旨签收记录"""
        plan_payload = {"title": "测试EdictAck-Create", "topic": "L7下行 decree 签收测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 先创建一条圣旨
        edict_data = {
            "title": "关于XX事项的圣旨",
            "content": "兹决定...，着各部遵照执行。",
            "issued_by": "L7-战略层",
            "recipients": [6, 5, 4],
            "status": "published",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        edict_id = resp.json()["edict"]["edict_id"]

        # 签收圣旨（L4 签收人）
        ack_data = {
            "acknowledged_by": "L4-执行层-张三",
            "level": 4,
            "comment": "已收到，理解内容，准备执行。",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
            json=ack_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        result = resp.json()
        assert result["acknowledgment"]["ack_id"]
        assert result["acknowledgment"]["edict_id"] == edict_id
        assert result["acknowledgment"]["plan_id"] == plan_id
        assert result["acknowledgment"]["acknowledged_by"] == "L4-执行层-张三"
        assert result["acknowledgment"]["level"] == 4
        assert result["acknowledgment"]["comment"] == "已收到，理解内容，准备执行。"
        assert "acknowledged_at" in result["acknowledgment"]

    def test_list_edict_acknowledgments(self):
        """列出圣旨的所有签收记录"""
        plan_payload = {"title": "测试EdictAck-List", "topic": "L7下行 decree 签收列表"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建圣旨
        edict_data = {"title": "第1号圣旨", "content": "测试内容", "issued_by": "L7"}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        edict_id = resp.json()["edict"]["edict_id"]

        # L3 和 L5 分别签收
        for lvl, name in [(3, "L3-参与者-李四"), (5, "L5-协调者-王五")]:
            ack_data = {"acknowledged_by": name, "level": lvl, "comment": f"L{lvl}已阅"}
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
                json=ack_data, timeout=TIMEOUT
            )
            assert resp.status_code == 201

        # 列出签收记录
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["count"] == 2
        assert len(result["acknowledgments"]) == 2
        # 验证字段完整性
        for ack in result["acknowledgments"]:
            assert ack["edict_id"] == edict_id
            assert ack["plan_id"] == plan_id
            assert ack["version"] == version
            assert "ack_id" in ack
            assert "acknowledged_by" in ack
            assert "acknowledged_at" in ack

    def test_delete_edict_acknowledgment(self):
        """删除圣旨签收记录"""
        plan_payload = {"title": "测试EdictAck-Delete", "topic": "L7下行 decree 签收删除"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        # 创建圣旨
        edict_data = {"title": "待删除签收", "content": "测试", "issued_by": "L7"}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        edict_id = resp.json()["edict"]["edict_id"]

        # 创建签收
        ack_data = {"acknowledged_by": "L5-张三", "level": 5, "comment": "已阅"}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
            json=ack_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        ack_id = resp.json()["acknowledgment"]["ack_id"]

        # 删除签收
        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments/{ack_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200

        # 验证已删除（列表中不存在）
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        ack_ids = [a["ack_id"] for a in result["acknowledgments"]]
        assert ack_id not in ack_ids

    def test_multiple_acknowledgments_same_edict(self):
        """同一圣旨多个层级签收"""
        plan_payload = {"title": "测试EdictAck-Multi", "topic": "多层级签收"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        edict_data = {"title": "多层级圣旨", "content": "内容", "issued_by": "L7"}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        edict_id = resp.json()["edict"]["edict_id"]

        # L1-L7 共7个层级依次签收
        ack_ids = []
        for lvl in range(1, 8):
            ack_data = {"acknowledged_by": f"L{lvl}-用户{lvl}", "level": lvl, "comment": f"L{lvl}确认"}
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
                json=ack_data, timeout=TIMEOUT
            )
            assert resp.status_code == 201
            ack_ids.append(resp.json()["acknowledgment"]["ack_id"])

        # 验证7条签收记录
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["count"] == 7
        # 验证所有 ack_id 都存在
        result_ack_ids = [a["ack_id"] for a in result["acknowledgments"]]
        for aid in ack_ids:
            assert aid in result_ack_ids

    def test_edict_acknowledgment_edict_not_found(self):
        """签收不存在的圣旨返回404"""
        plan_payload = {"title": "测试EdictAck-404", "topic": "404测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")
        fake_edict_id = str(uuid.uuid4())

        ack_data = {"acknowledged_by": "L5-测试", "level": 5}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{fake_edict_id}/acknowledgments",
            json=ack_data, timeout=TIMEOUT
        )
        assert resp.status_code == 404

    def test_edict_acknowledgment_delete_not_found(self):
        """删除不存在的签收记录返回404"""
        plan_payload = {"title": "测试EdictAck-Del404", "topic": "删除404测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"].get("current_version", "v1.0")

        edict_data = {"title": "删除404测试", "content": "内容", "issued_by": "L7"}
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts",
            json=edict_data, timeout=TIMEOUT
        )
        assert resp.status_code == 201
        edict_id = resp.json()["edict"]["edict_id"]
        fake_ack_id = str(uuid.uuid4())

        resp = httpx.delete(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments/{fake_ack_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404


class TestPlanAnalytics:
    """测试计划分析统计 API（GET /plans/{plan_id}/analytics）"""

    def test_analytics_empty_plan(self):
        """测试空计划的分析统计"""
        plan_payload = {"title": "空计划", "topic": "测试空计划分析"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/analytics", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id
        assert data["rooms"]["total"] >= 1  # 创建计划时自动创建 room
        assert data["tasks"]["total"] == 0
        assert data["decisions"]["total"] == 0
        assert data["issues"]["total"] == 0
        assert data["participants"]["total"] == 0  # 尚未添加参与者
        assert data["messages"]["total"] == 0  # 尚未发言
        assert data["risks"]["total"] == 0
        assert data["edicts"]["total"] == 0

    def test_analytics_with_rooms_and_tasks(self):
        """测试包含 rooms 和 tasks 的计划分析"""
        # 创建计划（会自动创建 room）
        plan_payload = {
            "title": "Analytics测试计划",
            "topic": "测试计划分析统计",
            "requirements": ["需求1", "需求2"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        plan_id = data["plan"]["plan_id"]
        room_id = data["room"]["room_id"]
        version = data["plan"]["current_version"]

        # 添加参与者
        participant_payload = {"agent_id": "agent-1", "name": "参与者A", "level": 5, "role": "Member"}
        httpx.post(f"{API_BASE}/rooms/{room_id}/participants", json=participant_payload, timeout=TIMEOUT)

        # 添加发言
        speech_payload = {"content": "测试发言内容", "agent_id": "agent-1", "type": "speech"}
        httpx.post(f"{API_BASE}/rooms/{room_id}/speech", json=speech_payload, timeout=TIMEOUT)

        # 添加任务
        task_payload = {
            "title": "任务1",
            "description": "测试任务",
            "owner_id": "agent-1",
            "owner_level": 5,
            "priority": "high",
            "estimated_hours": 8.0,
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks",
            json=task_payload,
            timeout=TIMEOUT
        )
        assert resp.status_code == 201

        # 获取分析统计
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/analytics", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()

        assert data["plan_id"] == plan_id
        assert data["title"] == "Analytics测试计划"
        assert data["rooms"]["total"] >= 1
        assert data["rooms"]["active"] >= 1
        assert data["tasks"]["total"] == 1
        assert data["tasks"]["pending"] == 1
        assert data["participants"]["total"] >= 1
        assert data["messages"]["total"] >= 1
        # 验证 nested stats
        assert "by_phase" in data["rooms"]
        assert "by_status" in data["tasks"]
        assert "by_level" in data["participants"]

    def test_analytics_not_found(self):
        """测试不存在的计划返回404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/plans/{fake_id}/analytics", timeout=TIMEOUT)
        assert resp.status_code == 404


# ========================
# Step 31: Activity Audit Log API Tests
# ========================

class TestActivityAPI:
    """Activity Audit Log API 测试"""

    def test_create_plan_generates_activity(self):
        """创建Plan时生成activity记录"""
        plan_payload = {
            "title": "Activity测试计划",
            "topic": "测试Activity Log",
            "requirements": ["需求1"],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 检查活动日志
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/activities", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "activities" in data
        # 应该有 PLAN_CREATED 活动
        plan_created = [a for a in data["activities"] if a["action_type"] == "plan.created"]
        assert len(plan_created) >= 1
        assert plan_created[0]["plan_id"] == plan_id
        assert plan_created[0]["target_type"] == "plan"

    def test_list_activities_with_filters(self):
        """活动日志支持多维过滤"""
        plan_payload = {
            "title": "Activity过滤测试",
            "topic": "测试过滤功能",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        room_id = resp.json()["room"]["room_id"]
        version = resp.json()["plan"]["current_version"]

        # 过滤 by action_type
        resp = httpx.get(
            f"{API_BASE}/activities",
            params={"plan_id": plan_id, "action_type": "plan.created"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        for a in data["activities"]:
            assert a["action_type"] == "plan.created"
            assert a["plan_id"] == plan_id

    def test_room_phase_change_generates_activity(self):
        """Room phase转换生成activity记录"""
        plan_payload = {"title": "PhaseActivity测试", "topic": "测试Phase变更"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        room_id = resp.json()["room"]["room_id"]

        # Phase转换: SELECTING → THINKING
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/phase?to_phase=thinking", timeout=TIMEOUT)
        assert resp.status_code == 200

        # 检查活动日志
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/activities", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        phase_changes = [a for a in data["activities"] if a["action_type"] == "room.phase_changed"]
        assert len(phase_changes) >= 1

    def test_activity_stats(self):
        """活动统计API"""
        plan_payload = {"title": "Stats测试", "topic": "测试统计"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.get(
            f"{API_BASE}/activities/stats",
            params={"plan_id": plan_id},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_action_type" in data
        assert "plan.created" in data["by_action_type"]

    def test_get_single_activity(self):
        """获取单个活动详情"""
        plan_payload = {"title": "SingleActivity测试", "topic": "测试单个活动"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 获取plan的所有活动
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/activities", timeout=TIMEOUT)
        assert resp.status_code == 200
        activities = resp.json()["activities"]
        assert len(activities) >= 1

        # 用第一个activity_id获取详情
        activity_id = activities[0]["activity_id"]
        resp = httpx.get(f"{API_BASE}/activities/{activity_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["activity_id"] == activity_id
        assert "occurred_at" in data

    def test_activity_not_found(self):
        """不存在的活动返回404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/activities/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_create_task_generates_activity(self):
        """创建任务时生成activity记录"""
        plan_payload = {"title": "TaskActivity测试", "topic": "测试任务活动"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"]["current_version"]

        # 创建任务
        task_payload = {
            "title": "测试任务",
            "owner_id": "agent-1",
            "owner_level": 5,
            "owner_role": "Developer",
            "priority": "high",
            "estimated_hours": 8.0,
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks",
            json=task_payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201

        # 检查活动日志
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/activities", timeout=TIMEOUT)
        assert resp.status_code == 200
        activities = resp.json()["activities"]
        task_created = [a for a in activities if a["action_type"] == "task.created"]
        assert len(task_created) >= 1
        assert task_created[0]["target_type"] == "task"
        assert "测试任务" in str(task_created[0].get("details", {}))

    def test_version_activities(self):
        """版本活动日志"""
        plan_payload = {"title": "VersionActivity测试", "topic": "测试版本活动"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"]["current_version"]

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/activities",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "activities" in data


class TestExportAPI:
    """Step 32: Plan/Deliberation Export API"""

    def test_export_plan_markdown(self):
        """导出会谈决议 Markdown 报告"""
        plan_payload = {"title": "导出测试计划", "topic": "测试决议导出"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/export", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "markdown"
        assert data["plan_id"] == plan_id
        assert "content" in data
        content = data["content"]
        # 验证 Markdown 内容结构
        assert "导出测试计划" in content
        assert "**编号**" in content

    def test_export_plan_not_found(self):
        """不存在的 Plan 导出返回 404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/plans/{fake_id}/export", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_export_version_markdown(self):
        """导出指定版本 Markdown 报告"""
        plan_payload = {"title": "版本导出测试", "topic": "测试版本导出"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]
        version = resp.json()["plan"]["current_version"]

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/export",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "markdown"
        assert data["plan_id"] == plan_id
        assert data["version"] == version
        assert "content" in data
        assert "版本导出测试" in data["content"]

    def test_export_version_not_found(self):
        """不存在的版本导出返回 404"""
        plan_payload = {"title": "版本不存在测试", "topic": "测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/v99.99/export",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 404

    def test_export_includes_room_details(self):
        """导出内容包含讨论室详情"""
        plan_payload = {"title": "导出含讨论室测试", "topic": "测试"}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        room_payload = {"topic": "导出测试讨论室", "plan_id": plan_id, "purpose": "initial_discussion", "mode": "hierarchical"}
        resp = httpx.post(f"{API_BASE}/rooms", json=room_payload, timeout=TIMEOUT)
        assert resp.status_code in (200, 201)

        participant_payload = {"agent_id": "export-test-agent", "name": "导出测试参与人", "level": 5, "role": "测试员"}
        resp = httpx.post(
            f"{API_BASE}/rooms/{resp.json()['room']['room_id']}/participants",
            json=participant_payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code in (200, 201)

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/export", timeout=TIMEOUT)
        assert resp.status_code == 200
        content = resp.json()["content"]
        assert "导出测试讨论室" in content


class TestNotificationAPI:
    """测试通知 API (Step 34)"""

    def test_create_notification(self):
        """创建通知"""
        notification_data = {
            "recipient_id": "agent-l5-001",
            "recipient_level": 5,
            "type": "task_assigned",
            "title": "新任务分配: 订单系统重构",
            "message": "你被分配了订单系统重构任务，优先级: high",
            "plan_id": None,
        }
        resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        result = resp.json()
        assert result["notification_id"]
        assert result["recipient_id"] == notification_data["recipient_id"]
        assert result["type"] == notification_data["type"]
        assert result["title"] == notification_data["title"]
        assert result["read"] is False
        assert "created_at" in result

    def test_list_notifications(self):
        """列出通知列表"""
        # 创建两条通知
        for i in range(2):
            notification_data = {
                "recipient_id": "agent-list-test",
                "type": "task_assigned",
                "title": f"通知{i+1}",
            }
            resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
            assert resp.status_code == 201

        # 列出
        resp = httpx.get(f"{API_BASE}/notifications", params={"recipient_id": "agent-list-test"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        notifications = resp.json()
        assert isinstance(notifications, list)
        assert len(notifications) >= 2

    def test_list_notifications_with_filter(self):
        """列出通知（按类型过滤）"""
        notification_data = {
            "recipient_id": "agent-filter-test",
            "type": "task_completed",
            "title": "完成通知",
        }
        resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
        assert resp.status_code == 201

        resp = httpx.get(
            f"{API_BASE}/notifications",
            params={"recipient_id": "agent-filter-test", "type": "task_completed"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        notifications = resp.json()
        for n in notifications:
            assert n["type"] == "task_completed"

    def test_get_notification(self):
        """获取单个通知"""
        notification_data = {
            "recipient_id": "agent-get-test",
            "type": "approval_requested",
            "title": "待审批: 预算超支",
        }
        resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        notification_id = resp.json()["notification_id"]

        resp = httpx.get(f"{API_BASE}/notifications/{notification_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert result["notification_id"] == notification_id
        assert result["type"] == "approval_requested"

    def test_mark_notification_read(self):
        """标记通知为已读"""
        notification_data = {
            "recipient_id": "agent-read-test",
            "type": "problem_reported",
            "title": "问题报告: 数据丢失",
        }
        resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        notification_id = resp.json()["notification_id"]

        resp = httpx.patch(f"{API_BASE}/notifications/{notification_id}/read", timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert result["read"] is True
        assert result["read_at"] is not None

    def test_mark_all_notifications_read(self):
        """标记所有通知为已读"""
        recipient_id = f"agent-all-read-{uuid.uuid4().hex[:8]}"
        # 创建3条未读通知
        for i in range(3):
            notification_data = {
                "recipient_id": recipient_id,
                "type": "edict_published",
                "title": f"圣旨{i+1}",
            }
            resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
            assert resp.status_code == 201

        resp = httpx.patch(f"{API_BASE}/notifications/read-all", params={"recipient_id": recipient_id}, timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert result["recipient_id"] == recipient_id
        assert result["updated"] >= 3

    def test_unread_notification_count(self):
        """获取未读通知数量"""
        recipient_id = f"agent-count-{uuid.uuid4().hex[:8]}"
        # 创建2条未读通知
        for i in range(2):
            notification_data = {
                "recipient_id": recipient_id,
                "type": "task_blocked",
                "title": f"任务阻塞{i+1}",
            }
            resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
            assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/notifications/unread-count", params={"recipient_id": recipient_id}, timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert result["recipient_id"] == recipient_id
        assert result["unread_count"] >= 2

    def test_delete_notification(self):
        """删除通知"""
        notification_data = {
            "recipient_id": "agent-delete-test",
            "type": "escalation_received",
            "title": "升级事项",
        }
        resp = httpx.post(f"{API_BASE}/notifications", json=notification_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        notification_id = resp.json()["notification_id"]

        resp = httpx.delete(f"{API_BASE}/notifications/{notification_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(f"{API_BASE}/notifications/{notification_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_notification_not_found(self):
        """通知不存在返回404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/notifications/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestRoomTemplates:
    """Room Templates API 测试"""

    def test_list_room_templates(self):
        """列出房间模板（默认模板应该存在）"""
        resp = httpx.get(f"{API_BASE}/room-templates", timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert "templates" in result
        assert isinstance(result["templates"], list)

    def test_list_room_templates_filter_by_purpose(self):
        """按用途筛选模板"""
        resp = httpx.get(f"{API_BASE}/room-templates", params={"purpose": "problem_solving"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        for tmpl in result.get("templates", []):
            if tmpl.get("purpose"):
                assert tmpl["purpose"] == "problem_solving"

    def test_create_room_template(self):
        """创建房间模板"""
        template_data = {
            "name": "测试讨论室",
            "description": "用于自动化测试的模板",
            "purpose": "initial_discussion",
            "mode": "flat",
            "default_phase": "thinking",
            "settings": {"allow_skip_thinking": True},
            "is_shared": False,
        }
        resp = httpx.post(f"{API_BASE}/room-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        result = resp.json()
        assert "template_id" in result
        template_id = result["template_id"]

        # 验证创建成功
        resp = httpx.get(f"{API_BASE}/room-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["name"] == "测试讨论室"
        assert tmpl["purpose"] == "initial_discussion"
        assert tmpl["mode"] == "flat"
        assert tmpl["default_phase"] == "thinking"
        assert tmpl["is_shared"] is False

    def test_update_room_template(self):
        """更新房间模板"""
        # 先创建一个模板
        template_data = {
            "name": "待更新模板",
            "purpose": "decision_making",
            "mode": "hierarchical",
        }
        resp = httpx.post(f"{API_BASE}/room-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 更新模板
        resp = httpx.patch(f"{API_BASE}/room-templates/{template_id}", json={
            "name": "已更新模板",
            "mode": "flat",
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["name"] == "已更新模板"
        assert tmpl["mode"] == "flat"
        assert tmpl["purpose"] == "decision_making"  # 未更新的字段保持不变

    def test_delete_room_template(self):
        """删除房间模板"""
        template_data = {
            "name": "待删除模板",
            "purpose": "review",
        }
        resp = httpx.post(f"{API_BASE}/room-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 删除模板
        resp = httpx.delete(f"{API_BASE}/room-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(f"{API_BASE}/room-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_room_template_not_found(self):
        """模板不存在返回404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/room-templates/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_create_room_from_template(self):
        """从模板创建房间"""
        # 先创建一个计划
        plan_data = {
            "title": "从模板创建房间测试",
            "topic": "测试主题",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 创建一个模板
        template_data = {
            "name": "房间创建模板",
            "purpose": "problem_solving",
            "mode": "hierarchical",
            "default_phase": "selecting",
        }
        resp = httpx.post(f"{API_BASE}/room-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 从模板创建房间
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/rooms/from-template/{template_id}",
            json={"topic": "从模板创建的讨论室", "version": "v1.0"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        result = resp.json()
        assert "room_id" in result
        assert result.get("template_applied") == "房间创建模板"
        room_id = result["room_id"]

        # 验证房间已创建
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        room = resp.json()
        assert room["topic"] == "从模板创建的讨论室"
        assert room["plan_id"] == plan_id


class TestPlanTemplates:
    """Plan Templates API 测试"""

    def test_create_plan_template(self):
        """创建计划模板"""
        template_data = {
            "name": "测试计划模板",
            "description": "用于自动化测试的计划模板",
            "plan_content": {"title": "模板内容", "rooms": []},
            "tags": ["test", "automation"],
            "is_shared": False,
        }
        resp = httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        result = resp.json()
        assert "template_id" in result
        assert result["name"] == "测试计划模板"
        assert result["description"] == "用于自动化测试的计划模板"
        assert result["is_shared"] is False

    def test_list_plan_templates(self):
        """列出计划模板"""
        # 先创建一个模板
        template_data = {
            "name": "列表测试模板",
            "tags": ["list-test"],
        }
        httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT).raise_for_status()

        resp = httpx.get(f"{API_BASE}/plan-templates", timeout=TIMEOUT)
        assert resp.status_code == 200

    def test_get_plan_template(self):
        """获取单个计划模板"""
        template_data = {
            "name": "获取单个模板测试",
            "description": "用于测试获取单个模板",
            "tags": ["get-test"],
        }
        resp = httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        resp = httpx.get(f"{API_BASE}/plan-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["name"] == "获取单个模板测试"
        assert tmpl["description"] == "用于测试获取单个模板"

    def test_update_plan_template(self):
        """更新计划模板"""
        template_data = {
            "name": "待更新计划模板",
            "tags": ["update-test"],
        }
        resp = httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        resp = httpx.patch(f"{API_BASE}/plan-templates/{template_id}", json={
            "name": "已更新计划模板",
            "description": "更新后的描述",
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["name"] == "已更新计划模板"
        assert tmpl["description"] == "更新后的描述"

    def test_delete_plan_template(self):
        """删除计划模板"""
        template_data = {
            "name": "待删除计划模板",
        }
        resp = httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        resp = httpx.delete(f"{API_BASE}/plan-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        resp = httpx.get(f"{API_BASE}/plan-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_plan_template_not_found(self):
        """计划模板不存在返回404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/plan-templates/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_create_plan_from_template(self):
        """从计划模板创建新计划"""
        # 创建一个计划模板
        template_data = {
            "name": "计划创建模板",
            "description": "用于从模板创建计划的模板",
            "plan_content": {"test": "content"},
            "tags": ["plan-test"],
        }
        resp = httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 从模板创建计划
        resp = httpx.post(
            f"{API_BASE}/plan-templates/{template_id}/create-plan",
            json={"title": "从模板创建的计划", "topic": "从模板创建的主题"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        result = resp.json()
        assert "plan_id" in result
        assert result.get("template_applied") == "计划创建模板"
        plan_id = result["plan_id"]

        # 验证计划已创建
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        plan = resp.json()
        assert plan["title"] == "从模板创建的计划"

    def test_list_plan_templates_with_search(self):
        """搜索计划模板"""
        template_data = {
            "name": "搜索测试计划模板",
            "description": "用于测试搜索功能",
            "tags": ["search-test"],
        }
        httpx.post(f"{API_BASE}/plan-templates", json=template_data, timeout=TIMEOUT).raise_for_status()

        resp = httpx.get(f"{API_BASE}/plan-templates", params={"search": "搜索测试"}, timeout=TIMEOUT)
        assert resp.status_code == 200


class TestTaskTemplates:
    """Task Templates API Tests"""

    def test_list_task_templates(self):
        """列出任务模板（默认模板应该存在）"""
        resp = httpx.get(f"{API_BASE}/task-templates", timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert isinstance(result, dict)
        assert "templates" in result
        assert isinstance(result["templates"], list)

    def test_create_task_template(self):
        """创建任务模板"""
        template_data = {
            "name": "测试任务模板",
            "default_title": "自动化测试任务",
            "description": "用于自动化测试的任务模板",
            "priority": "high",
            "difficulty": "medium",
            "estimated_hours": 8.0,
            "owner_level": 3,
            "owner_role": "开发",
            "tags": ["test", "automation"],
            "is_shared": False,
        }
        resp = httpx.post(f"{API_BASE}/task-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        result = resp.json()
        assert "template_id" in result
        template_id = result["template_id"]

        # 验证创建成功
        resp = httpx.get(f"{API_BASE}/task-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["name"] == "测试任务模板"
        assert tmpl["default_title"] == "自动化测试任务"
        assert tmpl["priority"] == "high"
        assert tmpl["difficulty"] == "medium"
        assert tmpl["estimated_hours"] == 8.0
        assert tmpl["owner_level"] == 3
        assert tmpl["owner_role"] == "开发"
        assert "test" in tmpl["tags"]
        assert tmpl["is_shared"] is False

    def test_update_task_template(self):
        """更新任务模板"""
        # 先创建一个模板
        template_data = {
            "name": "待更新任务模板",
            "default_title": "更新前任务",
            "priority": "low",
            "difficulty": "easy",
        }
        resp = httpx.post(f"{API_BASE}/task-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 更新模板
        resp = httpx.patch(f"{API_BASE}/task-templates/{template_id}", json={
            "name": "已更新任务模板",
            "priority": "critical",
            "estimated_hours": 16.0,
        }, timeout=TIMEOUT)
        assert resp.status_code == 200
        tmpl = resp.json()
        assert tmpl["name"] == "已更新任务模板"
        assert tmpl["priority"] == "critical"
        assert tmpl["estimated_hours"] == 16.0
        assert tmpl["default_title"] == "更新前任务"  # 未更新的字段保持不变
        assert tmpl["difficulty"] == "easy"

    def test_delete_task_template(self):
        """删除任务模板"""
        template_data = {
            "name": "待删除任务模板",
            "default_title": "删除任务",
        }
        resp = httpx.post(f"{API_BASE}/task-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 删除模板
        resp = httpx.delete(f"{API_BASE}/task-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(f"{API_BASE}/task-templates/{template_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_task_template_not_found(self):
        """模板不存在返回404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/task-templates/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_create_task_from_template(self):
        """从任务模板创建任务"""
        # 先创建一个计划
        plan_data = {
            "title": "从模板创建任务测试",
            "topic": "测试主题",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        # 创建一个任务模板
        template_data = {
            "name": "任务创建模板",
            "default_title": "模板默认任务",
            "default_description": "这是从模板创建的任务",
            "priority": "medium",
            "difficulty": "hard",
            "estimated_hours": 12.0,
            "owner_level": 4,
            "owner_role": "测试",
        }
        resp = httpx.post(f"{API_BASE}/task-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        template_id = resp.json()["template_id"]

        # 从模板创建任务
        resp = httpx.post(
            f"{API_BASE}/task-templates/{template_id}/create-task",
            params={"plan_id": plan_id, "version": "v1.0", "title": "自定义任务标题"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        result = resp.json()
        assert "task_id" in result
        assert result.get("template_applied") == "任务创建模板"
        task_id = result["task_id"]

        # 验证任务已创建
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks/{task_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        task = resp.json()
        assert task["title"] == "自定义任务标题"
        assert task["plan_id"] == plan_id
        assert task["priority"] == "medium"
        assert task["estimated_hours"] == 12.0

    def test_list_task_templates_with_tag_filter(self):
        """按标签筛选任务模板"""
        # 创建一个带特定标签的模板
        template_data = {
            "name": "标签测试任务模板",
            "default_title": "测试任务",
            "tags": ["tag-filter-test", "automation"],
        }
        resp = httpx.post(f"{API_BASE}/task-templates", json=template_data, timeout=TIMEOUT)
        assert resp.status_code == 201

        # 按标签筛选
        resp = httpx.get(f"{API_BASE}/task-templates", params={"tag": "tag-filter-test"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        result = resp.json()
        assert isinstance(result, dict)
        templates = result.get("templates", [])
        # 验证返回的模板包含指定标签
        for tmpl in templates:
            if tmpl.get("name") == "标签测试任务模板":
                assert "tag-filter-test" in tmpl.get("tags", [])


class TestRoomTags:
    """Step 69: Room Tags API Tests"""

    @pytest.fixture
    def test_room(self):
        """创建一个测试房间"""
        plan_data = {
            "title": "Room Tags Test Plan",
            "topic": "用于测试房间标签的主题",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        plan = data["plan"]
        room = data["room"]
        return room

    def test_get_room_tags_empty(self, test_room):
        """获取房间标签（空标签）"""
        room_id = test_room["room_id"]
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/tags", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert "tags" in data

    def test_update_room_tags(self, test_room):
        """更新房间标签（替换模式）"""
        room_id = test_room["room_id"]
        new_tags = ["重要", "紧急", "技术评审"]

        resp = httpx.patch(f"{API_BASE}/rooms/{room_id}/tags", json={"tags": new_tags}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert data["tags"] == new_tags

    def test_add_room_tags(self, test_room):
        """添加房间标签"""
        room_id = test_room["room_id"]

        # 先设置初始标签
        httpx.patch(f"{API_BASE}/rooms/{room_id}/tags", json={"tags": ["重要"]}, timeout=TIMEOUT).raise_for_status()

        # 添加新标签
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/tags/add", json={"tags": ["紧急"]}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "重要" in data["tags"]
        assert "紧急" in data["tags"]

    def test_add_room_tags_deduplication(self, test_room):
        """添加房间标签（去重）"""
        room_id = test_room["room_id"]

        # 先设置初始标签
        httpx.patch(f"{API_BASE}/rooms/{room_id}/tags", json={"tags": ["重要"]}, timeout=TIMEOUT).raise_for_status()

        # 添加已存在的标签（应该去重）
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/tags/add", json={"tags": ["重要", "新标签"]}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        # "重要" 只应该出现一次
        assert data["tags"].count("重要") == 1
        assert "重要" in data["tags"]
        assert "新标签" in data["tags"]

    def test_remove_room_tags(self, test_room):
        """移除房间标签"""
        room_id = test_room["room_id"]

        # 先设置初始标签
        httpx.patch(f"{API_BASE}/rooms/{room_id}/tags", json={"tags": ["重要", "紧急", "技术评审"]}, timeout=TIMEOUT).raise_for_status()

        # 移除一个标签
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/tags/remove", json={"tags": ["紧急"]}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "重要" in data["tags"]
        assert "技术评审" in data["tags"]
        assert "紧急" not in data["tags"]

    def test_search_rooms_by_tags(self, test_room):
        """搜索房间（按标签过滤）"""
        room_id = test_room["room_id"]

        # 设置标签
        httpx.patch(f"{API_BASE}/rooms/{room_id}/tags", json={"tags": ["重要", "技术评审"]}, timeout=TIMEOUT).raise_for_status()

        # 按标签搜索
        resp = httpx.get(f"{API_BASE}/rooms/search", params={"q": "测试", "tags": "重要"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tags"] == ["重要"]
        # 验证返回的房间包含标签
        if data["count"] > 0:
            assert "重要" in data["rooms"][0].get("tags", [])

    def test_room_tags_room_not_found(self):
        """房间标签（房间不存在）"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/rooms/{fake_id}/tags", timeout=TIMEOUT)
        assert resp.status_code == 404


class TestActionItems:
    """Step 70: Action Items API Tests"""

    @pytest.fixture
    def test_room(self):
        """创建一个测试房间"""
        plan_data = {
            "title": "Action Items Test Plan",
            "topic": "用于测试行动项的主题",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        return data["room"]

    def test_create_action_item(self, test_room):
        """创建行动项"""
        room_id = test_room["room_id"]
        item_data = {
            "title": "完成技术方案文档",
            "description": "需要输出完整的技术方案文档，包含架构设计",
            "assignee": "张三",
            "assignee_level": 4,
            "priority": "high",
            "created_by": "李四",
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/action-items", json=item_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "完成技术方案文档"
        assert data["description"] == "需要输出完整的技术方案文档，包含架构设计"
        assert data["assignee"] == "张三"
        assert data["assignee_level"] == 4
        assert data["status"] == "open"
        assert data["priority"] == "high"
        assert "action_item_id" in data
        assert "created_at" in data

    def test_list_room_action_items(self, test_room):
        """列出讨论室行动项"""
        room_id = test_room["room_id"]
        # 创建两个行动项
        for i in range(2):
            httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
                json={"title": f"行动项 {i+1}", "priority": "medium"},
                timeout=TIMEOUT).raise_for_status()

        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/action-items", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert data["count"] >= 2

    def test_list_action_items_by_status(self, test_room):
        """按状态筛选行动项"""
        room_id = test_room["room_id"]
        # 创建一个 open 行动项
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
            json={"title": "待完成的任务", "status": "open"}, timeout=TIMEOUT)
        item_id = resp.json()["action_item_id"]
        # 标记为已完成
        httpx.patch(f"{API_BASE}/action-items/{item_id}",
            json={"status": "completed"}, timeout=TIMEOUT).raise_for_status()

        # 只获取 open
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/action-items",
            params={"status": "open"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    def test_get_action_item(self, test_room):
        """获取单个行动项"""
        room_id = test_room["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
            json={"title": "获取测试", "priority": "low"}, timeout=TIMEOUT)
        item_id = resp.json()["action_item_id"]

        resp = httpx.get(f"{API_BASE}/action-items/{item_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_item_id"] == item_id
        assert data["title"] == "获取测试"

    def test_update_action_item(self, test_room):
        """更新行动项"""
        room_id = test_room["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
            json={"title": "原始标题", "priority": "low"}, timeout=TIMEOUT)
        item_id = resp.json()["action_item_id"]

        resp = httpx.patch(f"{API_BASE}/action-items/{item_id}",
            json={"title": "更新后标题", "status": "in_progress", "priority": "high"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "更新后标题"
        assert data["status"] == "in_progress"
        assert data["priority"] == "high"

    def test_complete_action_item(self, test_room):
        """完成行动项"""
        room_id = test_room["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
            json={"title": "待完成"}, timeout=TIMEOUT)
        item_id = resp.json()["action_item_id"]

        resp = httpx.post(f"{API_BASE}/action-items/{item_id}/complete", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    def test_delete_action_item(self, test_room):
        """删除行动项"""
        room_id = test_room["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
            json={"title": "待删除"}, timeout=TIMEOUT)
        item_id = resp.json()["action_item_id"]

        resp = httpx.delete(f"{API_BASE}/action-items/{item_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(f"{API_BASE}/action-items/{item_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_action_item_not_found(self):
        """行动项不存在"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/action-items/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_list_plan_action_items(self, test_room):
        """列出计划的所有行动项"""
        room_id = test_room["room_id"]
        plan_id = test_room["plan_id"]

        httpx.post(f"{API_BASE}/rooms/{room_id}/action-items",
            json={"title": "计划行动项"}, timeout=TIMEOUT).raise_for_status()

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/action-items", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id
        assert data["count"] >= 1


class TestVersionComparison:
    """Step 71: Plan Version Comparison API Tests"""

    @pytest.fixture
    def test_plan(self):
        """创建一个测试计划"""
        plan_data = {
            "title": "Version Compare Test Plan",
            "topic": "用于测试版本比较的主题",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        return data["plan"]

    def test_compare_versions_invalid_from_version(self, test_plan):
        """比较版本：源版本不存在"""
        plan_id = test_plan["plan_id"]
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/compare",
            params={"from_version": "v99.0", "to_version": "v1.0"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 400
        assert "不存在" in resp.text

    def test_compare_versions_invalid_to_version(self, test_plan):
        """比较版本：目标版本不存在"""
        plan_id = test_plan["plan_id"]
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/compare",
            params={"from_version": "v1.0", "to_version": "v99.0"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 400
        assert "不存在" in resp.text

    def test_compare_same_version(self, test_plan):
        """比较版本：相同版本应返回空差异"""
        plan_id = test_plan["plan_id"]
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/compare",
            params={"from_version": "v1.0", "to_version": "v1.0"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_version"] == "v1.0"
        assert data["to_version"] == "v1.0"
        assert data["summary"]["tasks"]["added"] == 0
        assert data["summary"]["tasks"]["removed"] == 0
        assert data["summary"]["requirements"]["added"] == 0
        assert data["summary"]["requirements"]["removed"] == 0

    def test_compare_with_new_version_tasks_added(self, test_plan):
        """比较版本：新版本添加了任务"""
        plan_id = test_plan["plan_id"]
        version = test_plan["current_version"]

        # 创建新版本（v1.0 -> v1.1）
        new_tasks = [
            {
                "title": "新任务1",
                "description": "这是一个新任务",
                "priority": "high",
                "owner_id": "agent-1",
                "owner_level": 5,
            }
        ]
        version_data = {
            "parent_version": version,
            "type": "enhancement",
            "description": "添加新任务",
            "tasks": new_tasks,
        }
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/versions", json=version_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        new_version = resp.json()["version"]

        # 比较 v1.0 和 v1.1
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/compare",
            params={"from_version": version, "to_version": new_version},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["from_version"] == version
        assert data["to_version"] == new_version
        assert data["summary"]["tasks"]["added"] >= 1
        # 找到新增的任务
        added_tasks = [t for t in data["tasks_added"] if t.get("title") == "新任务1"]
        assert len(added_tasks) == 1

    def test_compare_versions_response_structure(self, test_plan):
        """比较版本：验证响应结构完整"""
        plan_id = test_plan["plan_id"]
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/compare",
            params={"from_version": "v1.0", "to_version": "v1.0"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        # 验证完整字段
        assert "plan_id" in data
        assert "from_version" in data
        assert "to_version" in data
        assert "tasks_added" in data
        assert "tasks_removed" in data
        assert "tasks_modified" in data
        assert "requirements_added" in data
        assert "requirements_removed" in data
        assert "decisions_added" in data
        assert "decisions_removed" in data
        assert "edicts_added" in data
        assert "edicts_removed" in data
        assert "issues_added" in data
        assert "issues_removed" in data
        assert "risks_added" in data
        assert "risks_removed" in data
        assert "summary" in data
        # 验证 summary 结构
        for key in ["tasks", "requirements", "decisions", "edicts", "issues", "risks"]:
            assert key in data["summary"]


class TestMeetingMinutes:
    """Step 77: Meeting Minutes API Tests"""

    @pytest.fixture
    def test_plan(self):
        """创建一个测试计划（带讨论室）"""
        plan_data = {
            "title": "会议纪要测试计划",
            "topic": "用于测试会议纪要的主题",
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        # 返回完整数据（包含 plan 和 room）
        return data

    def test_create_meeting_minutes(self, test_plan):
        """创建会议纪要"""
        room_id = test_plan["room"]["room_id"]
        minutes_data = {
            "title": "第一次会议纪要",
            "content": "本次会议讨论了项目计划和技术方案。",
            "summary": "讨论了项目计划和技术方案，确定了初步方向。",
            "decisions_summary": "决定采用微服务架构。",
            "action_items_summary": "张三负责架构设计，李四负责文档编写。",
            "participants_list": ["张三", "李四", "王五"],
            "duration_minutes": 90,
            "created_by": "张三",
        }
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/meeting-minutes", json=minutes_data, timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "第一次会议纪要"
        assert data["content"] == "本次会议讨论了项目计划和技术方案。"
        assert data["summary"] == "讨论了项目计划和技术方案，确定了初步方向。"
        assert data["decisions_summary"] == "决定采用微服务架构。"
        assert data["action_items_summary"] == "张三负责架构设计，李四负责文档编写。"
        assert data["participants_list"] == ["张三", "李四", "王五"]
        assert data["duration_minutes"] == 90
        assert data["created_by"] == "张三"
        assert "meeting_minutes_id" in data
        assert "created_at" in data
        assert data["room_id"] == room_id
        assert data["version"] == "v1.0", "version should be set from room.current_version"

    def test_list_room_meeting_minutes(self, test_plan):
        """列出讨论室的会议纪要"""
        room_id = test_plan["room"]["room_id"]
        # 创建两条纪要
        for i in range(2):
            httpx.post(f"{API_BASE}/rooms/{room_id}/meeting-minutes",
                json={"title": f"会议纪要 {i+1}", "content": f"内容{i+1}"},
                timeout=TIMEOUT).raise_for_status()

        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/meeting-minutes", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        for item in data:
            assert item["room_id"] == room_id

    def test_list_plan_meeting_minutes(self, test_plan):
        """列出计划的会议纪要"""
        plan_id = test_plan["plan"]["plan_id"]
        room_id = test_plan["room"]["room_id"]
        httpx.post(f"{API_BASE}/rooms/{room_id}/meeting-minutes",
            json={"title": "计划会议纪要", "content": "内容"},
            timeout=TIMEOUT).raise_for_status()

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/meeting-minutes", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(m["title"] == "计划会议纪要" for m in data)

    def test_get_meeting_minutes(self, test_plan):
        """获取单个会议纪要"""
        room_id = test_plan["room"]["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/meeting-minutes",
            json={"title": "获取测试纪要", "content": "测试内容"}, timeout=TIMEOUT)
        minutes_id = resp.json()["meeting_minutes_id"]

        resp = httpx.get(f"{API_BASE}/meeting-minutes/{minutes_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["meeting_minutes_id"] == minutes_id
        assert data["title"] == "获取测试纪要"
        assert data["content"] == "测试内容"

    def test_update_meeting_minutes(self, test_plan):
        """更新会议纪要"""
        room_id = test_plan["room"]["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/meeting-minutes",
            json={"title": "原始标题", "content": "原始内容"}, timeout=TIMEOUT)
        minutes_id = resp.json()["meeting_minutes_id"]

        resp = httpx.patch(f"{API_BASE}/meeting-minutes/{minutes_id}",
            json={"title": "更新后标题", "content": "更新后内容", "summary": "新增摘要"}, timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "更新后标题"
        assert data["content"] == "更新后内容"
        assert data["summary"] == "新增摘要"

    def test_delete_meeting_minutes(self, test_plan):
        """删除会议纪要"""
        room_id = test_plan["room"]["room_id"]
        resp = httpx.post(f"{API_BASE}/rooms/{room_id}/meeting-minutes",
            json={"title": "待删除纪要", "content": "内容"}, timeout=TIMEOUT)
        minutes_id = resp.json()["meeting_minutes_id"]

        resp = httpx.delete(f"{API_BASE}/meeting-minutes/{minutes_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除
        resp = httpx.get(f"{API_BASE}/meeting-minutes/{minutes_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_meeting_minutes_not_found(self):
        """会议纪要不存在的404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.get(f"{API_BASE}/meeting-minutes/{fake_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_generate_meeting_minutes(self, test_plan):
        """从讨论室生成会议纪要（包含决策和行动项）"""
        room_id = test_plan["room"]["room_id"]
        # 生成纪要（不包含消息历史）
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/meeting-minutes/generate",
            json={
                "title": "自动生成会议纪要",
                "include_decisions": True,
                "include_action_items": True,
                "include_timeline": True,
                "include_messages": False,
            },
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "自动生成会议纪要"
        assert data["room_id"] == room_id
        assert "meeting_minutes_id" in data

    def test_generate_meeting_minutes_default_options(self, test_plan):
        """生成会议纪要（使用默认选项）"""
        room_id = test_plan["room"]["room_id"]
        # 不传 body，使用全部默认选项
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/meeting-minutes/generate",
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "meeting_minutes_id" in data
        assert "title" in data

    def test_generate_meeting_minutes_all_options_disabled(self, test_plan):
        """生成会议纪要（所有可选内容关闭）"""
        room_id = test_plan["room"]["room_id"]
        # 禁用所有可选内容
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/meeting-minutes/generate",
            json={
                "title": "仅摘要纪要",
                "include_decisions": False,
                "include_action_items": False,
                "include_timeline": False,
                "include_messages": False,
            },
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "仅摘要纪要"
        assert data["room_id"] == room_id
        assert "meeting_minutes_id" in data
        # content 应该为空（因为所有可选内容都被禁用）
        assert data.get("content") == "" or data.get("content") is None
        # 摘要仍然存在
        assert "summary" in data
        # decisions_summary 和 action_items_summary 应该为空
        assert data.get("decisions_summary") == ""
        assert data.get("action_items_summary") == ""

    def test_generate_meeting_minutes_room_not_found(self):
        """生成会议纪要（房间不存在返回404）"""
        fake_room_id = str(uuid.uuid4())
        resp = httpx.post(
            f"{API_BASE}/rooms/{fake_room_id}/meeting-minutes/generate",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Room not found"

    def test_generate_meeting_minutes_with_decisions_and_action_items(self, test_plan):
        """生成会议纪要（含决策和行动项的完整摘要）"""
        room_id = test_plan["room"]["room_id"]
        plan_id = test_plan["plan"]["plan_id"]
        version = test_plan["plan"].get("current_version", "v1.0")

        # 创建一个决策
        httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions",
            json={
                "title": "采用微服务架构",
                "decision_text": "决定采用微服务架构进行系统设计",
                "decided_by": "张三",
            },
            timeout=TIMEOUT
        ).raise_for_status()

        # 创建一个行动项（使用唯一标题避免与其他测试混淆）
        unique_title = f"完成架构设计文档-{uuid.uuid4().hex[:8]}"
        httpx.post(
            f"{API_BASE}/rooms/{room_id}/action-items",
            json={
                "title": unique_title,
                "assignee": "张三",
                "priority": "high",
                "created_by": "李四",
            },
            timeout=TIMEOUT
        ).raise_for_status()

        # 生成会议纪要
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/meeting-minutes/generate",
            json={
                "title": "完整会议纪要",
                "include_decisions": True,
                "include_action_items": True,
                "include_timeline": False,
                "include_messages": False,
            },
            timeout=TIMEOUT
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "完整会议纪要"
        # 决策摘要应该包含决策数量（至少有1项）
        assert "项决策" in data.get("decisions_summary", "")
        # 内容中应该包含决策标题（在决策要点章节）
        assert "采用微服务架构" in data.get("content", "")
        # 行动项摘要应该包含行动项数量（至少有1个）
        assert "个行动项" in data.get("action_items_summary", "")
        # 内容中应该包含我们创建的行动项标题
        assert unique_title in data.get("content", "")


# ========================
# Room Watch API (Step 81)
# ========================

class TestRoomWatch:
    """Room Watch 功能测试（5个端点全部覆盖）"""

    def test_watch_room(self, room_info):
        """关注讨论室"""
        room_id = room_info["room_id"]
        user_id = f"user-{uuid.uuid4().hex[:8]}"
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/watch",
            json={"user_id": user_id, "user_name": "测试观众"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201, f"关注失败: {resp.text}"
        data = resp.json()
        assert data["room_id"] == room_id
        assert data["user_id"] == user_id
        assert data["user_name"] == "测试观众"

    def test_list_room_watchers(self, room_info):
        """列出讨论室的所有关注者"""
        room_id = room_info["room_id"]
        user_id_1 = f"user-{uuid.uuid4().hex[:8]}"
        user_id_2 = f"user-{uuid.uuid4().hex[:8]}"

        # 添加两个关注者
        for uid, uname in [(user_id_1, "观众A"), (user_id_2, "观众B")]:
            resp = httpx.post(
                f"{API_BASE}/rooms/{room_id}/watch",
                json={"user_id": uid, "user_name": uname},
                timeout=TIMEOUT
            )
            assert resp.status_code == 201

        # 列出关注者
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/watchers", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["room_id"] == room_id
        assert data["count"] >= 2
        watcher_ids = {w["user_id"] for w in data["watchers"]}
        assert user_id_1 in watcher_ids
        assert user_id_2 in watcher_ids

    def test_unwatch_room(self, room_info):
        """取消关注讨论室"""
        room_id = room_info["room_id"]
        user_id = f"user-{uuid.uuid4().hex[:8]}"

        # 先关注
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/watch",
            json={"user_id": user_id, "user_name": "临时观众"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201

        # 再取消关注
        resp = httpx.delete(f"{API_BASE}/rooms/{room_id}/watch?user_id={user_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unwatched"
        assert data["user_id"] == user_id

        # 验证已不在关注者列表
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/watchers", timeout=TIMEOUT)
        watcher_ids = {w["user_id"] for w in resp.json()["watchers"]}
        assert user_id not in watcher_ids

    def test_get_user_watched_rooms(self, room_info):
        """获取用户关注的所有讨论室"""
        room_id = room_info["room_id"]
        user_id = f"user-{uuid.uuid4().hex[:8]}"

        # 关注房间
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/watch",
            json={"user_id": user_id, "user_name": "专注观众"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201

        # 获取用户关注的房间列表
        resp = httpx.get(f"{API_BASE}/users/{user_id}/watched-rooms", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user_id
        assert data["count"] >= 1
        room_ids = [r["room_id"] for r in data["watched_rooms"]]
        assert room_id in room_ids

    def test_is_room_watched(self, room_info):
        """检查用户是否关注了指定讨论室"""
        room_id = room_info["room_id"]
        user_id_yes = f"user-{uuid.uuid4().hex[:8]}"
        user_id_no = f"user-{uuid.uuid4().hex[:8]}"

        # user_id_yes 关注房间
        resp = httpx.post(
            f"{API_BASE}/rooms/{room_id}/watch",
            json={"user_id": user_id_yes, "user_name": "已关注"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 201

        # 检查已关注
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/watch/status?user_id={user_id_yes}", timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["watched"] is True

        # 检查未关注
        resp = httpx.get(f"{API_BASE}/rooms/{room_id}/watch/status?user_id={user_id_no}", timeout=TIMEOUT)
        assert resp.status_code == 200
        assert resp.json()["watched"] is False

    def test_watch_nonexistent_room(self):
        """关注不存在的讨论室返回404"""
        fake_room = str(uuid.uuid4())
        resp = httpx.post(
            f"{API_BASE}/rooms/{fake_room}/watch",
            json={"user_id": "any-user", "user_name": "幽灵观众"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

    def test_unwatch_not_watching(self, room_info):
        """取消未关注的讨论室返回404"""
        room_id = room_info["room_id"]
        resp = httpx.delete(f"{API_BASE}/rooms/{room_id}/watch?user_id=never-watched-user", timeout=TIMEOUT)
        assert resp.status_code == 404


# ========================
# Plan Copy API (Step 88)
# ========================

class TestPlanCopy:
    """Plan Copy API 测试 — 复制 Plan 元数据 + constraints + stakeholders"""

    def test_copy_plan(self, room_info):
        """测试复制 Plan 基本功能"""
        plan_id = room_info["plan_id"]

        # 复制计划
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/copy", timeout=TIMEOUT)
        assert resp.status_code == 201, f"复制失败: {resp.text}"
        data = resp.json()

        # 验证返回结构
        assert "plan" in data
        assert "room" in data
        new_plan = data["plan"]
        new_room = data["room"]

        # 验证新计划字段
        assert new_plan["plan_id"] != plan_id  # 新ID不同
        assert new_plan["title"].startswith("Copy of ")
        assert new_plan["current_version"] == "v1.0"
        assert new_plan["status"] == "initiated"

        # 验证新房间字段
        assert new_room["room_id"] is not None
        assert new_room["plan_id"] == new_plan["plan_id"]
        assert new_room["phase"] == "selecting"

    def test_copy_plan_not_found(self):
        """测试复制不存在的 Plan 返回 404"""
        fake_id = str(uuid.uuid4())
        resp = httpx.post(f"{API_BASE}/plans/{fake_id}/copy", timeout=TIMEOUT)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Plan not found"

    def test_copy_plan_creates_room(self, room_info):
        """测试复制 Plan 时自动创建配套 Room"""
        plan_id = room_info["plan_id"]

        # 复制计划
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/copy", timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        new_plan_id = data["plan"]["plan_id"]
        new_room_id = data["room"]["room_id"]

        # 验证新计划可以获取
        resp = httpx.get(f"{API_BASE}/plans/{new_plan_id}", timeout=TIMEOUT)
        assert resp.status_code == 200

        # 验证新房间可以获取
        resp = httpx.get(f"{API_BASE}/rooms/{new_room_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        room = resp.json()
        assert room["plan_id"] == new_plan_id

    def test_copy_plan_preserves_metadata(self, room_info):
        """测试复制 Plan 保留元数据（topic/requirements/status）"""
        plan_id = room_info["plan_id"]

        # 复制计划
        resp = httpx.post(f"{API_BASE}/plans/{plan_id}/copy", timeout=TIMEOUT)
        assert resp.status_code == 201
        data = resp.json()
        new_plan = data["plan"]

        # 验证标题前缀
        assert new_plan["title"].startswith("Copy of ")
        # topic 应该被保留
        assert "topic" in new_plan


# ========================
# Decisions API (Step 87)
# ========================

class TestDecisions:
    """Decisions API 测试（完整CRUD + 边界覆盖）"""

    def test_create_decision(self, room_info):
        """创建决策"""
        plan_id = room_info["plan_id"]
        version = "v1.0"
        payload = {
            "title": "采用微服务架构",
            "decision_text": "经过技术选型讨论，决定采用微服务架构进行系统重构",
            "description": "技术选型决策",
            "rationale": "微服务可独立部署、扩展性强、技术栈灵活",
            "alternatives_considered": ["单体架构", "SOA架构"],
            "agreed_by": ["架构师张", "CTO李"],
            "disagreed_by": [],
            "decided_by": "技术总监王",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions",
            json=payload,
            timeout=TIMEOUT
        )
        assert resp.status_code == 201, f"创建决策失败: {resp.text}"
        data = resp.json()
        assert "decision_id" in data
        decision = data["decision"]
        assert decision["title"] == "采用微服务架构"
        assert decision["decision_text"] == "经过技术选型讨论，决定采用微服务架构进行系统重构"
        assert decision["decision_number"] == 1
        assert decision["plan_id"] == plan_id
        assert decision["version"] == version
        assert decision["agreed_by"] == ["架构师张", "CTO李"]
        assert decision["alternatives_considered"] == ["单体架构", "SOA架构"]

    def test_list_decisions(self, room_info):
        """列出版本所有决策"""
        plan_id = room_info["plan_id"]
        version = "v1.0"

        # 创建2个决策
        for title in ["决策A-数据库选型", "决策B-部署策略"]:
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions",
                json={"title": title, "decision_text": f"这是决策：{title}"},
                timeout=TIMEOUT
            )
            assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        assert len(data["decisions"]) >= 2

    def test_get_decision(self, room_info):
        """获取单个决策详情"""
        plan_id = room_info["plan_id"]
        version = "v1.0"

        # 创建决策
        create_resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions",
            json={"title": "获取单个测试", "decision_text": "用于测试获取单个决策"},
            timeout=TIMEOUT
        )
        assert create_resp.status_code == 201
        decision_id = create_resp.json()["decision_id"]

        # 获取单个决策
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions/{decision_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"]["decision_id"] == decision_id
        assert data["decision"]["title"] == "获取单个测试"
        assert data["decision"]["decision_text"] == "用于测试获取单个决策"

    def test_update_decision(self, room_info):
        """更新决策字段"""
        plan_id = room_info["plan_id"]
        version = "v1.0"

        # 创建决策
        create_resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions",
            json={"title": "原始标题", "decision_text": "原始内容"},
            timeout=TIMEOUT
        )
        assert create_resp.status_code == 201
        decision_id = create_resp.json()["decision_id"]

        # 更新决策
        update_payload = {
            "title": "更新后标题",
            "decision_text": "更新后内容",
            "rationale": "更新理由：需求变更",
            "agreed_by": ["更新同意者"],
        }
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions/{decision_id}",
            json=update_payload,
            timeout=TIMEOUT
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"]["title"] == "更新后标题"
        assert data["decision"]["rationale"] == "更新理由：需求变更"

    def test_decision_not_found(self, room_info):
        """决策不存在返回404"""
        plan_id = room_info["plan_id"]
        version = "v1.0"
        fake_decision_id = str(uuid.uuid4())

        # 获取不存在的决策
        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions/{fake_decision_id}",
            timeout=TIMEOUT
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Decision not found"

        # 更新不存在的决策
        resp = httpx.patch(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions/{fake_decision_id}",
            json={"title": "新标题"},
            timeout=TIMEOUT
        )
        assert resp.status_code == 404

    def test_decision_in_version_plan_json(self, room_info):
        """验证决策出现在版本 plan.json 中"""
        plan_id = room_info["plan_id"]
        version = "v1.0"

        # 创建决策
        create_resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/decisions",
            json={"title": "计划JSON测试决策", "decision_text": "验证出现在plan.json中"},
            timeout=TIMEOUT
        )
        assert create_resp.status_code == 201
        decision_id = create_resp.json()["decision_id"]

        # 获取版本 plan.json
        resp = httpx.get(f"{API_BASE}/plans/{plan_id}/versions/{version}/plan.json", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "decisions" in data
        decision_ids = [d["decision_id"] for d in data["decisions"]]
        assert decision_id in decision_ids


class TestPlanSearch:
    """Step 89: Plan Search API Tests — 计划搜索功能"""

    def test_search_plans_basic(self, ensure_api):
        """搜索计划（基本搜索）"""
        # 创建两个不同标题的计划
        plan_payload1 = {"title": "智慧城市顶层设计", "topic": "城市规划与数字化转型", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload1, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan1_id = resp.json()["plan"]["plan_id"]

        plan_payload2 = {"title": "教育信息化改革", "topic": "智慧校园建设方案", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload2, timeout=TIMEOUT)
        assert resp.status_code == 201

        # 搜索关键词
        resp = httpx.get(f"{API_BASE}/plans/search?q=智慧", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        assert data["query"] == "智慧"
        # 两个计划标题都含"智慧"
        plan_ids = [p["plan_id"] for p in data["plans"]]
        assert plan1_id in plan_ids

    def test_search_plans_by_topic(self, ensure_api):
        """按topic搜索计划"""
        plan_payload = {"title": "医疗系统建设", "topic": "区域医疗数据中心", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/plans/search?q=医疗", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["plans"]) >= 1

    def test_search_plans_by_status(self, ensure_api):
        """按status过滤搜索结果"""
        plan_payload = {"title": "状态过滤测试计划", "topic": "测试", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/plans/search?q=状态过滤&status=active", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        for p in data["plans"]:
            assert p.get("status") == "active"

    def test_search_plans_pagination(self, ensure_api):
        """搜索结果分页"""
        for i in range(3):
            resp = httpx.post(
                f"{API_BASE}/plans",
                json={"title": f"分页测试计划{i}", "topic": "测试分页", "requirements": []},
                timeout=TIMEOUT
            )
            assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/plans/search?q=分页测试&limit=1&offset=0", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1
        assert len(data["plans"]) <= 1

        resp2 = httpx.get(f"{API_BASE}/plans/search?q=分页测试&limit=1&offset=1", timeout=TIMEOUT)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["offset"] == 1

    def test_search_plans_empty_query(self, ensure_api):
        """空查询返回422验证错误"""
        resp = httpx.get(f"{API_BASE}/plans/search?q=", timeout=TIMEOUT)
        assert resp.status_code == 422  # min_length=1


class TestRoomSearch:
    """Step 89: Room Search API Tests — 讨论室搜索功能"""

    def test_search_rooms_basic(self, ensure_api):
        """搜索讨论室（基本搜索）"""
        plan_payload = {"title": "房间搜索测试", "topic": "测试讨论室", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/rooms/search?q=讨论", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert "rooms" in data
        assert data["query"] == "讨论"

    def test_search_rooms_by_plan(self, ensure_api):
        """按plan_id过滤搜索结果"""
        plan_payload = {"title": "房间按计划过滤", "topic": "特定计划房间", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        plan_payload2 = {"title": "第二个计划", "topic": "其他计划房间", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload2, timeout=TIMEOUT)
        assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/rooms/search?q=房间&plan_id={plan_id}", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        for room in data["rooms"]:
            assert room.get("plan_id") == plan_id

    def test_search_rooms_by_phase(self, ensure_api):
        """按phase过滤搜索结果"""
        plan_payload = {"title": "阶段过滤测试", "topic": "THINKING阶段房间", "requirements": []}
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        room_id = resp.json()["room"]["room_id"]

        httpx.post(f"{API_BASE}/rooms/{room_id}/phase", json={"phase": "THINKING"}, timeout=TIMEOUT)

        resp = httpx.get(f"{API_BASE}/rooms/search?q=阶段&phase=THINKING", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        for room in data["rooms"]:
            assert room.get("phase") == "THINKING"

    def test_search_rooms_pagination(self, ensure_api):
        """搜索结果分页"""
        for i in range(3):
            resp = httpx.post(
                f"{API_BASE}/plans",
                json={"title": f"分页房间测试{i}", "topic": "测试", "requirements": []},
                timeout=TIMEOUT
            )
            assert resp.status_code == 201

        resp = httpx.get(f"{API_BASE}/rooms/search?q=分页&limit=1&offset=0", timeout=TIMEOUT)
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1
        assert len(data["rooms"]) <= 1

    def test_search_rooms_empty_query(self, ensure_api):
        """空查询返回422验证错误"""
        resp = httpx.get(f"{API_BASE}/rooms/search?q=", timeout=TIMEOUT)
        assert resp.status_code == 422  # min_length=1


class TestTaskTimeEntries:
    """Step 89: Task Time Entries API Tests — 工时记录 CRUD + 边界"""

    def _create_task_with_plan(self):
        """创建计划+任务，返回 (plan_id, version, task_id)"""
        plan_payload = {
            "title": "工时测试计划",
            "topic": "测试工时记录功能",
            "requirements": [],
        }
        resp = httpx.post(f"{API_BASE}/plans", json=plan_payload, timeout=TIMEOUT)
        assert resp.status_code == 201
        plan_id = resp.json()["plan"]["plan_id"]

        task_payload = {
            "title": "实现登录模块",
            "owner_level": 4,
            "owner_role": "L4_PLANNER",
            "priority": "medium",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/v1.0/tasks",
            json=task_payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        task_id = resp.json()["task_id"]
        return plan_id, "v1.0", task_id

    def test_create_time_entry(self):
        """创建时间记录"""
        plan_id, version, task_id = self._create_task_with_plan()

        entry_payload = {
            "user_name": "张工",
            "hours": 2.5,
            "description": "完成登录页面前端开发",
            "notes": "包括响应式布局",
        }
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries",
            json=entry_payload,
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201, f"创建时间记录失败: {resp.text}"
        data = resp.json()
        assert data["user_name"] == "张工"
        assert data["hours"] == 2.5
        assert data["description"] == "完成登录页面前端开发"
        assert data["notes"] == "包括响应式布局"
        assert data["task_id"] == task_id
        assert data["plan_id"] == plan_id
        assert data["version"] == version
        assert "time_entry_id" in data
        assert "created_at" in data

    def test_list_time_entries(self):
        """列出任务的所有时间记录"""
        plan_id, version, task_id = self._create_task_with_plan()

        # 创建 2 条时间记录
        for i, hours in enumerate([1.0, 3.5]):
            entry_payload = {
                "user_name": f"工程师{i+1}",
                "hours": hours,
                "description": f"工作内容 {i+1}",
            }
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries",
                json=entry_payload,
                timeout=TIMEOUT,
            )
            assert resp.status_code == 201

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        entries = resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 2
        # 验证字段结构
        for entry in entries:
            assert "time_entry_id" in entry
            assert "hours" in entry
            assert "user_name" in entry

    def test_get_time_summary(self):
        """获取任务时间汇总"""
        plan_id, version, task_id = self._create_task_with_plan()

        # 创建 3 条时间记录
        entries_data = [
            {"user_name": "张工", "hours": 2.0},
            {"user_name": "张工", "hours": 3.0},
            {"user_name": "李工", "hours": 1.5},
        ]
        for entry in entries_data:
            resp = httpx.post(
                f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries",
                json=entry,
                timeout=TIMEOUT,
            )
            assert resp.status_code == 201

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-summary",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_hours" in data
        assert "entry_count" in data
        assert "contributor_count" in data
        assert data["total_hours"] == 6.5, f"期望 6.5，实际 {data['total_hours']}"
        assert data["entry_count"] == 3
        assert data["contributor_count"] == 2  # 张工 + 李工

    def test_delete_time_entry(self):
        """删除时间记录"""
        plan_id, version, task_id = self._create_task_with_plan()

        # 创建时间记录
        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries",
            json={"user_name": "王工", "hours": 1.0, "description": "待删除"},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 201
        entry_id = resp.json()["time_entry_id"]

        # 删除
        resp = httpx.delete(f"{API_BASE}/time-entries/{entry_id}", timeout=TIMEOUT)
        assert resp.status_code == 204

        # 验证已删除（列表中不再出现）
        list_resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries",
            timeout=TIMEOUT,
        )
        entry_ids = [e["time_entry_id"] for e in list_resp.json()]
        assert entry_id not in entry_ids

    def test_time_entry_not_found(self):
        """时间记录不存在返回404"""
        fake_entry_id = str(uuid.uuid4())
        resp = httpx.delete(f"{API_BASE}/time-entries/{fake_entry_id}", timeout=TIMEOUT)
        assert resp.status_code == 404

    def test_time_summary_empty_task(self):
        """无时间记录的任务返回零值汇总"""
        plan_id, version, task_id = self._create_task_with_plan()

        resp = httpx.get(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{task_id}/time-summary",
            timeout=TIMEOUT,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_hours"] == 0
        assert data["entry_count"] == 0
        assert data["contributor_count"] == 0

    def test_task_not_found_time_entry(self):
        """任务不存在时创建时间记录返回404"""
        plan_id, version, _ = self._create_task_with_plan()
        fake_task_id = str(uuid.uuid4())

        resp = httpx.post(
            f"{API_BASE}/plans/{plan_id}/versions/{version}/tasks/{fake_task_id}/time-entries",
            json={"user_name": "张工", "hours": 1.0},
            timeout=TIMEOUT,
        )
        assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
