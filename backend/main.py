"""
Agora-V2 主入口
去中心化多Agent讨论协调系统

PDCA 迭代记录（2026-04-04）：
- Step 32: Plan/Deliberation Export API — 决议报告 Markdown 导出
  * GET /plans/{plan_id}/export — 完整 Plan Markdown 报告
  * GET /plans/{plan_id}/versions/{version}/export — 指定版本 Markdown 报告
  * 包含：Plan信息、Rooms讨论记录、Decisions、Constraints、Stakeholders、Tasks、Risks、Edicts、Analytics概览
- 本次迭代：Step 26 — Message Sequence Number Assignment
  * messages.sequence 字段赋值逻辑（每条消息自动获得递增序号）
  * crud.get_next_message_sequence(room_id) - 获取房间下一条消息序号
  * add_message/transition_phase/escalation 等所有消息创建点传递 sequence
  * _get_next_seq_for_room(room_id) - DB优先，内存兜底
  * 历史记录每条消息包含 sequence 字段
  * 测试：TestMessageSequence::test_message_sequence_assignment ✅
  * 测试：TestMessageSequence::test_room_history_includes_sequence ✅
"""
import os
import uuid
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum

from gateway_client import (
    GatewayClient,
    get_gateway_client,
    init_gateway_client,
)

# ========================
# CRUD 导入（PostgreSQL 持久化层）
# ========================
from repositories import crud

# 日志
logger = logging.getLogger("agora")


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
    PROBLEM_ANALYSIS = "problem_analysis"
    PROBLEM_DISCUSSION = "problem_discussion"
    PLAN_UPDATE = "plan_update"
    RESUMING = "resuming"


class RoomPurpose(str, Enum):
    INITIAL_DISCUSSION = "initial_discussion"
    PROBLEM_SOLVING = "problem_solving"
    DECISION_MAKING = "decision_making"
    REVIEW = "review"


class RoomMode(str, Enum):
    FLAT = "flat"
    HIERARCHICAL = "hierarchical"
    COLLABORATIVE = "collaborative"
    SPECIALIZED = "specialized"


# ========================
# Pydantic 模型
# ========================

class PlanCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(..., min_length=1)
    requirements: List[str] = Field(default_factory=list)
    hierarchy_id: Optional[str] = "default"
    purpose: RoomPurpose = Field(default=RoomPurpose.INITIAL_DISCUSSION)
    mode: RoomMode = Field(default=RoomMode.HIERARCHICAL)


# ========================
# Requirements 模型
# ========================

class RequirementPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementCategory(str, Enum):
    BUDGET = "budget"
    TIMELINE = "timeline"
    TECHNICAL = "technical"
    QUALITY = "quality"
    RESOURCE = "resource"
    RISK = "risk"
    COMPLIANCE = "compliance"
    OTHER = "other"


class RequirementStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_MET = "not_met"
    DEPRECATED = "deprecated"


class RequirementCreate(BaseModel):
    """创建需求"""
    description: str = Field(..., min_length=1, max_length=500)
    priority: RequirementPriority = RequirementPriority.MEDIUM
    category: RequirementCategory = RequirementCategory.OTHER
    status: RequirementStatus = RequirementStatus.PENDING
    notes: Optional[str] = ""


class RequirementUpdate(BaseModel):
    """更新需求（可选字段）"""
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    priority: Optional[RequirementPriority] = None
    category: Optional[RequirementCategory] = None
    status: Optional[RequirementStatus] = None
    notes: Optional[str] = None


# ========================
# Constraints & Stakeholders & Risks 模型
# 来源: 08-Data-Models-Details.md §2.1 Plan.constraints/stakeholders + §3.1 Version.risks
# ========================

class ConstraintType(str, Enum):
    BUDGET = "budget"
    TIMELINE = "timeline"
    RESOURCE = "resource"
    QUALITY = "quality"
    COMPLIANCE = "compliance"
    SCOPE = "scope"
    OTHER = "other"


class StakeholderInterest(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskProbability(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskImpact(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskStatus(str, Enum):
    IDENTIFIED = "identified"
    MITIGATED = "mitigated"
    REALIZED = "realized"


class ConstraintCreate(BaseModel):
    """创建约束"""
    type: ConstraintType
    value: str = Field(..., min_length=1)
    unit: Optional[str] = ""
    description: Optional[str] = ""


class ConstraintUpdate(BaseModel):
    """更新约束"""
    type: Optional[ConstraintType] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None


class StakeholderCreate(BaseModel):
    """创建干系人"""
    name: str = Field(..., min_length=1)
    level: Optional[int] = Field(None, ge=1, le=7)
    interest: StakeholderInterest = StakeholderInterest.MEDIUM
    influence: StakeholderInterest = StakeholderInterest.MEDIUM
    description: Optional[str] = ""


class StakeholderUpdate(BaseModel):
    """更新干系人"""
    name: Optional[str] = None
    level: Optional[int] = Field(None, ge=1, le=7)
    interest: Optional[StakeholderInterest] = None
    influence: Optional[StakeholderInterest] = None
    description: Optional[str] = None


class RiskCreate(BaseModel):
    """创建风险"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    probability: RiskProbability = RiskProbability.MEDIUM
    impact: RiskImpact = RiskImpact.MEDIUM
    mitigation: Optional[str] = ""
    contingency: Optional[str] = ""
    status: RiskStatus = RiskStatus.IDENTIFIED


class RiskUpdate(BaseModel):
    """更新风险"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    probability: Optional[RiskProbability] = None
    impact: Optional[RiskImpact] = None
    mitigation: Optional[str] = None
    contingency: Optional[str] = None
    status: Optional[RiskStatus] = None


class ParticipantAdd(BaseModel):
    agent_id: str
    name: str
    level: int = Field(default=5, ge=1, le=7)
    role: str = "Member"


# ========================
# Step 24: Room Hierarchy + Participant Contributions
# ========================

class RoomLinkRequest(BaseModel):
    """关联讨论室请求（建立父子/关联关系）"""
    parent_room_id: Optional[str] = None
    related_room_ids: List[str] = Field(default_factory=list)


class ParticipantContributionUpdate(BaseModel):
    """更新参与者贡献计数"""
    speech_count: Optional[int] = None
    challenge_count: Optional[int] = None
    response_count: Optional[int] = None
    thinking_complete: Optional[bool] = None
    sharing_complete: Optional[bool] = None


class RoomConclusionRequest(BaseModel):
    """结束讨论室并填写总结"""
    summary: str
    conclusion: Optional[str] = None


class SpeechAdd(BaseModel):
    agent_id: str
    content: str


# ========================
# Room Template 模型
# ========================

class RoomTemplateCreate(BaseModel):
    """创建房间模板"""
    name: str = Field(..., min_length=1)
    description: Optional[str] = ""
    purpose: str = "initial_discussion"
    mode: str = "hierarchical"
    default_phase: str = "selecting"
    settings: Optional[Dict[str, Any]] = {}
    is_shared: bool = False


class RoomTemplateUpdate(BaseModel):
    """更新房间模板"""
    name: Optional[str] = None
    description: Optional[str] = None
    purpose: Optional[str] = None
    mode: Optional[str] = None
    default_phase: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_shared: Optional[bool] = None


# ========================
# L1-L7 层级审批模型
# ========================

class ApprovalLevel(int, Enum):
    """L1=任务层(操作) → L7=战略层(最终决策)"""
    L1 = 1  # 任务层：具体操作意见
    L2 = 2  # 岗位层：专业意见
    L3 = 3  # 班组层：现场执行把关
    L4 = 4  # 团队层：方案整合
    L5 = 5  # 部门层：专业把关
    L6 = 6  # 事业部层：资源协调
    L7 = 7  # 战略层：最终决策

    @property
    def label(self) -> str:
        labels = {
            1: "任务层(操作)",
            2: "岗位层(专业意见)",
            3: "班组层(现场执行)",
            4: "团队层(方案整合)",
            5: "部门层(专业把关)",
            6: "事业部层(资源协调)",
            7: "战略层(最终决策)",
        }
        return labels[self.value]

    @property
    def reviewer_role(self) -> str:
        roles = {
            1: "操作员",
            2: "专家",
            3: "班长",
            4: "团队负责人",
            5: "部门负责人",
            6: "事业部负责人",
            7: "战略决策者",
        }
        return roles[self.value]


class ApprovalAction(str, Enum):
    APPROVE = "approve"      # 通过，流转下一级
    REJECT = "reject"        # 驳回，打回修改
    RETURN = "return"         # 退回上一级
    ESCALATE = "escalate"    # 升级，跳级处理


class ApprovalStepRecord(BaseModel):
    level: int                    # L1-L7
    status: str = "pending"       # pending/approved/rejected/returned/escalated
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    comment: Optional[str] = None
    decided_at: Optional[str] = None
    escalated_to: Optional[int] = None  # 升级到的级别


class ApprovalFlowCreate(BaseModel):
    """启动审批流"""
    initiator_id: str
    initiator_name: str
    skip_levels: List[int] = Field(default_factory=list)  # 跳过的级别，如[1,2]


class ApprovalActionRecord(BaseModel):
    """单个审批动作"""
    plan_id: str
    level: int
    action: ApprovalAction
    actor_id: str
    actor_name: str
    comment: Optional[str] = None


# ========================
# 层级汇报/升级模型（05-Hierarchy-Roles.md §7.2 层级汇报）
# ========================


class EscalationMode(str, Enum):
    """汇报模式"""
    LEVEL_BY_LEVEL = "level_by_level"    # 逐级汇报: L1→L2→L3→...→L7
    CROSS_LEVEL = "cross_level"          # 跨级汇报: L1→L3→L5→L7
    EMERGENCY = "emergency"              # 紧急汇报: L1→L5→L7
    FLATTEN = "flatten"                  # 扁平汇报: 同层级平等讨论


class EscalationRecord(BaseModel):
    """升级记录"""
    escalation_id: str
    room_id: str
    plan_id: str
    version: str
    from_level: int                      # L1-L7
    to_level: int                        # L1-L7, to_level > from_level 表示向上升级
    mode: EscalationMode                  # 汇报模式
    content: dict = Field(default_factory=dict)  # {proposal, attachments, approval_status, summary}
    escalation_path: List[int] = Field(default_factory=list)  # 升级路径，如 [4,5,6,7]
    status: str = "pending"              # pending/acknowledged/in_progress/completed/rejected
    escalated_by: str                     # 操作者
    escalated_at: str
    acknowledged_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: Optional[str] = None


class EscalationRequest(BaseModel):
    """层级升级请求（05-Hierarchy-Roles.md §7.2）"""
    from_level: int = Field(..., ge=1, le=7, description="起始层级")
    to_level: int = Field(..., ge=1, le=7, description="目标层级，to_level > from_level 表示向上")
    mode: EscalationMode = Field(default=EscalationMode.LEVEL_BY_LEVEL, description="汇报模式")
    content: dict = Field(
        default_factory=dict,
        description="升级内容: {proposal, attachments, approval_status, summary}"
    )
    escalation_path: Optional[List[int]] = Field(
        default=None,
        description="指定升级路径，如不提供则自动计算"
    )
    notes: Optional[str] = None


class EscalationResponse(BaseModel):
    """升级响应"""
    escalation_id: str
    room_id: str
    plan_id: str
    version: str
    from_level: int
    to_level: int
    mode: EscalationMode
    escalation_path: List[int]
    status: str
    content: dict
    escalated_by: str
    escalated_at: str
    message: str


def _calculate_escalation_path(from_level: int, to_level: int, mode: EscalationMode) -> List[int]:
    """
    根据汇报模式计算升级路径
    来源: 05-Hierarchy-Roles.md §4.1-§4.2
    """
    if mode == EscalationMode.LEVEL_BY_LEVEL:
        # 逐级汇报: 从 from_level 向上直到 to_level
        return [l for l in range(from_level, to_level + 1)]
    elif mode == EscalationMode.CROSS_LEVEL:
        # 跨级汇报: L1→L3→L5→L7（只走奇数层，跳过偶数层）
        # 规则：from_level 总是包含，然后只走奇数层直到 to_level
        path = []
        current = from_level
        while current <= to_level:
            if current == from_level:
                # 起始层级总是包含
                path.append(current)
            elif current % 2 == 1:
                # 后续只走奇数层
                path.append(current)
            current += 1
        # 如果 to_level 是偶数且不在路径中（to_level > from_level），补上
        if to_level not in path:
            path.append(to_level)
        return path
    elif mode == EscalationMode.EMERGENCY:
        # 紧急汇报: L1→L5→L7（简化流程）
        path = [from_level]
        if from_level < 5:
            path.append(5)
        if 5 < to_level:
            path.append(to_level)
        return path
    else:  # FLATTEN
        # 扁平: 只包含起止层级
        return [from_level, to_level]


# ========================
# 问题处理模型（PROBLEM_DETECTED → RESUMING 流程）
# ========================

class ProblemType(str, Enum):
    """问题类型分类"""
    BLOCKING = "blocking"       # 执行阻塞
    BUG = "bug"                # 方案缺陷
    ENHANCEMENT = "enhancement" # 功能增强
    RISK = "risk"              # 发现风险
    DEPENDENCY = "dependency"   # 依赖变更


class ProblemSeverity(str, Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProblemRecord(BaseModel):
    """问题记录"""
    issue_id: str
    plan_id: str
    room_id: str
    version: str
    type: ProblemType
    title: str
    description: str
    severity: ProblemSeverity
    detected_by: str
    detected_at: str
    affected_tasks: List[int] = Field(default_factory=list)
    progress_delay: int = 0
    related_context: dict = Field(default_factory=dict)


class ProblemAnalysisResult(BaseModel):
    """问题分析结果"""
    issue_id: str
    root_cause: str
    root_cause_confidence: float = Field(ge=0.0, le=1.0)
    impact_scope: str = "局部"  # 局部/全局
    affected_tasks: List[int] = Field(default_factory=list)
    progress_impact: str = "未知"
    severity_reassessment: ProblemSeverity
    solution_options: List[dict] = Field(default_factory=list)
    recommended_option: int = 0
    requires_discussion: bool = False
    discussion_needed_aspects: List[str] = Field(default_factory=list)


class ProblemDiscussionRecord(BaseModel):
    """问题讨论记录"""
    issue_id: str
    participants: List[str] = Field(default_factory=list)
    discussion_focus: List[str] = Field(default_factory=list)
    proposed_solutions: List[dict] = Field(default_factory=list)
    votes: dict = Field(default_factory=dict)
    final_recommendation: str = ""


class PlanUpdateRecord(BaseModel):
    """方案更新记录"""
    plan_id: str
    new_version: str
    parent_version: str
    update_type: str = "fix"  # fix/enhancement/dependency
    description: str
    changes: dict = Field(default_factory=dict)
    task_updates: List[dict] = Field(default_factory=list)
    new_tasks: List[dict] = Field(default_factory=list)
    cancelled_tasks: List[int] = Field(default_factory=list)


class ResumingRecord(BaseModel):
    """恢复执行记录"""
    plan_id: str
    new_version: str
    resuming_from_task: int
    checkpoint: str
    resume_instructions: dict = Field(default_factory=dict)


# ========================
# DEBATE 阶段数据模型（07-State-Machine-Details.md §2.5）
# ========================


class DebatePosition(str, Enum):
    """辩论立场"""
    AGREE = "agree"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"


class DebatePointRecord(BaseModel):
    """辩论议题点"""
    point_id: str
    content: str  # 议题描述
    created_by: str
    created_at: str
    positions: dict = Field(default_factory=dict)  # agent_id -> DebatePosition
    arguments: dict = Field(default_factory=dict)  # agent_id -> str (论证内容)


class DebateExchangeRecord(BaseModel):
    """辩论交锋记录"""
    exchange_id: str
    type: str  # challenge | response | evidence | update_position | consensus_building
    from_agent: str
    target_agent: Optional[str] = None  # None 表示对全体
    content: str
    timestamp: str


def calculate_consensus(debate_state: dict) -> float:
    """
    计算共识度
    公式: consensus_score = 1 - (disputed_points / total_points)
    来源: 07-State-Machine-Details.md §2.5 共识度计算
    """
    converged = debate_state.get("converged_points", [])
    disputed = debate_state.get("disputed_points", [])
    total = len(converged) + len(disputed)
    if total == 0:
        return 0.0
    return 1.0 - (len(disputed) / total)


def init_debate_state(room_id: str) -> dict:
    """初始化辩论状态（当 room 进入 DEBATE 阶段时调用）"""
    now = datetime.now().isoformat()
    state = {
        "room_id": room_id,
        "round": 0,
        "max_rounds": 10,  # 默认最大轮次（07-State-Machine-Details.md §2.5）
        "consensus_score": 0.0,
        "converged_points": [],  # 已共识点: [{"point": str, "agreed_by": [str]}]
        "disputed_points": [],   # 分歧点: [{"point": str, "supporters": [], "opposers": [], "arguments": {}}]
        "recent_exchanges": [],  # 最近交锋
        "all_points": [],       # 所有议题点: list[DebatePointRecord]
        "started_at": now,
        "last_updated": now,
    }
    _debate_states[room_id] = state
    return state


def get_debate_state(room_id: str) -> Optional[dict]:
    """获取辩论状态"""
    return _debate_states.get(room_id)


def add_debate_point(room_id: str, content: str, created_by: str) -> DebatePointRecord:
    """添加一个新的辩论议题点"""
    if room_id not in _debate_states:
        init_debate_state(room_id)
    state = _debate_states[room_id]
    point_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    point = DebatePointRecord(
        point_id=point_id,
        content=content,
        created_by=created_by,
        created_at=now,
        positions={},
        arguments={},
    )
    state["all_points"].append(point.model_dump())
    state["last_updated"] = now
    return point


def submit_position(room_id: str, point_id: str, agent_id: str,
                   position: DebatePosition, argument: Optional[str] = None) -> dict:
    """
    提交对某个议题点的立场
    自动重新计算共识度
    """
    if room_id not in _debate_states:
        init_debate_state(room_id)
    state = _debate_states[room_id]

    # 找到议题点
    point = None
    for p in state["all_points"]:
        if p["point_id"] == point_id:
            point = p
            break
    if not point:
        raise ValueError(f"Point {point_id} not found")

    point["positions"][agent_id] = position.value
    if argument:
        point["arguments"][agent_id] = argument

    # 重新评估该点是否已收敛或仍有分歧
    positions = list(point["positions"].values())
    if len(positions) >= 2:
        # 检查是否全同意或全反对
        unique_positions = set(positions)
        if unique_positions == {DebatePosition.AGREE.value}:
            # 已收敛为共识点
            if not any(cp["point"] == point["content"] for cp in state["converged_points"]):
                state["converged_points"].append({
                    "point": point["content"],
                    "agreed_by": [a for a, p in point["positions"].items() if p == DebatePosition.AGREE.value],
                })
            # 从分歧点移除
            state["disputed_points"] = [
                dp for dp in state["disputed_points"] if dp["point"] != point["content"]
            ]
        elif DebatePosition.OPPOSE.value in positions and DebatePosition.AGREE.value in positions:
            # 存在分歧
            if not any(dp["point"] == point["content"] for dp in state["disputed_points"]):
                state["disputed_points"].append({
                    "point": point["content"],
                    "supporters": [a for a, p in point["positions"].items() if p == DebatePosition.AGREE.value],
                    "opposers": [a for a, p in point["positions"].items() if p == DebatePosition.OPPOSE.value],
                    "arguments": point.get("arguments", {}),
                })

    # 重新计算共识度
    state["consensus_score"] = calculate_consensus(state)
    state["last_updated"] = datetime.now().isoformat()

    return {
        "point_id": point_id,
        "agent_id": agent_id,
        "position": position.value,
        "consensus_score": state["consensus_score"],
        "converged_count": len(state["converged_points"]),
        "disputed_count": len(state["disputed_points"]),
    }


def add_exchange(room_id: str, exchange_type: str, from_agent: str,
                 content: str, target_agent: Optional[str] = None) -> DebateExchangeRecord:
    """记录一次辩论交锋"""
    if room_id not in _debate_states:
        init_debate_state(room_id)
    state = _debate_states[room_id]
    now = datetime.now().isoformat()
    exchange = DebateExchangeRecord(
        exchange_id=str(uuid.uuid4()),
        type=exchange_type,
        from_agent=from_agent,
        target_agent=target_agent,
        content=content,
        timestamp=now,
    )
    state["recent_exchanges"].append(exchange.model_dump())
    # 只保留最近20条
    if len(state["recent_exchanges"]) > 20:
        state["recent_exchanges"] = state["recent_exchanges"][-20:]
    state["last_updated"] = now
    return exchange


def advance_debate_round(room_id: str) -> int:
    """推进辩论轮次"""
    if room_id not in _debate_states:
        return 0
    state = _debate_states[room_id]
    state["round"] += 1
    state["last_updated"] = datetime.now().isoformat()
    return state["round"]


# ========================
# DEBATE 阶段内存存储
# ========================

_debate_states: dict = {}  # room_id -> debate state


# ========================
# 问题处理内存存储
# ========================

_problems: dict = {}  # issue_id -> ProblemRecord
_problem_analyses: dict = {}  # issue_id -> ProblemAnalysisResult
_problem_discussions: dict = {}  # issue_id -> ProblemDiscussionRecord
_plan_updates: dict = {}  # plan_id -> PlanUpdateRecord
_resuming_records: dict = {}  # plan_id -> ResumingRecord
_active_issue_id: Optional[str] = None  # 当前正在处理的问题ID


# ========================
# 审批流内存存储
# ========================

_approval_flows: dict = {}  # plan_id -> { levels: {1: {}, 2: {}, ...}, current_level: int, status: str }
_approval_history: dict = {}  # plan_id -> list[ApprovalActionRecord]

# ========================
# 层级汇报/升级存储（05-Hierarchy-Roles.md §7.2）
# ========================

_escalations: dict = {}  # escalation_id -> EscalationRecord
_room_escalations: dict = {}  # room_id -> list[escalation_id]
_plan_escalations: dict = {}  # plan_id -> list[escalation_id]


# ========================
# Step 31: Activity Audit Log
# ========================

class ActivityType(str, Enum):
    """活动类型枚举"""
    # Plan actions
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"
    PLAN_APPROVED = "plan.approved"
    PLAN_REJECTED = "plan.rejected"
    PLAN_DRAFT = "plan.draft"
    # Room actions
    ROOM_CREATED = "room.created"
    ROOM_PHASE_CHANGED = "room.phase_changed"
    ROOM_CONCLUDED = "room.concluded"
    # Participant actions
    PARTICIPANT_JOINED = "participant.joined"
    PARTICIPANT_LEFT = "participant.left"
    # Task actions
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_COMPLETED = "task.completed"
    TASK_PROGRESS_UPDATED = "task.progress_updated"
    # Decision actions
    DECISION_CREATED = "decision.created"
    DECISION_UPDATED = "decision.updated"
    # Edict actions
    EDICT_ISSUED = "edict.issued"
    EDICT_REVOKED = "edict.revoked"
    # Problem actions
    PROBLEM_REPORTED = "problem.reported"
    PROBLEM_ANALYZED = "problem.analyzed"
    PROBLEM_DISCUSSED = "problem.discussed"
    PROBLEM_RESOLVED = "problem.resolved"
    # Approval actions
    APPROVAL_STARTED = "approval.started"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_ESCALATED = "approval.escalated"
    APPROVAL_DELEGATED = "approval.delegated"
    # Escalation actions
    ESCALATION_TRIGGERED = "escalation.triggered"
    # Risk/Constraint/Stakeholder actions
    RISK_CREATED = "risk.created"
    RISK_UPDATED = "risk.updated"
    CONSTRAINT_CREATED = "constraint.created"
    CONSTRAINT_UPDATED = "constraint.updated"
    STAKEHOLDER_CREATED = "stakeholder.created"
    STAKEHOLDER_UPDATED = "stakeholder.updated"
    # SubTask actions
    SUBTASK_CREATED = "subtask.created"
    SUBTASK_UPDATED = "subtask.updated"
    SUBTASK_DELETED = "subtask.deleted"


_activities: dict = {}  # activity_id -> activity record
_activity_index: dict = {}  # plan_id -> list[activity_id]


class ActivityCreate(BaseModel):
    """创建活动日志的请求模型"""
    plan_id: str
    version: Optional[str] = None
    room_id: Optional[str] = None
    action_type: ActivityType
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ActivityResponse(BaseModel):
    """活动日志响应"""
    activity_id: str
    plan_id: str
    version: Optional[str] = None
    room_id: Optional[str] = None
    action_type: str
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: str


def _build_activity_id() -> str:
    """生成活动ID"""
    return str(uuid.uuid4())


async def log_activity(
    plan_id: str,
    action_type: ActivityType,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    version: Optional[str] = None,
    room_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_label: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """记录活动日志（DB优先，内存兜底）"""
    activity_id = _build_activity_id()
    occurred_at = datetime.now().isoformat()

    # 内存记录
    record = {
        "activity_id": activity_id,
        "plan_id": plan_id,
        "version": version,
        "room_id": room_id,
        "action_type": action_type.value,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "target_type": target_type,
        "target_id": target_id,
        "target_label": target_label,
        "details": details or {},
        "occurred_at": occurred_at,
    }
    _activities[activity_id] = record
    if plan_id not in _activity_index:
        _activity_index[plan_id] = []
    _activity_index[plan_id].append(activity_id)
    if room_id:
        if room_id not in _activity_index:
            _activity_index[room_id] = []
        _activity_index[room_id].append(activity_id)

    # DB写入
    if _db_active:
        try:
            await crud.create_activity(
                activity_id=activity_id,
                plan_id=plan_id,
                version=version,
                room_id=room_id,
                action_type=action_type.value,
                actor_id=actor_id,
                actor_name=actor_name,
                target_type=target_type,
                target_id=target_id,
                target_label=target_label,
                details=details,
            )
        except Exception as e:
            logger.warning(f"[DB] log_activity 失败: {e}")


def build_approval_chain(skip_levels: List[int] = None) -> dict:
    """构建审批链：L7→L6→...→L1（或按配置跳过）"""
    skip = skip_levels or []
    chain = {}
    for lvl in range(7, 0, -1):  # L7 到 L1
        if lvl not in skip:
            chain[lvl] = {
                "level": lvl,
                "status": "pending",
                "approver_id": None,
                "approver_name": None,
                "comment": None,
                "decided_at": None,
                "escalated_to": None,
            }
    return chain


def start_approval_flow(plan_id: str, initiator_id: str, initiator_name: str, skip_levels: List[int] = None) -> dict:
    """为计划启动审批流"""
    flow = {
        "plan_id": plan_id,
        "initiator_id": initiator_id,
        "initiator_name": initiator_name,
        "started_at": datetime.now().isoformat(),
        "current_level": 7,  # 从L7开始向下
        "status": "in_progress",
        "levels": build_approval_chain(skip_levels),
        "history": [],
        "skip_levels": skip_levels or [],
    }
    _approval_flows[plan_id] = flow
    _approval_history[plan_id] = []
    return flow


def get_approval_flow(plan_id: str) -> Optional[dict]:
    return _approval_flows.get(plan_id)


def get_approval_status(plan_id: str) -> dict:
    """获取审批状态摘要"""
    flow = _approval_flows.get(plan_id)
    if not flow:
        return {"plan_id": plan_id, "status": "not_started"}

    levels_summary = {}
    for lvl, data in flow["levels"].items():
        levels_summary[lvl] = {
            "level": lvl,
            "level_label": ApprovalLevel(lvl).label,
            "reviewer_role": ApprovalLevel(lvl).reviewer_role,
            "status": data["status"],
            "approver_name": data["approver_name"],
            "decided_at": data["decided_at"],
        }

    return {
        "plan_id": plan_id,
        "status": flow["status"],
        "current_level": flow["current_level"],
        "current_level_label": ApprovalLevel(flow["current_level"]).label,
        "started_at": flow["started_at"],
        "levels": levels_summary,
        "history": _approval_history.get(plan_id, []),
    }


def execute_approval_action(plan_id: str, level: int, action: ApprovalAction,
                             actor_id: str, actor_name: str, comment: Optional[str] = None) -> dict:
    """执行审批动作"""
    flow = _approval_flows.get(plan_id)
    if not flow:
        raise ValueError("Approval flow not found")

    if level not in flow["levels"]:
        raise ValueError(f"Level {level} not in approval chain")

    level_data = flow["levels"][level]
    now = datetime.now().isoformat()

    # 记录动作
    record = {
        "plan_id": plan_id,
        "level": level,
        "action": action.value,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "comment": comment,
        "timestamp": now,
    }
    _approval_history[plan_id].append(record)
    flow["history"].append(record)

    if action == ApprovalAction.APPROVE:
        level_data["status"] = "approved"
        level_data["approver_id"] = actor_id
        level_data["approver_name"] = actor_name
        level_data["comment"] = comment
        level_data["decided_at"] = now

        # 找下一个待审批级别
        remaining = [l for l in sorted(flow["levels"].keys(), reverse=True)
                    if flow["levels"][l]["status"] == "pending" and l < level]
        if remaining:
            flow["current_level"] = remaining[0]
        else:
            # 全部审批完成
            flow["status"] = "fully_approved"
            if plan_id in _plans:
                _plans[plan_id]["status"] = PlanStatus.APPROVED

    elif action == ApprovalAction.REJECT:
        level_data["status"] = "rejected"
        level_data["approver_id"] = actor_id
        level_data["approver_name"] = actor_name
        level_data["comment"] = comment
        level_data["decided_at"] = now
        flow["status"] = "rejected"
        if plan_id in _plans:
            _plans[plan_id]["status"] = PlanStatus.DRAFT  # 打回草稿

    elif action == ApprovalAction.RETURN:
        level_data["status"] = "returned"
        level_data["approver_id"] = actor_id
        level_data["approver_name"] = actor_name
        level_data["comment"] = comment
        level_data["decided_at"] = now
        # 退回上一个未审批的级别
        prev = [l for l in sorted(flow["levels"].keys(), reverse=True)
                if flow["levels"][l]["status"] == "pending" and l < level]
        if prev:
            flow["current_level"] = prev[0]
        else:
            flow["status"] = "returned_to_initiator"

    elif action == ApprovalAction.ESCALATE:
        # 升级到更高（L数字更小=更高）
        escalated = level - 1
        if escalated < 1:
            raise ValueError("Already at highest level, cannot escalate")
        level_data["status"] = "escalated"
        level_data["approver_id"] = actor_id
        level_data["approver_name"] = actor_name
        level_data["comment"] = comment
        level_data["decided_at"] = now
        level_data["escalated_to"] = escalated
        flow["current_level"] = escalated

    return {
        "plan_id": plan_id,
        "level": level,
        "action": action.value,
        "new_status": flow["status"],
        "new_current_level": flow["current_level"],
    }


async def _get_next_seq_for_room(room_id: str) -> int:
    """获取房间下一条消息的序号（DB优先，内存兜底）"""
    if _db_active:
        try:
            return await crud.get_next_message_sequence(room_id)
        except Exception as e:
            logger.warning(f"[DB] get_next_message_sequence 失败: {e}")
    # 内存兜底：基于已有消息计数
    return len(_messages.get(room_id, [])) + 1


# ========================
# 内存存储（起步）
# ========================

_plans: dict = {}
_rooms: dict = {}
_room_summaries: dict = {}  # room_id -> room summary for fast access
_participants: dict = {}  # room_id -> list[Participant]
_messages: dict = {}  # room_id -> list[message] (讨论历史)
_tasks: dict = {}  # (plan_id, version) -> {task_id -> Task}
_snapshots: dict = {}  # (plan_id, version, snapshot_id) -> Snapshot
_decisions: dict = {}  # (plan_id, version, decision_id) -> Decision
_task_comments: dict = {}  # (plan_id, version, task_id) -> {comment_id -> Comment}
_task_checkpoints: dict = {}  # (plan_id, version, task_id) -> {checkpoint_id -> Checkpoint}
_sub_tasks: dict = {}  # (plan_id, version, task_id) -> {sub_task_id -> SubTask}
_constraints: dict = {}  # plan_id -> [Constraint, ...]
_stakeholders: dict = {}  # plan_id -> [Stakeholder, ...]
_risks: dict = {}  # (plan_id, version) -> [Risk, ...]
_edicts: dict = {}  # (plan_id, version, edict_id) -> Edict


# ========================
# 数据库层（PostgreSQL 持久化 + 内存回退）
# ========================

_db_active = False  # PostgreSQL 是否可用

async def _init_database():
    """初始化 PostgreSQL 数据库（可选，非致命）"""
    global _db_active
    try:
        from db import init_db, close_db
        await init_db()
        _db_active = True
        logger.info("[DB] PostgreSQL 持久化已启用")
        # 从 DB 加载 plan_number 和 room_number 计数器
        await _load_number_counters()
    except Exception as e:
        _db_active = False
        logger.warning(f"[DB] PostgreSQL 初始化失败，使用内存存储: {e}")


# ========================
# Plan / Room 序号生成器
# 格式: PLAN-YYYY-NNNN, ROOM-YYYY-NNNN
# ========================

_plan_counter: int = 0
_room_counter: int = 0
_issue_counter: int = 0
_max_plan_number_year: int = 0
_max_room_number_year: int = 0
_max_issue_number_year: int = 0


async def _load_number_counters():
    """从数据库加载当前最大序号，用于生成下一个序号"""
    global _plan_counter, _room_counter, _issue_counter, _max_plan_number_year, _max_room_number_year, _max_issue_number_year
    if not _db_active:
        return
    try:
        from repositories import crud
        current_year = datetime.now().year

        # 获取当前年份最大的 plan_number
        async with crud.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT plan_number FROM plans
                WHERE plan_number IS NOT NULL
                  AND substring(plan_number from 6 for 4) = $1
                ORDER BY plan_number DESC LIMIT 1
                """,
                str(current_year)
            )
            if row and row["plan_number"]:
                parts = row["plan_number"].split("-")
                # PLAN-YYYY-NNNN → parts = ["PLAN", "YYYY", "NNNN"] → counter at parts[2]
                if len(parts) >= 3:
                    _plan_counter = int(parts[2])
                    _max_plan_number_year = current_year
            else:
                _plan_counter = 0
                _max_plan_number_year = current_year

        # 获取当前年份最大的 room_number
        async with crud.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT room_number FROM rooms
                WHERE room_number IS NOT NULL
                  AND substring(room_number from 6 for 4) = $1
                ORDER BY room_number DESC LIMIT 1
                """,
                str(current_year)
            )
            if row and row["room_number"]:
                parts = row["room_number"].split("-")
                # ROOM-YYYY-NNNN → parts = ["ROOM", "YYYY", "NNNN"] → counter at parts[2]
                if len(parts) >= 3:
                    _room_counter = int(parts[2])
                    _max_room_number_year = current_year
            else:
                _room_counter = 0
                _max_room_number_year = current_year

        # 获取当前年份最大的 issue_number
        async with crud.get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT issue_number FROM problems
                WHERE issue_number IS NOT NULL
                  AND substring(issue_number from 7 for 4) = $1
                ORDER BY issue_number DESC LIMIT 1
                """,
                str(current_year)
            )
            if row and row["issue_number"]:
                parts = row["issue_number"].split("-")
                # ISSUE-YYYY-NNNN → parts = ["ISSUE", "YYYY", "NNNN"] → counter at parts[2]
                if len(parts) >= 3:
                    _issue_counter = int(parts[2])
                    _max_issue_number_year = current_year
            else:
                _issue_counter = 0
                _max_issue_number_year = current_year

        logger.info(f"[Counter] plan={_plan_counter}, room={_room_counter}, issue={_issue_counter} (year={current_year})")
    except Exception as e:
        logger.warning(f"[Counter] 加载失败，使用默认值: {e}")
        _plan_counter = 0
        _room_counter = 0
        _issue_counter = 0
        _max_plan_number_year = datetime.now().year
        _max_room_number_year = datetime.now().year
        _max_issue_number_year = datetime.now().year


def _generate_plan_number() -> str:
    """生成下一个 PLAN-YYYY-NNNN 序号（线程安全需配合锁）"""
    global _plan_counter, _max_plan_number_year
    current_year = datetime.now().year
    if current_year != _max_plan_number_year:
        # 新年重置计数器
        _plan_counter = 0
        _max_plan_number_year = current_year
    _plan_counter += 1
    return f"PLAN-{current_year}-{_plan_counter:04d}"


def _generate_room_number() -> str:
    """生成下一个 ROOM-YYYY-NNNN 序号"""
    global _room_counter, _max_room_number_year
    current_year = datetime.now().year
    if current_year != _max_room_number_year:
        _room_counter = 0
        _max_room_number_year = current_year
    _room_counter += 1
    return f"ROOM-{current_year}-{_room_counter:04d}"


def _generate_issue_number() -> str:
    """生成下一个 ISSUE-YYYY-NNNN 序号"""
    global _issue_counter, _max_issue_number_year
    current_year = datetime.now().year
    if current_year != _max_issue_number_year:
        _issue_counter = 0
        _max_issue_number_year = current_year
    _issue_counter += 1
    return f"ISSUE-{current_year}-{_issue_counter:04d}"


# ========================
# DB ↔ 内存 同步辅助函数
# DB 写成功 → 同步到内存（WS广播 + 状态机依赖）
# ========================

def _row_to_plan(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 PostgreSQL plan row 转换为内存格式"""
    if not row:
        return None
    r = dict(row)
    # JSONB 字段反序列化
    for field in ("requirements", "versions"):
        if field in r and isinstance(r[field], str):
            r[field] = json.loads(r[field])
    return r


def _version_exists(plan: Dict[str, Any], version: str) -> bool:
    """检查 plan 中是否存在指定版本"""
    versions = plan.get("versions", [])
    if not versions:
        return False
    # versions 是 [{"version": "v1.0", ...}, ...] 格式
    if isinstance(versions[0], str):
        return version in versions
    # 版本存储为对象列表
    return any(v.get("version") == version for v in versions)


def _row_to_room(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 PostgreSQL room row 转换为内存格式"""
    if not row:
        return None
    return dict(row)


def _row_to_participant(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 PostgreSQL participant row 转换为内存格式"""
    if not row:
        return None
    return dict(row)


def _row_to_message(row: Dict[str, Any]) -> Dict[str, Any]:
    """将 PostgreSQL message row 转换为内存格式"""
    if not row:
        return None
    r = dict(row)
    if "metadata" in r and isinstance(r["metadata"], str):
        r["metadata"] = json.loads(r["metadata"])
    return r


async def _sync_plan_to_memory(plan_id: str) -> Optional[Dict[str, Any]]:
    """从 DB 同步 plan 到内存；返回内存格式或 None"""
    # Always try DB first - _db_active might be False due to startup issues
    # but data may still exist in PostgreSQL from previous sessions
    try:
        row = await crud.get_plan(plan_id)
        plan = _row_to_plan(row)
        if plan:
            _plans[plan_id] = plan
        return plan
    except Exception as e:
        logger.warning(f"[_sync_plan_to_memory] {plan_id}: {e}")
        return _plans.get(plan_id)


async def _sync_room_to_memory(room_id: str) -> Optional[Dict[str, Any]]:
    """从 DB 同步 room 到内存；DB 失败时回退到内存"""
    # Always try DB first - _db_active might be False due to startup issues
    try:
        row = await crud.get_room(room_id)
        room = _row_to_room(row)
        if room:
            _rooms[room_id] = room
        return room
    except Exception as e:
        logger.warning(f"[_sync_room_to_memory] {room_id}: {e}")
    # DB 失败时回退到内存
    return _rooms.get(room_id)


async def _sync_participants_to_memory(room_id: str) -> List[Dict[str, Any]]:
    """从 DB 同步参与者列表到内存"""
    # Always try DB first - _db_active might be False due to startup issues
    try:
        rows = await crud.get_participants(room_id)
        participants = [_row_to_participant(r) for r in rows]
        _participants[room_id] = participants
        return participants
    except Exception as e:
        logger.warning(f"[_sync_participants_to_memory] {room_id}: {e}")
        return _participants.get(room_id, [])


async def _sync_messages_to_memory(room_id: str, limit: int = 0) -> List[Dict[str, Any]]:
    """从 DB 同步消息历史到内存"""
    # Always try DB first - _db_active might be False due to startup issues
    try:
        rows = await crud.get_messages(room_id, limit=limit)
        messages = [_row_to_message(r) for r in rows]
        _messages[room_id] = messages
        return messages
    except Exception as e:
        logger.warning(f"[_sync_messages_to_memory] {room_id}: {e}")
        return _messages.get(room_id, [])


# ========================
# Task Dependency & Blocking System
# 来源: 08-Data-Models-Details.md §3.1 Task模型 blocked_by
# 来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
# ========================

def _get_task(task_id: str, plan_id: str, version: str) -> Optional[Dict[str, Any]]:
    """获取任务，支持内存和DB"""
    key = (plan_id, version)
    # Try memory first
    if key in _tasks and task_id in _tasks[key]:
        return _tasks[key][task_id]
    # Try DB
    if _db_active:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        task = loop.run_until_complete(crud.get_task(task_id))
        if task:
            return dict(task)
    return None


def _list_tasks_sync(plan_id: str, version: str) -> List[Dict[str, Any]]:
    """列出所有任务，支持内存和DB"""
    key = (plan_id, version)
    # Try memory first
    if key in _tasks and _tasks[key]:
        return list(_tasks[key].values())
    # Try DB
    if _db_active:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        tasks = loop.run_until_complete(crud.list_tasks(plan_id, version))
        return [dict(t) for t in tasks]
    return []


def _evaluate_and_update_blocked_status(task: Dict[str, Any], plan_id: str, version: str) -> Dict[str, Any]:
    """
    评估任务的blocked_by状态
    根据dependencies中各任务的完成状态，自动更新blocked_by列表
    
    逻辑：
    - 遍历dependencies中的每个任务ID
    - 如果依赖任务未完成（非completed），则加入blocked_by
    - 如果依赖任务已完成，则不加入blocked_by
    - 如果blocked_by为空且状态为blocked，改为pending
    """
    # 兼容DB存储的JSON字符串格式
    dependencies = task.get("dependencies", [])
    if isinstance(dependencies, str):
        import json as _json
        try:
            dependencies = _json.loads(dependencies)
        except Exception:
            dependencies = []
    if not dependencies:
        # 无依赖，移除所有blocked_by
        if task.get("blocked_by"):
            task["blocked_by"] = []
        return task
    
    all_tasks = {t["task_id"]: t for t in _list_tasks_sync(plan_id, version)}
    new_blocked_by = []
    logger.warning(f"[DEBUG] _evaluate_and_update_blocked_status: task_id={task.get('task_id')}, dependencies={dependencies}, all_tasks keys={list(all_tasks.keys())}")
    
    for dep_id in dependencies:
        # 兼容字符串UUID和UUID对象的混合查找
        lookup_key = dep_id
        if dep_id not in all_tasks and isinstance(dep_id, str):
            try:
                import uuid
                lookup_key = uuid.UUID(dep_id)
            except Exception:
                pass
        dep_task = all_tasks.get(lookup_key)
        logger.warning(f"[DEBUG] dep_id={dep_id}, lookup_key={lookup_key}, dep_task={dep_task}")
        if dep_task is None:
            # 依赖任务不存在，跳过
            logger.warning(f"[DEBUG] dep_task is None, skipping")
            continue
        if dep_task.get("status") != "completed":
            # 依赖任务未完成，加入blocked_by
            if dep_id not in new_blocked_by:
                new_blocked_by.append(dep_id)
                logger.warning(f"[DEBUG] added {dep_id} to new_blocked_by")
    
    task["blocked_by"] = new_blocked_by
    
    # 如果blocked_by不为空且状态不是completed，设为blocked
    if new_blocked_by and task.get("status") != "completed":
        task["status"] = "blocked"
        logger.warning(f"[DEBUG] set task status to blocked")
    
    # 如果blocked_by为空且状态为blocked，改为pending
    if not new_blocked_by and task.get("status") == "blocked":
        task["status"] = "pending"
    
    logger.warning(f"[DEBUG] returning task: task_id={task.get('task_id')}, status={task.get('status')}, blocked_by={task.get('blocked_by')}")
    return task


async def _on_task_completed(completed_task_id: str, plan_id: str, version: str) -> List[Dict[str, Any]]:
    """
    当任务完成时调用，更新所有依赖此任务的任务的blocked_by状态
    
    返回：被影响的任务列表
    """
    affected_tasks = []
    all_tasks = _list_tasks_sync(plan_id, version)
    
    for task in all_tasks:
        # 兼容DB存储的JSON字符串格式
        dependencies = task.get("dependencies", [])
        if isinstance(dependencies, str):
            import json as _json
            try:
                dependencies = _json.loads(dependencies)
            except Exception:
                dependencies = []
        if completed_task_id not in dependencies:
            continue
        
        # 此任务依赖于完成的任务
        blocked_by = task.get("blocked_by", [])
        if completed_task_id in blocked_by:
            blocked_by.remove(completed_task_id)
            task["blocked_by"] = blocked_by
            
            # 如果blocked_by为空且状态为blocked，改为pending
            if not blocked_by and task.get("status") == "blocked":
                task["status"] = "pending"
            
            # 同步到内存
            key = (plan_id, version)
            if key in _tasks and task["task_id"] in _tasks[key]:
                _tasks[key][task["task_id"]] = task
            else:
                _tasks.setdefault(key, {})
                _tasks[key][task["task_id"]] = task
            
            # 同步到DB（异步）
            if _db_active:
                try:
                    await crud.update_task(task["task_id"], blocked_by=blocked_by, status=task["status"])
                except Exception as e:
                    logger.warning(f"[DB] _on_task_completed: update_task failed: {e}")
            
            affected_tasks.append({
                "task_id": task["task_id"],
                "title": task.get("title"),
                "blocked_by": task["blocked_by"],
                "status": task["status"],
                "unblocked": len(blocked_by) == 0,
            })
    
    return affected_tasks


def _validate_dependencies(dependencies: List[str], plan_id: str, version: str) -> Dict[str, Any]:
    """
    验证依赖列表的有效性
    - 检查循环依赖
    - 检查依赖任务是否存在
    - 检查依赖任务是否属于同一plan/version
    
    返回: {"valid": bool, "errors": List[str], "warnings": List[str]}
    """
    errors = []
    warnings = []
    
    if not dependencies:
        return {"valid": True, "errors": [], "warnings": []}
    
    all_tasks = {t["task_id"]: t for t in _list_tasks_sync(plan_id, version)}
    logger.warning(f"[DEBUG] _validate_dependencies: dependencies={dependencies}, all_tasks keys={list(all_tasks.keys())}")
    
    for dep_id in dependencies:
        # 兼容字符串UUID和UUID对象的混合查找
        lookup_key = dep_id
        if dep_id not in all_tasks and isinstance(dep_id, str):
            try:
                import uuid
                lookup_key = uuid.UUID(dep_id)
            except Exception:
                pass
        logger.warning(f"[DEBUG] dep_id={dep_id}, lookup_key={lookup_key}, in_all_tasks={lookup_key in all_tasks}")
        if lookup_key not in all_tasks:
            errors.append(f"依赖任务不存在: {dep_id}")
            continue
        
        dep_task = all_tasks[lookup_key]
        # 兼容UUID和字符串比较
        dep_plan_id = str(dep_task.get("plan_id")) if dep_task.get("plan_id") else None
        dep_version = str(dep_task.get("version")) if dep_task.get("version") else None
        if dep_plan_id != str(plan_id) or dep_version != str(version):
            errors.append(f"依赖任务不属于同一版本: {dep_id}")
    
    # 检查循环依赖
    def has_circular(task_id: str, visited: set, chain: list) -> bool:
        if task_id in chain:
            return True
        if task_id in visited:
            return False
        visited.add(task_id)
        chain.append(task_id)
        task = all_tasks.get(task_id)
        if task:
            for dep_id in task.get("dependencies", []):
                if has_circular(dep_id, visited, chain.copy()):
                    return True
        return False
    
    for dep_id in dependencies:
        if has_circular(dep_id, set(), []):
            errors.append(f"检测到循环依赖: {dep_id}")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ========================
# FastAPI 应用
# ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agora-V2 启动")
    # 初始化 PostgreSQL（可选）
    await _init_database()
    app.state.db_active = _db_active

    # 启动 OpenCLAW Gateway 客户端
    gateway_url = os.getenv("OPENCLAW_GATEWAY_URL", "ws://host.docker.internal:18789")
    agora_api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
    try:
        gateway = await init_gateway_client(gateway_url, agora_api_url)
        gateway.on_message = lambda msg: _handle_gateway_message(msg, app)
        app.state.gateway = gateway
        logger.info(f"OpenCLAW Gateway 客户端已连接: {gateway_url}")
    except Exception as e:
        logger.warning(f"OpenCLAW Gateway 连接失败（非致命）: {e}")
        app.state.gateway = None

    yield

    # 关闭 Gateway 客户端
    gateway = app.state.gateway
    if gateway:
        await gateway.stop()
    # 关闭数据库连接
    if _db_active:
        try:
            from db import close_db
            await close_db()
        except Exception:
            pass
    logger.info("Agora-V2 关闭")


async def _handle_gateway_message(msg: dict, app: FastAPI):
    """
    处理来自 OpenCLAW Gateway 的消息
    将外部 Agent 的发言/操作注入到 Agora Room 的 WebSocket 广播
    """
    import logging
    logger = logging.getLogger("gateway_handler")

    room_id = msg.get("room_id")
    if not room_id or room_id not in _rooms:
        return

    msg_type = msg.get("message_type", "")
    payload = msg.get("payload", {})

    if msg_type == "agent_speech":
        # 外部 Agent 的发言 → 注入房间广播
        speech_msg = {
            "type": "gateway_speech",
            "message_id": str(uuid.uuid4()),
            "room_id": room_id,
            "agent_id": payload.get("agent_id", "gateway-agent"),
            "content": payload.get("content", ""),
            "source": "gateway",
            "timestamp": datetime.now().isoformat(),
        }
        await ws_manager.broadcast(room_id, speech_msg)
        logger.info(f"[Gateway→Room] 外部Agent发言 room={room_id}: {payload.get('content', '')[:50]}")

    elif msg_type == "gateway_agent_join_request":
        # 外部 Agent 请求加入 → 自动批准并加入
        agent_info = payload
        p = {
            "participant_id": str(uuid.uuid4()),
            "agent_id": agent_info.get("agent_id", f"gw-{uuid.uuid4().hex[:8]}"),
            "name": agent_info.get("name", "Gateway Agent"),
            "level": agent_info.get("level", 5),
            "role": "Gateway Agent",
            "joined_at": datetime.now().isoformat(),
            "is_active": True,
            "source": "gateway",
        }
        if room_id not in _participants:
            _participants[room_id] = []
        _participants[room_id].append(p)

        # 持久化加入事件
        if room_id not in _messages:
            _messages[room_id] = []
        seq = await _get_next_seq_for_room(room_id)
        _messages[room_id].append({
            "message_id": str(uuid.uuid4()),
            "room_id": room_id,
            "type": "participant_joined",
            "participant": p,
            "source": "gateway",
            "timestamp": datetime.now().isoformat(),
            "sequence": seq,
        })

        await ws_manager.broadcast(room_id, {
            "type": "participant_joined",
            "participant": p,
        })
        logger.info(f"[Gateway→Room] Agent加入 room={room_id}: {p['name']}")

    elif msg_type == "gateway_agent_leave":
        agent_id = payload.get("agent_id")
        if room_id in _participants:
            _participants[room_id] = [
                x for x in _participants[room_id] if x.get("agent_id") != agent_id
            ]

        # 持久化离开事件
        if room_id not in _messages:
            _messages[room_id] = []
        seq = await _get_next_seq_for_room(room_id)
        _messages[room_id].append({
            "message_id": str(uuid.uuid4()),
            "room_id": room_id,
            "type": "participant_left",
            "agent_id": agent_id,
            "source": "gateway",
            "timestamp": datetime.now().isoformat(),
            "sequence": seq,
        })

        await ws_manager.broadcast(room_id, {
            "type": "participant_left",
            "agent_id": agent_id,
        })
        logger.info(f"[Gateway→Room] Agent离开 room={room_id}: {agent_id}")


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


# ========================
# 状态机规则
# ========================

# 合法的 phase 转换映射
PHASE_TRANSITIONS: dict = {
    RoomPhase.INITIATED: [RoomPhase.SELECTING],
    RoomPhase.SELECTING: [RoomPhase.THINKING],
    RoomPhase.THINKING: [RoomPhase.SHARING],
    RoomPhase.SHARING: [RoomPhase.DEBATE, RoomPhase.CONVERGING],
    RoomPhase.DEBATE: [RoomPhase.CONVERGING, RoomPhase.SHARING],
    RoomPhase.CONVERGING: [RoomPhase.HIERARCHICAL_REVIEW, RoomPhase.DECISION],
    RoomPhase.HIERARCHICAL_REVIEW: [RoomPhase.DECISION, RoomPhase.PROBLEM_DETECTED],
    RoomPhase.DECISION: [RoomPhase.EXECUTING, RoomPhase.PROBLEM_DETECTED],
    RoomPhase.EXECUTING: [RoomPhase.COMPLETED, RoomPhase.PROBLEM_DETECTED],
    RoomPhase.COMPLETED: [],
    # 问题处理流程: PROBLEM_DETECTED → PROBLEM_ANALYSIS → PROBLEM_DISCUSSION → PLAN_UPDATE → RESUMING → EXECUTING
    RoomPhase.PROBLEM_DETECTED: [RoomPhase.PROBLEM_ANALYSIS],
    RoomPhase.PROBLEM_ANALYSIS: [RoomPhase.PROBLEM_DISCUSSION, RoomPhase.PLAN_UPDATE],
    RoomPhase.PROBLEM_DISCUSSION: [RoomPhase.PLAN_UPDATE],
    RoomPhase.PLAN_UPDATE: [RoomPhase.RESUMING],
    RoomPhase.RESUMING: [RoomPhase.EXECUTING],
}


def can_transition(from_phase: RoomPhase, to_phase: RoomPhase) -> bool:
    """检查 phase 转换是否合法"""
    allowed = PHASE_TRANSITIONS.get(from_phase, [])
    return to_phase in allowed


def get_next_phases(current: RoomPhase) -> list:
    """获取当前 phase 的所有合法下一 phase"""
    return [p.value for p in PHASE_TRANSITIONS.get(current, [])]


ws_manager = ConnectionManager()


# ========================
# HTTP 端点
# ========================

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


def _is_duplicate_key_error(e: Exception, constraint_name: str) -> bool:
    """检测异常是否为指定约束的重复键错误"""
    err_str = str(e).lower()
    return "duplicate key" in err_str and constraint_name.lower() in err_str


@app.post("/plans", status_code=201)
async def create_plan(data: PlanCreate):
    """
    创建 Plan + 自动创建配套 Room
    写入路径：PostgreSQL（优先）→ 内存兜底
    来源: 08-Data-Models-Details.md §2.1 Plan.plan_number, §4.1 Room.room_number
    """
    plan_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    plan_number = _generate_plan_number()
    room_number = _generate_room_number()

    plan = {
        "plan_id": plan_id,
        "plan_number": plan_number,
        "title": data.title,
        "topic": data.topic,
        "requirements": data.requirements,
        "status": PlanStatus.INITIATED,
        "hierarchy_id": data.hierarchy_id,
        "created_at": now,
        "current_version": "v1.0",
        "versions": ["v1.0"],
    }

    # 自动创建讨论室
    room_id = str(uuid.uuid4())
    room = {
        "room_id": room_id,
        "room_number": room_number,
        "plan_id": plan_id,
        "topic": data.topic,
        "phase": RoomPhase.SELECTING,
        "coordinator_id": "coordinator",
        "current_version": "v1.0",
        "purpose": data.purpose.value,
        "mode": data.mode.value,
        "created_at": now,
    }

    # PostgreSQL 优先写入（双重写入）+ 并发安全重试
    if _db_active:
        db_success = False
        for attempt in range(10):
            try:
                await crud.create_plan(
                    plan_id=plan_id,
                    plan_number=plan_number,
                    title=data.title,
                    topic=data.topic,
                    requirements=data.requirements,
                    hierarchy_id=data.hierarchy_id or "default",
                    current_version="v1.0",
                )
                await crud.create_room(
                    room_id=room_id,
                    room_number=room_number,
                    plan_id=plan_id,
                    topic=data.topic,
                    coordinator_id="coordinator",
                    phase=RoomPhase.SELECTING.value,
                    current_version="v1.0",
                    purpose=data.purpose.value,
                    mode=data.mode.value,
                )
                logger.info(f"[DB] create_plan: plan={plan_id}({plan_number}), room={room_id}({room_number})")
                db_success = True
                break
            except Exception as e:
                if _is_duplicate_key_error(e, "plans_plan_number_key"):
                    # 序号冲突，递增后重试
                    plan_number = _generate_plan_number()
                    plan["plan_number"] = plan_number
                    room_number = _generate_room_number()
                    room["room_number"] = room_number
                    logger.warning(f"[DB] plan_number 冲突 ({plan_number})，重试 ({attempt + 1})")
                    continue
                elif _is_duplicate_key_error(e, "rooms_room_number_key"):
                    room_number = _generate_room_number()
                    room["room_number"] = room_number
                    logger.warning(f"[DB] room_number 冲突 ({room_number})，重试 ({attempt + 1})")
                    continue
                else:
                    # 非序号冲突的其他错误，降级内存
                    logger.warning(f"[DB] create_plan 失败，使用内存存储: {e}")
                    break
        if not db_success and attempt >= 9:
            logger.warning(f"[DB] create_plan 重试10次均失败，使用内存存储")

    # 内存写入（WS广播 + 状态机依赖）
    _plans[plan_id] = plan
    _rooms[room_id] = room
    _participants[room_id] = []
    _messages[room_id] = []

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.PLAN_CREATED,
        actor_id=None,
        actor_name="system",
        target_type="plan",
        target_id=plan_id,
        target_label=plan_number,
        details={"title": data.title, "topic": data.topic, "room_id": room_id},
    )

    # 向 OpenCLAW Gateway 注册房间（外部 Agent 可发现并加入）
    # 非致命：Gateway不可用时不影响核心流程
    try:
        gateway = get_gateway_client()
        if gateway:
            await gateway.register_room(room_id, data.topic, plan_id)
    except Exception as e:
        import logging
        logging.getLogger("agora").warning(f"Gateway注册失败（不影响核心流程）: {e}")

    return {"plan": plan, "room": room}


@app.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    """
    读取 Plan（PostgreSQL 优先，内存回退）
    """
    # PostgreSQL 优先读取
    if _db_active:
        try:
            row = await crud.get_plan(plan_id)
            if row:
                plan = _row_to_plan(row)
                _plans[plan_id] = plan  # sync to memory
                return plan
        except Exception as e:
            logger.warning(f"[DB] get_plan {plan_id}: {e}")

    # 内存回退
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plans[plan_id]


@app.get("/plans")
async def list_plans():
    """
    列出所有 Plan（PostgreSQL 优先，内存回退）
    """
    if _db_active:
        try:
            rows = await crud.list_plans()
            plans = [_row_to_plan(r) for r in rows]
            # 同步到内存
            for p in plans:
                if p:
                    _plans[p["plan_id"]] = p
            return plans
        except Exception as e:
            logger.warning(f"[DB] list_plans: {e}")

    return list(_plans.values())


# ========================
# Requirements API
# ========================

async def _get_plan_requirements(plan_id: str) -> List[Dict[str, Any]]:
    """从 plans 表的 requirements JSONB 字段读取需求列表（异步）"""
    # PostgreSQL 优先：始终尝试从 DB 读取（即使 _db_active=False，requirements 仍可能已写入 DB）
    if _db_active:
        try:
            row = await crud.get_plan(plan_id)
            if row:
                reqs = row.get("requirements", [])
                # asyncpg 对 JSONB 的反序列化可能返回 str 或 list，统一处理
                if isinstance(reqs, str):
                    reqs = json.loads(reqs)
                return reqs if isinstance(reqs, list) else []
        except Exception as e:
            logger.warning(f"[DB] _get_plan_requirements {plan_id}: {e}")
    # 内存回退（_db_active=False 时仍尝试 DB 读取，见上文）
    try:
        row = await crud.get_plan(plan_id)
        if row:
            reqs = row.get("requirements", [])
            if isinstance(reqs, str):
                reqs = json.loads(reqs)
            return reqs if isinstance(reqs, list) else []
    except Exception:
        pass
    # 最终回退到内存
    plan = _plans.get(plan_id, {})
    reqs = plan.get("requirements", [])
    return reqs if isinstance(reqs, list) else []


async def _save_plan_requirements(plan_id: str, requirements: List[Dict[str, Any]]) -> None:
    """保存需求列表到 plans.requirements JSONB 字段（异步）"""
    # PostgreSQL 优先
    if _db_active:
        try:
            await crud.update_plan(plan_id, requirements=requirements)
        except Exception as e:
            logger.warning(f"[DB] _save_plan_requirements {plan_id}: {e}")
    # 内存回退
    if plan_id in _plans:
        _plans[plan_id]["requirements"] = requirements
        _plans[plan_id]["updated_at"] = datetime.now().isoformat()


async def _get_version_metrics(plan_id: str, version: str) -> Dict[str, Any]:
    """获取版本指标（用于 version plan.json）"""
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        return {}

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        return {}

    # 尝试从 DB 获取 metrics
    if _db_active:
        try:
            metrics = await crud.get_task_metrics(plan_id, version)
            return metrics if metrics else {}
        except Exception as e:
            logger.warning(f"[DB] _get_version_metrics failed: {e}")

    # 内存兜底
    key = (plan_id, version)
    tasks = list(_tasks.get(key, {}).values())
    if not tasks:
        return {
            "total": 0, "completed": 0, "blocked": 0,
            "total_estimated_hours": 0, "total_actual_hours": 0,
            "progress_percentage": 0.0,
        }

    from collections import Counter
    status_counts = Counter(t.get("status", "pending") for t in tasks)
    total_est = sum(t.get("estimated_hours") or 0 for t in tasks)
    total_act = sum(t.get("actual_hours") or 0 for t in tasks)
    completed_count = status_counts.get("completed", 0)
    total_count = len(tasks)
    progress_pct = (completed_count / total_count * 100) if total_count > 0 else 0.0

    return {
        "total": total_count,
        "completed": completed_count,
        "blocked": status_counts.get("blocked", 0),
        "total_estimated_hours": total_est,
        "total_actual_hours": total_act,
        "progress_percentage": round(progress_pct, 2),
    }


@app.post("/plans/{plan_id}/requirements", status_code=201)
async def create_requirement(plan_id: str, data: RequirementCreate):
    """
    添加需求到 Plan
    POST /plans/{plan_id}/requirements
    来源: 08-Data-Models-Details.md §2.1 Plan.requirements
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="PLAN_NOT_FOUND")

    requirements = await _get_plan_requirements(plan_id)
    new_req = {
        "id": str(uuid.uuid4()),
        "description": data.description,
        "priority": data.priority.value,
        "category": data.category.value,
        "status": data.status.value,
        "notes": data.notes or "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    requirements.append(new_req)
    await _save_plan_requirements(plan_id, requirements)
    return new_req


@app.get("/plans/{plan_id}/requirements")
async def list_requirements(plan_id: str):
    """
    列出 Plan 的所有需求
    GET /plans/{plan_id}/requirements
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="PLAN_NOT_FOUND")
    return await _get_plan_requirements(plan_id)


@app.get("/plans/{plan_id}/requirements/stats")
async def get_requirements_stats(plan_id: str):
    """
    需求统计（按状态/优先级/分类统计）
    GET /plans/{plan_id}/requirements/stats
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="PLAN_NOT_FOUND")
    requirements = await _get_plan_requirements(plan_id)
    stats = {
        "total": len(requirements),
        "by_status": {},
        "by_priority": {},
        "by_category": {},
    }
    for req in requirements:
        s = req.get("status", "pending")
        p = req.get("priority", "medium")
        c = req.get("category", "other")
        stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
        stats["by_priority"][p] = stats["by_priority"].get(p, 0) + 1
        stats["by_category"][c] = stats["by_category"].get(c, 0) + 1
    return stats


@app.get("/plans/{plan_id}/requirements/{req_id}")
async def get_requirement(plan_id: str, req_id: str):
    """
    获取单个需求详情
    GET /plans/{plan_id}/requirements/{req_id}
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="PLAN_NOT_FOUND")
    requirements = await _get_plan_requirements(plan_id)
    for req in requirements:
        if req.get("id") == req_id:
            return req
    raise HTTPException(status_code=404, detail="REQUIREMENT_NOT_FOUND")


@app.patch("/plans/{plan_id}/requirements/{req_id}")
async def update_requirement(plan_id: str, req_id: str, data: RequirementUpdate):
    """
    更新需求字段
    PATCH /plans/{plan_id}/requirements/{req_id}
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="PLAN_NOT_FOUND")
    requirements = await _get_plan_requirements(plan_id)
    for i, req in enumerate(requirements):
        if req.get("id") == req_id:
            if data.description is not None:
                req["description"] = data.description
            if data.priority is not None:
                req["priority"] = data.priority.value
            if data.category is not None:
                req["category"] = data.category.value
            if data.status is not None:
                req["status"] = data.status.value
            if data.notes is not None:
                req["notes"] = data.notes
            req["updated_at"] = datetime.now().isoformat()
            requirements[i] = req
            await _save_plan_requirements(plan_id, requirements)
            return req
    raise HTTPException(status_code=404, detail="REQUIREMENT_NOT_FOUND")


@app.delete("/plans/{plan_id}/requirements/{req_id}", status_code=204)
async def delete_requirement(plan_id: str, req_id: str):
    """
    删除需求
    DELETE /plans/{plan_id}/requirements/{req_id}
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="PLAN_NOT_FOUND")
    requirements = await _get_plan_requirements(plan_id)
    new_reqs = [r for r in requirements if r.get("id") != req_id]
    if len(new_reqs) == len(requirements):
        raise HTTPException(status_code=404, detail="REQUIREMENT_NOT_FOUND")
    await _save_plan_requirements(plan_id, new_reqs)


@app.get("/rooms")
async def list_rooms():
    """
    列出所有讨论房间
    """
    if _db_active:
        try:
            rooms = await crud.list_rooms()
            return {"rooms": rooms}
        except Exception as e:
            logger.warning(f"[DB] list_rooms failed: {e}")
    
    # Fallback to in-memory
    rooms = []
    for room_id, room in _rooms.items():
        r = _room_summaries.get(room_id, {})
        rooms.append({
            "room_id": room_id,
            "topic": room.get("topic", ""),
            "phase": room.get("phase", "initiated"),
            "participant_count": len(_participants.get(room_id, [])),
            "plan_id": room.get("plan_id"),
            "created_at": room.get("created_at"),
            "room_number": room.get("room_number"),
        })
    return {"rooms": rooms}


@app.get("/plans/{plan_id}/rooms")
async def get_rooms_by_plan(plan_id: str):
    """
    获取指定 Plan 下的所有房间
    """
    if _db_active:
        try:
            rooms = await crud.get_rooms_by_plan(plan_id)
            return {"rooms": rooms}
        except Exception as e:
            logger.warning(f"[DB] get_rooms_by_plan failed: {e}")
    
    # Fallback to in-memory
    rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]
    return {"rooms": rooms}


@app.post("/rooms")
async def create_room(data: dict = None):
    """
    创建独立房间（不依赖 Plan）
    """
    room_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    room_number = _generate_room_number()
    topic = (data.get("topic") or "讨论室") if data else "讨论室"
    plan_id = data.get("plan_id", "") if data else ""
    
    room = {
        "room_id": room_id,
        "room_number": room_number,
        "plan_id": plan_id,
        "topic": topic,
        "phase": "selecting",
        "coordinator_id": "coordinator",
        "current_version": "v1.0",
        "purpose": "general_discussion",
        "mode": "hierarchical",
        "created_at": now,
    }
    
    if _db_active:
        try:
            await crud.create_room(
                room_id=room_id,
                room_number=room_number,
                plan_id=plan_id,
                topic=topic,
                coordinator_id="coordinator",
                phase="selecting",
            )
            logger.info(f"[DB] create_room: {room_id}({room_number})")
        except Exception as e:
            logger.warning(f"[DB] create_room failed: {e}")
    
    _rooms[room_id] = room
    _room_summaries[room_id] = room.copy()
    return {"room_id": room_id, "room": room}


# ========================
# Room Templates API
# ========================

@app.post("/room-templates", status_code=201)
async def create_room_template(data: RoomTemplateCreate):
    """创建房间模板"""
    template_id = str(uuid.uuid4())
    try:
        template = await crud.create_room_template(
            template_id=template_id,
            name=data.name,
            description=data.description,
            purpose=data.purpose,
            mode=data.mode,
            default_phase=data.default_phase,
            settings=data.settings,
            created_by=None,
            is_shared=data.is_shared,
        )
        logger.info(f"[DB] create_room_template: {template_id}({data.name})")
        return {"template_id": template_id, "template": template}
    except Exception as e:
        logger.warning(f"[DB] create_room_template failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/room-templates")
async def list_room_templates(
    purpose: Optional[str] = None,
    is_shared: Optional[bool] = None,
):
    """列出房间模板"""
    try:
        templates = await crud.list_room_templates(
            purpose=purpose,
            is_shared=is_shared,
        )
        return {"templates": templates}
    except Exception as e:
        logger.warning(f"[DB] list_room_templates failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/room-templates/{template_id}")
async def get_room_template(template_id: str):
    """获取单个房间模板"""
    try:
        template = await crud.get_room_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[DB] get_room_template failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/room-templates/{template_id}")
async def update_room_template(template_id: str, data: RoomTemplateUpdate):
    """更新房间模板"""
    try:
        template = await crud.update_room_template(
            template_id=template_id,
            name=data.name,
            description=data.description,
            purpose=data.purpose,
            mode=data.mode,
            default_phase=data.default_phase,
            settings=data.settings,
            is_shared=data.is_shared,
        )
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[DB] update_room_template failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/room-templates/{template_id}", status_code=204)
async def delete_room_template(template_id: str):
    """删除房间模板"""
    try:
        deleted = await crud.delete_room_template(template_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Template not found")
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[DB] delete_room_template failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/plans/{plan_id}/rooms/from-template/{template_id}", status_code=201)
async def create_room_from_template(plan_id: str, template_id: str, data: dict = None):
    """从模板创建房间"""
    # 获取模板
    template = await crud.get_room_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 解析模板设置
    settings = template.get("settings", {}) if isinstance(template.get("settings"), dict) else {}
    topic = (data.get("topic") if data else None) or template.get("name", "讨论室")

    room_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    room_number = _generate_room_number()

    room = {
        "room_id": room_id,
        "room_number": room_number,
        "plan_id": plan_id,
        "topic": topic,
        "phase": template.get("default_phase", "selecting"),
        "coordinator_id": "coordinator",
        "current_version": data.get("version", "v1.0") if data else "v1.0",
        "purpose": template.get("purpose", "initial_discussion"),
        "mode": template.get("mode", "hierarchical"),
        "created_at": now,
        "template_id": template_id,
        "settings": settings,
    }

    if _db_active:
        try:
            await crud.create_room(
                room_id=room_id,
                room_number=room_number,
                plan_id=plan_id,
                topic=topic,
                coordinator_id="coordinator",
                phase=template.get("default_phase", "selecting"),
            )
            # Update purpose and mode if they exist in DB schema
            try:
                await crud.update_room(room_id, purpose=room["purpose"], mode=room["mode"])
            except Exception:
                pass
            logger.info(f"[DB] create_room_from_template: {room_id}({room_number}) from template {template_id}")
        except Exception as e:
            logger.warning(f"[DB] create_room_from_template failed: {e}")

    _rooms[room_id] = room
    _room_summaries[room_id] = room.copy()
    return {"room_id": room_id, "room": room, "template_applied": template.get("name")}


@app.get("/rooms/{room_id}")
async def get_room(room_id: str):
    """
    读取 Room 详情（PostgreSQL 优先，内存回退）
    """
    # PostgreSQL 优先读取
    if _db_active:
        try:
            row = await crud.get_room(room_id)
            if row:
                room = _row_to_room(row)
                _rooms[room_id] = room  # sync to memory
                participants = await crud.get_participants(room_id)
                room["participants"] = [_row_to_participant(p) for p in participants]
                _participants[room_id] = room["participants"]
                return room
        except Exception as e:
            logger.warning(f"[DB] get_room {room_id}: {e}")

    # 内存回退
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = _rooms[room_id].copy()
    room["participants"] = _participants.get(room_id, [])
    return room


@app.post("/rooms/{room_id}/participants")
async def add_participant(room_id: str, data: ParticipantAdd):
    """
    添加参与者（PostgreSQL 优先写入 + 内存同步）
    """
    # 确保 room 存在（从 DB 或内存）
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    if room_id not in _participants:
        _participants[room_id] = []

    participant_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    p = {
        "participant_id": participant_id,
        "agent_id": data.agent_id,
        "name": data.name,
        "level": data.level,
        "role": data.role,
        "joined_at": now,
        "is_active": True,
    }

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.add_participant(
                room_id=room_id,
                participant_id=participant_id,
                agent_id=data.agent_id,
                name=data.name,
                level=data.level,
                role=data.role,
                source="internal",
            )
            logger.info(f"[DB] add_participant: {participant_id} → room={room_id}")
        except Exception as e:
            logger.warning(f"[DB] add_participant 失败: {e}")

    _participants[room_id].append(p)

    # 持久化参与者加入事件
    seq = await _get_next_seq_for_room(room_id)
    join_msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "type": "participant_joined",
        "participant": p,
        "timestamp": datetime.now().isoformat(),
        "sequence": seq,
    }
    if room_id not in _messages:
        _messages[room_id] = []
    _messages[room_id].append(join_msg)

    await ws_manager.broadcast(room_id, {
        "type": "participant_joined",
        "participant": p,
    })

    # 通过 Gateway 通知外部 Agent（非致命）
    try:
        gateway = get_gateway_client()
        if gateway:
            await gateway.notify_agent_joined(room_id, data.agent_id, data.name, data.level)
            await gateway.forward_to_gateway(room_id, "participant_joined", p)
    except Exception as e:
        import logging
        logging.getLogger("agora").warning(f"Gateway通知失败（不影响核心流程）: {e}")

    return p


@app.post("/rooms/{room_id}/phase")
async def transition_phase(room_id: str, to_phase: RoomPhase):
    """
    Phase 状态转换
    写入路径：PostgreSQL（room.phase 更新）+ 内存同步
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    current = RoomPhase(room["phase"])

    if not can_transition(current, to_phase):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_transition",
                "current_phase": current.value,
                "requested_phase": to_phase.value,
                "allowed_phases": get_next_phases(current),
            }
        )

    old = current.value
    _rooms[room_id]["phase"] = to_phase.value

    # Step 31: Activity Log
    plan_id = _rooms[room_id].get("plan_id", "")
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.ROOM_PHASE_CHANGED,
        room_id=room_id,
        actor_id=None,
        actor_name="system",
        target_type="room",
        target_id=room_id,
        details={"from_phase": old, "to_phase": to_phase.value},
    )

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.update_room(room_id, phase=to_phase.value)
            logger.info(f"[DB] transition_phase: room={room_id} {old}→{to_phase.value}")
        except Exception as e:
            logger.warning(f"[DB] transition_phase 失败: {e}")

    # DEBATE 阶段进入时：初始化辩论状态（07-State-Machine-Details.md §2.5）
    if to_phase == RoomPhase.DEBATE:
        debate_state = init_debate_state(room_id)
        await ws_manager.broadcast(room_id, {
            "type": "debate_initialized",
            "room_id": room_id,
            "debate": {
                "round": debate_state["round"],
                "max_rounds": debate_state["max_rounds"],
                "consensus_score": debate_state["consensus_score"],
            },
        })

    # 持久化 phase 变更到历史
    seq = await _get_next_seq_for_room(room_id)
    phase_msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "type": "phase_change",
        "from_phase": old,
        "to_phase": to_phase.value,
        "timestamp": datetime.now().isoformat(),
        "sequence": seq,
    }
    if room_id not in _messages:
        _messages[room_id] = []
    _messages[room_id].append(phase_msg)

    # PostgreSQL 消息持久化
    if _db_active:
        try:
            await crud.add_message(
                room_id=room_id,
                message_id=phase_msg["message_id"],
                type="phase_change",
                metadata={"from_phase": old, "to_phase": to_phase.value},
                sequence=seq,
            )
        except Exception as e:
            logger.warning(f"[DB] add_message phase_change 失败: {e}")

    await ws_manager.broadcast(room_id, {
        "type": "phase_change",
        "from_phase": old,
        "to_phase": to_phase.value,
    })

    # 通过 Gateway 通知外部 Agent（非致命）
    try:
        gateway = get_gateway_client()
        if gateway:
            await gateway.forward_to_gateway(room_id, "phase_change", {
                "from_phase": old,
                "to_phase": to_phase.value,
            })
    except Exception as e:
        import logging
        logging.getLogger("agora").warning(f"Gateway phase通知失败: {e}")

    return {
        "room_id": room_id,
        "from_phase": old,
        "to_phase": to_phase.value,
        "allowed_next": get_next_phases(to_phase),
    }


@app.get("/rooms/{room_id}/phase")
async def get_phase(room_id: str):
    """获取当前 phase 及可转换目标"""
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    current = RoomPhase(room["phase"])

    return {
        "room_id": room_id,
        "current_phase": current.value,
        "allowed_next": get_next_phases(current),
    }


# ========================
# Step 24: Room Hierarchy API（08-Data-Models-Details.md §4.1 Room related_rooms/parent_room_id/child_rooms）
# ========================

@app.post("/rooms/{room_id}/link")
async def link_room(room_id: str, data: RoomLinkRequest):
    """
    建立讨论室层级关系（父子/关联）
    - 设置 parent_room_id 和 child_rooms（双向维护）
    - 设置 related_rooms（双向维护）
    来源：08-Data-Models-Details.md §4.1 Room.parent_room_id/child_rooms/related_rooms
    """
    logger.warning(f"[DEBUG link_room] room_id={room_id}, in_rooms={room_id in _rooms}")
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
        logger.warning(f"[DEBUG link_room] after sync, in_rooms={room_id in _rooms}, rooms_keys={list(_rooms.keys())[:5]}")
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    updated = await crud.link_rooms(
        room_id=room_id,
        parent_room_id=data.parent_room_id,
        related_room_ids=data.related_room_ids,
    )

    if updated:
        _rooms[room_id] = updated
        return updated
    raise HTTPException(status_code=404, detail="Room not found")


@app.get("/rooms/{room_id}/hierarchy")
async def get_room_hierarchy(room_id: str):
    """
    获取讨论室层级关系（父房间、子房间、关联房间）
    来源：08-Data-Models-Details.md §4.1 Room.parent_room_id/child_rooms/related_rooms
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]

    # 提取关系字段
    parent_id = room.get("parent_room_id")
    child_ids = room.get("child_rooms", [])
    related_ids = room.get("related_rooms", [])

    if isinstance(child_ids, str):
        child_ids = json.loads(child_ids) if child_ids else []
    if isinstance(related_ids, str):
        related_ids = json.loads(related_ids) if related_ids else []

    # 获取关联房间简要信息
    async def get_room_summary(rid: str) -> Optional[dict]:
        r = await crud.get_room(rid)
        if r:
            return {"room_id": rid, "topic": r.get("topic", ""), "phase": r.get("phase", "")}
        return None

    parent_summary = await get_room_summary(parent_id) if parent_id else None
    children = [s for s in (await asyncio.gather(*[get_room_summary(cid) for cid in child_ids])) if s]
    related = [s for s in (await asyncio.gather(*[get_room_summary(rid) for rid in related_ids])) if s]

    return {
        "room_id": room_id,
        "parent": parent_summary,
        "children": children,
        "related": related,
    }


@app.post("/rooms/{room_id}/conclude")
async def conclude_room(room_id: str, data: RoomConclusionRequest):
    """
    结束讨论室（填写总结、设置结束时间）
    - 更新 room.ended_at 和 room.duration_seconds
    - 更新 room.summary 和 room.conclusion
    来源：08-Data-Models-Details.md §4.1 Room.ended_at/duration_seconds/summary/conclusion
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    now = datetime.now()
    room = _rooms[room_id]
    started = room.get("started_at")
    duration_seconds = None
    if started:
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        elif hasattr(started, "tzinfo") and started.tzinfo:
            started = started.replace(tzinfo=None)
        duration_seconds = int((now - started).total_seconds())

    updates = {
        "ended_at": now,
        "summary": data.summary,
        "conclusion": data.conclusion,
    }
    if duration_seconds is not None:
        updates["duration_seconds"] = duration_seconds

    updated = await crud.update_room(room_id, **updates)
    if updated:
        _rooms[room_id] = updated
        return updated
    raise HTTPException(status_code=500, detail="Failed to conclude room")


# ========================
# Step 24: Participant Contributions API（08-Data-Models-Details.md §4.1 Room.participants.contributions）
# ========================

@app.patch("/rooms/{room_id}/participants/{participant_id}/contributions")
async def update_participant_contributions(
    room_id: str,
    participant_id: str,
    data: ParticipantContributionUpdate,
):
    """
    更新参与者贡献计数（speech/challenge/response）和阶段完成状态
    来源：08-Data-Models-Details.md §4.1 Room.participants.contributions/thinking_complete/sharing_complete
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    updated = await crud.update_participant_contributions(
        participant_id=participant_id,
        speech_delta=data.speech_count or 0,
        challenge_delta=data.challenge_count or 0,
        response_delta=data.response_count or 0,
        thinking_complete=data.thinking_complete,
        sharing_complete=data.sharing_complete,
    )

    if updated:
        # 同步到内存
        for i, p in enumerate(_participants.get(room_id, [])):
            if p["participant_id"] == participant_id:
                _participants[room_id][i] = updated
                break
        return updated
    raise HTTPException(status_code=404, detail="Participant not found")


@app.get("/rooms/{room_id}/history")
async def get_room_history(room_id: str):
    """
    获取讨论室完整历史
    包含所有发言、phase变更、参与者加入/离开等事件
    按时间顺序返回
    读取路径：PostgreSQL（messages 表）优先，内存回退
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    # PostgreSQL 优先读取
    if _db_active:
        try:
            rows = await crud.get_messages(room_id)
            messages = [_row_to_message(r) for r in rows]
            _messages[room_id] = messages
            return {
                "room_id": room_id,
                "total": len(messages),
                "history": messages,
            }
        except Exception as e:
            logger.warning(f"[DB] get_room_history {room_id}: {e}")

    messages = _messages.get(room_id, [])
    return {
        "room_id": room_id,
        "total": len(messages),
        "history": messages,
    }


@app.get("/rooms/{room_id}/messages/search")
async def search_room_messages(
    room_id: str,
    q: str,
    limit: int = 50,
):
    """
    搜索讨论室消息内容
    支持关键词模糊匹配，按时间倒序返回
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    # PostgreSQL 优先读取
    if _db_active:
        try:
            rows = await crud.search_messages(room_id, q, limit)
            messages = [_row_to_message(r) for r in rows]
            return {
                "room_id": room_id,
                "query": q,
                "total": len(messages),
                "results": messages,
            }
        except Exception as e:
            logger.warning(f"[DB] search_room_messages {room_id}: {e}")

    # 内存回退：过滤当前内存中的消息
    messages = [
        m for m in _messages.get(room_id, [])
        if q.lower() in m.get("content", "").lower()
    ][:limit]
    return {
        "room_id": room_id,
        "query": q,
        "total": len(messages),
        "results": messages,
    }


@app.get("/rooms/{room_id}/context")
async def get_room_context(room_id: str, level: Optional[int] = None):
    """
    获取讨论室当前上下文
    包含：主题、当前阶段、参与者列表、历史消息摘要
    用于 Agent 重新加入时快速恢复上下文
    读取路径：PostgreSQL 优先，内存回退

    当 level 参数提供时（05-Hierarchy-Roles.md §7.3），返回该层级专属视角：
    - 只显示该层级及以下层级的参与者可见信息
    - 根据可见性规则过滤消息历史
    - 附加该层级的待审批/已审批状态摘要
    """
    # 可见性规则（05-Hierarchy-Roles.md §4.3 可见性矩阵）
    # 查看方 →  L7  L6  L5  L4  L3  L2  L1
    # L7:     [✅  ✅  ✅  ✅  ✅  ✅  ✅]
    # L6:     [❌  ✅  ✅  ✅  ✅  ✅  ✅]
    # L5:     [❌  ❌  ✅  ✅  ✅  ✅  ✅]
    # L4:     [❌  ❌  ❌  ✅  ✅  ✅  ✅]
    # L3:     [❌  ❌  ❌  ❌  ✅  ✅  ✅]
    # L2:     [❌  ❌  ❌  ❌  ❌  ✅  ✅]
    # L1:     [❌  ❌  ❌  ❌  ❌  ❌  ✅]
    # 简化为：level=X 只能看到 level>=X 的信息
    def _is_visible_to(viewer_level: int, target_level: int) -> bool:
        """判断目标层级对查看方是否可见"""
        if viewer_level == target_level:
            return True  # 自己总能看到自己
        if viewer_level == 7:
            return True  # L7 可见所有
        if target_level > viewer_level:
            return False  # 比自己高的层级不可见
        return True

    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]

    # PostgreSQL 优先读取 messages 和 participants
    if _db_active:
        try:
            msg_rows = await crud.get_messages(room_id)
            messages = [_row_to_message(r) for r in msg_rows]
            _messages[room_id] = messages
            p_rows = await crud.get_participants(room_id)
            db_participant_ids = {str(p["participant_id"]) for p in p_rows}
            participants = [_row_to_participant(p) for p in p_rows]
            # DB + memory merge（解决"读到自己写"的一致性问题）
            # 注意：内存中 participant_id 存为 str，DB 返回 uuid.UUID，需统一为 str 比较
            mem_participants = [
                p for p in _participants.get(room_id, [])
                if str(p.get("participant_id")) not in db_participant_ids
            ]
            participants = participants + mem_participants
            # 统一 participant_id 为 str 类型，避免后续比较时 UUID vs str 不一致
            for p in participants:
                if "participant_id" in p:
                    p["participant_id"] = str(p["participant_id"])
            _participants[room_id] = participants
        except Exception as e:
            logger.warning(f"[DB] get_room_context {room_id}: {e}")
            messages = _messages.get(room_id, [])
            participants = _participants.get(room_id, [])
    else:
        messages = _messages.get(room_id, [])
        participants = _participants.get(room_id, [])

    # 生成历史摘要：每个 phase 最近一条消息
    phase_last_msg = {}
    for msg in messages:
        phase = msg.get("to_phase") or msg.get("phase")
        if phase:
            phase_last_msg[phase] = msg

    # 发言统计
    speech_count = {}
    for msg in messages:
        if msg.get("type") == "speech":
            agent_id = msg.get("agent_id", "unknown")
            speech_count[agent_id] = speech_count.get(agent_id, 0) + 1

    # 共识点（从 CONVERGING 阶段消息中提取描述）
    consensus_points = []
    for msg in messages:
        if msg.get("type") == "phase_change" and msg.get("to_phase") == "converging":
            consensus_points.append({
                "phase": "converging",
                "at": msg.get("timestamp"),
            })

    current = RoomPhase(room["phase"])

    # 根据 level 参数应用可见性过滤（05-Hierarchy-Roles.md §4.3）
    if level is not None:
        # 过滤参与者：只显示 viewer_level 及以上的参与者（可见性矩阵）
        visible_participants = [
            {
                "participant_id": p["participant_id"],
                "agent_id": p["agent_id"],
                "name": p["name"],
                "level": p["level"],
                "role": p["role"],
                "joined_at": p["joined_at"],
            }
            for p in participants
            if _is_visible_to(level, p.get("level", 5))
        ]

        # 过滤历史消息：隐藏高于 viewer_level 的参与者发言（仅对自己可见）
        # 简化处理：speech 类型消息按 agent_id 对应 participant level 过滤
        # 构建 agent_id -> level 映射
        agent_level_map = {p["agent_id"]: p.get("level", 5) for p in participants}

        def _message_visible(msg: dict, viewer_level: int) -> bool:
            """判断单条消息对 viewer_level 是否可见"""
            if msg.get("type") in ("phase_change", "system"):
                return True  # 系统消息对所有可见
            if msg.get("type") == "participant_joined":
                # 加入消息根据加入者 level 判断
                p_data = msg.get("participant", {})
                p_level = p_data.get("level", 5)
                return _is_visible_to(viewer_level, p_level)
            agent_id = msg.get("agent_id", "")
            msg_level = agent_level_map.get(agent_id, 5)
            return _is_visible_to(viewer_level, msg_level)

        visible_messages = [m for m in messages if _message_visible(m, level)]
        visible_speech_count = {
            k: v for k, v in speech_count.items()
            if _is_visible_to(level, agent_level_map.get(k, 5))
        }
        visible_stats = {
            "total_messages": len(visible_messages),
            "speech_count": visible_speech_count,
        }
    else:
        visible_participants = [
            {
                "participant_id": p["participant_id"],
                "agent_id": p["agent_id"],
                "name": p["name"],
                "level": p["level"],
                "role": p["role"],
                "joined_at": p["joined_at"],
            }
            for p in participants
        ]
        visible_messages = messages
        visible_stats = {
            "total_messages": len(messages),
            "speech_count": speech_count,
        }

    response = {
        "room_id": room_id,
        "plan_id": room.get("plan_id"),
        "topic": room.get("topic"),
        "current_phase": current.value,
        "allowed_next": get_next_phases(current),
        "participants": visible_participants,
        "stats": visible_stats,
        "phase_timeline": [
            {
                "phase": phase,
                "last_msg_at": msg.get("timestamp"),
            }
            for phase, msg in phase_last_msg.items()
        ],
        "consensus_points": consensus_points,
        "recent_history": visible_messages[-20:] if len(visible_messages) > 20 else visible_messages,
    }

    # 当指定 level 时，附加层级专属上下文（05-Hierarchy-Roles.md §7.3）
    if level is not None:
        # 当前层级的审批状态摘要
        plan_id = room.get("plan_id")
        approval_summary = None
        if plan_id and plan_id in _approval_flows:
            flow = _approval_flows[plan_id]
            levels_summary = {}
            for lvl, data in flow.get("levels", {}).items():
                if _is_visible_to(level, lvl):
                    levels_summary[lvl] = {
                        "level": lvl,
                        "level_label": ApprovalLevel(lvl).label,
                        "reviewer_role": ApprovalLevel(lvl).reviewer_role,
                        "status": data["status"],
                        "approver_name": data["approver_name"],
                        "decided_at": data["decided_at"],
                    }
            approval_summary = {
                "current_level": flow.get("current_level"),
                "current_level_label": ApprovalLevel(flow.get("current_level", 7)).label,
                "status": flow.get("status"),
                "levels": levels_summary,
            }

        # 层级可见范围说明
        visible_levels = [l for l in range(1, 8) if _is_visible_to(level, l)]

        # 待处理事项（高于当前层级的待审批）
        pending_items = []
        if approval_summary:
            for lvl, data in approval_summary.get("levels", {}).items():
                if data["status"] == "pending" and lvl < level:
                    pending_items.append({
                        "level": lvl,
                        "label": ApprovalLevel(lvl).label,
                        "type": "awaiting_approval_from_higher",
                    })

        response["hierarchy_context"] = {
            "viewer_level": level,
            "viewer_level_label": ApprovalLevel(level).label,
            "visible_levels": visible_levels,
            "approval_summary": approval_summary,
            "pending_items": pending_items,
            "visibility_note": f"L{level} ({ApprovalLevel(level).label}) 可见层级: {visible_levels}",
        }


    # DEBATE 阶段：附加辩论状态（07-State-Machine-Details.md §2.5）
    if current == RoomPhase.DEBATE:
        debate = get_debate_state(room_id)
        if debate:
            response["debate"] = {
                "round": debate.get("round", 0),
                "max_rounds": debate.get("max_rounds", 10),
                "consensus_score": debate.get("consensus_score", 0.0),
                "converged_points": debate.get("converged_points", []),
                "disputed_points": debate.get("disputed_points", []),
                "recent_exchanges": debate.get("recent_exchanges", [])[-10:],
                "all_points_count": len(debate.get("all_points", [])),
            }

    return response


@app.post("/rooms/{room_id}/speech")
async def add_speech(room_id: str, data: SpeechAdd):
    """
    添加发言（PostgreSQL 优先写入 + 内存同步）
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    # 获取下一条消息的序号
    seq = 1
    if _db_active:
        try:
            seq = await crud.get_next_message_sequence(room_id)
        except Exception as e:
            logger.warning(f"[DB] get_next_message_sequence 失败: {e}")
            # 内存兜底：基于已有消息计数
            seq = len(_messages.get(room_id, [])) + 1
    else:
        seq = len(_messages.get(room_id, [])) + 1

    msg = {
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "agent_id": data.agent_id,
        "content": data.content,
        "timestamp": datetime.now().isoformat(),
        "sequence": seq,
    }

    # 持久化消息到历史存储
    if room_id not in _messages:
        _messages[room_id] = []
    _messages[room_id].append({**msg, "type": "speech"})

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.add_message(
                room_id=room_id,
                message_id=msg["message_id"],
                type="speech",
                agent_id=data.agent_id,
                content=data.content,
                metadata={},
                sequence=seq,
            )
            logger.info(f"[DB] add_speech: room={room_id}, agent={data.agent_id}, seq={seq}")
        except Exception as e:
            logger.warning(f"[DB] add_speech 失败: {e}")

    await ws_manager.broadcast(room_id, {
        "type": "speech",
        **msg,
    })

    # 通过 Gateway 通知外部 Agent（非致命）
    try:
        gateway = get_gateway_client()
        if gateway:
            await gateway.forward_to_gateway(room_id, "speech", msg)
    except Exception as e:
        import logging
        logging.getLogger("agora").warning(f"Gateway speech通知失败: {e}")

    return msg


# ========================
# DEBATE 阶段 API 端点（07-State-Machine-Details.md §2.5）
# ========================


class DebatePointCreate(BaseModel):
    """创建辩论议题点"""
    content: str = Field(..., min_length=1)
    created_by: str


class DebatePositionSubmit(BaseModel):
    """提交立场"""
    point_id: str
    agent_id: str
    position: DebatePosition
    argument: Optional[str] = None


class DebateExchangeSubmit(BaseModel):
    """提交辩论交锋"""
    exchange_type: str  # challenge | response | evidence | update_position | consensus_building
    from_agent: str
    target_agent: Optional[str] = None
    content: str


@app.post("/rooms/{room_id}/debate/points")
async def create_debate_point(room_id: str, data: DebatePointCreate):
    """
    创建新的辩论议题点
    来源: 07-State-Machine-Details.md §2.5 - 辩论规则
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    current = RoomPhase(room["phase"])
    if current != RoomPhase.DEBATE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add debate point in phase {current.value}, only DEBATE phase is allowed",
        )

    point = add_debate_point(room_id, data.content, data.created_by)

    # 持久化到历史
    if room_id not in _messages:
        _messages[room_id] = []
    seq = await _get_next_seq_for_room(room_id)
    _messages[room_id].append({
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "type": "debate_point_created",
        "point": point.model_dump(),
        "timestamp": datetime.now().isoformat(),
        "sequence": seq,
    })

    await ws_manager.broadcast(room_id, {
        "type": "debate_point_created",
        "point": point.model_dump(),
    })

    return {"point": point.model_dump()}


@app.get("/rooms/{room_id}/debate/state")
async def get_debate_state_api(room_id: str):
    """
    获取辩论状态
    包含: round, consensus_score, converged_points, disputed_points, recent_exchanges
    来源: 07-State-Machine-Details.md §2.5 - 上下文更新
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    state = get_debate_state(room_id)
    if not state:
        raise HTTPException(status_code=404, detail="Debate state not initialized for this room")

    # 共识度阈值说明（07-State-Machine-Details.md §2.5）
    score = state["consensus_score"]
    if score >= 0.9:
        consensus_level = "高共识"
    elif score >= 0.7:
        consensus_level = "中共识"
    elif score >= 0.5:
        consensus_level = "低共识"
    else:
        consensus_level = "分歧大"

    return {
        "room_id": room_id,
        "round": state["round"],
        "max_rounds": state["max_rounds"],
        "consensus_score": score,
        "consensus_level": consensus_level,
        "converged_points": state["converged_points"],
        "disputed_points": state["disputed_points"],
        "all_points": state["all_points"],
        "recent_exchanges": state["recent_exchanges"],
        "started_at": state["started_at"],
        "last_updated": state["last_updated"],
    }


@app.post("/rooms/{room_id}/debate/position")
async def submit_debate_position(room_id: str, data: DebatePositionSubmit):
    """
    提交对某个议题点的立场
    来源: 07-State-Machine-Details.md §2.5 - 共识度计算
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    current = RoomPhase(room["phase"])
    if current != RoomPhase.DEBATE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit position in phase {current.value}, only DEBATE phase is allowed",
        )

    result = submit_position(
        room_id=room_id,
        point_id=data.point_id,
        agent_id=data.agent_id,
        position=data.position,
        argument=data.argument,
    )

    # 持久化到历史
    if room_id not in _messages:
        _messages[room_id] = []
    seq = await _get_next_seq_for_room(room_id)
    _messages[room_id].append({
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "type": "debate_position_submitted",
        "point_id": data.point_id,
        "agent_id": data.agent_id,
        "position": data.position.value,
        "consensus_score": result["consensus_score"],
        "timestamp": datetime.now().isoformat(),
        "sequence": seq,
    })

    await ws_manager.broadcast(room_id, {
        "type": "debate_position_submitted",
        **result,
    })

    return result


@app.post("/rooms/{room_id}/debate/exchange")
async def submit_debate_exchange(room_id: str, data: DebateExchangeSubmit):
    """
    记录一次辩论交锋
    来源: 07-State-Machine-Details.md §2.5 - recent_exchanges
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    current = RoomPhase(room["phase"])
    if current != RoomPhase.DEBATE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit exchange in phase {current.value}, only DEBATE phase is allowed",
        )

    exchange = add_exchange(
        room_id=room_id,
        exchange_type=data.exchange_type,
        from_agent=data.from_agent,
        content=data.content,
        target_agent=data.target_agent,
    )

    # 持久化到历史
    if room_id not in _messages:
        _messages[room_id] = []
    seq = await _get_next_seq_for_room(room_id)
    _messages[room_id].append({
        "message_id": str(uuid.uuid4()),
        "room_id": room_id,
        "type": "debate_exchange",
        "exchange": exchange.model_dump(),
        "timestamp": datetime.now().isoformat(),
        "sequence": seq,
    })

    await ws_manager.broadcast(room_id, {
        "type": "debate_exchange",
        "exchange": exchange.model_dump(),
    })

    return {"exchange": exchange.model_dump()}


@app.post("/rooms/{room_id}/debate/round")
async def advance_debate_round_api(room_id: str):
    """
    推进辩论轮次
    来源: 07-State-Machine-Details.md §2.5 - 最大轮次限制
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    current = RoomPhase(room["phase"])
    if current != RoomPhase.DEBATE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot advance round in phase {current.value}, only DEBATE phase is allowed",
        )

    new_round = advance_debate_round(room_id)
    state = get_debate_state(room_id)

    return {
        "room_id": room_id,
        "new_round": new_round,
        "max_rounds": state.get("max_rounds", 10) if state else 10,
        "at_max": new_round >= (state.get("max_rounds", 10) if state else 10),
    }


# ========================
# L1-L7 审批流 API 端点
# ========================

@app.post("/plans/{plan_id}/approval/start")
async def start_approval(plan_id: str, data: ApprovalFlowCreate):
    """
    启动 L1-L7 层级审批流（从L7战略层开始）
    写入路径：PostgreSQL（审批流+审批级别）+ 内存同步
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan_id in _approval_flows:
        raise HTTPException(status_code=409, detail="Approval flow already started")

    flow = start_approval_flow(
        plan_id=plan_id,
        initiator_id=data.initiator_id,
        initiator_name=data.initiator_name,
        skip_levels=data.skip_levels,
    )

    _plans[plan_id]["status"] = PlanStatus.IN_REVIEW

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.APPROVAL_STARTED,
        actor_id=data.initiator_id,
        actor_name=data.initiator_name,
        target_type="approval_flow",
        target_id=plan_id,
        target_label="approval_flow",
        details={"levels": list(flow["levels"].keys()), "skip_levels": data.skip_levels or []},
    )

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.start_approval_flow(
                plan_id=plan_id,
                initiator_id=data.initiator_id,
                initiator_name=data.initiator_name,
                levels_data=flow["levels"],
                skip_levels=data.skip_levels,
            )
            logger.info(f"[DB] start_approval: plan={plan_id}")
        except Exception as e:
            logger.warning(f"[DB] start_approval 失败: {e}")

    return {
        "plan_id": plan_id,
        "message": f"审批流启动，从 {ApprovalLevel(flow['current_level']).label} 开始",
        "flow": get_approval_status(plan_id),
    }


@app.get("/plans/{plan_id}/approval")
async def get_approval(plan_id: str):
    """
    获取审批流状态（PostgreSQL 优先，内存回退）
    """
    # PostgreSQL 优先读取
    if _db_active:
        try:
            row = await crud.get_approval_flow(plan_id)
            if row:
                _approval_flows[plan_id] = row
                return get_approval_status(plan_id)
        except Exception as e:
            logger.warning(f"[DB] get_approval {plan_id}: {e}")

    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    return get_approval_status(plan_id)


@app.post("/plans/{plan_id}/approval/{level}/action")
async def approval_action(plan_id: str, level: int, action: ApprovalAction,
                           actor_id: str, actor_name: str, comment: Optional[str] = None):
    """
    执行审批动作
    - APPROVE: 通过，流转下一级
    - REJECT: 驳回，打回草稿
    - RETURN: 退回上一级
    - ESCALATE: 升级到更高决策层
    写入路径：PostgreSQL（审批级别+审批流更新）+ 内存同步
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    try:
        result = execute_approval_action(
            plan_id=plan_id,
            level=level,
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            comment=comment,
        )

        # Step 31: Activity Log
        if action == ApprovalAction.APPROVE:
            await log_activity(
                plan_id=plan_id,
                action_type=ActivityType.APPROVAL_APPROVED,
                actor_id=actor_id,
                actor_name=actor_name,
                target_type="approval_level",
                target_id=f"{plan_id}:L{level}",
                target_label=f"L{level}",
                details={"comment": comment, "new_current_level": result.get("new_current_level")},
            )
            flow = _approval_flows.get(plan_id)
            if flow and flow.get("status") == "fully_approved":
                await log_activity(
                    plan_id=plan_id,
                    action_type=ActivityType.PLAN_APPROVED,
                    actor_id=actor_id,
                    actor_name=actor_name,
                    target_type="plan",
                    target_id=plan_id,
                    details={"comment": comment},
                )
        elif action == ApprovalAction.REJECT:
            await log_activity(
                plan_id=plan_id,
                action_type=ActivityType.APPROVAL_REJECTED,
                actor_id=actor_id,
                actor_name=actor_name,
                target_type="plan",
                target_id=plan_id,
                details={"comment": comment},
            )
            await log_activity(
                plan_id=plan_id,
                action_type=ActivityType.PLAN_REJECTED,
                actor_id=actor_id,
                actor_name=actor_name,
                target_type="plan",
                target_id=plan_id,
                details={"comment": comment},
            )
        elif action == ApprovalAction.ESCALATE:
            await log_activity(
                plan_id=plan_id,
                action_type=ActivityType.APPROVAL_ESCALATED,
                actor_id=actor_id,
                actor_name=actor_name,
                target_type="approval_level",
                target_id=f"{plan_id}:L{level}",
                target_label=f"L{level}",
                details={"comment": comment, "new_level": result.get("new_current_level")},
            )

        # PostgreSQL 优先写入
        if _db_active:
            try:
                now = datetime.now()  # asyncpg needs datetime object, not ISO string
                await crud.update_approval_level(
                    plan_id=plan_id,
                    level=level,
                    status=action.value,
                    approver_id=actor_id,
                    approver_name=actor_name,
                    comment=comment,
                    decided_at=now,
                )
                # 更新 plan status
                if action == ApprovalAction.APPROVE:
                    # 找下一个待审批级别
                    flow = _approval_flows.get(plan_id)
                    if flow and flow.get("status") == "fully_approved":
                        await crud.update_plan(plan_id, status=PlanStatus.APPROVED.value)
                        await crud.update_approval_flow(plan_id, status="fully_approved")
                    else:
                        await crud.update_approval_flow(
                            plan_id=plan_id,
                            current_level=result["new_current_level"],
                        )
                elif action == ApprovalAction.REJECT:
                    await crud.update_plan(plan_id, status=PlanStatus.DRAFT.value)
                    await crud.update_approval_flow(plan_id=plan_id, status="rejected")
                logger.info(f"[DB] approval_action: plan={plan_id}, level={level}, action={action.value}")
            except Exception as e:
                logger.warning(f"[DB] approval_action 失败: {e}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/plans/{plan_id}/approval/levels")
async def get_approval_levels(plan_id: str):
    """获取审批层级说明"""
    return [
        {
            "level": lvl,
            "level_label": ApprovalLevel(lvl).label,
            "reviewer_role": ApprovalLevel(lvl).reviewer_role,
            "description": f"{ApprovalLevel(lvl).reviewer_role} 对方案进行审批",
        }
        for lvl in range(7, 0, -1)
    ]


# ========================
# 层级汇报/升级 API 端点（05-Hierarchy-Roles.md §7.2 层级汇报）
# ========================


@app.post("/rooms/{room_id}/escalate", status_code=201)
async def escalate_room(room_id: str, data: EscalationRequest):
    """
    层级汇报/升级
    来源: 05-Hierarchy-Roles.md §7.2 - 层级汇报 API

    将内容从低层级升级到高层级进行审批或决策
    支持三种模式:
    - level_by_level: 逐级汇报 L1→L2→L3→...→L7
    - cross_level: 跨级汇报 L1→L3→L5→L7
    - emergency: 紧急汇报 L1→L5→L7

    写入路径：PostgreSQL（escalations 表）+ 内存同步
    """
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    plan_id = room.get("plan_id")
    version = room.get("current_version", "v1.0")

    # 验证 from_level < to_level（只能向上升级）
    if data.from_level >= data.to_level:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_escalation",
                "message": f"to_level ({data.to_level}) must be greater than from_level ({data.from_level})",
                "from_level": data.from_level,
                "to_level": data.to_level,
            }
        )

    # 计算升级路径
    escalation_path = data.escalation_path or _calculate_escalation_path(
        data.from_level, data.to_level, data.mode
    )

    # 构建升级记录
    escalation_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    escalation = {
        "escalation_id": escalation_id,
        "room_id": room_id,
        "plan_id": plan_id,
        "version": version,
        "from_level": data.from_level,
        "to_level": data.to_level,
        "mode": data.mode.value,
        "content": data.content,
        "escalation_path": escalation_path,
        "status": "pending",
        "escalated_by": data.content.get("escalated_by", "system"),
        "escalated_at": now,
        "acknowledged_at": None,
        "completed_at": None,
        "notes": data.notes,
    }

    # 存储
    _escalations[escalation_id] = escalation
    _room_escalations.setdefault(room_id, []).append(escalation_id)
    _plan_escalations.setdefault(plan_id, []).append(escalation_id)

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_escalation(
                escalation_id=escalation_id,
                room_id=room_id,
                plan_id=plan_id,
                version=version,
                from_level=data.from_level,
                to_level=data.to_level,
                mode=data.mode.value,
                content=data.content,
                escalation_path=escalation_path,
                status="pending",
                escalated_by=escalation["escalated_by"],
                notes=data.notes,
            )
            logger.info(f"[DB] escalate_room: escalation={escalation_id}, room={room_id}, path={escalation_path}")
        except Exception as e:
            logger.warning(f"[DB] escalate_room 失败: {e}")

    # 更新 room 状态为 HIERARCHICAL_REVIEW（如果当前不在审批流中）
    current_phase = RoomPhase(room.get("phase", "initiated"))
    if current_phase not in [RoomPhase.HIERARCHICAL_REVIEW, RoomPhase.DECISION, RoomPhase.EXECUTING]:
        old_phase = current_phase.value
        _rooms[room_id]["phase"] = RoomPhase.HIERARCHICAL_REVIEW.value
        if _db_active:
            try:
                await crud.update_room(room_id, phase=RoomPhase.HIERARCHICAL_REVIEW.value)
            except Exception as e:
                logger.warning(f"[DB] update_room HIERARCHICAL_REVIEW 失败: {e}")

        # 持久化 phase 变更
        if room_id not in _messages:
            _messages[room_id] = []
        seq = await _get_next_seq_for_room(room_id)
        phase_msg = {
            "message_id": str(uuid.uuid4()),
            "room_id": room_id,
            "type": "escalation_phase_change",
            "from_phase": old_phase,
            "to_phase": RoomPhase.HIERARCHICAL_REVIEW.value,
            "escalation_id": escalation_id,
            "escalation_path": escalation_path,
            "timestamp": now,
            "sequence": seq,
        }
        _messages[room_id].append(phase_msg)
        if _db_active:
            try:
                await crud.add_message(
                    room_id=room_id,
                    message_id=phase_msg["message_id"],
                    type="escalation_phase_change",
                    metadata={
                        "from_phase": old_phase,
                        "to_phase": RoomPhase.HIERARCHICAL_REVIEW.value,
                        "escalation_id": escalation_id,
                    },
                    sequence=seq,
                )
            except Exception as e:
                logger.warning(f"[DB] add_message escalation_phase_change 失败: {e}")

        await ws_manager.broadcast(room_id, {
            "type": "escalation_initiated",
            "escalation_id": escalation_id,
            "from_level": data.from_level,
            "to_level": data.to_level,
            "mode": data.mode.value,
            "escalation_path": escalation_path,
            "from_phase": old_phase,
            "to_phase": RoomPhase.HIERARCHICAL_REVIEW.value,
        })

    # 通过 Gateway 通知外部 Agent（非致命）
    try:
        gateway = get_gateway_client()
        if gateway:
            await gateway.forward_to_gateway(room_id, "escalation_initiated", {
                "escalation_id": escalation_id,
                "from_level": data.from_level,
                "to_level": data.to_level,
                "mode": data.mode.value,
                "escalation_path": escalation_path,
            })
    except Exception as e:
        import logging
        logging.getLogger("agora").warning(f"Gateway escalation通知失败: {e}")

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.ESCALATION_TRIGGERED,
        version=version,
        room_id=room_id,
        actor_id=escalation["escalated_by"],
        actor_name=None,
        target_type="escalation",
        target_id=escalation_id,
        target_label=f"L{data.from_level}→L{data.to_level}",
        details={
            "from_level": data.from_level,
            "to_level": data.to_level,
            "mode": data.mode.value,
            "escalation_path": escalation_path,
            "content_summary": str(data.content)[:100] if data.content else None,
        },
    )

    return EscalationResponse(
        escalation_id=escalation_id,
        room_id=room_id,
        plan_id=plan_id,
        version=version,
        from_level=data.from_level,
        to_level=data.to_level,
        mode=data.mode,
        escalation_path=escalation_path,
        status="pending",
        content=data.content,
        escalated_by=escalation["escalated_by"],
        escalated_at=now,
        message=f"升级请求已提交，从 L{data.from_level} 到 L{data.to_level}，路径: {'→'.join(f'L{l}' for l in escalation_path)}",
    )


@app.get("/rooms/{room_id}/escalations")
async def get_room_escalations(room_id: str):
    """
    获取讨论室的所有升级记录
    来源: 05-Hierarchy-Roles.md §7.2
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    escalation_ids = _room_escalations.get(room_id, [])
    escalations = [_escalations[eid] for eid in escalation_ids if eid in _escalations]

    # PostgreSQL 优先读取（补充内存缺失的记录）
    if _db_active:
        try:
            rows = await crud.get_room_escalations(room_id)
            for row in rows:
                eid = str(row["escalation_id"])  # 统一转为字符串，避免 uuid.UUID vs str 不一致
                if eid not in _escalations:
                    row_dict = dict(row)
                    row_dict["escalation_id"] = eid  # 确保 escalation_id 是字符串
                    _escalations[eid] = row_dict
                    if eid not in _room_escalations.get(room_id, []):
                        _room_escalations.setdefault(room_id, []).append(eid)
            # 统一从内存构建返回列表（避免循环内重复构建导致重复）
            escalation_ids_final = _room_escalations.get(room_id, [])
            escalations = [_escalations[eid] for eid in escalation_ids_final if eid in _escalations]
        except Exception as e:
            logger.warning(f"[DB] get_room_escalations {room_id}: {e}")

    return {
        "room_id": room_id,
        "total": len(escalations),
        "escalations": escalations,
    }


@app.get("/plans/{plan_id}/escalations")
async def get_plan_escalations(plan_id: str):
    """
    获取方案的所有升级记录
    来源: 05-Hierarchy-Roles.md §7.2
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    escalation_ids = _plan_escalations.get(plan_id, [])
    escalations = [_escalations[eid] for eid in escalation_ids if eid in _escalations]

    # PostgreSQL 优先读取（补充内存缺失的记录）
    if _db_active:
        try:
            rows = await crud.get_plan_escalations(plan_id)
            for row in rows:
                eid = str(row["escalation_id"])  # 统一转为字符串，避免 uuid.UUID vs str 不一致
                if eid not in _escalations:
                    row_dict = dict(row)
                    row_dict["escalation_id"] = eid  # 确保 escalation_id 是字符串
                    _escalations[eid] = row_dict
                    if eid not in _plan_escalations.get(plan_id, []):
                        _plan_escalations.setdefault(plan_id, []).append(eid)
            # 统一从内存构建返回列表（避免循环内重复构建导致重复）
            escalations = [_escalations[eid] for eid in _plan_escalations.get(plan_id, []) if eid in _escalations]
        except Exception as e:
            logger.warning(f"[DB] get_plan_escalations {plan_id}: {e}")

    return {
        "plan_id": plan_id,
        "total": len(escalations),
        "escalations": escalations,
    }


@app.get("/escalations/{escalation_id}")
async def get_escalation(escalation_id: str):
    """
    获取单个升级记录详情
    来源: 05-Hierarchy-Roles.md §7.2
    """
    if escalation_id not in _escalations:
        # PostgreSQL 兜底读取
        if _db_active:
            try:
                row = await crud.get_escalation(escalation_id)
                if row:
                    _escalations[escalation_id] = dict(row)
                    plan_id = row.get("plan_id")
                    room_id = row.get("room_id")
                    if plan_id:
                        _plan_escalations.setdefault(plan_id, []).append(escalation_id)
                    if room_id:
                        _room_escalations.setdefault(room_id, []).append(escalation_id)
            except Exception as e:
                logger.warning(f"[DB] get_escalation {escalation_id}: {e}")
        if escalation_id not in _escalations:
            raise HTTPException(status_code=404, detail="Escalation not found")
    return _escalations[escalation_id]


class EscalationActionRequest(BaseModel):
    """执行升级动作"""
    action: str = Field(..., description="动作: acknowledge | complete | reject")
    actor_id: str
    actor_name: str
    comment: Optional[str] = None


@app.patch("/escalations/{escalation_id}")
async def update_escalation(escalation_id: str, data: EscalationActionRequest):
    """
    更新升级记录状态
    支持: acknowledge（确认收到）、complete（完成升级）、reject（拒绝升级）
    来源: 05-Hierarchy-Roles.md §7.2
    """
    if escalation_id not in _escalations:
        raise HTTPException(status_code=404, detail="Escalation not found")

    escalation = _escalations[escalation_id]
    now = datetime.now().isoformat()

    if data.action == "acknowledge":
        escalation["status"] = "acknowledged"
        escalation["acknowledged_at"] = now
        message = f"升级已被 {data.actor_name} 确认"
    elif data.action == "complete":
        escalation["status"] = "completed"
        escalation["completed_at"] = now
        message = f"升级流程已完成，由 {data.actor_name} 完成"
    elif data.action == "reject":
        escalation["status"] = "rejected"
        message = f"升级被 {data.actor_name} 拒绝"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {data.action}")

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.update_escalation_status(escalation_id, escalation["status"])
            logger.info(f"[DB] update_escalation: escalation={escalation_id}, action={data.action}")
        except Exception as e:
            logger.warning(f"[DB] update_escalation 失败: {e}")

    # WS 广播
    await ws_manager.broadcast(escalation["room_id"], {
        "type": "escalation_updated",
        "escalation_id": escalation_id,
        "status": escalation["status"],
        "actor_id": data.actor_id,
        "actor_name": data.actor_name,
        "comment": data.comment,
    })

    return {
        "escalation_id": escalation_id,
        "status": escalation["status"],
        "message": message,
    }


@app.get("/rooms/{room_id}/escalation-path")
async def get_escalation_path(room_id: str, from_level: int, mode: EscalationMode = EscalationMode.LEVEL_BY_LEVEL):
    """
    计算指定汇报模式下的升级路径（预览）
    来源: 05-Hierarchy-Roles.md §4.2 - 对话模式
    """
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    room = _rooms[room_id]
    # 找到当前审批流中的最高级别作为目标
    plan_id = room.get("plan_id")
    to_level = 7  # 默认到 L7

    if plan_id and plan_id in _approval_flows:
        flow = _approval_flows[plan_id]
        # 找到当前审批流的最高（数字最小）未审批级别
        pending_levels = [l for l in sorted(flow["levels"].keys()) if flow["levels"][l]["status"] == "pending"]
        if pending_levels:
            to_level = max(pending_levels)  # 最大数字 = 最低级别

    path = _calculate_escalation_path(from_level, to_level, mode)

    return {
        "room_id": room_id,
        "from_level": from_level,
        "to_level": to_level,
        "mode": mode.value,
        "escalation_path": path,
        "path_description": f"L{from_level} → " + " → ".join(f"L{l}" for l in path[1:]),
    }


# ========================
# 问题处理 API 端点（PROBLEM_DETECTED → RESUMING 流程）
# ========================

class ProblemReport(BaseModel):
    """报告问题"""
    plan_id: str
    room_id: str
    type: ProblemType
    title: str
    description: str
    severity: ProblemSeverity
    detected_by: str
    affected_tasks: List[int] = Field(default_factory=list)
    progress_delay: int = 0
    related_context: dict = Field(default_factory=dict)


class ProblemAnalysisRequest(BaseModel):
    """请求分析问题"""
    root_cause: str
    root_cause_confidence: float = Field(ge=0.0, le=1.0)
    impact_scope: str = "局部"
    affected_tasks: List[int] = Field(default_factory=list)
    progress_impact: str = "未知"
    severity_reassessment: ProblemSeverity
    solution_options: List[dict] = Field(default_factory=list)
    recommended_option: int = 0
    requires_discussion: bool = False
    discussion_needed_aspects: List[str] = Field(default_factory=list)


class ProblemDiscussionRequest(BaseModel):
    """问题讨论请求"""
    participants: List[dict]  # List of participant objects
    discussion_focus: List[dict]  # List of focus objects with aspect/concerns
    proposed_solutions: List[dict]
    votes: dict = Field(default_factory=dict)
    final_recommendation: str = ""


class PlanUpdateRequest(BaseModel):
    """方案更新请求"""
    plan_id: Optional[str] = None  # Optional - can come from problem if not provided
    new_version: str
    parent_version: str
    update_type: str = "fix"
    description: str
    changes: dict
    task_updates: List[dict] = Field(default_factory=list)
    new_tasks: List[dict] = Field(default_factory=list)
    cancelled_tasks: List[int] = Field(default_factory=list)


class ResumingRequest(BaseModel):
    """恢复执行请求"""
    plan_id: Optional[str] = None  # Optional - can come from problem if not provided
    new_version: str
    resuming_from_task: int
    checkpoint: str
    resume_instructions: dict


@app.post("/problems/report")
async def report_problem(data: ProblemReport):
    """
    报告问题
    入口: EXECUTING 状态中发现问题时
    触发: PROBLEM_DETECTED 状态
    写入路径：PostgreSQL（problems 表）+ 内存同步
    """
    issue_id = str(uuid.uuid4())
    issue_number = _generate_issue_number()
    now = datetime.now().isoformat()

    # 确保 plan 存在
    if data.plan_id not in _plans:
        await _sync_plan_to_memory(data.plan_id)

    problem = {
        "issue_id": issue_id,
        "issue_number": issue_number,
        "plan_id": data.plan_id,
        "room_id": data.room_id,
        "version": _plans.get(data.plan_id, {}).get("current_version", "v1.0"),
        "type": data.type.value,
        "title": data.title,
        "description": data.description,
        "severity": data.severity.value,
        "detected_by": data.detected_by,
        "detected_at": now,
        "affected_tasks": data.affected_tasks,
        "progress_delay": data.progress_delay,
        "related_context": data.related_context,
        "status": "detected",
    }
    _problems[issue_id] = problem

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_problem(
                issue_id=issue_id,
                plan_id=data.plan_id,
                room_id=data.room_id,
                version=problem["version"],
                type=data.type.value,
                title=data.title,
                description=data.description,
                severity=data.severity.value,
                detected_by=data.detected_by,
                issue_number=issue_number,
                affected_tasks=data.affected_tasks,
                progress_delay=data.progress_delay,
                related_context=data.related_context,
            )
            logger.info(f"[DB] report_problem: issue={issue_id}, issue_number={issue_number}, plan={data.plan_id}")
        except Exception as e:
            logger.warning(f"[DB] report_problem 失败: {e}")

    # 更新room状态为PROBLEM_DETECTED
    if data.room_id in _rooms:
        old_phase = _rooms[data.room_id]["phase"]
        _rooms[data.room_id]["phase"] = RoomPhase.PROBLEM_DETECTED.value
        # PostgreSQL room phase 更新
        if _db_active:
            try:
                await crud.update_room(data.room_id, phase=RoomPhase.PROBLEM_DETECTED.value)
            except Exception as e:
                logger.warning(f"[DB] update_room PROBLEM_DETECTED 失败: {e}")
        await ws_manager.broadcast(data.room_id, {
            "type": "problem_detected",
            "issue_id": issue_id,
            "from_phase": old_phase,
            "to_phase": RoomPhase.PROBLEM_DETECTED.value,
            "problem": problem,
        })

    # 更新plan状态
    if data.plan_id in _plans:
        _plans[data.plan_id]["status"] = PlanStatus.DRAFT
        if _db_active:
            try:
                await crud.update_plan(data.plan_id, status=PlanStatus.DRAFT.value)
            except Exception as e:
                logger.warning(f"[DB] update_plan DRAFT 失败: {e}")

    global _active_issue_id
    _active_issue_id = issue_id

    # Step 31: Activity Log
    await log_activity(
        plan_id=data.plan_id,
        action_type=ActivityType.PROBLEM_REPORTED,
        version=problem["version"],
        room_id=data.room_id,
        actor_id=data.detected_by,
        actor_name=None,
        target_type="problem",
        target_id=issue_id,
        target_label=issue_number,
        details={
            "title": data.title,
            "type": data.type.value,
            "severity": data.severity.value,
            "affected_tasks": data.affected_tasks,
        },
    )

    # Return flat response matching design spec and tests
    return {
        "issue_id": issue_id,
        "issue_number": issue_number,
        "plan_id": problem["plan_id"],
        "room_id": problem["room_id"],
        "version": problem["version"],
        "type": problem["type"],
        "title": problem["title"],
        "description": problem["description"],
        "severity": problem["severity"],
        "detected_by": problem["detected_by"],
        "detected_at": problem["detected_at"],
        "status": problem["status"],
    }


@app.get("/problems/{issue_id}")
async def get_problem(issue_id: str):
    """获取问题详情（内存优先，DB兜底）"""
    # Memory first
    if issue_id in _problems:
        return _problems[issue_id]
    # DB fallback
    if _db_active:
        try:
            row = await crud.get_problem(issue_id)
            if row:
                _problems[issue_id] = row
                return row
        except Exception as e:
            logger.warning(f"[DB] get_problem fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Problem not found")


@app.get("/plans/{plan_id}/problems")
async def get_plan_problems(plan_id: str):
    """获取计划的所有问题（内存优先，DB兜底）"""
    # Memory first
    memory_problems = [p for p in _problems.values() if p.get("plan_id") == plan_id]
    if memory_problems:
        return memory_problems
    # DB fallback
    if _db_active:
        try:
            rows = await crud.get_problems_by_plan(plan_id)
            if rows:
                # Populate memory
                for p in rows:
                    _problems[p["issue_id"]] = p
                return rows
        except Exception as e:
            logger.warning(f"[DB] get_plan_problems fallback failed: {e}")
    return []


@app.post("/problems/{issue_id}/analyze")
async def analyze_problem(issue_id: str, data: ProblemAnalysisRequest):
    """
    分析问题
    入口: PROBLEM_DETECTED 状态
    触发: PROBLEM_ANALYSIS 状态
    根据 requires_discussion 决定下一步:
    - False: 直接进入 PLAN_UPDATE
    - True: 进入 PROBLEM_DISCUSSION
    写入路径：PostgreSQL（problem_analyses 表）+ 内存同步
    """
    if issue_id not in _problems:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem = _problems[issue_id]
    room_id = problem["room_id"]

    analysis = {
        "issue_id": issue_id,
        "root_cause": data.root_cause,
        "root_cause_confidence": data.root_cause_confidence,
        "impact_scope": data.impact_scope,
        "affected_tasks": data.affected_tasks,
        "progress_impact": data.progress_impact,
        "severity_reassessment": data.severity_reassessment.value,
        "solution_options": data.solution_options,
        "recommended_option": data.recommended_option,
        "requires_discussion": data.requires_discussion,
        "discussion_needed_aspects": data.discussion_needed_aspects,
        "analyzed_at": datetime.now().isoformat(),
    }
    _problem_analyses[issue_id] = analysis

    # 更新problem状态
    _problems[issue_id]["status"] = "analyzed"

    # 确定下一状态
    if data.requires_discussion:
        next_phase = RoomPhase.PROBLEM_DISCUSSION
        _problems[issue_id]["status"] = "needs_discussion"
    else:
        next_phase = RoomPhase.PLAN_UPDATE
        _problems[issue_id]["status"] = "ready_for_update"

    # Preserve analyzed status for response (tests expect "analyzed")
    analysis_status = "analyzed"

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_problem_analysis(
                issue_id=issue_id,
                root_cause=data.root_cause,
                root_cause_confidence=data.root_cause_confidence,
                impact_scope=data.impact_scope,
                affected_tasks=data.affected_tasks,
                progress_impact=data.progress_impact,
                severity_reassessment=data.severity_reassessment.value,
                solution_options=data.solution_options,
                recommended_option=data.recommended_option,
                requires_discussion=data.requires_discussion,
                discussion_needed_aspects=data.discussion_needed_aspects,
            )
            await crud.update_problem(issue_id, status=_problems[issue_id]["status"])
            logger.info(f"[DB] analyze_problem: issue={issue_id}")
        except Exception as e:
            logger.warning(f"[DB] analyze_problem 失败: {e}")

    # 更新room状态
    if room_id in _rooms:
        _rooms[room_id]["phase"] = next_phase.value
        if _db_active:
            try:
                await crud.update_room(room_id, phase=next_phase.value)
            except Exception as e:
                logger.warning(f"[DB] update_room in analyze 失败: {e}")
        await ws_manager.broadcast(room_id, {
            "type": "phase_change",
            "from_phase": RoomPhase.PROBLEM_DETECTED.value,
            "to_phase": next_phase.value,
            "issue_id": issue_id,
            "analysis": analysis,
        })

    # Return flat response matching design spec and tests
    # Step 31: Activity Log
    await log_activity(
        plan_id=problem["plan_id"],
        action_type=ActivityType.PROBLEM_ANALYZED,
        version=problem.get("version"),
        room_id=room_id,
        actor_id=None,
        actor_name=None,
        target_type="problem",
        target_id=issue_id,
        target_label=problem.get("issue_number"),
        details={
            "root_cause": data.root_cause,
            "severity_reassessment": data.severity_reassessment.value,
            "requires_discussion": data.requires_discussion,
            "recommended_option": data.recommended_option,
        },
    )

    return {
        "issue_id": issue_id,
        "status": analysis_status,
        "root_cause": analysis["root_cause"],
        "root_cause_confidence": analysis["root_cause_confidence"],
        "impact_scope": analysis["impact_scope"],
        "affected_tasks": analysis["affected_tasks"],
        "progress_impact": analysis["progress_impact"],
        "severity_reassessment": analysis["severity_reassessment"],
        "solution_options": analysis["solution_options"],
        "recommended_option": analysis["recommended_option"],
        "requires_discussion": analysis["requires_discussion"],
        "discussion_needed_aspects": analysis["discussion_needed_aspects"],
        "analyzed_at": analysis["analyzed_at"],
        "next_phase": next_phase.value,
    }


@app.post("/problems/{issue_id}/discuss")
async def discuss_problem(issue_id: str, data: ProblemDiscussionRequest):
    """
    问题讨论
    入口: PROBLEM_DISCUSSION 状态
    触发: PLAN_UPDATE 状态
    写入路径：PostgreSQL（problem_discussions 表）+ 内存同步
    """
    if issue_id not in _problems:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem = _problems[issue_id]
    room_id = problem["room_id"]

    discussion = {
        "issue_id": issue_id,
        "participants": data.participants,
        "discussion_focus": data.discussion_focus,
        "proposed_solutions": data.proposed_solutions,
        "votes": data.votes,
        "final_recommendation": data.final_recommendation,
        "discussed_at": datetime.now().isoformat(),
    }
    _problem_discussions[issue_id] = discussion

    # 更新problem状态
    _problems[issue_id]["status"] = "discussed"

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_problem_discussion(
                issue_id=issue_id,
                participants=data.participants,
                discussion_focus=data.discussion_focus,
                proposed_solutions=data.proposed_solutions,
                votes=data.votes,
                final_recommendation=data.final_recommendation,
            )
            await crud.update_problem(issue_id, status="discussed")
            logger.info(f"[DB] discuss_problem: issue={issue_id}")
        except Exception as e:
            logger.warning(f"[DB] discuss_problem 失败: {e}")

    # 更新room状态为PLAN_UPDATE
    if room_id in _rooms:
        _rooms[room_id]["phase"] = RoomPhase.PLAN_UPDATE.value
        if _db_active:
            try:
                await crud.update_room(room_id, phase=RoomPhase.PLAN_UPDATE.value)
            except Exception as e:
                logger.warning(f"[DB] update_room PLAN_UPDATE 失败: {e}")
        await ws_manager.broadcast(room_id, {
            "type": "phase_change",
            "from_phase": RoomPhase.PROBLEM_DISCUSSION.value,
            "to_phase": RoomPhase.PLAN_UPDATE.value,
            "issue_id": issue_id,
            "discussion": discussion,
        })

    # Return flat response matching design spec and tests
    # Step 31: Activity Log
    await log_activity(
        plan_id=problem["plan_id"],
        action_type=ActivityType.PROBLEM_DISCUSSED,
        version=problem.get("version"),
        room_id=room_id,
        actor_id=None,
        actor_name=None,
        target_type="problem",
        target_id=issue_id,
        target_label=problem.get("issue_number"),
        details={
            "discussion_focus": str(data.discussion_focus)[:100] if data.discussion_focus else None,
            "final_recommendation": data.final_recommendation,
        },
    )

    return {
        "issue_id": issue_id,
        "status": "discussed",
        "participants": discussion["participants"],
        "discussion_focus": discussion["discussion_focus"],
        "proposed_solutions": discussion["proposed_solutions"],
        "votes": discussion["votes"],
        "final_recommendation": discussion["final_recommendation"],
        "discussed_at": discussion["discussed_at"],
        "next_phase": RoomPhase.PLAN_UPDATE.value,
    }


@app.post("/problems/{issue_id}/update-plan")
async def update_plan(issue_id: str, data: PlanUpdateRequest):
    """
    更新方案
    入口: PLAN_UPDATE 状态
    触发: RESUMING 状态
    写入路径：PostgreSQL（plan_updates + plans 版本更新）+ 内存同步
    """
    if issue_id not in _problems:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem = _problems[issue_id]
    room_id = problem["room_id"]
    plan_id = data.plan_id or problem["plan_id"]

    update_record = {
        "plan_id": plan_id,
        "new_version": data.new_version,
        "parent_version": data.parent_version,
        "update_type": data.update_type,
        "description": data.description,
        "changes": data.changes,
        "task_updates": data.task_updates,
        "new_tasks": data.new_tasks,
        "cancelled_tasks": data.cancelled_tasks,
        "created_at": datetime.now().isoformat(),
    }
    _plan_updates[plan_id] = update_record

    # 更新plan版本
    if plan_id in _plans:
        plan = _plans[plan_id]
        plan["current_version"] = data.new_version
        if data.new_version not in plan["versions"]:
            plan["versions"].append(data.new_version)

    # 更新problem状态
    _problems[issue_id]["status"] = "plan_updated"

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_plan_update(
                plan_id=plan_id,
                new_version=data.new_version,
                parent_version=data.parent_version,
                update_type=data.update_type,
                description=data.description,
                changes=data.changes,
                task_updates=data.task_updates,
                new_tasks=data.new_tasks,
                cancelled_tasks=data.cancelled_tasks,
            )
            await crud.add_plan_version(plan_id, data.new_version)
            await crud.update_problem(issue_id, status="plan_updated")
            logger.info(f"[DB] update_plan: plan={plan_id}, new_version={data.new_version}")
        except Exception as e:
            logger.warning(f"[DB] update_plan 失败: {e}")

    # 更新room状态为RESUMING
    if room_id in _rooms:
        _rooms[room_id]["phase"] = RoomPhase.RESUMING.value
        if _db_active:
            try:
                await crud.update_room(room_id, phase=RoomPhase.RESUMING.value)
            except Exception as e:
                logger.warning(f"[DB] update_room RESUMING 失败: {e}")
        await ws_manager.broadcast(room_id, {
            "type": "phase_change",
            "from_phase": RoomPhase.PLAN_UPDATE.value,
            "to_phase": RoomPhase.RESUMING.value,
            "issue_id": issue_id,
            "plan_update": update_record,
        })

    # Return flat response matching design spec and tests
    return {
        "issue_id": issue_id,
        "status": "plan_updated",
        "plan_id": update_record["plan_id"],
        "new_version": update_record["new_version"],
        "parent_version": update_record["parent_version"],
        "update_type": update_record["update_type"],
        "description": update_record["description"],
        "changes": update_record["changes"],
        "task_updates": update_record["task_updates"],
        "new_tasks": update_record["new_tasks"],
        "cancelled_tasks": update_record["cancelled_tasks"],
        "created_at": update_record["created_at"],
        "next_phase": RoomPhase.RESUMING.value,
    }


@app.post("/problems/{issue_id}/resume")
async def resume_execution(issue_id: str, data: ResumingRequest):
    """
    恢复执行
    入口: RESUMING 状态
    触发: EXECUTING 状态
    写入路径：PostgreSQL（resuming_records + plans 状态更新）+ 内存同步
    """
    if issue_id not in _problems:
        raise HTTPException(status_code=404, detail="Problem not found")

    problem = _problems[issue_id]
    room_id = problem["room_id"]
    plan_id = data.plan_id or problem["plan_id"]

    resuming_record = {
        "plan_id": plan_id,
        "new_version": data.new_version,
        "resuming_from_task": data.resuming_from_task,
        "checkpoint": data.checkpoint,
        "resume_instructions": data.resume_instructions,
        "resumed_at": datetime.now().isoformat(),
    }
    _resuming_records[plan_id] = resuming_record

    # 更新problem状态
    _problems[issue_id]["status"] = "resumed"

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_resuming_record(
                plan_id=plan_id,
                new_version=data.new_version,
                resuming_from_task=data.resuming_from_task,
                checkpoint=data.checkpoint,
                resume_instructions=data.resume_instructions,
            )
            await crud.update_plan(plan_id, status=PlanStatus.EXECUTING.value)
            await crud.update_problem(issue_id, status="resumed")
            logger.info(f"[DB] resume_execution: plan={plan_id}")
        except Exception as e:
            logger.warning(f"[DB] resume_execution 失败: {e}")

    # 更新room状态为EXECUTING
    if room_id in _rooms:
        _rooms[room_id]["phase"] = RoomPhase.EXECUTING.value
        if _db_active:
            try:
                await crud.update_room(room_id, phase=RoomPhase.EXECUTING.value)
            except Exception as e:
                logger.warning(f"[DB] update_room EXECUTING 失败: {e}")
        await ws_manager.broadcast(room_id, {
            "type": "phase_change",
            "from_phase": RoomPhase.RESUMING.value,
            "to_phase": RoomPhase.EXECUTING.value,
            "issue_id": issue_id,
            "resuming": resuming_record,
        })

    # 更新plan状态
    if plan_id in _plans:
        _plans[plan_id]["status"] = PlanStatus.EXECUTING

    global _active_issue_id
    _active_issue_id = None

    # Return flat response matching design spec and tests
    return {
        "issue_id": issue_id,
        "status": "resumed",
        "plan_id": plan_id,
        "new_version": resuming_record["new_version"],
        "resuming_from_task": resuming_record["resuming_from_task"],
        "checkpoint": resuming_record["checkpoint"],
        "resume_instructions": resuming_record["resume_instructions"],
        "resumed_at": resuming_record["resumed_at"],
        "next_phase": RoomPhase.EXECUTING.value,
        "message": "恢复执行，可以继续任务",
    }


@app.get("/problems/{issue_id}/analysis")
async def get_problem_analysis(issue_id: str):
    """获取问题分析结果（内存优先，DB兜底）"""
    # Memory first
    if issue_id in _problem_analyses:
        return _problem_analyses[issue_id]
    # DB fallback
    if _db_active:
        try:
            row = await crud.get_problem_analysis(issue_id)
            if row:
                _problem_analyses[issue_id] = row
                return row
        except Exception as e:
            logger.warning(f"[DB] get_problem_analysis fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Analysis not found")


@app.get("/problems/{issue_id}/discussion")
async def get_problem_discussion(issue_id: str):
    """获取问题讨论结果（内存优先，DB兜底）"""
    # Memory first
    if issue_id in _problem_discussions:
        return _problem_discussions[issue_id]
    # DB fallback
    if _db_active:
        try:
            row = await crud.get_problem_discussion(issue_id)
            if row:
                _problem_discussions[issue_id] = row
                return row
        except Exception as e:
            logger.warning(f"[DB] get_problem_discussion fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Discussion not found")


@app.get("/plans/{plan_id}/plan-update")
async def get_plan_update(plan_id: str):
    """获取方案更新记录（内存优先，DB兜底）"""
    # Memory first
    if plan_id in _plan_updates:
        return [_plan_updates[plan_id]]
    # DB fallback
    if _db_active:
        try:
            row = await crud.get_plan_update(plan_id)
            if row:
                _plan_updates[plan_id] = row
                return [row]
        except Exception as e:
            logger.warning(f"[DB] get_plan_update fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Plan update not found")


@app.get("/plans/{plan_id}/resuming")
async def get_resuming_record(plan_id: str):
    """获取恢复执行记录（内存优先，DB兜底）"""
    # Memory first
    if plan_id in _resuming_records:
        return [_resuming_records[plan_id]]
    # DB fallback
    if _db_active:
        try:
            row = await crud.get_resuming_record(plan_id)
            if row:
                _resuming_records[plan_id] = row
                return [row]
        except Exception as e:
            logger.warning(f"[DB] get_resuming_record fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Resuming record not found")


# ========================
# 索引 API（INDEX.md 生成）
# ========================

@app.get("/plans/INDEX.md")
async def get_all_plans_index():
    """
    获取所有方案索引文档
    返回格式: Markdown
    来源: 03-API-Protocol.md §4.1 - 获取总索引
    """
    logger.info("[get_all_plans_index] called")
    import sys
    print("[DEBUG] get_all_plans_index called", flush=True)
    all_plans = list(_plans.values())

    if not all_plans:
        md = """# 方案总索引

> 生成时间: {timestamp}

## 暂无方案记录

尚未创建任何讨论方案。
""".format(timestamp=datetime.now().isoformat())
        return md

    # 按创建时间倒序
    all_plans.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    md = """# 方案总索引

> 生成时间: {timestamp}
> 方案总数: {count}

---

## 方案列表

| # | 方案ID | 标题 | 主题 | 状态 | 当前版本 | 创建时间 |
|---|--------|------|------|------|----------|----------|
""".format(timestamp=datetime.now().isoformat(), count=len(all_plans))

    for i, plan in enumerate(all_plans, 1):
        plan_id = plan.get("plan_id", "")
        title = plan.get("title", "-")
        topic = plan.get("topic", "-")
        status = plan.get("status", "-")
        current_version = plan.get("current_version", "-")
        created_at = plan.get("created_at", "-")[:19] if plan.get("created_at") else "-"

        md += f"| {i} | `{plan_id}` | {title} | {topic} | {status} | {current_version} | {created_at} |\n"

    md += """
---

## 状态说明

| 状态 | 说明 |
|------|------|
| draft | 草稿 |
| initiated | 已发起 |
| in_review | 审批中 |
| approved | 已批准 |
| executing | 执行中 |
| completed | 已完成 |
| cancelled | 已取消 |

## 快速链接

"""
    for plan in all_plans[:20]:  # 最多显示20个链接
        plan_id = plan.get("plan_id", "")
        title = plan.get("title", "未命名")
        md += f"- [{title}](./{plan_id}/INDEX.md)\n"

    if len(all_plans) > 20:
        md += f"\n_...还有 {len(all_plans) - 20} 个方案未显示_\n"

    return md


@app.get("/plans/{plan_id}/INDEX.md")
async def get_plan_index(plan_id: str):
    """
    获取方案索引文档
    返回格式: Markdown
    """
    # FastAPI routes /plans/INDEX.md before /plans/{plan_id}/INDEX.md
    # 但 Starlette 路由匹配可能将 /plans/INDEX.md 路由到 {plan_id} 参数
    # 在此处理特殊 case: plan_id == "INDEX.md" → 重定向到总索引
    import sys
    print(f"[DEBUG] get_plan_index called with plan_id={repr(plan_id)}", flush=True)
    sys.stdout.flush()
    if plan_id == "INDEX.md":
        return await get_all_plans_index()

    logger.info(f"[get_plan_index] plan_id={plan_id!r}")
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]
    issues = [p for p in _problems.values() if p["plan_id"] == plan_id]

    md = f"""# 方案索引: {plan.get('title', '未命名方案')}

## 基本信息

| 字段 | 值 |
|------|-----|
| 方案ID | {plan_id} |
| 主题 | {plan.get('topic', '-')} |
| 状态 | {plan.get('status', '-')} |
| 当前版本 | {plan.get('current_version', '-')} |
| 创建时间 | {plan.get('created_at', '-')} |

## 版本列表

"""
    for v in plan.get("versions", []):
        md += f"- **{v}**: {plan.get('current_version') == v and '当前版本' or '历史版本'}\n"

    md += f"""
## 讨论室列表

"""
    for room in rooms:
        md += f"- Room: `{room['room_id']}` - Phase: {room.get('phase', '-')}\n"

    md += f"""
## 问题列表

"""
    if issues:
        for issue in issues:
            md += f"- [{issue['issue_id']}] {issue.get('title', '未命名问题')} ({issue.get('severity', '-')})\n"
    else:
        md += "- 暂无问题记录\n"

    md += f"""
## 审批状态

"""
    approval = get_approval_status(plan_id)
    if approval.get("status") == "not_started":
        md += "- 审批流尚未启动\n"
    else:
        md += f"- 当前审批级别: {approval.get('current_level_label', '-')}\n"
        md += f"- 审批状态: {approval.get('status', '-')}\n"
        for lvl, data in approval.get("levels", {}).items():
            md += f"  - L{lvl}: {data.get('status', '-')} ({data.get('approver_name') or '待审批'})\n"

    return md


@app.get("/plans/{plan_id}/versions/INDEX.md")
async def get_versions_index(plan_id: str):
    """
    获取版本列表索引文档
    返回格式: Markdown
    来源: 03-API-Protocol.md §4.3 - 获取版本索引
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    versions = plan.get("versions", [])
    current_version = plan.get("current_version", "")

    if not versions:
        md = """# 版本索引: {title}

> 生成时间: {timestamp}

## 暂无版本记录

尚未创建任何版本。
""".format(title=plan.get("title", "未命名方案"), timestamp=datetime.now().isoformat())
        return md

    # 收集每个版本的元数据
    version_rows = []
    for v in versions:
        is_current = (v == current_version)
        # 该版本的问题数
        version_issues = [
            p for p in _problems.values()
            if p["plan_id"] == plan_id and p.get("version") == v
        ]
        # 该版本的讨论室数
        version_rooms = [
            r for r in _rooms.values()
            if r.get("plan_id") == plan_id and r.get("current_version") == v
        ]
        # 该版本的plan_update记录（PostgreSQL）
        plan_update = await crud.get_plan_update(plan_id)
        if plan_update and plan_update.get("new_version") == v:
            update_type = plan_update.get("update_type", "-")
            description = plan_update.get("description", "-")
            parent = plan_update.get("parent_version", "-")
        else:
            update_type = "initial" if v == "v1.0" else "-"
            description = "初始版本" if v == "v1.0" else "-"
            parent = "-" if v == "v1.0" else "-"

        version_rows.append({
            "version": v,
            "is_current": is_current,
            "issue_count": len(version_issues),
            "room_count": len(version_rooms),
            "update_type": update_type,
            "parent_version": parent,
            "description": description,
        })

    md = """# 版本索引: {title}

> 生成时间: {timestamp}
> 版本总数: {count}

---

## 版本列表

| 版本 | 类型 | 父版本 | 问题数 | 讨论室数 | 当前版本 | 说明 |
|------|------|--------|--------|----------|----------|------|
""".format(
        title=plan.get("title", "未命名方案"),
        timestamp=datetime.now().isoformat(),
        count=len(version_rows)
    )

    for row in version_rows:
        current_marker = "**当前**" if row["is_current"] else ""
        md += f"| {row['version']} | {row['update_type']} | {row['parent_version']} | {row['issue_count']} | {row['room_count']} | {current_marker} | {row['description']} |\n"

    md += """
---

## 版本类型说明

| 类型 | 说明 |
|------|------|
| initial | 初始版本 |
| fix | 修复版本 |
| enhancement | 增强版本 |
| major | 重大版本 |

## 快速链接

"""
    for row in version_rows:
        md += f"- [{row['version']}](./{row['version']}/INDEX.md)\n"

    md += f"""
---

## 问题总览

| 版本 | 问题数 | 状态 |
|------|--------|------|
"""
    for row in version_rows:
        status = "⚠️ 有问题" if row["issue_count"] > 0 else "✅ 无问题"
        md += f"| {row['version']} | {row['issue_count']} | {status} |\n"

    return md


@app.get("/plans/{plan_id}/versions")
async def get_plan_versions(plan_id: str):
    """
    获取方案版本列表
    来源: 03-API-Protocol.md §2.3 - 获取版本列表
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    versions = plan.get("versions", [])

    version_list = []
    for v in versions:
        is_current = (v == plan.get("current_version"))
        # 查找该版本对应的room
        version_rooms = [
            r for r in _rooms.values()
            if r.get("plan_id") == plan_id and r.get("current_version") == v
        ]
        # 查找该版本的问题数
        version_issues = [
            p for p in _problems.values()
            if p["plan_id"] == plan_id and p.get("version") == v
        ]
        # 查找该版本的plan_update记录
        plan_update = None
        if _plan_updates.get(plan_id) and _plan_updates[plan_id].get("new_version") == v:
            plan_update = _plan_updates[plan_id]

        version_list.append({
            "version": v,
            "is_current": is_current,
            "phase": version_rooms[0].get("phase") if version_rooms else None,
            "room_count": len(version_rooms),
            "issue_count": len(version_issues),
            "update_type": plan_update.get("update_type") if plan_update else "initial",
            "parent_version": plan_update.get("parent_version") if plan_update else None,
            "description": plan_update.get("description") if plan_update else None,
        })

    return {
        "plan_id": plan_id,
        "title": plan.get("title"),
        "current_version": plan.get("current_version"),
        "versions": version_list,
    }


class VersionCreate(BaseModel):
    """创建新版本请求"""
    parent_version: str = Field(..., description="父版本，如 v1.0")
    type: str = Field(..., description="版本类型: fix | enhancement | major")
    description: str = Field(..., description="版本说明")
    tasks: List[dict] = Field(default_factory=list, description="新版本包含的任务列表")
    decisions: List[dict] = Field(default_factory=list, description="新版本包含的决策列表")


def _calculate_next_version(parent: str, vtype: str) -> str:
    """根据父版本和类型计算新版本号"""
    # 解析版本号，如 v1.3 -> (1, 3)
    ver_str = parent.lstrip("v")
    parts = ver_str.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 1
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        major, minor = 1, 0

    if vtype == "major":
        return f"v{major + 1}.0"
    elif vtype == "enhancement":
        return f"v{major}.{minor + 2}"
    else:  # fix
        return f"v{major}.{minor + 1}"


@app.post("/plans/{plan_id}/versions", status_code=201)
async def create_version(plan_id: str, data: VersionCreate):
    """
    创建新版本
    来源: 03-API-Protocol.md §2.3 - 创建新版本

    创建新版本后：
    - 新版本成为 plan.current_version
    - 创建 plan_updates 记录（decisions 转为 changes）
    - 同步创建新版本的任务到 tasks 表
    """
    # 确保 plan 存在
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    parent_version = data.parent_version

    # 验证父版本存在
    if not _version_exists(plan, parent_version):
        raise HTTPException(status_code=400, detail=f"Parent version '{parent_version}' not found in plan")

    # 计算新版本号
    new_version = _calculate_next_version(parent_version, data.type)

    # 构建 changes（decisions 转为结构化 changes）
    changes = {
        "type": data.type,
        "description": data.description,
        "decisions": data.decisions,
        "tasks": data.tasks,
    }

    # 构建 plan_update 记录
    update_record = {
        "plan_id": plan_id,
        "new_version": new_version,
        "parent_version": parent_version,
        "update_type": data.type,
        "description": data.description,
        "changes": changes,
        "task_updates": [],
        "new_tasks": data.tasks,
        "cancelled_tasks": [],
        "created_at": datetime.now().isoformat(),
    }
    _plan_updates[plan_id] = update_record

    # 更新 plan 内存状态
    plan["current_version"] = new_version
    if new_version not in plan["versions"]:
        plan["versions"].append(new_version)
    plan["updated_at"] = datetime.now().isoformat()

    # PostgreSQL 优先写入
    if _db_active:
        try:
            # 创建 plan_updates 记录
            await crud.create_plan_update(
                plan_id=plan_id,
                new_version=new_version,
                parent_version=parent_version,
                update_type=data.type,
                description=data.description,
                changes=changes,
                task_updates=[],
                new_tasks=data.tasks,
                cancelled_tasks=[],
            )
            # 更新 plan 版本
            await crud.add_plan_version(plan_id, new_version)
            # 同步创建新版本任务
            for task_data in data.tasks:
                task_id = str(uuid.uuid4())
                await crud.create_task(
                    task_id=task_id,
                    plan_id=plan_id,
                    version=new_version,
                    task_number=task_data.get("task_number", 0),
                    title=task_data.get("title", ""),
                    description=task_data.get("description"),
                    owner_id=task_data.get("owner_id"),
                    owner_level=task_data.get("owner_level"),
                    owner_role=task_data.get("owner_role"),
                    priority=task_data.get("priority", "medium"),
                    difficulty=task_data.get("difficulty", "medium"),
                    estimated_hours=task_data.get("estimated_hours"),
                    actual_hours=task_data.get("actual_hours"),
                    progress=task_data.get("progress", 0.0),
                    status=task_data.get("status", "pending"),
                    dependencies=task_data.get("dependencies", []),
                    blocked_by=task_data.get("blocked_by", []),
                    deadline=task_data.get("deadline"),
                    started_at=task_data.get("started_at"),
                    completed_at=task_data.get("completed_at"),
                )
                # 同步到内存
                _tasks.setdefault((plan_id, new_version), {})
                _tasks[(plan_id, new_version)][task_id] = {
                    "task_id": task_id,
                    "plan_id": plan_id,
                    "version": new_version,
                    **task_data,
                }
            logger.info(f"[DB] create_version: plan={plan_id}, new_version={new_version}, tasks={len(data.tasks)}")
        except Exception as e:
            logger.warning(f"[DB] create_version 失败: {e}")

    return {
        "version": new_version,
        "parent_version": parent_version,
        "status": "pending_execution",
        "update_type": data.type,
        "description": data.description,
        "tasks_created": len(data.tasks),
    }


@app.get("/plans/{plan_id}/plan.json")
async def get_plan_json(plan_id: str):
    """
    获取方案完整内容（JSON格式）
    来源: 03-API-Protocol.md §2.2 - 获取方案内容
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]

    # 收集关联的rooms
    rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]

    # 收集关联的问题
    issues = [p for p in _problems.values() if p["plan_id"] == plan_id]

    # 收集所有决策（按版本分组）
    decisions_by_version = {}
    for k, v in _decisions.items():
        if k[0] == plan_id:
            ver = k[1]
            if ver not in decisions_by_version:
                decisions_by_version[ver] = []
            decisions_by_version[ver].append({
                "decision_id": v.get("decision_id"),
                "decision_number": v.get("decision_number"),
                "title": v.get("title"),
                "decision_text": v.get("decision_text"),
                "agreed_by": v.get("agreed_by", []),
                "disagreed_by": v.get("disagreed_by", []),
                "decided_by": v.get("decided_by"),
                "created_at": v.get("created_at"),
            })

    # 收集审批流
    approval = get_approval_status(plan_id)

    # 收集plan_update和resuming
    plan_update = _plan_updates.get(plan_id)
    resuming = _resuming_records.get(plan_id)

    # 收集约束（constraints）和干系人（stakeholders）
    constraints = _constraints.get(plan_id, [])
    stakeholders = _stakeholders.get(plan_id, [])

    return {
        "plan_id": plan["plan_id"],
        "title": plan.get("title"),
        "topic": plan.get("topic"),
        "requirements": plan.get("requirements", []),
        "constraints": constraints,
        "stakeholders": stakeholders,
        "status": plan.get("status"),
        "hierarchy_id": plan.get("hierarchy_id"),
        "current_version": plan.get("current_version"),
        "versions": plan.get("versions", []),
        "created_at": plan.get("created_at"),
        "rooms": [
            {
                "room_id": r["room_id"],
                "phase": r.get("phase"),
                "coordinator_id": r.get("coordinator_id"),
                "current_version": r.get("current_version"),
            }
            for r in rooms
        ],
        "issues": issues,
        "decisions": decisions_by_version,
        "approval": approval if approval.get("status") != "not_started" else None,
        "plan_update": plan_update,
        "resuming": resuming,
    }


@app.get("/plans/{plan_id}/versions/{version}/plan.json")
async def get_version_json(plan_id: str, version: str):
    """
    获取版本完整内容（JSON格式）
    来源: 03-API-Protocol.md §2.3 - 获取版本内容
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # 该版本的rooms
    version_rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]
    current_room = next(
        (r for r in version_rooms if r.get("current_version") == version),
        version_rooms[0] if version_rooms else None
    )

    # 该版本的问题
    version_issues = [p for p in _problems.values() if p["plan_id"] == plan_id and p.get("version") == version]

    # 该版本的快照
    version_snapshots = [
        {"snapshot_id": k[2], "phase": v.get("phase"), "created_at": v.get("created_at")}
        for k, v in _snapshots.items()
        if k[0] == plan_id and k[1] == version
    ]

    # 该版本的决策
    version_decisions = [
        {
            "decision_id": v.get("decision_id"),
            "decision_number": v.get("decision_number"),
            "title": v.get("title"),
            "decision_text": v.get("decision_text"),
            "description": v.get("description"),
            "rationale": v.get("rationale"),
            "agreed_by": v.get("agreed_by", []),
            "disagreed_by": v.get("disagreed_by", []),
            "decided_by": v.get("decided_by"),
            "created_at": v.get("created_at"),
        }
        for k, v in _decisions.items()
        if k[0] == plan_id and k[1] == version
    ]
    version_decisions.sort(key=lambda d: d.get("decision_number", 0))

    # 该版本的圣旨（Edict/L7下行 decree）
    version_edicts = await list_edicts(plan_id, version)

    # plan_update记录（如果这个版本是由更新产生的）
    plan_update = None
    if _plan_updates.get(plan_id) and _plan_updates[plan_id].get("new_version") == version:
        plan_update = _plan_updates[plan_id]

    # resuming记录
    resuming = None
    if _resuming_records.get(plan_id) and _resuming_records[plan_id].get("new_version") == version:
        resuming = _resuming_records[plan_id]

    # 该版本的风险
    version_risks = _risks.get((plan_id, version), [])

    # 该版本的指标（来自 tasks metrics）
    version_metrics = await _get_version_metrics(plan_id, version)

    # 该版本的任务列表（08-Data-Models-Details.md §3.1 Version.content.tasks）
    try:
        task_rows = await crud.list_tasks(plan_id, version)
        version_tasks = [dict(r) for r in task_rows] if task_rows else []
    except Exception as e:
        logger.warning(f"[DB] get_version_json list_tasks failed: {e}")
        key = (plan_id, version)
        version_tasks = list(_tasks.get(key, {}).values())
    version_tasks.sort(key=lambda t: t.get("task_number", 0))

    return {
        "plan_id": plan_id,
        "version": version,
        "is_current": (version == plan.get("current_version")),
        "title": plan.get("title"),
        "topic": plan.get("topic"),
        "requirements": plan.get("requirements", []),
        "status": plan.get("status"),
        "phase": current_room.get("phase") if current_room else None,
        "room_id": current_room.get("room_id") if current_room else None,
        "rooms": [
            {
                "room_id": r["room_id"],
                "phase": r.get("phase"),
                "coordinator_id": r.get("coordinator_id"),
            }
            for r in version_rooms
        ],
        "tasks": version_tasks,
        "decisions": version_decisions,
        "edicts": version_edicts,
        "issues": version_issues,
        "risks": version_risks,
        "snapshots": version_snapshots,
        "metrics": version_metrics,
        "plan_update": plan_update,
        "resuming": resuming,
    }


@app.get("/plans/{plan_id}/versions/{version}/issues/{issue_id}/issue.json")
async def get_issue_json(plan_id: str, version: str, issue_id: str):
    """
    获取问题详情（JSON格式）
    来源: 03-API-Protocol.md §2.5 - 获取问题详情
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    if issue_id not in _problems:
        raise HTTPException(status_code=404, detail="Issue not found")

    issue = _problems[issue_id]
    if issue["plan_id"] != plan_id or issue.get("version") != version:
        raise HTTPException(status_code=404, detail="Issue not found for this version")

    # 收集分析记录
    analysis = _problem_analyses.get(issue_id)

    # 收集讨论记录
    discussion = _problem_discussions.get(issue_id)

    # 收集关联的room
    room_id = issue.get("room_id")
    room = _rooms.get(room_id) if room_id else None

    return {
        "issue_id": issue_id,
        "issue_number": issue.get("issue_number"),
        "plan_id": plan_id,
        "version": version,
        "title": issue.get("title"),
        "description": issue.get("description"),
        "type": issue.get("type"),
        "severity": issue.get("severity"),
        "status": issue.get("status"),
        "detected_by": issue.get("detected_by"),
        "detected_at": issue.get("detected_at"),
        "affected_tasks": issue.get("affected_tasks", []),
        "progress_delay": issue.get("progress_delay", 0),
        "related_context": issue.get("related_context", {}),
        "room_id": room_id,
        "room_phase": room.get("phase") if room else None,
        "analysis": analysis,
        "discussion": discussion,
        "plan_update": _plan_updates.get(plan_id),
        "resuming": _resuming_records.get(plan_id),
    }


@app.get("/plans/{plan_id}/analytics")
async def get_plan_analytics(plan_id: str):
    """
    获取计划分析统计（聚合视图）
    来源: 08-Data-Models-Details.md §2.2 Plan.analytics
    提供 Plan 全局统计：rooms/tasks/decisions/issues/participants/messages/risks/edicts
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    from collections import Counter

    # ── Room 统计 ──────────────────────────────────────────────
    all_rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]
    room_phases = Counter(r.get("phase", "unknown") for r in all_rooms)
    room_stats = {
        "total": len(all_rooms),
        "by_phase": dict(room_phases),
        "active": sum(1 for r in all_rooms if r.get("phase") not in ("completed", "cancelled")),
        "completed": sum(1 for r in all_rooms if r.get("phase") == "completed"),
    }

    # ── Task 统计（所有版本） ───────────────────────────────────
    all_tasks = []
    for ver in plan.get("versions", ["v1.0"]):
        try:
            if _db_active:
                rows = await crud.list_tasks(plan_id, ver)
                all_tasks.extend([dict(r) for r in rows])
            else:
                key = (plan_id, ver)
                all_tasks.extend(list(_tasks.get(key, {}).values()))
        except Exception:
            key = (plan_id, ver)
            all_tasks.extend(list(_tasks.get(key, {}).values()))

    task_status = Counter(t.get("status", "pending") for t in all_tasks)
    task_priority = Counter(t.get("priority", "medium") for t in all_tasks)
    total_est = sum(t.get("estimated_hours") or 0 for t in all_tasks)
    total_act = sum(t.get("actual_hours") or 0 for t in all_tasks)
    completed_tasks = [t for t in all_tasks if t.get("status") == "completed"]
    avg_progress = (
        sum(t.get("progress", 0) for t in all_tasks) / len(all_tasks)
        if all_tasks else 0.0
    )
    task_stats = {
        "total": len(all_tasks),
        "by_status": dict(task_status),
        "by_priority": dict(task_priority),
        "completed": task_status.get("completed", 0),
        "in_progress": task_status.get("in_progress", 0),
        "blocked": task_status.get("blocked", 0),
        "pending": task_status.get("pending", 0),
        "total_estimated_hours": total_est,
        "total_actual_hours": total_act,
        "completion_rate": len(completed_tasks) / len(all_tasks) if all_tasks else 0.0,
        "average_progress": avg_progress,
    }

    # ── Decision 统计（所有版本）────────────────────────────────
    all_decisions = []
    for k, v in _decisions.items():
        if k[0] == plan_id:
            all_decisions.append(v)
    decision_by_version = Counter(k[1] for k in _decisions.keys() if k[0] == plan_id)
    decision_stats = {
        "total": len(all_decisions),
        "by_version": dict(decision_by_version),
        "undecided": sum(1 for d in all_decisions if not d.get("decided_by")),
    }

    # ── Issue 统计（所有版本）──────────────────────────────────
    all_issues = [p for p in _problems.values() if p["plan_id"] == plan_id]
    issue_severity = Counter(i.get("severity", "medium") for i in all_issues)
    issue_status = Counter(i.get("status", "detected") for i in all_issues)
    issue_stats = {
        "total": len(all_issues),
        "by_severity": dict(issue_severity),
        "by_status": dict(issue_status),
        "open": sum(1 for i in all_issues if i.get("status") not in ("resolved", "closed")),
        "resolved": sum(1 for i in all_issues if i.get("status") in ("resolved", "closed")),
    }

    # ── Participant 统计 ────────────────────────────────────────
    all_participants = []
    for r in all_rooms:
        room_id = r.get("room_id")
        try:
            if _db_active:
                rows = await crud.get_participants(room_id)
                all_participants.extend([dict(row) for row in rows])
            else:
                all_participants.extend(_participants.get(room_id, []))
        except Exception:
            all_participants.extend(_participants.get(room_id, []))
    level_dist = Counter(p.get("level", 5) for p in all_participants)
    participant_stats = {
        "total": len(all_participants),
        "by_level": {str(k): v for k, v in dict(level_dist).items()},
    }

    # ── Message 统计 ─────────────────────────────────────────────
    all_messages = []
    for r in all_rooms:
        room_id = r.get("room_id")
        try:
            if _db_active:
                rows = await crud.get_messages(room_id)
                all_messages.extend([dict(row) for row in rows])
            else:
                all_messages.extend(_messages.get(room_id, []))
        except Exception:
            all_messages.extend(_messages.get(room_id, []))
    message_stats = {
        "total": len(all_messages),
        "by_room": {r.get("room_id"): len([m for m in all_messages if m.get("room_id") == r.get("room_id")]) for r in all_rooms},
    }

    # ── Risk 统计 ───────────────────────────────────────────────
    all_risks = []
    for ver in plan.get("versions", ["v1.0"]):
        all_risks.extend(_risks.get((plan_id, ver), []))
    risk_severity = Counter(r.get("severity", "medium") for r in all_risks)
    risk_status = Counter(r.get("status", "identified") for r in all_risks)
    risk_stats = {
        "total": len(all_risks),
        "by_severity": dict(risk_severity),
        "by_status": dict(risk_status),
    }

    # ── Edict 统计 ───────────────────────────────────────────────
    all_edicts = []
    for ver in plan.get("versions", ["v1.0"]):
        try:
            edicts = await list_edicts(plan_id, ver)
            all_edicts.extend(edicts)
        except Exception:
            pass
    edict_status = Counter(e.get("status", "published") for e in all_edicts)
    edict_stats = {
        "total": len(all_edicts),
        "by_status": dict(edict_status),
    }

    # ── Approval 统计 ────────────────────────────────────────────
    approval = get_approval_status(plan_id)

    # ── 汇总 ─────────────────────────────────────────────────────
    return {
        "plan_id": plan_id,
        "title": plan.get("title"),
        "status": plan.get("status"),
        "current_version": plan.get("current_version"),
        "versions": plan.get("versions", []),
        "rooms": room_stats,
        "tasks": task_stats,
        "decisions": decision_stats,
        "issues": issue_stats,
        "participants": participant_stats,
        "messages": message_stats,
        "risks": risk_stats,
        "edicts": edict_stats,
        "approval": approval,
    }


# ========================
# Step 31: Activity Audit Log API
# ========================

@app.get("/activities")
async def list_activities(
    plan_id: Optional[str] = None,
    room_id: Optional[str] = None,
    version: Optional[str] = None,
    action_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    列出活动日志（支持多维过滤）
    来源: Step 31 - Activity Audit Log
    """
    # PostgreSQL 优先
    if _db_active:
        try:
            rows = await crud.list_activities(
                plan_id=plan_id,
                room_id=room_id,
                version=version,
                action_type=action_type,
                actor_id=actor_id,
                limit=limit,
                offset=offset,
            )
            # 同步到内存
            for row in rows:
                r = dict(row)
                if r.get("details") and isinstance(r["details"], str):
                    import json as _json
                    try:
                        r["details"] = _json.loads(r["details"])
                    except Exception:
                        r["details"] = {}
                _activities[r["activity_id"]] = r
                if plan_id and plan_id not in _activity_index:
                    _activity_index[plan_id] = []
                if r["activity_id"] not in (_activity_index.get(plan_id) or []):
                    if plan_id:
                        _activity_index.setdefault(plan_id, []).append(r["activity_id"])
                    if r.get("room_id"):
                        _activity_index.setdefault(r["room_id"], []).append(r["activity_id"])
            return {"activities": rows, "count": len(rows)}
        except Exception as e:
            logger.warning(f"[DB] list_activities fallback: {e}")

    # 内存兜底
    results = []
    for act in _activities.values():
        if plan_id and act.get("plan_id") != plan_id:
            continue
        if room_id and act.get("room_id") != room_id:
            continue
        if version and act.get("version") != version:
            continue
        if action_type and act.get("action_type") != action_type:
            continue
        if actor_id and act.get("actor_id") != actor_id:
            continue
        results.append(act)

    results.sort(key=lambda x: x.get("occurred_at", ""), reverse=True)
    return {
        "activities": results[offset:offset + limit],
        "count": len(results),
    }


@app.get("/plans/{plan_id}/activities")
async def list_plan_activities(
    plan_id: str,
    version: Optional[str] = None,
    action_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """列出计划的所有活动日志"""
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    return await list_activities(
        plan_id=plan_id,
        version=version,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )


@app.get("/plans/{plan_id}/versions/{version}/activities")
async def list_version_activities(
    plan_id: str,
    version: str,
    action_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """列出版本的所有活动日志"""
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    return await list_activities(
        plan_id=plan_id,
        version=version,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )


@app.get("/rooms/{room_id}/activities")
async def list_room_activities(
    room_id: str,
    action_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """列出房间的所有活动日志"""
    if room_id not in _rooms:
        await _sync_room_to_memory(room_id)
    if room_id not in _rooms:
        raise HTTPException(status_code=404, detail="Room not found")

    return await list_activities(
        room_id=room_id,
        action_type=action_type,
        limit=limit,
        offset=offset,
    )


@app.get("/activities/stats")
async def get_activity_stats(
    plan_id: Optional[str] = None,
    by_action_type: bool = True,
    by_actor: bool = True,
):
    """
    获取活动统计（聚合视图）
    来源: Step 31 - Activity Audit Log
    """
    # PostgreSQL 优先
    if _db_active:
        try:
            rows = await crud.list_activities(plan_id=plan_id, limit=10000, offset=0)
            from collections import Counter
            by_type = Counter(a.get("action_type") for a in rows)
            by_act = Counter(a.get("actor_id") for a in rows if a.get("actor_id"))
            total = len(rows)
            return {
                "total": total,
                "by_action_type": dict(by_type),
                "by_actor": dict(by_act) if by_actor else {},
                "plan_id": plan_id,
            }
        except Exception as e:
            logger.warning(f"[DB] get_activity_stats fallback: {e}")

    # 内存兜底
    from collections import Counter
    acts = list(_activities.values())
    if plan_id:
        acts = [a for a in acts if a.get("plan_id") == plan_id]
    by_type = Counter(a.get("action_type") for a in acts)
    by_act = Counter(a.get("actor_id") for a in acts if a.get("actor_id"))
    return {
        "total": len(acts),
        "by_action_type": dict(by_type),
        "by_actor": dict(by_act) if by_actor else {},
        "plan_id": plan_id,
    }


@app.get("/activities/{activity_id}")
async def get_activity(activity_id: str):
    """获取单个活动详情"""
    # 内存优先
    if activity_id in _activities:
        return _activities[activity_id]
    # DB fallback
    if _db_active:
        try:
            row = await crud.get_activity(activity_id)
            if row:
                r = dict(row)
                if r.get("details") and isinstance(r["details"], str):
                    import json as _json
                    r["details"] = _json.loads(r["details"])
                _activities[activity_id] = r
                return r
        except Exception as e:
            logger.warning(f"[DB] get_activity fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Activity not found")


# ============================================================
# Step 34: Notification System
# ============================================================

class NotificationCreate(BaseModel):
    plan_id: Optional[str] = None
    version: Optional[str] = None
    room_id: Optional[str] = None
    task_id: Optional[str] = None
    recipient_id: str
    recipient_level: Optional[int] = None
    type: str  # task_assigned | task_completed | task_blocked | problem_reported | problem_resolved | approval_requested | approval_completed | edict_published | escalation_received
    title: str
    message: Optional[str] = None


class NotificationUpdate(BaseModel):
    read: Optional[bool] = None
    title: Optional[str] = None
    message: Optional[str] = None


# 内存缓存
_notifications: Dict[str, Dict[str, Any]] = {}


async def _sync_notification_to_memory(notification_id: str):
    """同步通知到内存"""
    if notification_id in _notifications:
        return
    try:
        row = await crud.get_notification(notification_id)
        if row:
            _notifications[notification_id] = dict(row)
    except Exception:
        pass


async def _notify(
    recipient_id: str,
    notification_type: str,
    title: str,
    message: Optional[str] = None,
    plan_id: Optional[str] = None,
    version: Optional[str] = None,
    room_id: Optional[str] = None,
    task_id: Optional[str] = None,
    recipient_level: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """内部通知创建辅助函数（不返回HTTP响应）"""
    notification_id = str(uuid.uuid4())
    notification = {
        "notification_id": notification_id,
        "plan_id": plan_id,
        "version": version,
        "room_id": room_id,
        "task_id": task_id,
        "recipient_id": recipient_id,
        "recipient_level": recipient_level,
        "type": notification_type,
        "title": title,
        "message": message,
        "read": False,
        "created_at": datetime.now().isoformat(),
    }
    try:
        row = await crud.create_notification(
            notification_id=notification_id,
            plan_id=plan_id,
            recipient_id=recipient_id,
            recipient_level=recipient_level,
            notification_type=notification_type,
            title=title,
            message=message,
            version=version,
            room_id=room_id,
            task_id=task_id,
        )
        if row:
            notification = dict(row)
    except Exception as e:
        logger.warning(f"[DB] _notify failed: {e}")
    _notifications[notification_id] = notification
    return notification


@app.post("/notifications", status_code=201)
async def create_notification(data: NotificationCreate):
    """
    创建通知
    来源: Step 34 Notification System
    """
    notification_id = str(uuid.uuid4())
    notification = {
        "notification_id": notification_id,
        "plan_id": data.plan_id,
        "version": data.version,
        "room_id": data.room_id,
        "task_id": data.task_id,
        "recipient_id": data.recipient_id,
        "recipient_level": data.recipient_level,
        "type": data.type,
        "title": data.title,
        "message": data.message,
        "read": False,
        "created_at": datetime.now().isoformat(),
    }
    # DB写入
    try:
        row = await crud.create_notification(
            notification_id=notification_id,
            plan_id=data.plan_id,
            recipient_id=data.recipient_id,
            recipient_level=data.recipient_level,
            notification_type=data.type,
            title=data.title,
            message=data.message,
            version=data.version,
            room_id=data.room_id,
            task_id=data.task_id,
        )
        if row:
            notification = dict(row)
            _notifications[notification_id] = notification
    except Exception as e:
        logger.warning(f"[DB] create_notification failed: {e}")
        _notifications[notification_id] = notification

    return notification


@app.get("/notifications")
async def list_notifications(
    recipient_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    room_id: Optional[str] = None,
    type: Optional[str] = None,
    read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    列出通知（支持过滤）
    来源: Step 34 Notification System
    """
    try:
        rows = await crud.list_notifications(
            recipient_id=recipient_id,
            plan_id=plan_id,
            room_id=room_id,
            notification_type=type,
            read=read,
            limit=limit,
            offset=offset,
        )
        return rows
    except Exception as e:
        logger.warning(f"[DB] list_notifications failed: {e}")
        # 内存兜底
        all_notifs = list(_notifications.values())
        if recipient_id:
            all_notifs = [n for n in all_notifs if n.get("recipient_id") == recipient_id]
        if plan_id:
            all_notifs = [n for n in all_notifs if n.get("plan_id") == plan_id]
        if type:
            all_notifs = [n for n in all_notifs if n.get("type") == type]
        if read is not None:
            all_notifs = [n for n in all_notifs if n.get("read") == read]
        all_notifs.sort(key=lambda n: n.get("created_at", ""), reverse=True)
        return all_notifs[offset:offset + limit]


@app.get("/notifications/unread-count")
async def get_unread_notification_count(recipient_id: str):
    """
    获取未读通知数量
    来源: Step 34 Notification System
    """
    try:
        count = await crud.get_unread_notification_count(recipient_id)
        return {"recipient_id": recipient_id, "unread_count": count}
    except Exception as e:
        logger.warning(f"[DB] get_unread_notification_count failed: {e}")
        # 内存兜底
        count = sum(
            1 for n in _notifications.values()
            if n.get("recipient_id") == recipient_id and not n.get("read")
        )
        return {"recipient_id": recipient_id, "unread_count": count}


@app.get("/notifications/{notification_id}")
async def get_notification(notification_id: str):
    """
    获取单个通知详情
    来源: Step 34 Notification System
    """
    # 内存优先
    if notification_id in _notifications:
        return _notifications[notification_id]
    # DB兜底
    try:
        row = await crud.get_notification(notification_id)
        if row:
            notification = dict(row)
            _notifications[notification_id] = notification
            return notification
    except Exception as e:
        logger.warning(f"[DB] get_notification fallback failed: {e}")
    raise HTTPException(status_code=404, detail="Notification not found")


@app.patch("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """
    标记通知为已读
    来源: Step 34 Notification System
    """
    # 内存更新
    if notification_id in _notifications:
        _notifications[notification_id]["read"] = True
        _notifications[notification_id]["read_at"] = datetime.now().isoformat()
    # DB更新
    try:
        row = await crud.mark_notification_read(notification_id)
        if row:
            notification = dict(row)
            _notifications[notification_id] = notification
            return notification
    except Exception as e:
        logger.warning(f"[DB] mark_notification_read failed: {e}")
    raise HTTPException(status_code=404, detail="Notification not found")


@app.patch("/notifications/read-all")
async def mark_all_notifications_read(recipient_id: str):
    """
    标记该接收人的所有通知为已读
    来源: Step 34 Notification System
    """
    updated = 0
    # 内存更新
    for nid, n in _notifications.items():
        if n.get("recipient_id") == recipient_id and not n.get("read"):
            n["read"] = True
            n["read_at"] = datetime.now().isoformat()
            updated += 1
    # DB更新
    try:
        updated = await crud.mark_all_notifications_read(recipient_id)
    except Exception as e:
        logger.warning(f"[DB] mark_all_notifications_read failed: {e}")
    return {"recipient_id": recipient_id, "updated": updated}


@app.delete("/notifications/{notification_id}", status_code=204)
async def delete_notification(notification_id: str):
    """
    删除通知
    来源: Step 34 Notification System
    """
    # 内存删除
    _notifications.pop(notification_id, None)
    # DB删除
    try:
        await crud.delete_notification(notification_id)
    except Exception as e:
        logger.warning(f"[DB] delete_notification failed: {e}")
    return Response(status_code=204)


@app.get("/plans/{plan_id}/versions/{version}/INDEX.md")
async def get_version_index(plan_id: str, version: str):
    """
    获取版本索引文档
    返回格式: Markdown
    """
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]
    issues = [p for p in _problems.values() if p["plan_id"] == plan_id and p.get("version") == version]

    plan_update = _plan_updates.get(plan_id)
    resuming = _resuming_records.get(plan_id)

    md = f"""# 版本索引: {plan.get('title', '未命名方案')} - {version}

## 版本信息

| 字段 | 值 |
|------|-----|
| 方案ID | {plan_id} |
| 版本 | {version} |
| 父版本 | {plan_update.get('parent_version') if plan_update else '-'} |
| 更新类型 | {plan_update.get('update_type') if plan_update else 'initial'} |

## 状态概览

"""
    current_room = next((r for r in rooms if r.get("current_version") == version), rooms[0] if rooms else None)
    if current_room:
        md += f"- 当前阶段: {current_room.get('phase', '-')}\n"
    md += f"- 问题数: {len(issues)}\n"
    if plan_update:
        md += f"- 方案更新: {plan_update.get('description', '-')}\n"
    if resuming:
        md += f"- 恢复检查点: {resuming.get('checkpoint', '-')}\n"

    md += f"""
## 讨论室

"""
    version_rooms = [r for r in rooms if r.get("current_version") == version or not r.get("current_version")]
    for room in version_rooms:
        md += f"- `{room['room_id']}`: {room.get('phase', '-')}\n"

    md += f"""
## 问题记录

"""
    if issues:
        for issue in issues:
            md += f"""### [{issue['issue_id']}] {issue.get('title', '未命名问题')}

- 类型: {issue.get('type', '-')}
- 严重程度: {issue.get('severity', '-')}
- 状态: {issue.get('status', '-')}
- 报告人: {issue.get('detected_by', '-')}
- 检测时间: {issue.get('detected_at', '-')}

"""
    else:
        md += "- 暂无问题记录\n"

    return md


@app.get("/plans/{plan_id}/versions/{version}/rooms/INDEX.md")
async def get_rooms_index(plan_id: str, version: str):
    """
    获取讨论室索引文档
    返回格式: Markdown
    """
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    rooms = [r for r in _rooms.values() if r.get("plan_id") == plan_id]

    md = f"""# 讨论室索引: {plan.get('title', '未命名方案')} - {version}

## 讨论室列表

| Room ID | 阶段 | Coordinator | 创建时间 |
|---------|------|-------------|----------|
"""
    for room in rooms:
        md += f"| `{room['room_id']}` | {room.get('phase', '-')} | {room.get('coordinator_id', '-')} | {room.get('created_at', '-')} |\n"

    md += """
## 阶段说明

| 阶段 | 说明 |
|------|------|
| INITIATED | 已接收发起请求 |
| SELECTING | Coordinator选择参与者 |
| THINKING | 各参与者独立思考 |
| SHARING | 按顺序陈述观点 |
| DEBATE | 自由交叉辩论 |
| CONVERGING | 收敛阶段，整理方案 |
| HIERARCHICAL_REVIEW | 层级审批流程 |
| DECISION | 决策完成 |
| EXECUTING | 执行方案中 |
| COMPLETED | 方案执行完成 |

## 问题处理流程

| 阶段 | 说明 |
|------|------|
| PROBLEM_DETECTED | 检测到问题 |
| PROBLEM_ANALYSIS | 分析问题 |
| PROBLEM_DISCUSSION | 问题讨论 |
| PLAN_UPDATE | 更新方案 |
| RESUMING | 恢复执行 |

"""
    return md


@app.get("/plans/{plan_id}/versions/{version}/issues/INDEX.md")
async def get_issues_index(plan_id: str, version: str):
    """
    获取问题索引文档
    返回格式: Markdown
    """
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    issues = [p for p in _problems.values() if p["plan_id"] == plan_id and p.get("version") == version]

    md = f"""# 问题索引: {plan.get('title', '未命名方案')} - {version}

## 问题汇总

| # | 问题编号 | 问题ID | 标题 | 类型 | 严重程度 | 状态 |
|---|----------|--------|------|------|----------|------|
"""
    for i, issue in enumerate(issues, 1):
        md += f"| {i} | {issue.get('issue_number', '-')} | `{issue['issue_id']}` | {issue.get('title', '-')} | {issue.get('type', '-')} | {issue.get('severity', '-')} | {issue.get('status', '-')} |\n"

    md += """
## 问题详情

"""
    if issues:
        for issue in issues:
            analysis = _problem_analyses.get(issue["issue_id"], {})
            discussion = _problem_discussions.get(issue["issue_id"], {})

            md += f"""### [{issue.get('issue_number', '-')}] {issue.get('title', '未命名问题')}

**问题编号**: {issue.get('issue_number', '-')}
**问题ID**: `{issue['issue_id']}`
**描述**: {issue.get('description', '-')}

**类型**: {issue.get('type', '-')}
**严重程度**: {issue.get('severity', '-')}
**状态**: {issue.get('status', '-')}
**检测人**: {issue.get('detected_by', '-')}
**检测时间**: {issue.get('detected_at', '-')}

"""
            if analysis:
                md += f"""**根因分析**:
- 根因: {analysis.get('root_cause', '-')}
- 置信度: {analysis.get('root_cause_confidence', '-')}
- 影响范围: {analysis.get('impact_scope', '-')}
- 建议方案: {analysis.get('recommended_option', '-') + 1 if analysis.get('solution_options') else '-'}
- 需要讨论: {'是' if analysis.get('requires_discussion') else '否'}

"""
            if discussion:
                md += f"""**讨论记录**:
- 参与者: {', '.join(discussion.get('participants', []) or ['-'])}
- 最终建议: {discussion.get('final_recommendation', '-')}

"""
    else:
        md += "- 暂无问题记录\n"

    return md


# ========================
# 快照管理 API
# ========================

class SnapshotCreate(BaseModel):
    """创建快照"""
    plan_id: str
    version: str
    room_id: str
    phase: str
    context_summary: str
    participants: List[str] = Field(default_factory=list)
    messages_summary: List[dict] = Field(default_factory=list)


@app.post("/plans/{plan_id}/versions/{version}/snapshots/")
async def create_snapshot(plan_id: str, version: str, data: SnapshotCreate):
    """
    创建上下文快照
    用于保存当前讨论状态，以便后续恢复或审计
    写入路径：PostgreSQL（snapshots 表）+ 内存同步
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot_id = str(uuid.uuid4())
    snapshot = {
        "snapshot_id": snapshot_id,
        "plan_id": plan_id,
        "version": version,
        "room_id": data.room_id,
        "phase": data.phase,
        "context_summary": data.context_summary,
        "participants": data.participants,
        "messages_summary": data.messages_summary,
        "created_at": datetime.now().isoformat(),
    }

    # 存储快照（内存）
    key = (plan_id, version, snapshot_id)
    _snapshots[key] = snapshot

    # PostgreSQL 优先写入
    if _db_active:
        try:
            await crud.create_snapshot(
                snapshot_id=snapshot_id,
                plan_id=plan_id,
                version=version,
                room_id=data.room_id,
                phase=data.phase,
                context_summary=data.context_summary,
                participants=data.participants,
                messages_summary=data.messages_summary,
            )
            logger.info(f"[DB] create_snapshot: snapshot={snapshot_id}")
        except Exception as e:
            logger.warning(f"[DB] create_snapshot 失败: {e}")

    return {
        "snapshot_id": snapshot_id,
        "snapshot": snapshot,
    }


@app.get("/plans/{plan_id}/versions/{version}/snapshots/")
async def list_snapshots(plan_id: str, version: str):
    """
    获取快照列表
    读取路径：PostgreSQL 优先，内存回退
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # PostgreSQL 优先读取
    if _db_active:
        try:
            rows = await crud.list_snapshots(plan_id, version)
            # DB + memory merge（解决"读到自己写"的一致性问题）
            # 注意：内存中 snapshot_id 存为 str，DB 返回 uuid.UUID，需统一为 str 比较
            db_ids = {str(r["snapshot_id"]) for r in rows}
            mem_rows = [
                {"snapshot_id": v["snapshot_id"], "phase": v.get("phase"),
                 "context_summary": v.get("context_summary"), "created_at": v.get("created_at")}
                for k, v in _snapshots.items()
                if k[0] == plan_id and k[1] == version and str(k[2]) not in db_ids
            ]
            rows = rows + mem_rows
            return {"snapshots": rows}
        except Exception as e:
            logger.warning(f"[DB] list_snapshots {plan_id}/{version}: {e}")

    # 内存回退
    snapshots = [
        {
            "snapshot_id": v.get("snapshot_id"),
            "phase": v.get("phase"),
            "context_summary": v.get("context_summary"),
            "created_at": v.get("created_at"),
        }
        for k, v in _snapshots.items()
        if k[0] == plan_id and k[1] == version
    ]

    return {"snapshots": snapshots}


@app.get("/plans/{plan_id}/versions/{version}/snapshots/{snapshot_id}.json")
async def get_snapshot(plan_id: str, version: str, snapshot_id: str):
    """
    获取快照详情
    读取路径：PostgreSQL 优先，内存回退
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # PostgreSQL 优先读取
    if _db_active:
        try:
            row = await crud.get_snapshot(plan_id, version, snapshot_id)
            if row:
                return dict(row)
        except Exception as e:
            logger.warning(f"[DB] get_snapshot {snapshot_id}: {e}")

    key = (plan_id, version, snapshot_id)
    if key not in _snapshots:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    return _snapshots[key]


# ========================
# Task Dependency Validation (Step 22)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 dependencies/blocked_by
# 来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
# ========================

class DependencyValidationRequest(BaseModel):
    """验证依赖请求体"""
    dependencies: List[str] = Field(..., description="要验证的依赖任务ID列表")


# ========================
# Task 任务追踪 (Step 16 - 执行层任务追踪)
# 来源: 08-Data-Models-Details.md §3.1 Task模型
# ========================

class TaskCreate(BaseModel):
    """创建任务的请求体"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    owner_id: Optional[str] = None
    owner_level: Optional[int] = Field(default=None, ge=1, le=7)
    owner_role: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    estimated_hours: Optional[float] = Field(default=None, ge=0)
    dependencies: List[str] = Field(default_factory=list)
    deadline: Optional[str] = None


class TaskUpdate(BaseModel):
    """更新任务的请求体"""
    title: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[str] = None
    owner_level: Optional[int] = Field(default=None, ge=1, le=7)
    owner_role: Optional[str] = None
    priority: Optional[str] = Field(default=None, pattern="^(high|medium|low)$")
    difficulty: Optional[str] = None
    estimated_hours: Optional[float] = Field(default=None, ge=0)
    actual_hours: Optional[float] = Field(default=None, ge=0)
    progress: Optional[float] = Field(default=None, ge=0, le=1)
    status: Optional[str] = Field(
        default=None,
        pattern="^(pending|in_progress|completed|blocked|cancelled)$"
    )
    dependencies: Optional[List[str]] = None
    blocked_by: Optional[List[str]] = None
    deadline: Optional[str] = None


class TaskProgressUpdate(BaseModel):
    """更新任务进度的简化请求体"""
    progress: float = Field(..., ge=0, le=1)
    status: Optional[str] = Field(
        default=None,
        pattern="^(pending|in_progress|completed|blocked)$"
    )


# ========================
# Decision 模型
# 来源: 08-Data-Models-Details.md §3.1 Decision模型
# ========================

class DecisionCreate(BaseModel):
    """创建决策的请求体"""
    title: str = Field(..., min_length=1, max_length=200)
    decision_text: str = Field(..., min_length=1)
    description: Optional[str] = None
    rationale: Optional[str] = None
    alternatives_considered: List[str] = Field(default_factory=list)
    agreed_by: List[str] = Field(default_factory=list)
    disagreed_by: List[str] = Field(default_factory=list)
    decided_by: Optional[str] = None
    room_id: Optional[str] = None


class DecisionUpdate(BaseModel):
    """更新决策的请求体"""
    title: Optional[str] = None
    decision_text: Optional[str] = None
    description: Optional[str] = None
    rationale: Optional[str] = None
    alternatives_considered: Optional[List[str]] = None
    agreed_by: Optional[List[str]] = None
    disagreed_by: Optional[List[str]] = None
    decided_by: Optional[str] = None


# ========================
# Edict Models (圣旨/下行 decree from L7)
# 来源: 01-Edict-Reference.md
# ========================

class EdictCreate(BaseModel):
    """创建圣旨的请求体"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    decision_id: Optional[str] = None
    issued_by: str = Field(..., min_length=1)
    effective_from: Optional[datetime] = None
    recipients: List[int] = Field(default_factory=list)  # L1-L7
    status: str = Field(default="published")


class EdictUpdate(BaseModel):
    """更新圣旨的请求体"""
    title: Optional[str] = None
    content: Optional[str] = None
    decision_id: Optional[str] = None
    issued_by: Optional[str] = None
    effective_from: Optional[datetime] = None
    recipients: Optional[List[int]] = None
    status: Optional[str] = None


# ========================
# Step 38: Edict Acknowledgment Models（圣旨签收）
# ========================

class EdictAcknowledgmentCreate(BaseModel):
    """签收圣旨的请求体"""
    acknowledged_by: str = Field(..., min_length=1, description="签收人名称")
    level: int = Field(..., ge=1, le=7, description="L层级 (1-7)")
    comment: Optional[str] = None


class EdictAcknowledgmentResponse(BaseModel):
    """签收记录响应"""
    ack_id: str
    edict_id: str
    plan_id: str
    version: str
    acknowledged_by: str
    level: int
    comment: Optional[str]
    acknowledged_at: str


# ========================
# Task Comments & Checkpoints (Step 21)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 comments/checkpoints
# ========================

class TaskCommentCreate(BaseModel):
    """创建任务评论"""
    author_id: Optional[str] = None
    author_name: str = Field(..., min_length=1)
    author_level: Optional[int] = Field(default=None, ge=1, le=7)
    content: str = Field(..., min_length=1)


class TaskCommentUpdate(BaseModel):
    """更新任务评论"""
    content: str = Field(..., min_length=1)


class TaskCheckpointCreate(BaseModel):
    """创建任务检查点"""
    name: str = Field(..., min_length=1, max_length=200)


class TaskCheckpointUpdate(BaseModel):
    """更新任务检查点"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[str] = Field(default=None, pattern="^(pending|completed)$")


# ========================
# SubTask 模型 (Step 23)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
# ========================

class SubTaskCreate(BaseModel):
    """创建子任务"""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = Field(default="pending", pattern="^(pending|in_progress|completed|cancelled)$")


class SubTaskUpdate(BaseModel):
    """更新子任务"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(pending|in_progress|completed|cancelled)$")
    progress: Optional[float] = Field(default=None, ge=0, le=1)


@app.post("/plans/{plan_id}/versions/{version}/tasks", status_code=201)
async def create_task(plan_id: str, version: str, data: TaskCreate):
    """
    为指定版本创建任务
    来源: 08-Data-Models-Details.md §3.1 Task模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # Get current max task_number - always try DB first
    task_number = 1
    try:
        rows = await crud.list_tasks(plan_id, version)
        task_number = max([t.get("task_number", 0) for t in rows], default=0) + 1
    except Exception as e:
        logger.warning(f"[DB] list_tasks for task_number failed: {e}")
        # Fallback to memory
        key = (plan_id, version)
        if key in _tasks:
            task_number = max([t.get("task_number", 0) for t in _tasks[key].values()], default=0) + 1

    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "plan_id": plan_id,
        "version": version,
        "task_number": task_number,
        "title": data.title,
        "description": data.description,
        "owner_id": data.owner_id,
        "owner_level": data.owner_level,
        "owner_role": data.owner_role,
        "priority": data.priority,
        "difficulty": data.difficulty,
        "estimated_hours": data.estimated_hours,
        "dependencies": data.dependencies,
        "deadline": data.deadline,
    }

    # Always try DB first - _db_active might be False due to startup issues
    try:
        row = await crud.create_task(**task_data)
        task = dict(row)
        # 同步到内存并评估blocked状态
        key = (plan_id, version)
        _tasks.setdefault(key, {})
        _tasks[key][task_id] = task
        # 评估blocked状态（检查依赖是否完成）
        task = _evaluate_and_update_blocked_status(task, plan_id, version)
        _tasks[key][task_id] = task
        # 如果blocked_by不为空，更新DB
        if task.get("blocked_by"):
            await crud.update_task(task_id, blocked_by=task["blocked_by"])
            if task.get("status") == "blocked":
                await crud.update_task(task_id, status="blocked")

        # Step 31: Activity Log
        await log_activity(
            plan_id=plan_id,
            action_type=ActivityType.TASK_CREATED,
            version=version,
            actor_id=data.owner_id,
            actor_name=data.owner_role,
            target_type="task",
            target_id=task_id,
            target_label=f"T{task_number}",
            details={
                "title": data.title,
                "priority": data.priority,
                "owner_role": data.owner_role,
                "estimated_hours": data.estimated_hours,
            },
        )
        # Step 34: Notification - notify owner of new task assignment
        if task.get("owner_id") and task.get("title"):
            await _notify(
                recipient_id=task["owner_id"],
                notification_type="task_assigned",
                title=f"新任务分配: {task['title']}",
                message=f"你被分配了任务 [{task.get('owner_role', '未指定')}] {task['title']}，优先级: {task.get('priority', 'medium')}",
                plan_id=plan_id,
                version=version,
                task_id=task_id,
                recipient_level=task.get("owner_level"),
            )
        return task
    except Exception as e:
        logger.warning(f"[DB] create_task failed: {e}, falling back to memory")

    # 内存兜底
    key = (plan_id, version)
    if key not in _tasks:
        _tasks[key] = {}
    _tasks[key][task_id] = {
        "task_id": task_id,
        "plan_id": plan_id,
        "version": version,
        "task_number": task_number,
        "title": data.title,
        "description": data.description,
        "owner_id": data.owner_id,
        "owner_level": data.owner_level,
        "owner_role": data.owner_role,
        "priority": data.priority,
        "difficulty": data.difficulty,
        "estimated_hours": data.estimated_hours,
        "actual_hours": None,
        "progress": 0,
        "status": "pending",
        "dependencies": data.dependencies,
        "blocked_by": [],
        "deadline": data.deadline,
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    # 评估blocked状态
    _tasks[key][task_id] = _evaluate_and_update_blocked_status(_tasks[key][task_id], plan_id, version)
    # Step 31: Activity Log (memory fallback path)
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.TASK_CREATED,
        version=version,
        actor_id=data.owner_id,
        actor_name=data.owner_role,
        target_type="task",
        target_id=task_id,
        target_label=f"T{task_number}",
        details={"title": data.title, "priority": data.priority, "owner_role": data.owner_role},
    )
    return _tasks[key][task_id]


@app.get("/plans/{plan_id}/versions/{version}/tasks")
async def list_tasks(plan_id: str, version: str):
    """
    列出指定版本的所有任务
    来源: 08-Data-Models-Details.md §3.1 Task模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # Always try DB first - _db_active might be False due to startup issues
    try:
        rows = await crud.list_tasks(plan_id, version)
        if rows:
            return {"plan_id": plan_id, "version": version, "tasks": [dict(r) for r in rows]}
    except Exception as e:
        logger.warning(f"[DB] list_tasks failed: {e}")

    key = (plan_id, version)
    tasks = list(_tasks.get(key, {}).values())
    tasks.sort(key=lambda t: t.get("task_number", 0))
    return {"plan_id": plan_id, "version": version, "tasks": tasks}


@app.get("/plans/{plan_id}/versions/{version}/tasks/metrics")
async def get_task_metrics_endpoint(plan_id: str, version: str):
    """获取任务统计指标"""
    return await get_task_metrics(plan_id, version)


@app.post("/plans/{plan_id}/versions/{version}/tasks/validate-dependencies")
async def validate_task_dependencies_endpoint(plan_id: str, version: str, data: DependencyValidationRequest):
    """验证任务依赖列表的有效性"""
    return await validate_task_dependencies(plan_id, version, data)


@app.get("/plans/{plan_id}/versions/{version}/tasks/dependency-graph")
async def get_task_dependency_graph_endpoint(plan_id: str, version: str):
    """获取任务依赖关系图"""
    return await get_task_dependency_graph(plan_id, version)


@app.get("/plans/{plan_id}/versions/{version}/tasks/blocked")
async def get_blocked_tasks_endpoint(plan_id: str, version: str):
    """获取所有被阻塞的任务列表"""
    return await get_blocked_tasks(plan_id, version)


@app.get("/plans/{plan_id}/versions/{version}/tasks/{task_id}")
async def get_task(plan_id: str, version: str, task_id: str):
    """获取单个任务详情"""
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Always try DB first - _db_active might be False due to startup issues
    # but data may still exist in PostgreSQL from previous sessions
    try:
        row = await crud.get_task(task_id)
        if row and row["plan_id"] == plan_id and row["version"] == version:
            return dict(row)
    except Exception as e:
        logger.warning(f"[DB] get_task failed: {e}")

    # Fallback to memory
    key = (plan_id, version)
    if task_id not in _tasks.get(key, {}):
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[key][task_id]


@app.patch("/plans/{plan_id}/versions/{version}/tasks/{task_id}")
async def update_task(plan_id: str, version: str, task_id: str, data: TaskUpdate):
    """
    更新任务字段
    来源: 08-Data-Models-Details.md §3.1 Task模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    update_fields = data.model_dump(exclude_unset=True)
    if not update_fields:
        return await get_task(plan_id, version, task_id)

    # Always try DB first
    try:
        row = await crud.update_task(task_id, **update_fields)
        if row:
            task = dict(row)
            # 如果dependencies变化，重新评估blocked状态
            if "dependencies" in update_fields:
                task = _evaluate_and_update_blocked_status(task, plan_id, version)
                await crud.update_task(task_id, blocked_by=task["blocked_by"], status=task["status"])
            return task
    except Exception as e:
        logger.warning(f"[DB] update_task failed: {e}")

    # 内存兜底
    key = (plan_id, version)
    if task_id not in _tasks.get(key, {}):
        raise HTTPException(status_code=404, detail="Task not found")

    _tasks[key][task_id].update(update_fields)
    _tasks[key][task_id]["updated_at"] = datetime.now().isoformat()
    
    # 如果dependencies变化，重新评估blocked状态
    if "dependencies" in update_fields:
        _tasks[key][task_id] = _evaluate_and_update_blocked_status(_tasks[key][task_id], plan_id, version)
    
    return _tasks[key][task_id]


@app.patch("/plans/{plan_id}/versions/{version}/tasks/{task_id}/progress")
async def update_task_progress(plan_id: str, version: str, task_id: str, data: TaskProgressUpdate):
    """
    快捷更新任务进度
    来源: 08-Data-Models-Details.md §4.1 EXECUTING 进度跟踪
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    # 检查是否是完成操作
    is_completing = data.status == "completed" or (data.progress >= 1.0 and data.progress > 0)
    
    # 获取当前任务状态（用于比较）
    current_task = _get_task(task_id, plan_id, version)
    was_completed = current_task and current_task.get("status") == "completed"

    if _db_active:
        try:
            row = await crud.update_task_progress(task_id, data.progress, data.status)
            if row:
                task = dict(row)
                # 同步到内存
                key = (plan_id, version)
                _tasks.setdefault(key, {})
                _tasks[key][task_id] = task
                
                # 如果任务完成，触发blocked状态更新
                if is_completing and not was_completed:
                    affected = await _on_task_completed(task_id, plan_id, version)
                    task["_affected_tasks"] = affected
                    # Step 34: Notification - notify owner of task completion
                    if task.get("owner_id"):
                        await _notify(
                            recipient_id=task["owner_id"],
                            notification_type="task_completed",
                            title=f"任务已完成: {task['title']}",
                            message=f"任务 [{task.get('owner_role', '')}] {task['title']} 已标记为完成",
                            plan_id=plan_id,
                            version=version,
                            task_id=task_id,
                            recipient_level=task.get("owner_level"),
                        )
                
                return task
        except Exception as e:
            logger.warning(f"[DB] update_task_progress failed: {e}")

    # 内存兜底
    key = (plan_id, version)
    if task_id not in _tasks.get(key, {}):
        raise HTTPException(status_code=404, detail="Task not found")

    task = _tasks[key][task_id]
    task["progress"] = data.progress
    if data.status:
        task["status"] = data.status
    if data.progress > 0 and not task.get("started_at"):
        task["started_at"] = datetime.now().isoformat()
    if is_completing:
        task["completed_at"] = datetime.now().isoformat()
        task["progress"] = 1.0
        task["status"] = "completed"
    task["updated_at"] = datetime.now().isoformat()
    
    # 如果任务完成，触发blocked状态更新
    if is_completing and not was_completed:
        affected = await _on_task_completed(task_id, plan_id, version)
        task["_affected_tasks"] = affected
    
    return task


async def get_task_metrics(plan_id: str, version: str):
    """
    获取任务统计指标
    来源: 08-Data-Models-Details.md §3.1 tasks.metrics
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    if _db_active:
        try:
            metrics = await crud.get_task_metrics(plan_id, version)
            return {
                "plan_id": plan_id,
                "version": version,
                **metrics,
            }
        except Exception as e:
            logger.warning(f"[DB] get_task_metrics failed: {e}")

    # 内存兜底
    key = (plan_id, version)
    tasks = list(_tasks.get(key, {}).values())
    if not tasks:
        return {
            "plan_id": plan_id,
            "version": version,
            "total": 0,
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
            "cancelled": 0,
            "total_estimated_hours": 0,
            "total_actual_hours": 0,
            "progress_percentage": 0.0,
        }

    from collections import Counter
    status_counts = Counter(t.get("status", "pending") for t in tasks)
    total_est = sum(t.get("estimated_hours") or 0 for t in tasks)
    total_act = sum(t.get("actual_hours") or 0 for t in tasks)
    completed_progress = sum(t.get("progress", 0) for t in tasks if t.get("status") == "completed")

    return {
        "plan_id": plan_id,
        "version": version,
        "total": len(tasks),
        "pending": status_counts.get("pending", 0),
        "in_progress": status_counts.get("in_progress", 0),
        "completed": status_counts.get("completed", 0),
        "blocked": status_counts.get("blocked", 0),
        "cancelled": status_counts.get("cancelled", 0),
        "total_estimated_hours": total_est,
        "total_actual_hours": total_act,
        "progress_percentage": completed_progress / max(len(tasks), 1),
    }


# ========================
# Task Dependency Validation API (Step 22)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 dependencies/blocked_by
# 来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
# ========================

async def validate_task_dependencies(plan_id: str, version: str, data: DependencyValidationRequest):
    """
    验证任务依赖列表的有效性
    - 检查依赖任务是否存在
    - 检查依赖任务是否属于同一版本
    - 检查循环依赖
    
    来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    result = _validate_dependencies(data.dependencies, plan_id, version)
    return result


async def get_task_dependency_graph(plan_id: str, version: str):
    """
    获取任务的依赖关系图
    返回所有任务及其依赖关系，用于可视化blocked状态
    
    来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    all_tasks = _list_tasks_sync(plan_id, version)
    
    # 构建依赖图
    nodes = []
    edges = []
    blocked_task_ids = set()
    
    for task in all_tasks:
        task_id = task["task_id"]
        blocked_by = task.get("blocked_by", [])
        dependencies = task.get("dependencies", [])

        # 兼容DB存储的JSON字符串格式（double-encode问题）
        if isinstance(dependencies, str):
            import json as _json
            try:
                dependencies = _json.loads(dependencies)
            except Exception:
                dependencies = []
        if isinstance(blocked_by, str):
            import json as _json
            try:
                blocked_by = _json.loads(blocked_by)
            except Exception:
                blocked_by = []

        if blocked_by:
            blocked_task_ids.add(task_id)

        nodes.append({
            "task_id": task_id,
            "task_number": task.get("task_number"),
            "title": task.get("title"),
            "status": task.get("status"),
            "blocked_by": blocked_by,
            "dependencies": dependencies,
            "is_blocked": len(blocked_by) > 0,
        })

        for dep_id in dependencies:
            if isinstance(dep_id, str):
                edges.append({
                    "from": dep_id,
                    "to": task_id,
                    "type": "depends_on",
                })
    
    return {
        "plan_id": plan_id,
        "version": version,
        "nodes": nodes,
        "edges": edges,
        "blocked_task_count": len(blocked_task_ids),
        "total_tasks": len(all_tasks),
    }


async def get_blocked_tasks(plan_id: str, version: str):
    """
    获取所有被阻塞的任务列表
    
    来源: 07-State-Machine-Details.md §4.1 EXECUTING blockers
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    all_tasks = _list_tasks_sync(plan_id, version)
    
    blocked_tasks = []
    for task in all_tasks:
        blocked_by = task.get("blocked_by", [])
        if blocked_by:
            # 获取blocking任务的详细信息
            blocking_tasks = []
            for blocker_id in blocked_by:
                blocker = _get_task(blocker_id, plan_id, version)
                if blocker:
                    blocking_tasks.append({
                        "task_id": blocker_id,
                        "task_number": blocker.get("task_number"),
                        "title": blocker.get("title"),
                        "status": blocker.get("status"),
                    })
            
            blocked_tasks.append({
                "task_id": task["task_id"],
                "task_number": task.get("task_number"),
                "title": task.get("title"),
                "status": task.get("status"),
                "blocked_by": blocked_by,
                "blocking_tasks": blocking_tasks,
            })
    
    return {
        "plan_id": plan_id,
        "version": version,
        "blocked_count": len(blocked_tasks),
        "blocked_tasks": blocked_tasks,
    }


# ========================
# Decision 端点
# 来源: 08-Data-Models-Details.md §3.1 Decision模型
# ========================

@app.post("/plans/{plan_id}/versions/{version}/decisions", status_code=201)
async def create_decision(plan_id: str, version: str, data: DecisionCreate):
    """
    为指定版本创建决策
    来源: 08-Data-Models-Details.md §3.1 Decision模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # 获取当前最大 decision_number
    decisions = await crud.list_decisions(plan_id, version) if _db_active else []
    decision_number = max([d.get("decision_number", 0) for d in decisions], default=0) + 1

    decision_id = str(uuid.uuid4())
    decision_data = {
        "decision_id": decision_id,
        "plan_id": plan_id,
        "version": version,
        "decision_number": decision_number,
        "title": data.title,
        "decision_text": data.decision_text,
        "description": data.description,
        "rationale": data.rationale,
        "alternatives_considered": data.alternatives_considered,
        "agreed_by": data.agreed_by,
        "disagreed_by": data.disagreed_by,
        "decided_by": data.decided_by,
        "room_id": data.room_id,
        "created_at": datetime.now().isoformat(),
    }

    # 内存写入
    key = (plan_id, version, decision_id)
    _decisions[key] = decision_data

    # PostgreSQL 写入
    if _db_active:
        try:
            await crud.create_decision(
                decision_id=decision_id,
                plan_id=plan_id,
                version=version,
                decision_number=decision_number,
                title=data.title,
                decision_text=data.decision_text,
                description=data.description,
                rationale=data.rationale,
                alternatives_considered=data.alternatives_considered,
                agreed_by=data.agreed_by,
                disagreed_by=data.disagreed_by,
                decided_by=data.decided_by,
                room_id=data.room_id,
            )
            logger.info(f"[DB] create_decision: decision_id={decision_id}")
        except Exception as e:
            logger.warning(f"[DB] create_decision 失败: {e}")

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.DECISION_CREATED,
        version=version,
        actor_id=data.decided_by,
        actor_name=None,
        target_type="decision",
        target_id=decision_id,
        target_label=f"D{decision_number}",
        details={"title": data.title, "decision_text": data.decision_text, "room_id": data.room_id},
    )

    return {"decision_id": decision_id, "decision": decision_data}


@app.get("/plans/{plan_id}/versions/{version}/decisions")
async def list_decisions(plan_id: str, version: str):
    """
    列出指定版本的所有决策
    来源: 08-Data-Models-Details.md §3.1 Decision模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # PostgreSQL 优先
    if _db_active:
        try:
            rows = await crud.list_decisions(plan_id, version)
            decisions = []
            for row in rows:
                d = dict(row)
                # JSONB 字段解析
                for field in ("alternatives_considered", "agreed_by", "disagreed_by"):
                    if field in d and isinstance(d[field], str):
                        import json as _json
                        try:
                            d[field] = _json.loads(d[field])
                        except Exception:
                            d[field] = []
                decisions.append(d)
            return {"decisions": decisions}
        except Exception as e:
            logger.warning(f"[DB] list_decisions {plan_id}/{version}: {e}")

    # 内存兜底
    decisions = [
        {
            "decision_id": v.get("decision_id"),
            "decision_number": v.get("decision_number"),
            "title": v.get("title"),
            "decision_text": v.get("decision_text"),
            "description": v.get("description"),
            "rationale": v.get("rationale"),
            "alternatives_considered": v.get("alternatives_considered", []),
            "agreed_by": v.get("agreed_by", []),
            "disagreed_by": v.get("disagreed_by", []),
            "decided_by": v.get("decided_by"),
            "room_id": v.get("room_id"),
            "created_at": v.get("created_at"),
        }
        for k, v in _decisions.items()
        if k[0] == plan_id and k[1] == version
    ]
    decisions.sort(key=lambda d: d.get("decision_number", 0))
    return {"decisions": decisions}


@app.get("/plans/{plan_id}/versions/{version}/decisions/{decision_id}")
async def get_decision(plan_id: str, version: str, decision_id: str):
    """
    获取单个决策详情
    来源: 08-Data-Models-Details.md §3.1 Decision模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    key = (plan_id, version, decision_id)

    # PostgreSQL 优先
    if _db_active:
        try:
            row = await crud.get_decision(decision_id)
            if row and row.get("plan_id") == plan_id and row.get("version") == version:
                d = dict(row)
                for field in ("alternatives_considered", "agreed_by", "disagreed_by"):
                    if field in d and isinstance(d[field], str):
                        import json as _json
                        try:
                            d[field] = _json.loads(d[field])
                        except Exception:
                            d[field] = []
                return {"decision": d}
        except Exception as e:
            logger.warning(f"[DB] get_decision {decision_id}: {e}")

    # 内存兜底
    if key in _decisions:
        return {"decision": _decisions[key]}

    raise HTTPException(status_code=404, detail="Decision not found")


@app.patch("/plans/{plan_id}/versions/{version}/decisions/{decision_id}")
async def update_decision(
    plan_id: str, version: str, decision_id: str, data: DecisionUpdate
):
    """
    更新决策字段
    来源: 08-Data-Models-Details.md §3.1 Decision模型
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    key = (plan_id, version, decision_id)

    # PostgreSQL 优先
    if _db_active:
        try:
            fields = {k: v for k, v in data.model_dump().items() if v is not None}
            if fields:
                updated = await crud.update_decision(decision_id, **fields)
                if updated and updated.get("plan_id") == plan_id and updated.get("version") == version:
                    d = dict(updated)
                    for field in ("alternatives_considered", "agreed_by", "disagreed_by"):
                        if field in d and isinstance(d[field], str):
                            import json as _json
                            try:
                                d[field] = _json.loads(d[field])
                            except Exception:
                                d[field] = []
                    # 同步内存
                    _decisions[key] = d
                    return {"decision": d}
        except Exception as e:
            logger.warning(f"[DB] update_decision {decision_id}: {e}")

    # 内存兜底
    if key in _decisions:
        for fld, val in data.model_dump().items():
            if val is not None:
                _decisions[key][fld] = val
        return {"decision": _decisions[key]}

    raise HTTPException(status_code=404, detail="Decision not found")


# ========================
# Edict API (圣旨/下行 decree from L7)
# 来源: 01-Edict-Reference.md
# ========================

@app.post("/plans/{plan_id}/versions/{version}/edicts", status_code=201)
async def create_edict(plan_id: str, version: str, data: EdictCreate):
    """
    创建圣旨（L7正式颁布的政令，下行至各层级执行）
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    edict_id = str(uuid.uuid4())

    # 获取当前最大 edict_number
    edicts = await list_edicts(plan_id, version)
    edict_number = max([d.get("edict_number", 0) for d in edicts], default=0) + 1

    edict_data = {
        "edict_id": edict_id,
        "plan_id": plan_id,
        "version": version,
        "edict_number": edict_number,
        "title": data.title,
        "content": data.content,
        "decision_id": data.decision_id,
        "issued_by": data.issued_by,
        "issued_at": datetime.now().isoformat(),
        "effective_from": data.effective_from.isoformat() if data.effective_from else None,
        "recipients": data.recipients,
        "status": data.status,
    }

    key = (plan_id, version, edict_id)

    # PostgreSQL 优先
    if _db_active:
        try:
            row = await crud.create_edict(
                edict_id=edict_id,
                plan_id=plan_id,
                version=version,
                edict_number=edict_number,
                title=data.title,
                content=data.content,
                decision_id=data.decision_id,
                issued_by=data.issued_by,
                effective_from=data.effective_from,
                recipients=data.recipients,
                status=data.status,
            )
            if row:
                d = dict(row)
                for field in ("recipients",):
                    if field in d and isinstance(d[field], str):
                        import json as _json
                        try:
                            d[field] = _json.loads(d[field])
                        except Exception:
                            d[field] = []
                _edicts[key] = d
                logger.info(f"[DB] create_edict: edict_id={edict_id}")
                return {"edict": d}
        except Exception as e:
            logger.warning(f"[DB] create_edict 失败: {e}")

    # 内存兜底
    _edicts[key] = edict_data

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.EDICT_ISSUED,
        version=version,
        actor_id=data.issued_by,
        actor_name=None,
        target_type="edict",
        target_id=edict_id,
        target_label=f"EDICT-{edict_number}",
        details={
            "title": data.title,
            "content": data.content[:100] if data.content else None,
            "recipients": data.recipients,
            "decision_id": data.decision_id,
        },
    )

    return {"edict": edict_data}


async def list_edicts(plan_id: str, version: str) -> List[Dict[str, Any]]:
    """列出指定版本的所有圣旨（内部函数）"""
    # PostgreSQL 优先
    if _db_active:
        try:
            rows = await crud.list_edicts(plan_id, version)
            if rows:
                result = []
                for row in rows:
                    d = dict(row)
                    for field in ("recipients",):
                        if field in d and isinstance(d[field], str):
                            import json as _json
                            try:
                                d[field] = _json.loads(d[field])
                            except Exception:
                                d[field] = []
                    result.append(d)
                # 同步内存
                for d in result:
                    key = (plan_id, version, d["edict_id"])
                    _edicts[key] = d
                return result
        except Exception as e:
            logger.warning(f"[DB] list_edicts {plan_id}/{version}: {e}")

    # 内存兜底
    return [
        d for k, d in _edicts.items()
        if k[0] == plan_id and k[1] == version
    ]


@app.get("/plans/{plan_id}/versions/{version}/edicts")
async def get_edicts(plan_id: str, version: str):
    """
    列出指定版本的所有圣旨
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    edicts = await list_edicts(plan_id, version)
    edicts.sort(key=lambda d: d.get("edict_number", 0))
    return {"edicts": edicts, "count": len(edicts)}


@app.get("/plans/{plan_id}/versions/{version}/edicts/{edict_id}")
async def get_edict(plan_id: str, version: str, edict_id: str):
    """
    获取单个圣旨详情
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    key = (plan_id, version, edict_id)

    # PostgreSQL 优先
    if _db_active:
        try:
            row = await crud.get_edict(edict_id)
            if row and row.get("plan_id") == plan_id and row.get("version") == version:
                d = dict(row)
                for field in ("recipients",):
                    if field in d and isinstance(d[field], str):
                        import json as _json
                        try:
                            d[field] = _json.loads(d[field])
                        except Exception:
                            d[field] = []
                # 加载签收统计
                try:
                    ack_rows = await crud.list_edict_acknowledgments(edict_id)
                    d["acknowledgments"] = ack_rows
                    d["acknowledgment_count"] = len(ack_rows)
                except Exception:
                    d["acknowledgments"] = []
                    d["acknowledgment_count"] = 0
                _edicts[key] = d
                return {"edict": d}
        except Exception as e:
            logger.warning(f"[DB] get_edict {edict_id}: {e}")

    # 内存兜底
    if key in _edicts:
        d = dict(_edicts[key])
        # 加载签收统计
        acks = [a for a in _edict_acks.values() if a.get("edict_id") == edict_id]
        d["acknowledgments"] = acks
        d["acknowledgment_count"] = len(acks)
        return {"edict": d}

    raise HTTPException(status_code=404, detail="Edict not found")


@app.patch("/plans/{plan_id}/versions/{version}/edicts/{edict_id}")
async def update_edict(plan_id: str, version: str, edict_id: str, data: EdictUpdate):
    """
    更新圣旨字段
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    key = (plan_id, version, edict_id)

    # PostgreSQL 优先
    if _db_active:
        try:
            fields = {k: v for k, v in data.model_dump().items() if v is not None}
            if fields:
                updated = await crud.update_edict(edict_id, **fields)
                if updated and updated.get("plan_id") == plan_id and updated.get("version") == version:
                    d = dict(updated)
                    for field in ("recipients",):
                        if field in d and isinstance(d[field], str):
                            import json as _json
                            try:
                                d[field] = _json.loads(d[field])
                            except Exception:
                                d[field] = []
                    _edicts[key] = d
                    return {"edict": d}
        except Exception as e:
            logger.warning(f"[DB] update_edict {edict_id}: {e}")

    # 内存兜底
    if key in _edicts:
        for fld, val in data.model_dump().items():
            if val is not None:
                _edicts[key][fld] = val
        return {"edict": _edicts[key]}

    raise HTTPException(status_code=404, detail="Edict not found")


@app.delete("/plans/{plan_id}/versions/{version}/edicts/{edict_id}", status_code=204)
async def delete_edict(plan_id: str, version: str, edict_id: str):
    """
    删除圣旨
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    key = (plan_id, version, edict_id)

    # PostgreSQL 优先
    if _db_active:
        try:
            deleted = await crud.delete_edict(edict_id)
            if deleted:
                if key in _edicts:
                    del _edicts[key]
                return None
        except Exception as e:
            logger.warning(f"[DB] delete_edict {edict_id}: {e}")

    # 内存兜底
    if key in _edicts:
        del _edicts[key]
        return None

    raise HTTPException(status_code=404, detail="Edict not found")


# ========================
# Step 38: Edict Acknowledgment API（圣旨签收）
# ========================

_edict_acks: dict = {}  # ack_id -> ack_data


@app.post("/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments", status_code=201)
async def create_edict_acknowledgment(
    plan_id: str, version: str, edict_id: str, data: EdictAcknowledgmentCreate
):
    """
    签收圣旨（接收方确认收到）
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    key = (plan_id, version, edict_id)

    # 确认 edict 存在
    edict = None
    if key in _edicts:
        edict = _edicts[key]
    if _db_active:
        try:
            row = await crud.get_edict(edict_id)
            if row and row.get("plan_id") == plan_id and row.get("version") == version:
                edict = dict(row)
        except Exception:
            pass
    if not edict:
        raise HTTPException(status_code=404, detail="Edict not found")

    ack_id = str(uuid.uuid4())
    ack_data = {
        "ack_id": ack_id,
        "edict_id": edict_id,
        "plan_id": plan_id,
        "version": version,
        "acknowledged_by": data.acknowledged_by,
        "level": data.level,
        "comment": data.comment,
        "acknowledged_at": datetime.now().isoformat(),
    }

    # PostgreSQL 优先
    if _db_active:
        try:
            row = await crud.create_edict_acknowledgment(
                ack_id=ack_id,
                edict_id=edict_id,
                plan_id=plan_id,
                version=version,
                acknowledged_by=data.acknowledged_by,
                level=data.level,
                comment=data.comment,
            )
            if row:
                d = dict(row)
                _edict_acks[ack_id] = d
                logger.info(f"[DB] create_edict_acknowledgment: ack_id={ack_id}")
                return {"acknowledgment": d}
        except Exception as e:
            logger.warning(f"[DB] create_edict_acknowledgment 失败: {e}")

    # 内存兜底
    _edict_acks[ack_id] = ack_data
    return {"acknowledgment": ack_data}


@app.get("/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments")
async def get_edict_acknowledgments(plan_id: str, version: str, edict_id: str):
    """
    列出某圣旨的所有签收记录
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # PostgreSQL 优先
    if _db_active:
        try:
            rows = await crud.list_edict_acknowledgments(edict_id)
            if rows is not None:
                result = [dict(row) for row in rows]
                return {"acknowledgments": result, "count": len(result)}
        except Exception as e:
            logger.warning(f"[DB] list_edict_acknowledgments {edict_id}: {e}")

    # 内存兜底
    acks = [d for d in _edict_acks.values() if d.get("edict_id") == edict_id]
    return {"acknowledgments": acks, "count": len(acks)}


@app.delete("/plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments/{ack_id}")
async def delete_edict_acknowledgment(plan_id: str, version: str, edict_id: str, ack_id: str):
    """
    删除签收记录
    来源: 01-Edict-Reference.md
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # PostgreSQL 优先
    if _db_active:
        try:
            deleted = await crud.delete_edict_acknowledgment(ack_id)
            if deleted:
                if ack_id in _edict_acks:
                    del _edict_acks[ack_id]
                return None
        except Exception as e:
            logger.warning(f"[DB] delete_edict_acknowledgment {ack_id}: {e}")

    # 内存兜底
    if ack_id in _edict_acks:
        del _edict_acks[ack_id]
        return None

    raise HTTPException(status_code=404, detail="Acknowledgment not found")


# ========================
# Task Comments API (Step 21)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 comments
# ========================

@app.post("/plans/{plan_id}/versions/{version}/tasks/{task_id}/comments", status_code=201)
async def create_task_comment(plan_id: str, version: str, task_id: str, data: TaskCommentCreate):
    """
    为任务添加评论
    来源: 08-Data-Models-Details.md §3.1 Task模型 comments
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    comment_id = str(uuid.uuid4())

    # Always try DB first - _db_active might be False due to startup issues
    # but data may still exist in PostgreSQL from previous sessions
    try:
        row = await crud.create_task_comment(
            comment_id=comment_id,
            task_id=task_id,
            plan_id=plan_id,
            version=version,
            author_id=data.author_id,
            author_name=data.author_name,
            author_level=data.author_level,
            content=data.content,
        )
        return dict(row)
    except Exception as e:
        logger.warning(f"[DB] create_task_comment failed: {e}")

    # 内存兜底
    key = (plan_id, version, task_id)
    if key not in _task_comments:
        _task_comments[key] = {}
    comment = {
        "comment_id": comment_id,
        "task_id": task_id,
        "plan_id": plan_id,
        "version": version,
        "author_id": data.author_id,
        "author_name": data.author_name,
        "author_level": data.author_level,
        "content": data.content,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _task_comments[key][comment_id] = comment
    return comment


@app.get("/plans/{plan_id}/versions/{version}/tasks/{task_id}/comments")
async def list_task_comments(plan_id: str, version: str, task_id: str):
    """
    获取任务的所有评论
    来源: 08-Data-Models-Details.md §3.1 Task模型 comments
    """
    # Always try DB first - _db_active might be False due to startup issues
    try:
        rows = await crud.list_task_comments(task_id)
        if rows:
            return {"comments": [dict(r) for r in rows]}
    except Exception as e:
        logger.warning(f"[DB] list_task_comments failed: {e}")

    # Fall back to memory
    key = (plan_id, version, task_id)
    comments = list(_task_comments.get(key, {}).values())
    return {"comments": comments}

    key = (plan_id, version, task_id)
    comments = list(_task_comments.get(key, {}).values())
    return {"comments": comments}


@app.patch("/plans/{plan_id}/versions/{version}/tasks/{task_id}/comments/{comment_id}")
async def update_task_comment(
    plan_id: str, version: str, task_id: str, comment_id: str, data: TaskCommentUpdate
):
    """
    更新任务评论
    来源: 08-Data-Models-Details.md §3.1 Task模型 comments
    """
    # Always try DB first
    try:
        row = await crud.update_task_comment(comment_id, data.content)
        if row:
            return dict(row)
    except Exception as e:
        logger.warning(f"[DB] update_task_comment failed: {e}")

    key = (plan_id, version, task_id)
    if key in _task_comments and comment_id in _task_comments[key]:
        _task_comments[key][comment_id]["content"] = data.content
        _task_comments[key][comment_id]["updated_at"] = datetime.now().isoformat()
        return _task_comments[key][comment_id]

    raise HTTPException(status_code=404, detail="Comment not found")


@app.delete("/plans/{plan_id}/versions/{version}/tasks/{task_id}/comments/{comment_id}")
async def delete_task_comment(plan_id: str, version: str, task_id: str, comment_id: str):
    """
    删除任务评论
    来源: 08-Data-Models-Details.md §3.1 Task模型 comments
    """
    # Always try DB first
    try:
        ok = await crud.delete_task_comment(comment_id)
        if ok:
            return {"deleted": True}
    except Exception as e:
        logger.warning(f"[DB] delete_task_comment failed: {e}")

    key = (plan_id, version, task_id)
    if key in _task_comments and comment_id in _task_comments[key]:
        del _task_comments[key][comment_id]
        return {"deleted": True}

    raise HTTPException(status_code=404, detail="Comment not found")


# ========================
# Task Checkpoints API (Step 21)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 checkpoints
# ========================

@app.post("/plans/{plan_id}/versions/{version}/tasks/{task_id}/checkpoints", status_code=201)
async def create_task_checkpoint(plan_id: str, version: str, task_id: str, data: TaskCheckpointCreate):
    """
    为任务添加检查点
    来源: 08-Data-Models-Details.md §3.1 Task模型 checkpoints
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    checkpoint_id = str(uuid.uuid4())

    # Always try DB first - _db_active might be False due to startup issues
    try:
        row = await crud.create_task_checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            plan_id=plan_id,
            version=version,
            name=data.name,
            status="pending",
        )
        return dict(row)
    except Exception as e:
        logger.warning(f"[DB] create_task_checkpoint failed: {e}")

    # 内存兜底
    key = (plan_id, version, task_id)
    if key not in _task_checkpoints:
        _task_checkpoints[key] = {}
    checkpoint = {
        "checkpoint_id": checkpoint_id,
        "task_id": task_id,
        "plan_id": plan_id,
        "version": version,
        "name": data.name,
        "status": "pending",
        "completed_at": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _task_checkpoints[key][checkpoint_id] = checkpoint
    return checkpoint


@app.get("/plans/{plan_id}/versions/{version}/tasks/{task_id}/checkpoints")
async def list_task_checkpoints(plan_id: str, version: str, task_id: str):
    """
    获取任务的所有检查点
    来源: 08-Data-Models-Details.md §3.1 Task模型 checkpoints
    """
    # Always try DB first
    try:
        rows = await crud.list_task_checkpoints(task_id)
        if rows:
            return {"checkpoints": [dict(r) for r in rows]}
    except Exception as e:
        logger.warning(f"[DB] list_task_checkpoints failed: {e}")

    key = (plan_id, version, task_id)
    checkpoints = list(_task_checkpoints.get(key, {}).values())
    return {"checkpoints": checkpoints}


@app.patch("/plans/{plan_id}/versions/{version}/tasks/{task_id}/checkpoints/{checkpoint_id}")
async def update_task_checkpoint(
    plan_id: str, version: str, task_id: str, checkpoint_id: str, data: TaskCheckpointUpdate
):
    """
    更新检查点（名称或完成状态）
    来源: 08-Data-Models-Details.md §3.1 Task模型 checkpoints
    """
    # Always try DB first
    try:
        row = await crud.update_task_checkpoint(
            checkpoint_id,
            name=data.name,
            status=data.status,
        )
        if row:
            return dict(row)
    except Exception as e:
        logger.warning(f"[DB] update_task_checkpoint failed: {e}")

    key = (plan_id, version, task_id)
    if key in _task_checkpoints and checkpoint_id in _task_checkpoints[key]:
        cp = _task_checkpoints[key][checkpoint_id]
        if data.name is not None:
            cp["name"] = data.name
        if data.status is not None:
            cp["status"] = data.status
            cp["completed_at"] = datetime.now().isoformat() if data.status == "completed" else None
        cp["updated_at"] = datetime.now().isoformat()
        return cp

    raise HTTPException(status_code=404, detail="Checkpoint not found")


@app.delete("/plans/{plan_id}/versions/{version}/tasks/{task_id}/checkpoints/{checkpoint_id}")
async def delete_task_checkpoint(plan_id: str, version: str, task_id: str, checkpoint_id: str):
    """
    删除检查点
    来源: 08-Data-Models-Details.md §3.1 Task模型 checkpoints
    """
    # Always try DB first
    try:
        ok = await crud.delete_task_checkpoint(checkpoint_id)
        if ok:
            return {"deleted": True}
    except Exception as e:
        logger.warning(f"[DB] delete_task_checkpoint failed: {e}")

    key = (plan_id, version, task_id)
    if key in _task_checkpoints and checkpoint_id in _task_checkpoints[key]:
        del _task_checkpoints[key][checkpoint_id]
        return {"deleted": True}

    raise HTTPException(status_code=404, detail="Checkpoint not found")


# ========================
# SubTask API (Step 23)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
# ========================

@app.post("/plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks", status_code=201)
async def create_sub_task(plan_id: str, version: str, task_id: str, data: SubTaskCreate):
    """
    为任务创建子任务
    来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
    """
    if plan_id not in _plans:
        await _sync_plan_to_memory(plan_id)
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan = _plans[plan_id]
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    sub_task_id = str(uuid.uuid4())

    # Always try DB first
    try:
        row = await crud.create_sub_task(
            sub_task_id=sub_task_id,
            task_id=task_id,
            plan_id=plan_id,
            version=version,
            title=data.title,
            description=data.description,
            status=data.status,
        )
        sub_task = dict(row)
        # Sync to memory
        key = (plan_id, version, task_id)
        _sub_tasks.setdefault(key, {})
        _sub_tasks[key][sub_task_id] = sub_task
        # Step 31: Activity Log
        await log_activity(
            plan_id=plan_id,
            action_type=ActivityType.SUBTASK_CREATED,
            version=version,
            actor_id=None,
            actor_name=None,
            target_type="subtask",
            target_id=sub_task_id,
            target_label=data.title[:20],
            details={"task_id": task_id, "title": data.title, "status": data.status},
        )
        return sub_task
    except Exception as e:
        logger.warning(f"[DB] create_sub_task failed: {e}")

    # Memory fallback
    key = (plan_id, version, task_id)
    _sub_tasks.setdefault(key, {})
    sub_task = {
        "sub_task_id": sub_task_id,
        "task_id": task_id,
        "plan_id": plan_id,
        "version": version,
        "title": data.title,
        "description": data.description,
        "status": data.status,
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _sub_tasks[key][sub_task_id] = sub_task
    # Step 31: Activity Log (memory fallback)
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.SUBTASK_CREATED,
        version=version,
        actor_id=None,
        actor_name=None,
        target_type="subtask",
        target_id=sub_task_id,
        target_label=data.title[:20],
        details={"task_id": task_id, "title": data.title, "status": data.status},
    )
    return sub_task


@app.get("/plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks")
async def list_sub_tasks(plan_id: str, version: str, task_id: str):
    """
    获取任务的所有子任务
    来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
    """
    # Always try DB first
    try:
        rows = await crud.list_sub_tasks(task_id)
        if rows:
            return {"sub_tasks": [dict(r) for r in rows]}
    except Exception as e:
        logger.warning(f"[DB] list_sub_tasks failed: {e}")

    # Memory fallback
    key = (plan_id, version, task_id)
    sub_tasks = list(_sub_tasks.get(key, {}).values())
    return {"sub_tasks": sub_tasks}


@app.get("/plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks/{sub_task_id}")
async def get_sub_task(plan_id: str, version: str, task_id: str, sub_task_id: str):
    """
    获取单个子任务详情
    来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
    """
    # Always try DB first
    try:
        rows = await crud.list_sub_tasks(task_id)
        for row in rows:
            if str(row["sub_task_id"]) == sub_task_id:
                return dict(row)
    except Exception as e:
        logger.warning(f"[DB] get_sub_task failed: {e}")

    # Memory fallback
    key = (plan_id, version, task_id)
    if key in _sub_tasks and sub_task_id in _sub_tasks[key]:
        return _sub_tasks[key][sub_task_id]

    raise HTTPException(status_code=404, detail="SubTask not found")


@app.patch("/plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks/{sub_task_id}")
async def update_sub_task(
    plan_id: str, version: str, task_id: str, sub_task_id: str, data: SubTaskUpdate
):
    """
    更新子任务
    来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
    """
    # Always try DB first
    try:
        row = await crud.update_sub_task(
            sub_task_id=sub_task_id,
            title=data.title,
            description=data.description,
            status=data.status,
            progress=data.progress,
        )
        if row:
            # Sync to memory
            key = (plan_id, version, task_id)
            _sub_tasks.setdefault(key, {})
            _sub_tasks[key][sub_task_id] = dict(row)
            return dict(row)
    except Exception as e:
        logger.warning(f"[DB] update_sub_task failed: {e}")

    # Memory fallback
    key = (plan_id, version, task_id)
    if key in _sub_tasks and sub_task_id in _sub_tasks[key]:
        st = _sub_tasks[key][sub_task_id]
        if data.title is not None:
            st["title"] = data.title
        if data.description is not None:
            st["description"] = data.description
        if data.status is not None:
            st["status"] = data.status
        if data.progress is not None:
            st["progress"] = data.progress
        st["updated_at"] = datetime.now().isoformat()
        return st

    raise HTTPException(status_code=404, detail="SubTask not found")


@app.delete("/plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks/{sub_task_id}")
async def delete_sub_task(plan_id: str, version: str, task_id: str, sub_task_id: str):
    """
    删除子任务
    来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
    """
    # Always try DB first
    try:
        ok = await crud.delete_sub_task(sub_task_id)
        if ok:
            # Remove from memory
            key = (plan_id, version, task_id)
            if key in _sub_tasks and sub_task_id in _sub_tasks[key]:
                del _sub_tasks[key][sub_task_id]
            return {"deleted": True}
    except Exception as e:
        logger.warning(f"[DB] delete_sub_task failed: {e}")

    # Memory fallback
    key = (plan_id, version, task_id)
    if key in _sub_tasks and sub_task_id in _sub_tasks[key]:
        del _sub_tasks[key][sub_task_id]
        return {"deleted": True}

    raise HTTPException(status_code=404, detail="SubTask not found")


# ========================
# Constraints API (Plan 约束)
# 来源: 08-Data-Models-Details.md §2.1 Plan.constraints
# ========================

@app.post("/plans/{plan_id}/constraints", status_code=201)
async def create_constraint(plan_id: str, data: ConstraintCreate):
    """创建约束"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    constraint = {
        "constraint_id": str(uuid.uuid4()),
        "plan_id": plan_id,
        "type": data.type.value,
        "value": data.value,
        "unit": data.unit or "",
        "description": data.description or "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # DB write
    try:
        await crud.create_constraint(constraint)
    except Exception as e:
        logger.warning(f"[DB] create_constraint failed: {e}")

    # Memory fallback
    if plan_id not in _constraints:
        _constraints[plan_id] = []
    _constraints[plan_id].append(constraint)

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.CONSTRAINT_CREATED,
        actor_id=None,
        actor_name=None,
        target_type="constraint",
        target_id=constraint["constraint_id"],
        target_label=data.type.value,
        details={"type": data.type.value, "value": data.value, "unit": data.unit, "description": data.description},
    )

    return constraint


@app.get("/plans/{plan_id}/constraints")
async def list_constraints(plan_id: str):
    """列出 Plan 的所有约束"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # DB + memory merge（解决"读到自己写"的一致性问题）
    try:
        db_constraints = await crud.get_constraints(plan_id) or []
        # 注意：内存中 constraint_id 存为 str，DB 返回 uuid.UUID，需统一为 str 比较
        db_ids = {str(c["constraint_id"]) for c in db_constraints}
        mem_constraints = [c for c in _constraints.get(plan_id, []) if str(c.get("constraint_id")) not in db_ids]
        return db_constraints + mem_constraints
    except Exception as e:
        logger.warning(f"[DB] get_constraints failed: {e}")
        return _constraints.get(plan_id, [])


@app.get("/plans/{plan_id}/constraints/{constraint_id}")
async def get_constraint(plan_id: str, constraint_id: str):
    """获取单个约束详情"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Try DB first
    try:
        constraint = await crud.get_constraint(constraint_id)
        if constraint:
            return constraint
    except Exception as e:
        logger.warning(f"[DB] get_constraint failed: {e}")

    for c in _constraints.get(plan_id, []):
        if c.get("constraint_id") == constraint_id:
            return c
    raise HTTPException(status_code=404, detail="Constraint not found")


@app.patch("/plans/{plan_id}/constraints/{constraint_id}")
async def update_constraint(plan_id: str, constraint_id: str, data: ConstraintUpdate):
    """更新约束"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Find in memory
    found = None
    for i, c in enumerate(_constraints.get(plan_id, [])):
        if c.get("constraint_id") == constraint_id:
            found = (i, c)
            break

    if not found:
        raise HTTPException(status_code=404, detail="Constraint not found")

    idx, constraint = found
    if data.type is not None:
        constraint["type"] = data.type.value
    if data.value is not None:
        constraint["value"] = data.value
    if data.unit is not None:
        constraint["unit"] = data.unit
    if data.description is not None:
        constraint["description"] = data.description
    constraint["updated_at"] = datetime.now().isoformat()

    # DB write
    try:
        await crud.update_constraint(constraint_id, constraint)
    except Exception as e:
        logger.warning(f"[DB] update_constraint failed: {e}")

    _constraints[plan_id][idx] = constraint
    return constraint


@app.delete("/plans/{plan_id}/constraints/{constraint_id}", status_code=204)
async def delete_constraint(plan_id: str, constraint_id: str):
    """删除约束"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # DB delete
    try:
        ok = await crud.delete_constraint(constraint_id)
        if ok:
            pass  # Continue to memory delete
    except Exception as e:
        logger.warning(f"[DB] delete_constraint failed: {e}")

    if plan_id in _constraints:
        original_len = len(_constraints[plan_id])
        _constraints[plan_id] = [c for c in _constraints[plan_id] if c.get("constraint_id") != constraint_id]
        if len(_constraints[plan_id]) < original_len:
            return
    raise HTTPException(status_code=404, detail="Constraint not found")


# ========================
# Stakeholders API (Plan 干系人)
# 来源: 08-Data-Models-Details.md §2.1 Plan.stakeholders
# ========================

@app.post("/plans/{plan_id}/stakeholders", status_code=201)
async def create_stakeholder(plan_id: str, data: StakeholderCreate):
    """创建干系人"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    stakeholder = {
        "stakeholder_id": str(uuid.uuid4()),
        "plan_id": plan_id,
        "name": data.name,
        "level": data.level,
        "interest": data.interest.value,
        "influence": data.influence.value,
        "description": data.description or "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # DB write
    try:
        await crud.create_stakeholder(stakeholder)
    except Exception as e:
        logger.warning(f"[DB] create_stakeholder failed: {e}")

    # Memory fallback
    if plan_id not in _stakeholders:
        _stakeholders[plan_id] = []
    _stakeholders[plan_id].append(stakeholder)

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.STAKEHOLDER_CREATED,
        actor_id=None,
        actor_name=data.name,
        target_type="stakeholder",
        target_id=stakeholder["stakeholder_id"],
        target_label=data.name,
        details={"name": data.name, "level": data.level, "interest": data.interest.value, "influence": data.influence.value},
    )

    return stakeholder


@app.get("/plans/{plan_id}/stakeholders")
async def list_stakeholders(plan_id: str):
    """列出 Plan 的所有干系人"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # DB + memory merge（解决"读到自己写"的一致性问题）
    try:
        db_stakeholders = await crud.get_stakeholders(plan_id) or []
        # 注意：内存中 stakeholder_id 存为 str，DB 返回 uuid.UUID，需统一为 str 比较
        db_ids = {str(s["stakeholder_id"]) for s in db_stakeholders}
        mem_stakeholders = [s for s in _stakeholders.get(plan_id, []) if str(s.get("stakeholder_id")) not in db_ids]
        return db_stakeholders + mem_stakeholders
    except Exception as e:
        logger.warning(f"[DB] get_stakeholders failed: {e}")
        return _stakeholders.get(plan_id, [])


@app.get("/plans/{plan_id}/stakeholders/{stakeholder_id}")
async def get_stakeholder(plan_id: str, stakeholder_id: str):
    """获取单个干系人详情"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Try DB first
    try:
        stakeholder = await crud.get_stakeholder(stakeholder_id)
        if stakeholder:
            return stakeholder
    except Exception as e:
        logger.warning(f"[DB] get_stakeholder failed: {e}")

    for s in _stakeholders.get(plan_id, []):
        if s.get("stakeholder_id") == stakeholder_id:
            return s
    raise HTTPException(status_code=404, detail="Stakeholder not found")


@app.patch("/plans/{plan_id}/stakeholders/{stakeholder_id}")
async def update_stakeholder(plan_id: str, stakeholder_id: str, data: StakeholderUpdate):
    """更新干系人"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Find in memory
    found = None
    for i, s in enumerate(_stakeholders.get(plan_id, [])):
        if s.get("stakeholder_id") == stakeholder_id:
            found = (i, s)
            break

    if not found:
        raise HTTPException(status_code=404, detail="Stakeholder not found")

    idx, stakeholder = found
    if data.name is not None:
        stakeholder["name"] = data.name
    if data.level is not None:
        stakeholder["level"] = data.level
    if data.interest is not None:
        stakeholder["interest"] = data.interest.value
    if data.influence is not None:
        stakeholder["influence"] = data.influence.value
    if data.description is not None:
        stakeholder["description"] = data.description
    stakeholder["updated_at"] = datetime.now().isoformat()

    # DB write
    try:
        await crud.update_stakeholder(stakeholder_id, stakeholder)
    except Exception as e:
        logger.warning(f"[DB] update_stakeholder failed: {e}")

    _stakeholders[plan_id][idx] = stakeholder
    return stakeholder


@app.delete("/plans/{plan_id}/stakeholders/{stakeholder_id}", status_code=204)
async def delete_stakeholder(plan_id: str, stakeholder_id: str):
    """删除干系人"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # DB delete
    try:
        ok = await crud.delete_stakeholder(stakeholder_id)
        if ok:
            pass
    except Exception as e:
        logger.warning(f"[DB] delete_stakeholder failed: {e}")

    if plan_id in _stakeholders:
        original_len = len(_stakeholders[plan_id])
        _stakeholders[plan_id] = [s for s in _stakeholders[plan_id] if s.get("stakeholder_id") != stakeholder_id]
        if len(_stakeholders[plan_id]) < original_len:
            return
    raise HTTPException(status_code=404, detail="Stakeholder not found")


# ========================
# Risks API (Version 风险)
# 来源: 08-Data-Models-Details.md §3.1 Version.risks
# ========================

@app.post("/plans/{plan_id}/versions/{version}/risks", status_code=201)
async def create_risk(plan_id: str, version: str, data: RiskCreate):
    """创建风险"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    risk = {
        "risk_id": str(uuid.uuid4()),
        "plan_id": plan_id,
        "version": version,
        "title": data.title,
        "description": data.description or "",
        "probability": data.probability.value,
        "impact": data.impact.value,
        "severity": _calc_severity(data.probability.value, data.impact.value),
        "mitigation": data.mitigation or "",
        "contingency": data.contingency or "",
        "status": data.status.value,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # DB write
    try:
        await crud.create_risk(risk)
    except Exception as e:
        logger.warning(f"[DB] create_risk failed: {e}")

    # Memory fallback
    key = (plan_id, version)
    if key not in _risks:
        _risks[key] = []
    _risks[key].append(risk)

    # Step 31: Activity Log
    await log_activity(
        plan_id=plan_id,
        action_type=ActivityType.RISK_CREATED,
        version=version,
        actor_id=None,
        actor_name=None,
        target_type="risk",
        target_id=risk["risk_id"],
        target_label=data.title[:20],
        details={
            "title": data.title,
            "probability": data.probability.value,
            "impact": data.impact.value,
            "severity": risk["severity"],
            "status": data.status.value,
        },
    )

    return risk


@app.get("/plans/{plan_id}/versions/{version}/risks")
async def list_risks(plan_id: str, version: str):
    """列出 Version 的所有风险"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # DB + memory merge（解决"读到自己写"的一致性问题）
    try:
        db_risks = await crud.get_risks(plan_id, version) or []
        # 注意：内存中 risk_id 存为 str，DB 返回 uuid.UUID，需统一为 str 比较
        db_ids = {str(r["risk_id"]) for r in db_risks}
        mem_risks = [r for r in _risks.get((plan_id, version), []) if str(r.get("risk_id")) not in db_ids]
        return db_risks + mem_risks
    except Exception as e:
        logger.warning(f"[DB] get_risks failed: {e}")
        return _risks.get((plan_id, version), [])


@app.get("/plans/{plan_id}/versions/{version}/risks/{risk_id}")
async def get_risk(plan_id: str, version: str, risk_id: str):
    """获取单个风险详情"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # Try DB first
    try:
        risk = await crud.get_risk(risk_id)
        if risk:
            return risk
    except Exception as e:
        logger.warning(f"[DB] get_risk failed: {e}")

    for r in _risks.get((plan_id, version), []):
        if r.get("risk_id") == risk_id:
            return r
    raise HTTPException(status_code=404, detail="Risk not found")


@app.patch("/plans/{plan_id}/versions/{version}/risks/{risk_id}")
async def update_risk(plan_id: str, version: str, risk_id: str, data: RiskUpdate):
    """更新风险"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # Find in memory
    found = None
    for i, r in enumerate(_risks.get((plan_id, version), [])):
        if r.get("risk_id") == risk_id:
            found = (i, r)
            break

    if not found:
        raise HTTPException(status_code=404, detail="Risk not found")

    idx, risk = found
    if data.title is not None:
        risk["title"] = data.title
    if data.description is not None:
        risk["description"] = data.description
    if data.probability is not None:
        risk["probability"] = data.probability.value
    if data.impact is not None:
        risk["impact"] = data.impact.value
    if data.mitigation is not None:
        risk["mitigation"] = data.mitigation
    if data.contingency is not None:
        risk["contingency"] = data.contingency
    if data.status is not None:
        risk["status"] = data.status.value
    risk["severity"] = _calc_severity(risk["probability"], risk["impact"])
    risk["updated_at"] = datetime.now().isoformat()

    # DB write
    try:
        await crud.update_risk(risk_id, risk)
    except Exception as e:
        logger.warning(f"[DB] update_risk failed: {e}")

    _risks[(plan_id, version)][idx] = risk
    return risk


@app.delete("/plans/{plan_id}/versions/{version}/risks/{risk_id}", status_code=204)
async def delete_risk(plan_id: str, version: str, risk_id: str):
    """删除风险"""
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    # DB delete
    try:
        ok = await crud.delete_risk(risk_id)
        if ok:
            pass
    except Exception as e:
        logger.warning(f"[DB] delete_risk failed: {e}")

    key = (plan_id, version)
    if key in _risks:
        original_len = len(_risks[key])
        _risks[key] = [r for r in _risks[key] if r.get("risk_id") != risk_id]
        if len(_risks[key]) < original_len:
            return
    raise HTTPException(status_code=404, detail="Risk not found")


def _calc_severity(probability: str, impact: str) -> str:
    """计算风险严重程度"""
    score = {"low": 1, "medium": 2, "high": 3}
    s = score.get(probability, 2) * score.get(impact, 2)
    if s <= 2:
        return "low"
    elif s <= 4:
        return "medium"
    else:
        return "high"


# ========================
# Step 32: Plan/Deliberation Export API
# 来源: Agora-V2 迭代开发 - 决议报告导出
# ========================

@app.get("/plans/{plan_id}/export")
async def export_plan_markdown(plan_id: str):
    """
    导出会谈决议（完整 Plan Markdown 报告）
    包含：Plan 信息、全部版本摘要、所有 Rooms、Decisions、Risks、Edicts、Tasks、Analytics
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    current_version = plan.get("current_version", "v1.0")
    rooms_data = await get_rooms_by_plan(plan_id)
    rooms = rooms_data.get("rooms", [])

    # 预取 Rooms 的参与者 + 消息
    room_details = {}
    for room in rooms:
        rid = room.get("room_id")
        if rid:
            try:
                ctx = await get_room_context(rid)
                msgs = await get_room_history(rid)
                room_details[rid] = {
                    "participants": ctx.get("participants", []),
                    "messages": msgs[-10:] if msgs else [],
                }
            except Exception:
                room_details[rid] = {"participants": [], "messages": []}

    # 收集关联数据
    decisions = await _get_version_decisions(plan_id, current_version)
    constraints = await _get_plan_constraints(plan_id)
    stakeholders = await _get_plan_stakeholders(plan_id)
    risks = await _get_version_risks(plan_id, current_version)
    edicts = await _get_version_edicts(plan_id, current_version)
    tasks = await _get_version_tasks(plan_id, current_version)
    analytics = await _get_plan_analytics_data(plan_id, rooms, current_version)

    md = _build_plan_markdown(
        plan, rooms, decisions, constraints, stakeholders, risks, edicts, tasks, analytics,
        room_details=room_details,
    )
    return {"content": md, "format": "markdown", "plan_id": plan_id}


@app.get("/plans/{plan_id}/versions/{version}/export")
async def export_version_markdown(plan_id: str, version: str):
    """
    导出指定版本的 Markdown 报告
    包含：该版本的 Rooms、Decisions、Risks、Edicts、Tasks、Analytics
    """
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not _version_exists(plan, version):
        raise HTTPException(status_code=404, detail="Version not found")

    rooms_data = await get_rooms_by_plan(plan_id)
    rooms = [r for r in rooms_data.get("rooms", []) if r.get("version") == version]

    # 预取 Rooms 的参与者 + 消息
    room_details = {}
    for room in rooms:
        rid = room.get("room_id")
        if rid:
            try:
                ctx = await get_room_context(rid)
                msgs = await get_room_history(rid)
                room_details[rid] = {
                    "participants": ctx.get("participants", []),
                    "messages": msgs[-10:] if msgs else [],
                }
            except Exception:
                room_details[rid] = {"participants": [], "messages": []}

    decisions = await _get_version_decisions(plan_id, version)
    constraints = await _get_plan_constraints(plan_id)
    stakeholders = await _get_plan_stakeholders(plan_id)
    risks = await _get_version_risks(plan_id, version)
    edicts = await _get_version_edicts(plan_id, version)
    tasks = await _get_version_tasks(plan_id, version)
    analytics = await _get_plan_analytics_data(plan_id, rooms, version)

    md = _build_plan_markdown(
        plan, rooms, decisions, constraints, stakeholders, risks, edicts, tasks, analytics,
        room_details=room_details, version_filter=version,
    )
    return {"content": md, "format": "markdown", "plan_id": plan_id, "version": version}


# --- 辅助函数（数据获取）---

async def _get_version_decisions(plan_id: str, version: str) -> List[Dict[str, Any]]:
    try:
        rows = await crud.get_decisions(plan_id, version) or []
        return rows
    except Exception as e:
        logger.warning(f"[DB] get_decisions failed: {e}")
        return _decisions.get((plan_id, version), [])


async def _get_plan_constraints(plan_id: str) -> List[Dict[str, Any]]:
    try:
        rows = await crud.get_constraints(plan_id) or []
        return rows
    except Exception as e:
        logger.warning(f"[DB] get_constraints failed: {e}")
        return _constraints.get(plan_id, [])


async def _get_plan_stakeholders(plan_id: str) -> List[Dict[str, Any]]:
    try:
        rows = await crud.get_stakeholders(plan_id) or []
        return rows
    except Exception as e:
        logger.warning(f"[DB] get_stakeholders failed: {e}")
        return _stakeholders.get(plan_id, [])


async def _get_version_risks(plan_id: str, version: str) -> List[Dict[str, Any]]:
    try:
        rows = await crud.get_risks(plan_id, version) or []
        return rows
    except Exception as e:
        logger.warning(f"[DB] get_risks failed: {e}")
        return _risks.get((plan_id, version), [])


async def _get_version_edicts(plan_id: str, version: str) -> List[Dict[str, Any]]:
    try:
        rows = await crud.get_edicts(plan_id, version) or []
        return rows
    except Exception as e:
        logger.warning(f"[DB] get_edicts failed: {e}")
        return _edicts.get((plan_id, version), [])


async def _get_version_tasks(plan_id: str, version: str) -> List[Dict[str, Any]]:
    try:
        rows = await crud.get_tasks(plan_id, version) or []
        return rows
    except Exception as e:
        logger.warning(f"[DB] get_tasks failed: {e}")
        return _tasks.get((plan_id, version), [])


async def _get_plan_analytics_data(plan_id: str, rooms: List[Dict], version: str) -> Dict[str, Any]:
    """构建 Plan 分析统计（用于导出报告）"""
    result = {
        "plan_id": plan_id,
        "rooms": {"total": len(rooms), "by_phase": {}},
        "tasks": {"total": 0, "completed": 0, "completion_rate": 0},
        "decisions": {"total": 0},
        "risks": {"total": 0},
        "edicts": {"total": 0},
    }
    try:
        for r in rooms:
            phase = r.get("phase", "unknown")
            result["rooms"]["by_phase"][phase] = result["rooms"]["by_phase"].get(phase, 0) + 1
    except Exception:
        pass
    try:
        tasks = await _get_version_tasks(plan_id, version)
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        result["tasks"] = {
            "total": total,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        pass
    try:
        decisions = await _get_version_decisions(plan_id, version)
        result["decisions"] = {"total": len(decisions)}
    except Exception:
        pass
    try:
        risks = await _get_version_risks(plan_id, version)
        result["risks"] = {"total": len(risks)}
    except Exception:
        pass
    try:
        edicts = await _get_version_edicts(plan_id, version)
        result["edicts"] = {"total": len(edicts)}
    except Exception:
        pass
    return result


def _format_date(value: Any) -> str:
    """安全格式化日期值（处理 datetime 对象或字符串）"""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value)
    return s[:10] if len(s) >= 10 else s


def _build_plan_markdown(
    plan: Dict[str, Any],
    rooms: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    constraints: List[Dict[str, Any]],
    stakeholders: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    edicts: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    analytics: Dict[str, Any],
    room_details: Optional[Dict[str, Dict[str, Any]]] = None,
    version_filter: Optional[str] = None,
) -> str:
    """构建 Plan Markdown 报告（同步函数，数据已预取）"""
    rd = room_details or {}
    lines = []

    # ---- Header ----
    title = plan.get("title", "未命名计划")
    plan_number = plan.get("plan_number", plan.get("plan_id", ""))
    created_at = _format_date(plan.get("created_at"))
    status = plan.get("status", "draft")
    current_version = plan.get("current_version", "v1.0")
    description = plan.get("description", "")

    version_tag = f" [v{version_filter}]" if version_filter else f" (当前版本: {current_version})"
    lines.append(f"# {title}{version_tag}\n")
    lines.append(f"**编号**: {plan_number}  |  **状态**: {status}  |  **创建日期**: {created_at}\n")
    if description:
        lines.append(f"**描述**: {description}\n")
    lines.append("---\n")

    # ---- Analytics Summary ----
    if analytics:
        a = analytics
        rooms_info = a.get("rooms", {})
        tasks_info = a.get("tasks", {})
        decisions_info = a.get("decisions", {})
        risks_info = a.get("risks", {})
        edicts_info = a.get("edicts", {})
        lines.append("## 📊 统计概览\n")
        lines.append(f"- **讨论室**: {rooms_info.get('total', 0)} 个")
        if rooms_info.get("by_phase"):
            phases = ", ".join(f"{k}: {v}" for k, v in rooms_info["by_phase"].items())
            lines.append(f"  - 按阶段: {phases}")
        lines.append(f"- **任务**: {tasks_info.get('total', 0)} 个，完成 {tasks_info.get('completed', 0)} 个 ({tasks_info.get('completion_rate', 0)}%)")
        lines.append(f"- **决策**: {decisions_info.get('total', 0)} 项")
        lines.append(f"- **风险**: {risks_info.get('total', 0)} 项")
        lines.append(f"- **圣旨**: {edicts_info.get('total', 0)} 道")
        lines.append("")

    # ---- Constraints ----
    if constraints:
        lines.append("## 🚫 约束条件\n")
        for c in constraints:
            ctype = c.get("type", "unknown")
            value = c.get("value", "")
            unit = c.get("unit", "")
            desc = c.get("description", "")
            lines.append(f"- **[{ctype}]** {value} {unit} — {desc}")
        lines.append("")

    # ---- Stakeholders ----
    if stakeholders:
        lines.append("## 👥 干系人\n")
        for s in stakeholders:
            name = s.get("name", "未知")
            level = s.get("level", "?")
            interest = s.get("interest", "")
            influence = s.get("influence", "")
            lines.append(f"- **{name}** (L{level}) — 利益: {interest}, 影响: {influence}")
        lines.append("")

    # ---- Decisions ----
    if decisions:
        lines.append("## ✅ 决策记录\n")
        for d in decisions:
            dn = d.get("decision_number", "?")
            dt = d.get("title", "未命名决策")
            drationale = d.get("rationale", "")
            dagreed = d.get("agreed_by", [])
            ddisagreed = d.get("disagreed_by", [])
            lines.append(f"### {dn}: {dt}\n")
            if drationale:
                lines.append(f"**理由**: {drationale}\n")
            if dagreed:
                lines.append(f"**赞成**: {', '.join(dagreed) if isinstance(dagreed, list) else dagreed}\n")
            if ddisagreed:
                lines.append(f"**反对**: {', '.join(ddisagreed) if isinstance(ddisagreed, list) else ddisagreed}\n")
        lines.append("")

    # ---- Edicts ----
    if edicts:
        lines.append("## 📜 圣旨\n")
        for e in edicts:
            en = e.get("edict_number", "?")
            et = e.get("title", "未命名圣旨")
            eby = e.get("issued_by", "未知")
            eat = _format_date(e.get("issued_at"))
            erecip = e.get("recipients", [])
            estatus = e.get("status", "draft")
            econtent = e.get("content", "")
            lines.append(f"### 圣旨 {en}: {et}\n")
            lines.append(f"**签发人**: {eby}  |  **日期**: {eat}  |  **状态**: {estatus}\n")
            if erecip:
                lines.append(f"**接收方**: {', '.join(erecip) if isinstance(erecip, list) else erecip}\n")
            if econtent:
                lines.append(f"\n{econtent}\n")
        lines.append("")

    # ---- Rooms ----
    if rooms:
        lines.append("## 💬 讨论室\n")
        for room in rooms:
            rn = room.get("room_number", room.get("room_id", ""))
            rt = room.get("topic", "未命名讨论室")
            rp = room.get("phase", "unknown")
            rpurpose = room.get("purpose", "initial_discussion")
            rmode = room.get("mode", "hierarchical")
            rcreated = _format_date(room.get("created_at"))

            lines.append(f"### {rn}: {rt}\n")
            lines.append(f"**阶段**: {rp}  |  **目的**: {rpurpose}  |  **模式**: {rmode}  |  **创建**: {rcreated}\n")

            room_id = room.get("room_id")
            detail = rd.get(room_id, {}) if room_id else {}
            participants_list = detail.get("participants", [])
            msgs = detail.get("messages", [])

            if participants_list:
                pnames = [f"L{p.get('level', '?')}-{p.get('name', '?')}" for p in participants_list]
                lines.append(f"**参与者**: {', '.join(pnames)}\n")

            if msgs:
                lines.append("**讨论记录**:\n")
                for m in msgs:
                    mtype = m.get("type", "speech")
                    mseq = m.get("sequence", "?")
                    mspeaker = m.get("participant_name", m.get("participant_id", "?"))
                    mcontent = m.get("content", m.get("text", ""))
                    if mcontent and mtype == "speech":
                        lines.append(f"- #{mseq} {mspeaker}: {mcontent[:100]}")
                    elif mtype in ("phase_change", "participant_joined", "participant_left"):
                        lines.append(f"- #{mseq} [{mtype}]")

            lines.append("")
        lines.append("")

    # ---- Tasks ----
    if tasks:
        lines.append("## 📋 任务清单\n")
        for t in tasks:
            tn = t.get("task_number", t.get("task_id", "?"))
            ttl = t.get("title", "未命名任务")
            tstatus = t.get("status", "pending")
            tprogress = t.get("progress", 0)
            towner = t.get("owner_name", t.get("owner_id", "未分配"))
            tpriority = t.get("priority", "medium")
            lines.append(f"- [{tstatus.upper()}] **{tn}**: {ttl} — 负责人: {towner} | 优先级: {tpriority} | 进度: {tprogress}%\n")
        lines.append("")

    # ---- Risks ----
    if risks:
        lines.append("## ⚠️ 风险登记\n")
        for r in risks:
            rt = r.get("title", "未命名风险")
            rsev = r.get("severity", "medium")
            rprob = r.get("probability", "medium")
            rimpact = r.get("impact", "medium")
            rmit = r.get("mitigation", "")
            lines.append(f"- **[{rsev.upper()}]** {rt} (概率: {rprob}, 影响: {rimpact})\n")
            if rmit:
                lines.append(f"  - 缓解措施: {rmit}\n")
        lines.append("")

    # ---- Footer ----
    lines.append("---\n")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Agora-V2 决议导出*\n")

    return "\n".join(lines)


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
