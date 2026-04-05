"""
CRUD 操作层 - 数据库持久化实现
替换原有的内存存储 (_plans, _rooms, _participants, _messages 等)
"""
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from asyncpg import Pool, Record

from db import get_pool, get_connection


# ========================
# Plans
# ========================

async def create_plan(plan_id: str, plan_number: str, title: str, topic: str,
                      requirements: List[str], hierarchy_id: str,
                      current_version: str = "v1.0") -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO plans (plan_id, plan_number, title, topic, requirements, hierarchy_id,
                               current_version, versions, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
            RETURNING *
            """,
            plan_id, plan_number, title, topic,
            json.dumps(requirements), hierarchy_id,
            current_version, json.dumps([current_version])
        )
        return dict(row)


async def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM plans WHERE plan_id = $1", plan_id
        )
        return dict(row) if row else None


async def update_plan(plan_id: str, **fields) -> Optional[Dict[str, Any]]:
    """更新 plan 的指定字段"""
    if not fields:
        return await get_plan(plan_id)
    set_clauses = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{k} = ${i}")
        values.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    values.append(plan_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"UPDATE plans SET {', '.join(set_clauses)}, updated_at = NOW() "
            f"WHERE plan_id = ${len(values)} RETURNING *",
            *values
        )
        return dict(row) if row else None


async def list_plans() -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch("SELECT * FROM plans ORDER BY created_at DESC")
        return [dict(r) for r in rows]


async def copy_plan(
    original_plan_id: str,
    new_plan_id: str,
    new_plan_number: str,
    new_title: str,
) -> Dict[str, Any]:
    """
    复制 Plan（不含 rooms/tasks/decisions 等版本级内容，仅复制 plan 级元数据）
    复制内容：title, topic, requirements, hierarchy_id, purpose, mode, constraints, stakeholders
    新计划创建 v1.0 配套 Room
    """
    orig = await get_plan(original_plan_id)
    if not orig:
        raise ValueError(f"Original plan not found: {original_plan_id}")

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO plans (plan_id, plan_number, title, topic, requirements, hierarchy_id,
                               current_version, versions, purpose, mode, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), NOW())
            RETURNING *
            """,
            new_plan_id, new_plan_number, new_title, orig["topic"],
            orig.get("requirements"), orig.get("hierarchy_id", "default"),
            "v1.0", json.dumps(["v1.0"]),
            orig.get("purpose", "initial_discussion"),
            orig.get("mode", "hierarchical"),
        )

    # 复制 constraints
    constraints = await get_constraints(original_plan_id)
    for c in constraints:
        import uuid as _uuid
        await create_constraint({
            "constraint_id": str(_uuid.uuid4()),
            "plan_id": new_plan_id,
            "type": c.get("type"),
            "value": c.get("value"),
            "unit": c.get("unit"),
            "description": c.get("description"),
        })

    # 复制 stakeholders
    stakeholders = await get_stakeholders(original_plan_id)
    for s in stakeholders:
        import uuid as _uuid
        await create_stakeholder({
            "stakeholder_id": str(_uuid.uuid4()),
            "plan_id": new_plan_id,
            "name": s.get("name"),
            "level": s.get("level"),
            "interest": s.get("interest"),
            "influence": s.get("influence"),
            "description": s.get("description"),
        })

    return dict(row)


async def list_rooms() -> List[Dict[str, Any]]:
    """List all rooms ordered by creation time descending."""
    async with get_connection() as conn:
        rows = await conn.fetch("""
            SELECT r.*, COUNT(p.participant_id) as participant_count
            FROM rooms r
            LEFT JOIN participants p ON r.room_id = p.room_id AND p.is_active = TRUE
            GROUP BY r.room_id
            ORDER BY r.created_at DESC
        """)
        return [dict(r) for r in rows]


async def add_plan_version(plan_id: str, new_version: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE plans
            SET current_version = $2,
                versions = array_append(versions, $2),
                updated_at = NOW()
            WHERE plan_id = $1
            """,
            plan_id, new_version
        )


# ========================
# Rooms
# ========================

async def create_room(room_id: str, room_number: str, plan_id: str, topic: str,
                      coordinator_id: str = "coordinator",
                      phase: str = "selecting",
                      current_version: str = "v1.0",
                      purpose: str = "initial_discussion",
                      mode: str = "hierarchical") -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO rooms (room_id, room_number, plan_id, topic, phase,
                               coordinator_id, current_version, purpose, mode, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            RETURNING *
            """,
            room_id, room_number, plan_id, topic, phase, coordinator_id, current_version, purpose, mode
        )
        return dict(row)


async def get_room(room_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM rooms WHERE room_id = $1", room_id)
        return dict(row) if row else None


async def update_room(room_id: str, **fields) -> Optional[Dict[str, Any]]:
    if not fields:
        return await get_room(room_id)
    set_clauses = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{k} = ${i}")
        values.append(v)
    values.append(room_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"UPDATE rooms SET {', '.join(set_clauses)} WHERE room_id = ${len(values)} RETURNING *",
            *values
        )
        return dict(row) if row else None


async def get_rooms_by_plan(plan_id: str) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM rooms WHERE plan_id = $1 ORDER BY created_at",
            plan_id
        )
        return [dict(r) for r in rows]


# ========================
# Participants
# ========================

async def add_participant(room_id: str, participant_id: str,
                           agent_id: str, name: str, level: int,
                           role: str, source: str = "internal") -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO participants
              (participant_id, room_id, agent_id, name, level, role, source, joined_at, is_active)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), TRUE)
            RETURNING *
            """,
            participant_id, room_id, agent_id, name, level, role, source
        )
        return dict(row)


async def get_participants(room_id: str) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM participants WHERE room_id = $1 AND is_active = TRUE "
            "ORDER BY joined_at",
            room_id
        )
        return [dict(r) for r in rows]


async def deactivate_participant(room_id: str, agent_id: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE participants SET is_active = FALSE "
            "WHERE room_id = $1 AND agent_id = $2",
            room_id, agent_id
        )


# ========================
# Messages
# ========================

async def get_next_message_sequence(room_id: str) -> int:
    """获取房间下一条消息的序号"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(sequence), 0) + 1 as next_seq FROM messages WHERE room_id = $1",
            room_id
        )
        return row["next_seq"] if row else 1


async def add_message(room_id: str, message_id: str, type: str,
                      agent_id: Optional[str] = None,
                      content: Optional[str] = None,
                      metadata: Optional[Dict] = None,
                      source: str = "internal",
                      sequence: Optional[int] = None) -> Dict[str, Any]:
    # 如果未提供 sequence，自动获取下一个序号
    if sequence is None:
        sequence = await get_next_message_sequence(room_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO messages (message_id, room_id, type, agent_id, content,
                                  metadata, source, timestamp, sequence)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8)
            RETURNING *
            """,
            message_id, room_id, type, agent_id, content,
            json.dumps(metadata or {}), source, sequence
        )
        return dict(row)


async def get_messages(room_id: str, limit: int = 0) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        if limit > 0:
            rows = await conn.fetch(
                "SELECT * FROM messages WHERE room_id = $1 ORDER BY timestamp LIMIT $2",
                room_id, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM messages WHERE room_id = $1 ORDER BY timestamp",
                room_id
            )
        return [dict(r) for r in rows]


async def search_messages(room_id: str, query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """搜索讨论室消息内容"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM messages
            WHERE room_id = $1
              AND content ILIKE $2
            ORDER BY timestamp DESC
            LIMIT $3
            """,
            room_id, f"%{query}%", limit
        )
        return [dict(r) for r in rows]


# ========================
# Approval Flows
# ========================

async def start_approval_flow(plan_id: str, initiator_id: str,
                               initiator_name: str,
                               levels_data: Dict[int, Dict],
                               skip_levels: List[int]) -> Dict[str, Any]:
    async with get_connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO approval_flows
                  (plan_id, initiator_id, initiator_name, current_level, status, skip_levels, started_at)
                VALUES ($1, $2, $3, 7, 'in_progress', $4, NOW())
                ON CONFLICT (plan_id) DO NOTHING
                """,
                plan_id, initiator_id, initiator_name, json.dumps(skip_levels)
            )
            for lvl, data in levels_data.items():
                await conn.execute(
                    """
                    INSERT INTO approval_levels
                      (plan_id, level, status, approver_id, approver_name, comment, decided_at, escalated_to)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    plan_id, lvl, data.get("status", "pending"),
                    data.get("approver_id"), data.get("approver_name"),
                    data.get("comment"), data.get("decided_at"), data.get("escalated_to")
                )
        return await get_approval_flow(plan_id)


async def get_approval_flow(plan_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM approval_flows WHERE plan_id = $1", plan_id
        )
        if not row:
            return None
        flow = dict(row)
        level_rows = await conn.fetch(
            "SELECT * FROM approval_levels WHERE plan_id = $1 ORDER BY level DESC",
            plan_id
        )
        flow["levels"] = {r["level"]: dict(r) for r in level_rows}
        return flow


async def update_approval_level(plan_id: str, level: int, **fields) -> None:
    set_clauses = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{k} = ${i}")
        values.append(v)
    values.extend([plan_id, level])
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE approval_levels SET {', '.join(set_clauses)} "
            f"WHERE plan_id = ${len(values)-1} AND level = ${len(values)}",
            *values
        )


async def update_approval_flow(plan_id: str, **fields) -> None:
    set_clauses = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{k} = ${i}")
        values.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    values.append(plan_id)
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE approval_flows SET {', '.join(set_clauses)} WHERE plan_id = ${len(values)}",
            *values
        )


# ========================
# Problems
# ========================

async def create_problem(issue_id: str, plan_id: str, room_id: str,
                         version: str, type: str, title: str,
                         description: str, severity: str,
                         detected_by: str,
                         issue_number: str = None,
                         affected_tasks: List[int] = None,
                         progress_delay: int = 0,
                         related_context: Dict = None) -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO problems
              (issue_id, plan_id, room_id, version, type, title, description,
               severity, detected_by, issue_number, affected_tasks, progress_delay, related_context, detected_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
            RETURNING *
            """,
            issue_id, plan_id, room_id, version, type, title, description,
            severity, detected_by, issue_number,
            json.dumps(affected_tasks or []), progress_delay,
            json.dumps(related_context or {})
        )
        return dict(row)


async def get_problem(issue_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM problems WHERE issue_id = $1", issue_id
        )
        return dict(row) if row else None


async def update_problem(issue_id: str, **fields) -> None:
    if not fields:
        return
    set_clauses = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{k} = ${i}")
        values.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    values.append(issue_id)
    async with get_connection() as conn:
        await conn.execute(
            f"UPDATE problems SET {', '.join(set_clauses)} WHERE issue_id = ${len(values)}",
            *values
        )


async def get_problems_by_plan(plan_id: str) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM problems WHERE plan_id = $1 ORDER BY detected_at",
            plan_id
        )
        return [dict(r) for r in rows]


# ========================
# Problem Analysis
# ========================

async def create_problem_analysis(
    issue_id: str,
    root_cause: str,
    root_cause_confidence: float,
    impact_scope: str,
    affected_tasks: List[int],
    progress_impact: str,
    severity_reassessment: str,
    solution_options: List[Dict],
    recommended_option: int,
    requires_discussion: bool,
    discussion_needed_aspects: List[str]
) -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO problem_analyses
              (issue_id, root_cause, root_cause_confidence, impact_scope,
               affected_tasks, progress_impact, severity_reassessment,
               solution_options, recommended_option, requires_discussion,
               discussion_needed_aspects, analyzed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            RETURNING *
            """,
            issue_id, root_cause, root_cause_confidence, impact_scope,
            json.dumps(affected_tasks), progress_impact, severity_reassessment,
            json.dumps(solution_options), recommended_option,
            requires_discussion, json.dumps(discussion_needed_aspects)
        )
        return dict(row)


async def get_problem_analysis(issue_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM problem_analyses WHERE issue_id = $1", issue_id
        )
        return dict(row) if row else None


# ========================
# Problem Discussion
# ========================

async def create_problem_discussion(
    issue_id: str,
    participants: List[str],
    discussion_focus: List[str],
    proposed_solutions: List[Dict],
    votes: Dict,
    final_recommendation: str
) -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO problem_discussions
              (issue_id, participants, discussion_focus, proposed_solutions,
               votes, final_recommendation, discussed_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING *
            """,
            issue_id, json.dumps(participants), json.dumps(discussion_focus),
            json.dumps(proposed_solutions), json.dumps(votes), final_recommendation
        )
        return dict(row)


async def get_problem_discussion(issue_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM problem_discussions WHERE issue_id = $1", issue_id
        )
        return dict(row) if row else None


# ========================
# Plan Updates
# ========================

async def create_plan_update(
    plan_id: str, new_version: str, parent_version: str,
    update_type: str, description: str,
    changes: Dict, task_updates: List[Dict],
    new_tasks: List[Dict], cancelled_tasks: List[int]
) -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO plan_updates
              (plan_id, new_version, parent_version, update_type, description,
               changes, task_updates, new_tasks, cancelled_tasks, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            RETURNING *
            """,
            plan_id, new_version, parent_version, update_type, description,
            json.dumps(changes), json.dumps(task_updates),
            json.dumps(new_tasks), json.dumps(cancelled_tasks)
        )
        return dict(row)


async def get_plan_update(plan_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM plan_updates WHERE plan_id = $1", plan_id
        )
        return dict(row) if row else None


# ========================
# Resuming Records
# ========================

async def create_resuming_record(
    plan_id: str, new_version: str, resuming_from_task: int,
    checkpoint: str, resume_instructions: Dict
) -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO resuming_records
              (plan_id, new_version, resuming_from_task, checkpoint,
               resume_instructions, resumed_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING *
            """,
            plan_id, new_version, resuming_from_task, checkpoint,
            json.dumps(resume_instructions)
        )
        return dict(row)


async def get_resuming_record(plan_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM resuming_records WHERE plan_id = $1", plan_id
        )
        return dict(row) if row else None


# ========================
# Snapshots
# ========================

async def create_snapshot(
    snapshot_id: str, plan_id: str, version: str, room_id: str,
    phase: str, context_summary: str,
    participants: List[str], messages_summary: List[Dict]
) -> Dict[str, Any]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO snapshots
              (snapshot_id, plan_id, version, room_id, phase, context_summary,
               participants, messages_summary, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            RETURNING *
            """,
            snapshot_id, plan_id, version, room_id, phase, context_summary,
            json.dumps(participants), json.dumps(messages_summary)
        )
        return dict(row)


async def list_snapshots(plan_id: str, version: str) -> List[Dict[str, Any]]:
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT snapshot_id, phase, context_summary, created_at "
            "FROM snapshots WHERE plan_id = $1 AND version = $2 ORDER BY created_at",
            plan_id, version
        )
        return [dict(r) for r in rows]


async def get_snapshot(plan_id: str, version: str, snapshot_id: str) -> Optional[Dict[str, Any]]:
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM snapshots WHERE plan_id = $1 AND version = $2 AND snapshot_id = $3",
            plan_id, version, snapshot_id
        )
        return dict(row) if row else None


# ========================
# Tasks (执行任务追踪)
# ========================

async def create_task(
    task_id: str,
    plan_id: str,
    version: str,
    task_number: int,
    title: str,
    description: Optional[str] = None,
    owner_id: Optional[str] = None,
    owner_level: Optional[int] = None,
    owner_role: Optional[str] = None,
    priority: str = "medium",
    difficulty: str = "medium",
    estimated_hours: Optional[float] = None,
    dependencies: Optional[List[str]] = None,
    deadline: Optional[str] = None,
) -> Dict[str, Any]:
    """创建任务记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks (task_id, plan_id, version, task_number, title,
                              description, owner_id, owner_level, owner_role,
                              priority, difficulty, estimated_hours, dependencies,
                              deadline, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW(), NOW())
            RETURNING *
            """,
            task_id, plan_id, version, task_number, title,
            description, owner_id, owner_level, owner_role,
            priority, difficulty, estimated_hours,
            json.dumps(dependencies or []),
            deadline
        )
        return dict(row)


async def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取单个任务"""
    async with get_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM tasks WHERE task_id = $1", task_id)
        return dict(row) if row else None


async def list_tasks(plan_id: str, version: str) -> List[Dict[str, Any]]:
    """列出指定版本的所有任务"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM tasks WHERE plan_id = $1 AND version = $2 ORDER BY task_number",
            plan_id, version
        )
        return [dict(row) for row in rows]


async def update_task(task_id: str, **fields) -> Optional[Dict[str, Any]]:
    """更新任务字段"""
    if not fields:
        return await get_task(task_id)
    set_clauses = []
    values = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        set_clauses.append(f"{k} = ${i}")
        # JSONB列需要JSON字符串，asyncpg直接存储
        # 读取时asyncpg返回Python list/dict（asyncpg自动解码JSONB）
        # blocked_by/dependencies可能已经是list（来自asyncpg）或str（来自内存）
        if isinstance(v, (list, dict)):
            values.append(json.dumps(v))
        elif k in ("blocked_by", "dependencies") and isinstance(v, str):
            # 如果已经是JSON字符串（原样使用，避免double-encode）
            values.append(v)
        else:
            values.append(v)
    values.append(task_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"UPDATE tasks SET {', '.join(set_clauses)}, updated_at = NOW() "
            f"WHERE task_id = ${len(values)} RETURNING *",
            *values
        )
        return dict(row) if row else None


async def update_task_progress(task_id: str, progress: float, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """更新任务进度"""
    now = datetime.now()
    fields = {"progress": progress}
    if status:
        fields["status"] = status
    if progress > 0:
        fields["started_at"] = now
    if status == "completed":
        fields["completed_at"] = now
        fields["progress"] = 1.0
    return await update_task(task_id, **fields)


async def delete_task(task_id: str) -> bool:
    """删除任务"""
    async with get_connection() as conn:
        result = await conn.execute("DELETE FROM tasks WHERE task_id = $1", task_id)
        return result == "DELETE 1"


async def get_task_metrics(plan_id: str, version: str) -> Dict[str, Any]:
    """获取任务统计指标"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) as count, SUM(progress) as total_progress "
            "FROM tasks WHERE plan_id = $1 AND version = $2 GROUP BY status",
            plan_id, version
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE plan_id = $1 AND version = $2",
            plan_id, version
        )
        total_hours_est = await conn.fetchval(
            "SELECT COALESCE(SUM(estimated_hours), 0) FROM tasks WHERE plan_id = $1 AND version = $2",
            plan_id, version
        )
        total_hours_act = await conn.fetchval(
            "SELECT COALESCE(SUM(actual_hours), 0) FROM tasks WHERE plan_id = $1 AND version = $2",
            plan_id, version
        )
        status_map = {row["status"]: row for row in rows}
        return {
            "total": total,
            "pending": status_map.get("pending", {}).get("count", 0),
            "in_progress": status_map.get("in_progress", {}).get("count", 0),
            "completed": status_map.get("completed", {}).get("count", 0),
            "blocked": status_map.get("blocked", {}).get("count", 0),
            "cancelled": status_map.get("cancelled", {}).get("count", 0),
            "total_estimated_hours": float(total_hours_est),
            "total_actual_hours": float(total_hours_act),
            "progress_percentage": (
                sum(status_map.get("completed", {}).get("total_progress", 0) or 0 for _ in [1]) / max(total, 1)
            ),
        }


# ========================
# Escalations（层级汇报/升级，05-Hierarchy-Roles.md §7.2）
# ========================


async def create_escalation(
    escalation_id: str,
    room_id: str,
    plan_id: str,
    version: str,
    from_level: int,
    to_level: int,
    mode: str,
    content: Dict[str, Any],
    escalation_path: List[int],
    status: str,
    escalated_by: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """创建升级记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO escalations (
                escalation_id, room_id, plan_id, version,
                from_level, to_level, mode, content,
                escalation_path, status, escalated_by, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING *
            """,
            escalation_id, room_id, plan_id, version,
            from_level, to_level, mode,
            json.dumps(content),
            json.dumps(escalation_path),
            status, escalated_by, notes,
        )
        return dict(row)


async def get_escalation(escalation_id: str) -> Optional[Dict[str, Any]]:
    """获取单个升级记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM escalations WHERE escalation_id = $1", escalation_id
        )
        return dict(row) if row else None


async def get_room_escalations(room_id: str) -> List[Dict[str, Any]]:
    """获取房间的所有升级记录"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM escalations WHERE room_id = $1 ORDER BY escalated_at DESC",
            room_id
        )
        return [dict(row) for row in rows]


async def get_plan_escalations(plan_id: str) -> List[Dict[str, Any]]:
    """获取方案的所有升级记录"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM escalations WHERE plan_id = $1 ORDER BY escalated_at DESC",
            plan_id
        )
        return [dict(row) for row in rows]


async def update_escalation_status(escalation_id: str, status: str) -> Optional[Dict[str, Any]]:
    """更新升级状态"""
    async with get_connection() as conn:
        update_fields = "status = $2"
        params = [escalation_id, status]
        param_idx = 3

        if status == "acknowledged":
            update_fields += f", acknowledged_at = ${param_idx}"
            params.append(datetime.now())
            param_idx += 1
        elif status == "completed":
            update_fields += f", completed_at = ${param_idx}"
            params.append(datetime.now())
            param_idx += 1

        row = await conn.fetchrow(
            f"UPDATE escalations SET {update_fields} WHERE escalation_id = $1 RETURNING *",
            *params
        )
        return dict(row) if row else None


# ========================
# Decisions
# ========================

async def create_decision(
    decision_id: str,
    plan_id: str,
    version: str,
    decision_number: int,
    title: str,
    decision_text: str,
    description: Optional[str] = None,
    rationale: Optional[str] = None,
    alternatives_considered: Optional[List[str]] = None,
    agreed_by: Optional[List[str]] = None,
    disagreed_by: Optional[List[str]] = None,
    decided_by: Optional[str] = None,
    room_id: Optional[str] = None,
) -> Dict[str, Any]:
    """创建决策记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO decisions
                (decision_id, plan_id, version, decision_number, title, description,
                 decision_text, rationale, alternatives_considered, agreed_by,
                 disagreed_by, decided_by, room_id, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
            RETURNING *
            """,
            decision_id, plan_id, version, decision_number, title, description,
            decision_text, rationale,
            json.dumps(alternatives_considered or []),
            json.dumps(agreed_by or []),
            json.dumps(disagreed_by or []),
            decided_by, room_id,
        )
        return dict(row)


async def list_decisions(plan_id: str, version: str) -> List[Dict[str, Any]]:
    """列出指定版本的所有决策"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM decisions
            WHERE plan_id = $1 AND version = $2
            ORDER BY decision_number ASC
            """,
            plan_id, version,
        )
        return [dict(row) for row in rows]


async def get_decision(decision_id: str) -> Optional[Dict[str, Any]]:
    """获取单个决策"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM decisions WHERE decision_id = $1",
            decision_id,
        )
        return dict(row) if row else None


async def update_decision(decision_id: str, **fields) -> Optional[Dict[str, Any]]:
    """更新决策字段"""
    if not fields:
        return await get_decision(decision_id)

    allowed = {
        "title", "description", "decision_text", "rationale",
        "alternatives_considered", "agreed_by", "disagreed_by", "decided_by",
    }
    set_clauses = []
    params = []
    idx = 1

    for key, val in fields.items():
        if key in allowed:
            if isinstance(val, (list, dict)):
                set_clauses.append(f"{key} = ${idx}")
                params.append(json.dumps(val))
            else:
                set_clauses.append(f"{key} = ${idx}")
                params.append(val)
            idx += 1

    if not set_clauses:
        return await get_decision(decision_id)

    params.append(decision_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"UPDATE decisions SET {', '.join(set_clauses)} "
            f"WHERE decision_id = ${idx} RETURNING *",
            *params,
        )
        return dict(row) if row else None


# ========================
# Task Comments（任务评论）
# 来源: 08-Data-Models-Details.md §3.1 Task模型 comments
# ========================

async def create_task_comment(
    comment_id: str,
    task_id: str,
    plan_id: str,
    version: str,
    author_name: str,
    content: str,
    author_id: Optional[str] = None,
    author_level: Optional[int] = None,
) -> Dict[str, Any]:
    """创建任务评论"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO task_comments
                (comment_id, task_id, plan_id, version, author_id,
                 author_name, author_level, content, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
            RETURNING *
            """,
            comment_id, task_id, plan_id, version,
            author_id, author_name, author_level, content,
        )
        return dict(row)


async def list_task_comments(task_id: str) -> List[Dict[str, Any]]:
    """列出任务的所有评论"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM task_comments
            WHERE task_id = $1
            ORDER BY created_at ASC
            """,
            task_id,
        )
        return [dict(row) for row in rows]


async def update_task_comment(
    comment_id: str,
    content: str,
) -> Optional[Dict[str, Any]]:
    """更新任务评论内容"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE task_comments
            SET content = $2, updated_at = NOW()
            WHERE comment_id = $1
            RETURNING *
            """,
            comment_id, content,
        )
        return dict(row) if row else None


async def delete_task_comment(comment_id: str) -> bool:
    """删除任务评论"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM task_comments WHERE comment_id = $1",
            comment_id,
        )
        return "DELETE 1" in result


# ========================
# Task Checkpoints（任务检查点）
# 来源: 08-Data-Models-Details.md §3.1 Task模型 checkpoints
# ========================

async def create_task_checkpoint(
    checkpoint_id: str,
    task_id: str,
    plan_id: str,
    version: str,
    name: str,
    status: str = "pending",
) -> Dict[str, Any]:
    """创建任务检查点"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO task_checkpoints
                (checkpoint_id, task_id, plan_id, version, name, status,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING *
            """,
            checkpoint_id, task_id, plan_id, version, name, status,
        )
        return dict(row)


async def list_task_checkpoints(task_id: str) -> List[Dict[str, Any]]:
    """列出任务的所有检查点"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM task_checkpoints
            WHERE task_id = $1
            ORDER BY created_at ASC
            """,
            task_id,
        )
        return [dict(row) for row in rows]


async def update_task_checkpoint(
    checkpoint_id: str,
    name: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """更新检查点（名称或状态）"""
    set_clauses = ["updated_at = NOW()"]
    params = []
    idx = 1

    if name is not None:
        set_clauses.append(f"name = ${idx}")
        params.append(name)
        idx += 1

    if status is not None:
        set_clauses.append(f"status = ${idx}")
        params.append(status)
        idx += 1
        if status == "completed":
            set_clauses.append("completed_at = NOW()")
        elif status == "pending":
            set_clauses.append("completed_at = NULL")

    params.append(checkpoint_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE task_checkpoints
            SET {', '.join(set_clauses)}
            WHERE checkpoint_id = ${idx}
            RETURNING *
            """,
            *params,
        )
        return dict(row) if row else None


async def delete_task_checkpoint(checkpoint_id: str) -> bool:
    """删除检查点"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM task_checkpoints WHERE checkpoint_id = $1",
            checkpoint_id,
        )
        return "DELETE 1" in result


# ========================
# SubTasks (子任务)
# 来源: 08-Data-Models-Details.md §3.1 Task模型 sub_tasks
# ========================

async def create_sub_task(
    sub_task_id: str,
    task_id: str,
    plan_id: str,
    version: str,
    title: str,
    description: Optional[str] = None,
    status: str = "pending",
) -> Dict[str, Any]:
    """创建子任务"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sub_tasks
                (sub_task_id, task_id, plan_id, version, title, description, status,
                 created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            RETURNING *
            """,
            sub_task_id, task_id, plan_id, version, title, description, status,
        )
        return dict(row)


async def list_sub_tasks(task_id: str) -> List[Dict[str, Any]]:
    """列出任务的所有子任务"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM sub_tasks
            WHERE task_id = $1
            ORDER BY created_at ASC
            """,
            task_id,
        )
        return [dict(row) for row in rows]


async def update_sub_task(
    sub_task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    progress: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """更新子任务"""
    set_clauses = ["updated_at = NOW()"]
    params = []
    idx = 1

    if title is not None:
        set_clauses.append(f"title = ${idx}")
        params.append(title)
        idx += 1

    if description is not None:
        set_clauses.append(f"description = ${idx}")
        params.append(description)
        idx += 1

    if status is not None:
        set_clauses.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    if progress is not None:
        set_clauses.append(f"progress = ${idx}")
        params.append(progress)
        idx += 1

    params.append(sub_task_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE sub_tasks
            SET {', '.join(set_clauses)}
            WHERE sub_task_id = ${idx}
            RETURNING *
            """,
            *params,
        )
        return dict(row) if row else None


async def delete_sub_task(sub_task_id: str) -> bool:
    """删除子任务"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM sub_tasks WHERE sub_task_id = $1",
            sub_task_id,
        )
        return "DELETE 1" in result


# ========================
# Constraints (Plan 约束)
# 来源: 08-Data-Models-Details.md §2.1 Plan.constraints
# ========================

async def create_constraint(constraint: Dict[str, Any]) -> Dict[str, Any]:
    """创建约束"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO constraints
              (constraint_id, plan_id, type, value, unit, description, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            RETURNING *
            """,
            constraint["constraint_id"], constraint["plan_id"], constraint["type"],
            constraint["value"], constraint["unit"], constraint["description"]
        )
        return dict(row)


async def get_constraints(plan_id: str) -> List[Dict[str, Any]]:
    """获取 Plan 的所有约束"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM constraints WHERE plan_id = $1 ORDER BY created_at",
            plan_id
        )
        return [dict(r) for r in rows]


async def get_constraint(constraint_id: str) -> Optional[Dict[str, Any]]:
    """获取单个约束"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM constraints WHERE constraint_id = $1",
            constraint_id
        )
        return dict(row) if row else None


async def update_constraint(constraint_id: str, constraint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新约束"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE constraints
            SET type = $2, value = $3, unit = $4, description = $5, updated_at = NOW()
            WHERE constraint_id = $1
            RETURNING *
            """,
            constraint_id, constraint["type"], constraint["value"],
            constraint["unit"], constraint["description"]
        )
        return dict(row) if row else None


async def delete_constraint(constraint_id: str) -> bool:
    """删除约束"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM constraints WHERE constraint_id = $1",
            constraint_id,
        )
        return "DELETE 1" in result


# ========================
# Stakeholders (Plan 干系人)
# 来源: 08-Data-Models-Details.md §2.1 Plan.stakeholders
# ========================

async def create_stakeholder(stakeholder: Dict[str, Any]) -> Dict[str, Any]:
    """创建干系人"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO stakeholders
              (stakeholder_id, plan_id, name, level, interest, influence, description, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            RETURNING *
            """,
            stakeholder["stakeholder_id"], stakeholder["plan_id"], stakeholder["name"],
            stakeholder["level"], stakeholder["interest"], stakeholder["influence"],
            stakeholder["description"]
        )
        return dict(row)


async def get_stakeholders(plan_id: str) -> List[Dict[str, Any]]:
    """获取 Plan 的所有干系人"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM stakeholders WHERE plan_id = $1 ORDER BY created_at",
            plan_id
        )
        return [dict(r) for r in rows]


async def get_stakeholder(stakeholder_id: str) -> Optional[Dict[str, Any]]:
    """获取单个干系人"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM stakeholders WHERE stakeholder_id = $1",
            stakeholder_id
        )
        return dict(row) if row else None


async def update_stakeholder(stakeholder_id: str, stakeholder: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新干系人"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE stakeholders
            SET name = $2, level = $3, interest = $4, influence = $5, description = $6, updated_at = NOW()
            WHERE stakeholder_id = $1
            RETURNING *
            """,
            stakeholder_id, stakeholder["name"], stakeholder["level"],
            stakeholder["interest"], stakeholder["influence"], stakeholder["description"]
        )
        return dict(row) if row else None


async def delete_stakeholder(stakeholder_id: str) -> bool:
    """删除干系人"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM stakeholders WHERE stakeholder_id = $1",
            stakeholder_id,
        )
        return "DELETE 1" in result


# ========================
# Risks (Version 风险)
# 来源: 08-Data-Models-Details.md §3.1 Version.risks
# ========================

async def create_risk(risk: Dict[str, Any]) -> Dict[str, Any]:
    """创建风险"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO risks
              (risk_id, plan_id, version, title, description, probability, impact,
               severity, mitigation, contingency, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
            RETURNING *
            """,
            risk["risk_id"], risk["plan_id"], risk["version"], risk["title"],
            risk["description"], risk["probability"], risk["impact"],
            risk["severity"], risk["mitigation"], risk["contingency"], risk["status"]
        )
        return dict(row)


async def get_risks(plan_id: str, version: str) -> List[Dict[str, Any]]:
    """获取 Version 的所有风险"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM risks WHERE plan_id = $1 AND version = $2 ORDER BY created_at",
            plan_id, version
        )
        return [dict(r) for r in rows]


async def get_risk(risk_id: str) -> Optional[Dict[str, Any]]:
    """获取单个风险"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM risks WHERE risk_id = $1",
            risk_id
        )
        return dict(row) if row else None


async def update_risk(risk_id: str, risk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新风险"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE risks
            SET title = $2, description = $3, probability = $4, impact = $5,
                severity = $6, mitigation = $7, contingency = $8, status = $9, updated_at = NOW()
            WHERE risk_id = $1
            RETURNING *
            """,
            risk_id, risk["title"], risk["description"], risk["probability"],
            risk["impact"], risk["severity"], risk["mitigation"],
            risk["contingency"], risk["status"]
        )
        return dict(row) if row else None


async def delete_risk(risk_id: str) -> bool:
    """删除风险"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM risks WHERE risk_id = $1",
            risk_id,
        )
        return "DELETE 1" in result


# ========================
# Step 24: Room Hierarchy + Participant Contributions
# ========================

async def link_rooms(room_id: str, parent_room_id: Optional[str] = None,
                     related_room_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """建立讨论室层级关系（父子/关联）"""
    # 获取当前 room 的 child_rooms 和 related_rooms
    current = await get_room(room_id)
    if not current:
        return None

    child_rooms = current.get("child_rooms") or []
    if isinstance(child_rooms, str):
        child_rooms = json.loads(child_rooms) if child_rooms else []
    related_rooms = current.get("related_rooms") or []
    if isinstance(related_rooms, str):
        related_rooms = json.loads(related_rooms) if related_rooms else []

    updates = {}
    if parent_room_id:
        updates["parent_room_id"] = parent_room_id
        # 将当前 room 加入父 room 的 child_rooms
        parent = await get_room(parent_room_id)
        if parent:
            parent_child = parent.get("child_rooms") or []
            if isinstance(parent_child, str):
                parent_child = json.loads(parent_child) if parent_child else []
            if room_id not in parent_child:
                parent_child.append(room_id)
            # child_rooms 在 DB 中存为 JSON 字符串
            await update_room(parent_room_id, child_rooms=json.dumps(parent_child))

    if related_room_ids is not None:
        # 建立双向关联
        for rel_id in related_room_ids:
            rel = await get_room(rel_id)
            if rel:
                rel_related = rel.get("related_rooms") or []
                if isinstance(rel_related, str):
                    rel_related = json.loads(rel_related) if rel_related else []
                if room_id not in rel_related:
                    rel_related.append(room_id)
                # related_rooms 在 DB 中存为 JSON 字符串
                await update_room(rel_id, related_rooms=json.dumps(rel_related))
        # related_rooms 在 DB 中存为 JSON 字符串
        updates["related_rooms"] = json.dumps(related_room_ids)

    if updates:
        return await update_room(room_id, **updates)
    return current


async def get_room_messages_count(room_id: str) -> int:
    """获取讨论室消息数量"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM messages WHERE room_id = $1",
            room_id
        )
        return int(row["cnt"]) if row else 0


async def update_participant_contributions(
    participant_id: str,
    speech_delta: int = 0,
    challenge_delta: int = 0,
    response_delta: int = 0,
    thinking_complete: Optional[bool] = None,
    sharing_complete: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """更新参与者贡献计数"""
    async with get_connection() as conn:
        # 先获取当前 contributions
        row = await conn.fetchrow(
            "SELECT contributions FROM participants WHERE participant_id = $1",
            participant_id
        )
        if not row:
            return None

        contributions = row["contributions"] or {}
        if isinstance(contributions, str):
            contributions = json.loads(contributions) if contributions else {}
        contributions = {
            "speech_count": contributions.get("speech_count", 0) + speech_delta,
            "challenge_count": contributions.get("challenge_count", 0) + challenge_delta,
            "response_count": contributions.get("response_count", 0) + response_delta,
        }

        # VALUES 顺序: $1=participant_id, $2=contributions, $3=last_activity(NOW),
        # $4=thinking_complete(optional), $5=sharing_complete(optional)
        values = [participant_id, json.dumps(contributions)]
        fields = ["contributions = $2", "last_activity = NOW()"]
        next_param = 3

        if thinking_complete is not None:
            fields.append(f"thinking_complete = ${next_param}")
            values.append(thinking_complete)
            next_param += 1
        if sharing_complete is not None:
            fields.append(f"sharing_complete = ${next_param}")
            values.append(sharing_complete)
            next_param += 1

        row = await conn.fetchrow(
            f"UPDATE participants SET {', '.join(fields)} "
            f"WHERE participant_id = $1 RETURNING *",
            *values
        )
        if not row:
            return None
        result = dict(row)
        # JSONB 列通过 asyncpg 返回 JSON 字符串（不是 dict），需要反序列化
        if isinstance(result.get("contributions"), str):
            result["contributions"] = json.loads(result["contributions"])
        return result




# ========================
# Edict CRUD (圣旨/下行 decree)
# 来源: 01-Edict-Reference.md
# ========================

async def create_edict(
    edict_id: str,
    plan_id: str,
    version: str,
    edict_number: int,
    title: str,
    content: str,
    issued_by: str,
    decision_id: Optional[str] = None,
    effective_from: Optional[Any] = None,
    recipients: Optional[List[str]] = None,
    status: str = "published",
) -> Dict[str, Any]:
    """创建圣旨记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO edicts
                (edict_id, plan_id, version, edict_number, title, content,
                 decision_id, issued_by, issued_at, effective_from, recipients, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), $9, $10, $11, NOW())
            RETURNING *
            """,
            edict_id, plan_id, version, edict_number, title, content,
            decision_id, issued_by,
            effective_from,
            json.dumps(recipients or []),
            status,
        )
        return dict(row)


async def list_edicts(plan_id: str, version: str) -> List[Dict[str, Any]]:
    """列出指定版本的所有圣旨"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM edicts
            WHERE plan_id = $1 AND version = $2
            ORDER BY edict_number ASC
            """,
            plan_id, version,
        )
        return [dict(row) for row in rows]


async def get_edict(edict_id: str) -> Optional[Dict[str, Any]]:
    """获取单个圣旨"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM edicts WHERE edict_id = $1",
            edict_id,
        )
        return dict(row) if row else None


async def update_edict(edict_id: str, **fields) -> Optional[Dict[str, Any]]:
    """更新圣旨字段"""
    if not fields:
        return await get_edict(edict_id)

    allowed = {
        "title", "content", "decision_id", "issued_by",
        "effective_from", "recipients", "status",
    }
    set_clauses = []
    params = []
    idx = 1

    for key, val in fields.items():
        if key in allowed and val is not None:
            if key in ("recipients",):
                set_clauses.append(f"{key} = ${idx}")
                params.append(json.dumps(val))
            else:
                set_clauses.append(f"{key} = ${idx}")
                params.append(val)
            idx += 1

    if not set_clauses:
        return await get_edict(edict_id)

    params.append(edict_id)
    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"UPDATE edicts SET {', '.join(set_clauses)}, updated_at = NOW() "
            f"WHERE edict_id = ${len(params)} RETURNING *",
            *params
        )
        return dict(row) if row else None


async def delete_edict(edict_id: str) -> bool:
    """删除圣旨"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM edicts WHERE edict_id = $1",
            edict_id,
        )
        return result == "DELETE 1"


# ========================
# Step 38: Edict Acknowledgments（圣旨签收记录）
# ========================

async def create_edict_acknowledgment(
    ack_id: str,
    edict_id: str,
    plan_id: str,
    version: str,
    acknowledged_by: str,
    level: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """创建圣旨签收记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO edict_acknowledgments
                (ack_id, edict_id, plan_id, version, acknowledged_by, level, comment, acknowledged_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING *
            """,
            ack_id, edict_id, plan_id, version, acknowledged_by, level, comment,
        )
        return dict(row)


async def list_edict_acknowledgments(edict_id: str) -> List[Dict[str, Any]]:
    """列出某圣旨的所有签收记录"""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM edict_acknowledgments
            WHERE edict_id = $1
            ORDER BY acknowledged_at ASC
            """,
            edict_id,
        )
        return [dict(row) for row in rows]


async def get_edict_acknowledgment(ack_id: str) -> Optional[Dict[str, Any]]:
    """获取单个签收记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM edict_acknowledgments WHERE ack_id = $1",
            ack_id,
        )
        return dict(row) if row else None


async def delete_edict_acknowledgment(ack_id: str) -> bool:
    """删除签收记录"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM edict_acknowledgments WHERE ack_id = $1",
            ack_id,
        )
        return result == "DELETE 1"


# ========================
# Step 31: Activity Audit Log
# ========================

async def create_activity(
    activity_id: str,
    plan_id: str,
    action_type: str,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    version: Optional[str] = None,
    room_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    target_label: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """创建活动日志"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO activities
                (activity_id, plan_id, version, room_id, action_type, actor_id, actor_name,
                 target_type, target_id, target_label, details, occurred_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            RETURNING *
            """,
            activity_id,
            plan_id,
            version,
            room_id,
            action_type,
            actor_id,
            actor_name,
            target_type,
            target_id,
            target_label,
            json.dumps(details) if details else {},
        )
        return dict(row) if row else {}


async def list_activities(
    plan_id: Optional[str] = None,
    room_id: Optional[str] = None,
    version: Optional[str] = None,
    action_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """列出活动日志（支持过滤）"""
    conditions = []
    params = []
    idx = 1

    if plan_id:
        conditions.append(f"plan_id = ${idx}")
        params.append(plan_id)
        idx += 1
    if room_id:
        conditions.append(f"room_id = ${idx}")
        params.append(room_id)
        idx += 1
    if version:
        conditions.append(f"version = ${idx}")
        params.append(version)
        idx += 1
    if action_type:
        conditions.append(f"action_type = ${idx}")
        params.append(action_type)
        idx += 1
    if actor_id:
        conditions.append(f"actor_id = ${idx}")
        params.append(actor_id)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])

    async with get_connection() as conn:
        rows = await conn.fetch(
            f"""
            SELECT * FROM activities
            {where}
            ORDER BY occurred_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params
        )
        return [dict(r) for r in rows]


async def get_activity(activity_id: str) -> Optional[Dict[str, Any]]:
    """获取单个活动"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM activities WHERE activity_id = $1",
            activity_id,
        )
        return dict(row) if row else None


async def count_activities(
    plan_id: Optional[str] = None,
    action_type: Optional[str] = None,
) -> int:
    """统计活动数量"""
    conditions = []
    params = []
    idx = 1

    if plan_id:
        conditions.append(f"plan_id = ${idx}")
        params.append(plan_id)
        idx += 1
    if action_type:
        conditions.append(f"action_type = ${idx}")
        params.append(action_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"SELECT COUNT(*) as cnt FROM activities {where}",
            *params
        )
        return row["cnt"] if row else 0


# ============================================================
# Notification System (Step 34)
# ============================================================

async def create_notification(
    notification_id: str,
    plan_id: Optional[str],
    recipient_id: str,
    recipient_level: Optional[int],
    notification_type: str,
    title: str,
    message: Optional[str],
    version: Optional[str] = None,
    room_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """创建通知记录"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO notifications
                (notification_id, plan_id, version, room_id, task_id,
                 recipient_id, recipient_level, type, title, message,
                 read, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, FALSE, NOW())
            RETURNING *
            """,
            notification_id, plan_id, version, room_id, task_id,
            recipient_id, recipient_level, notification_type, title, message,
        )
        return dict(row) if row else {}


async def list_notifications(
    recipient_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    room_id: Optional[str] = None,
    notification_type: Optional[str] = None,
    read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """列出通知（支持过滤）"""
    conditions = []
    params = []
    idx = 1

    if recipient_id:
        conditions.append(f"recipient_id = ${idx}")
        params.append(recipient_id)
        idx += 1
    if plan_id:
        conditions.append(f"plan_id = ${idx}")
        params.append(plan_id)
        idx += 1
    if room_id:
        conditions.append(f"room_id = ${idx}")
        params.append(room_id)
        idx += 1
    if notification_type:
        conditions.append(f"type = ${idx}")
        params.append(notification_type)
        idx += 1
    if read is not None:
        conditions.append(f"read = ${idx}")
        params.append(read)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])

    async with get_connection() as conn:
        rows = await conn.fetch(
            f"""
            SELECT * FROM notifications
            {where}
            ORDER BY created_at DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params
        )
        return [dict(r) for r in rows]


async def get_notification(notification_id: str) -> Optional[Dict[str, Any]]:
    """获取单个通知"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM notifications WHERE notification_id = $1",
            notification_id,
        )
        return dict(row) if row else None


async def mark_notification_read(notification_id: str) -> Optional[Dict[str, Any]]:
    """标记通知为已读"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE notifications
            SET read = TRUE, read_at = NOW()
            WHERE notification_id = $1
            RETURNING *
            """,
            notification_id,
        )
        return dict(row) if row else None


async def mark_all_notifications_read(recipient_id: str) -> int:
    """标记该接收人的所有通知为已读"""
    async with get_connection() as conn:
        row = await conn.execute(
            """
            UPDATE notifications
            SET read = TRUE, read_at = NOW()
            WHERE recipient_id = $1 AND read = FALSE
            """,
            recipient_id,
        )
        # row is the result string like "UPDATE 5"
        if row and "UPDATE" in row:
            parts = row.split()
            if len(parts) >= 2:
                return int(parts[1])
        return 0


async def get_unread_notification_count(recipient_id: str) -> int:
    """获取未读通知数量"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM notifications WHERE recipient_id = $1 AND read = FALSE",
            recipient_id,
        )
        return row["cnt"] if row else 0


async def delete_notification(notification_id: str) -> bool:
    """删除通知"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM notifications WHERE notification_id = $1",
            notification_id,
        )
        return result == "DELETE 1"


async def count_notifications(
    recipient_id: Optional[str] = None,
    read: Optional[bool] = None,
) -> int:
    """统计通知数量"""
    conditions = []
    params = []
    idx = 1

    if recipient_id:
        conditions.append(f"recipient_id = ${idx}")
        params.append(recipient_id)
        idx += 1
    if read is not None:
        conditions.append(f"read = ${idx}")
        params.append(read)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"SELECT COUNT(*) as cnt FROM notifications {where}",
            *params
        )
        return row["cnt"] if row else 0


# ========================
# Room Templates
# ========================

async def create_room_template(
    template_id: str,
    name: str,
    description: Optional[str] = None,
    purpose: str = "initial_discussion",
    mode: str = "hierarchical",
    default_phase: str = "selecting",
    settings: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None,
    is_shared: bool = False,
) -> Dict[str, Any]:
    """创建房间模板"""
    settings_json = json.dumps(settings or {})
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO room_templates (template_id, name, description, purpose, mode, default_phase, settings, created_by, is_shared, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
            RETURNING *
            """,
            template_id, name, description, purpose, mode, default_phase, settings_json, created_by, is_shared,
        )
        return dict(row) if row else {}


async def list_room_templates(
    purpose: Optional[str] = None,
    is_shared: Optional[bool] = None,
    created_by: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """列出房间模板"""
    conditions = []
    params = []
    idx = 1

    if purpose:
        conditions.append(f"purpose = ${idx}")
        params.append(purpose)
        idx += 1
    if is_shared is not None:
        conditions.append(f"is_shared = ${idx}")
        params.append(is_shared)
        idx += 1
    if created_by:
        conditions.append(f"created_by = ${idx}")
        params.append(created_by)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order = "ORDER BY created_at DESC"

    async with get_connection() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM room_templates {where} {order}",
            *params
        )
        return [dict(r) for r in rows]


async def get_room_template(template_id: str) -> Optional[Dict[str, Any]]:
    """获取单个房间模板"""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM room_templates WHERE template_id = $1",
            template_id,
        )
        return dict(row) if row else None


async def update_room_template(
    template_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    purpose: Optional[str] = None,
    mode: Optional[str] = None,
    default_phase: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    is_shared: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """更新房间模板"""
    fields = []
    params = []
    idx = 1

    if name is not None:
        fields.append(f"name = ${idx}")
        params.append(name)
        idx += 1
    if description is not None:
        fields.append(f"description = ${idx}")
        params.append(description)
        idx += 1
    if purpose is not None:
        fields.append(f"purpose = ${idx}")
        params.append(purpose)
        idx += 1
    if mode is not None:
        fields.append(f"mode = ${idx}")
        params.append(mode)
        idx += 1
    if default_phase is not None:
        fields.append(f"default_phase = ${idx}")
        params.append(default_phase)
        idx += 1
    if settings is not None:
        fields.append(f"settings = ${idx}")
        params.append(json.dumps(settings))
        idx += 1
    if is_shared is not None:
        fields.append(f"is_shared = ${idx}")
        params.append(is_shared)
        idx += 1

    if not fields:
        return await get_room_template(template_id)

    fields.append("updated_at = NOW()")
    params.append(template_id)

    async with get_connection() as conn:
        row = await conn.fetchrow(
            f"UPDATE room_templates SET {', '.join(fields)} WHERE template_id = ${idx} RETURNING *",
            *params
        )
        return dict(row) if row else None


async def delete_room_template(template_id: str) -> bool:
    """删除房间模板"""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM room_templates WHERE template_id = $1",
            template_id,
        )
        return result == "DELETE 1"

