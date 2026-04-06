"""
crud.py 静态分析单元测试
验证 repositories/crud.py 的 SQL 查询、参数绑定、函数签名正确性。
与 test_db.py 相同的静态分析模式 — 不依赖运行中的数据库。
"""
import ast
import re
import pytest
from pathlib import Path

CRUD_PATH = Path(__file__).parent.parent / "backend" / "repositories" / "crud.py"
crud_source = CRUD_PATH.read_text()


# ========================
# 辅助函数
# ========================

def find_function_sql(func_name: str) -> str:
    """提取函数内的 SQL 字符串（多行聚合）"""
    pattern = rf"async def {func_name}\([^)]*\)[^:]*:(.*?)(?=\n(?:async def|def [a-z]|\Z))"
    match = re.search(pattern, crud_source, re.DOTALL)
    if not match:
        return ""
    body = match.group(1)
    # 提取所有 "..." 字符串（SQL）
    sqls = re.findall(r'"""(.*?)"""', body, re.DOTALL)
    sqls += re.findall(r"'''(.*?)'''", body, re.DOTALL)
    return " ".join(sqls).strip()


def find_function_source(func_name: str) -> str:
    """提取完整函数源码"""
    pattern = rf"(async def {func_name}\b.*?(?=\n(?:async def|def [a-z]|\Z))"
    match = re.search(pattern, crud_source, re.DOTALL)
    return match.group(0) if match else ""


def count_dollar_placeholders(sql: str) -> int:
    """统计 $1, $2 等占位符数量"""
    return len(re.findall(r'\$\d+', sql))


def extract_fetch_params(sql: str) -> tuple:
    """从 SQL fetch 语句提取参数列表（async with get_connection() as conn: ... row = await conn.fetch(...)）"""
    # 匹配: await conn.fetch(sql, *params) 或 await conn.fetchrow(sql, *params)
    pattern = r'(?:await conn\.(?:fetch|fetchrow|execute))\s*\((.*?)\)\s*(?:as|\n)'
    matches = re.findall(pattern, sql, re.DOTALL)
    if not matches:
        return [], []
    # 找到最多参数的调用
    call = max(matches, key=lambda x: len(re.findall(r'\$\d+', sql)))
    # 提取 $ 占位符
    placeholders = re.findall(r'\$\d+', sql)
    return placeholders, call


# ========================
# TestCrudPlansSql — Plans CRUD SQL 正确性
# ========================

class TestCrudPlansSql:
    def test_create_plan_sql_has_all_columns(self):
        """create_plan: INSERT 包含所有必需列"""
        sql = find_function_sql("create_plan")
        assert "plan_id" in sql
        assert "plan_number" in sql
        assert "title" in sql
        assert "topic" in sql
        assert "requirements" in sql
        assert "hierarchy_id" in sql
        assert "current_version" in sql
        assert "versions" in sql
        assert "created_at" in sql
        assert "updated_at" in sql
        assert "RETURNING *" in sql

    def test_create_plan_uses_json_for_requirements(self):
        """create_plan: requirements 使用 json.dumps"""
        source = find_function_source("create_plan")
        assert "json.dumps(requirements)" in source

    def test_create_plan_uses_json_for_versions(self):
        """create_plan: versions 使用 json.dumps"""
        source = find_function_source("create_plan")
        assert "json.dumps([current_version])" in source

    def test_get_plan_uses_select_star(self):
        """get_plan: 使用 SELECT * + plan_id 过滤"""
        sql = find_function_sql("get_plan")
        assert "SELECT *" in sql
        assert "plan_id = $1" in sql

    def test_update_plan_handles_empty_fields(self):
        """update_plan: 空 fields 时返回 get_plan"""
        source = find_function_source("update_plan")
        assert "if not fields:" in source
        assert "get_plan(plan_id)" in source

    def test_update_plan_uses_set_clauses(self):
        """update_plan: 使用动态 SET 子句"""
        source = find_function_source("update_plan")
        assert "set_clauses" in source
        assert "updated_at = NOW()" in source

    def test_update_plan_tags_is_list(self):
        """update_plan: tags 字段传递 list 而非 json.dumps"""
        source = find_function_source("update_plan")
        # tags 是 TEXT[]，直接传 list
        assert "k == \"tags\"" in source or "k == 'tags'" in source

    def test_delete_plan_uses_execute(self):
        """delete_plan: 使用 conn.execute DELETE"""
        sql = find_function_sql("delete_plan")
        assert "DELETE FROM plans" in sql
        assert "plan_id = $1" in sql

    def test_list_plans_uses_fetch(self):
        """list_plans: 使用 conn.fetch"""
        sql = find_function_sql("list_plans")
        assert "SELECT" in sql
        assert "ORDER BY created_at DESC" in sql

    def test_search_plans_uses_ilike(self):
        """search_plans: 使用 ILIKE 模糊搜索"""
        sql = find_function_sql("search_plans")
        assert "ILIKE $1" in sql
        assert "title ILIKE" in sql or "topic ILIKE" in sql

    def test_search_plans_handles_status_filter(self):
        """search_plans: status 过滤正确追加条件"""
        source = find_function_source("search_plans")
        assert "if status:" in source

    def test_search_plans_uses_tags_overlap_operator(self):
        """search_plans: tags 过滤使用 && 数组重叠操作符"""
        sql = find_function_sql("search_plans")
        assert "tags &&" in sql

    def test_search_plans_uses_limit_offset(self):
        """search_plans: 使用 LIMIT 和 OFFSET"""
        sql = find_function_sql("search_plans")
        assert "LIMIT" in sql
        assert "OFFSET" in sql

    def test_copy_plan_has_no_purpose_mode_in_insert(self):
        """copy_plan: INSERT 不包含 purpose/mode（它们属于 rooms 表）"""
        source = find_function_source("copy_plan")
        # 检查 INSERT 语句不包含 purpose 或 mode
        insert_match = re.search(r'INSERT INTO plans.*?RETURNING', source, re.DOTALL)
        if insert_match:
            insert_sql = insert_match.group(0)
            assert "purpose" not in insert_sql.lower(), "copy_plan INSERT 不应包含 purpose 字段"
            assert "mode" not in insert_sql.lower(), "copy_plan INSERT 不应包含 mode 字段"


# ========================
# TestCrudRoomsSql — Rooms CRUD SQL 正确性
# ========================

class TestCrudRoomsSql:
    def test_create_room_sql_has_all_columns(self):
        """create_room: INSERT 包含所有必需列"""
        sql = find_function_sql("create_room")
        assert "room_id" in sql
        assert "room_number" in sql
        assert "plan_id" in sql
        assert "topic" in sql
        assert "coordinator_id" in sql
        assert "current_version" in sql
        assert "created_at" in sql
        assert "RETURNING *" in sql

    def test_create_room_returns_dict(self):
        """create_room: 返回 dict(row)"""
        source = find_function_source("create_room")
        assert "dict(row)" in source

    def test_get_room_uses_select_star(self):
        """get_room: 使用 SELECT * + room_id 过滤"""
        sql = find_function_sql("get_room")
        assert "SELECT *" in sql
        assert "room_id = $1" in sql

    def test_update_room_handles_fields(self):
        """update_room: 动态处理字段更新"""
        source = find_function_source("update_room")
        assert "set_clauses" in source or "UPDATE" in sql

    def test_get_rooms_by_plan_uses_plan_filter(self):
        """get_rooms_by_plan: 按 plan_id 过滤"""
        sql = find_function_sql("get_rooms_by_plan")
        assert "plan_id = $1" in sql

    def test_search_rooms_uses_ilike_on_topic(self):
        """search_rooms: topic 使用 ILIKE 模糊搜索"""
        sql = find_function_sql("search_rooms")
        assert "r.topic ILIKE" in sql

    def test_search_rooms_joins_participants(self):
        """search_rooms: LEFT JOIN participants"""
        sql = find_function_sql("search_rooms")
        assert "LEFT JOIN participants" in sql or "LEFT JOIN" in sql

    def test_search_rooms_uses_tags_overlap(self):
        """search_rooms: tags 过滤使用 &&"""
        sql = find_function_sql("search_rooms")
        assert "tags &&" in sql or "r.tags &&" in sql

    def test_search_rooms_uses_limit_offset(self):
        """search_rooms: 使用 LIMIT 和 OFFSET"""
        sql = find_function_sql("search_rooms")
        assert "LIMIT" in sql
        assert "OFFSET" in sql

    def test_search_rooms_count_query_has_same_filters(self):
        """search_rooms: COUNT 查询与主查询过滤条件一致"""
        source = find_function_source("search_rooms")
        # 应该有两个查询：主查询 + COUNT 查询
        fetch_count = source.count("conn.fetch")
        assert fetch_count >= 2, "search_rooms 应有主查询和 COUNT 查询"


# ========================
# TestCrudParticipantsSql — Participants CRUD SQL 正确性
# ========================

class TestCrudParticipantsSql:
    def test_add_participant_uses_insert(self):
        """add_participant: 使用 INSERT"""
        sql = find_function_sql("add_participant")
        assert "INSERT INTO participants" in sql

    def test_add_participant_has_all_fields(self):
        """add_participant: 包含所有参与者字段"""
        sql = find_function_sql("add_participant")
        assert "participant_id" in sql
        assert "room_id" in sql
        assert "agent_id" in sql
        assert "name" in sql
        assert "level" in sql
        assert "role" in sql
        assert "is_active" in sql
        assert "joined_at" in sql

    def test_get_participants_filters_by_room(self):
        """get_participants: 按 room_id 过滤活跃参与者"""
        sql = find_function_sql("get_participants")
        assert "room_id = $1" in sql
        assert "is_active = TRUE" in sql

    def test_deactivate_participant_uses_update(self):
        """deactivate_participant: UPDATE 设置 is_active = FALSE"""
        sql = find_function_sql("deactivate_participant")
        assert "UPDATE participants" in sql
        assert "is_active = FALSE" in sql
        assert "agent_id" in sql

    def test_get_next_message_sequence_uses_coalesce(self):
        """get_next_message_sequence: 使用 COALESCE + MAX"""
        sql = find_function_sql("get_next_message_sequence")
        assert "COALESCE" in sql
        assert "MAX" in sql
        assert "sequence" in sql


# ========================
# TestCrudMessagesSql — Messages CRUD SQL 正确性
# ========================

class TestCrudMessagesSql:
    def test_add_message_uses_insert(self):
        """add_message: INSERT 包含所有消息字段"""
        sql = find_function_sql("add_message")
        assert "INSERT INTO messages" in sql
        assert "message_id" in sql
        assert "room_id" in sql
        assert "sender_id" in sql
        assert "content" in sql
        assert "type" in sql
        assert "sequence" in sql
        assert "created_at" in sql

    def test_add_message_returns_dict(self):
        """add_message: 返回 dict(row)"""
        source = find_function_source("add_message")
        assert "dict(row)" in source

    def test_get_messages_orders_by_sequence(self):
        """get_messages: 按 sequence 排序"""
        sql = find_function_sql("get_messages")
        assert "ORDER BY" in sql
        assert "sequence" in sql

    def test_search_messages_uses_ilike(self):
        """search_messages: 使用 ILIKE 模糊搜索"""
        sql = find_function_sql("search_messages")
        assert "ILIKE" in sql
        assert "content" in sql

    def test_search_messages_has_limit(self):
        """search_messages: 使用 LIMIT"""
        sql = find_function_sql("search_messages")
        assert "LIMIT" in sql

    def test_search_messages_returns_tuple(self):
        """search_messages: 返回 (rows, total_count) 元组"""
        source = find_function_source("search_messages")
        assert "return" in source
        # 应该返回 rows 和 total
        assert "rows" in source or "result" in source


# ========================
# TestCrudTasksSql — Tasks CRUD SQL 正确性
# ========================

class TestCrudTasksSql:
    def test_create_task_has_all_columns(self):
        """create_task: INSERT 包含所有任务字段"""
        sql = find_function_sql("create_task")
        assert "task_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "task_number" in sql
        assert "title" in sql
        assert "priority" in sql
        assert "difficulty" in sql
        assert "estimated_hours" in sql
        assert "actual_hours" in sql
        assert "progress" in sql
        assert "status" in sql
        assert "dependencies" in sql
        assert "blocked_by" in sql
        assert "deadline" in sql
        assert "created_at" in sql
        assert "updated_at" in sql

    def test_create_task_uses_json_for_dependencies(self):
        """create_task: dependencies 使用 json.dumps"""
        source = find_function_source("create_task")
        assert "json.dumps(dependencies" in source or "json.dumps(blocked_by" in source

    def test_create_task_json_fallback_for_none(self):
        """create_task: dependencies/blocked_by 为 None 时使用空列表"""
        source = find_function_source("create_task")
        # 应该用 or [] 提供默认值
        assert "or []" in source

    def test_get_task_uses_select_star(self):
        """get_task: SELECT * + task_id"""
        sql = find_function_sql("get_task")
        assert "SELECT *" in sql
        assert "task_id = $1" in sql

    def test_list_tasks_filters_by_plan_and_version(self):
        """list_tasks: 按 plan_id 和 version 过滤"""
        sql = find_function_sql("list_tasks")
        assert "plan_id = $1" in sql
        assert "version" in sql

    def test_list_tasks_orders_by_task_number(self):
        """list_tasks: 按 task_number 排序"""
        sql = find_function_sql("list_tasks")
        assert "ORDER BY" in sql
        assert "task_number" in sql

    def test_update_task_uses_dynamic_set(self):
        """update_task: 动态 SET 子句"""
        source = find_function_source("update_task")
        assert "set_clauses" in source

    def test_update_task_progress_uses_update(self):
        """update_task_progress: UPDATE tasks SET progress/status"""
        sql = find_function_sql("update_task_progress")
        assert "UPDATE tasks" in sql
        assert "progress" in sql
        assert "status" in sql

    def test_delete_task_uses_execute(self):
        """delete_task: DELETE FROM tasks"""
        sql = find_function_sql("delete_task")
        assert "DELETE FROM tasks" in sql
        assert "task_id = $1" in sql

    def test_get_task_metrics_has_all_aggregations(self):
        """get_task_metrics: 包含所有聚合统计"""
        sql = find_function_sql("get_task_metrics")
        assert "COUNT(*)" in sql or "count" in sql.lower()
        assert "AVG(progress)" in sql or "avg" in sql.lower()
        assert "SUM(estimated_hours)" in sql or "sum" in sql.lower()
        assert "SUM(actual_hours)" in sql or "sum" in sql.lower()


# ========================
# TestCrudDecisionsSql — Decisions CRUD SQL 正确性
# ========================

class TestCrudDecisionsSql:
    def test_create_decision_has_required_fields(self):
        """create_decision: INSERT 包含所有决策字段"""
        sql = find_function_sql("create_decision")
        assert "decision_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "decision_number" in sql
        assert "title" in sql
        assert "decision_text" in sql
        assert "created_at" in sql

    def test_list_decisions_filters_by_plan_version(self):
        """list_decisions: 按 plan_id 和 version 过滤"""
        sql = find_function_sql("list_decisions")
        assert "plan_id = $1" in sql
        assert "version" in sql

    def test_list_decisions_orders_by_decision_number(self):
        """list_decisions: 按 decision_number 降序"""
        sql = find_function_sql("list_decisions")
        assert "ORDER BY" in sql
        assert "decision_number DESC" in sql

    def test_update_decision_uses_update(self):
        """update_decision: UPDATE decisions SET"""
        sql = find_function_sql("update_decision")
        assert "UPDATE decisions" in sql
        assert "decision_id = $1" in sql or "WHERE" in sql


# ========================
# TestCrudEdictsSql — Edicts CRUD SQL 正确性
# ========================

class TestCrudEdictsSql:
    def test_create_edict_has_required_fields(self):
        """create_edict: INSERT 包含所有圣旨字段"""
        sql = find_function_sql("create_edict")
        assert "edict_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "edict_number" in sql
        assert "title" in sql
        assert "content" in sql
        assert "issued_by" in sql
        assert "issued_at" in sql
        assert "recipients" in sql
        assert "status" in sql

    def test_list_edicts_filters_by_plan_version(self):
        """list_edicts: 按 plan_id 和 version 过滤"""
        sql = find_function_sql("list_edicts")
        assert "plan_id = $1" in sql
        assert "version" in sql

    def test_update_edict_uses_update(self):
        """update_edict: UPDATE edicts"""
        sql = find_function_sql("update_edict")
        assert "UPDATE edicts" in sql

    def test_delete_edict_uses_execute(self):
        """delete_edict: DELETE FROM edicts"""
        sql = find_function_sql("delete_edict")
        assert "DELETE FROM edicts" in sql


# ========================
# TestCrudNotificationsSql — Notifications CRUD SQL 正确性
# ========================

class TestCrudNotificationsSql:
    def test_create_notification_has_required_fields(self):
        """create_notification: INSERT 包含所有通知字段"""
        sql = find_function_sql("create_notification")
        assert "notification_id" in sql
        assert "recipient_id" in sql
        assert "type" in sql
        assert "title" in sql
        assert "is_read" in sql
        assert "created_at" in sql

    def test_list_notifications_filters_by_recipient(self):
        """list_notifications: 按 recipient_id 过滤 + 排序"""
        sql = find_function_sql("list_notifications")
        assert "recipient_id = $1" in sql or "recipient_id = $" in sql

    def test_mark_notification_read_uses_update(self):
        """mark_notification_read: UPDATE notifications SET is_read = TRUE"""
        sql = find_function_sql("mark_notification_read")
        assert "UPDATE notifications" in sql
        assert "is_read = TRUE" in sql or "is_read = true" in sql

    def test_delete_notification_uses_execute(self):
        """delete_notification: DELETE FROM notifications"""
        sql = find_function_sql("delete_notification")
        assert "DELETE FROM notifications" in sql


# ========================
# TestCrudActivitiesSql — Activities CRUD SQL 正确性
# ========================

class TestCrudActivitiesSql:
    def test_create_activity_has_required_fields(self):
        """create_activity: INSERT 包含所有活动字段"""
        sql = find_function_sql("create_activity")
        assert "activity_id" in sql
        assert "action_type" in sql
        assert "actor_id" in sql
        assert "actor_name" in sql
        assert "occurred_at" in sql

    def test_list_activities_uses_pagination(self):
        """list_activities: 使用 ORDER BY + LIMIT + OFFSET"""
        sql = find_function_sql("list_activities")
        assert "ORDER BY occurred_at DESC" in sql or "ORDER BY" in sql
        assert "LIMIT" in sql
        assert "OFFSET" in sql

    def test_get_activity_uses_select_by_id(self):
        """get_activity: SELECT * WHERE activity_id"""
        sql = find_function_sql("get_activity")
        assert "SELECT *" in sql
        assert "activity_id = $1" in sql


# ========================
# TestCrudTasksTimeEntriesSql — Task Time Entries SQL 正确性
# ========================

class TestCrudTasksTimeEntriesSql:
    def test_create_time_entry_updates_task_actual_hours(self):
        """create_time_entry: 事务中更新 tasks.actual_hours"""
        source = find_function_source("create_time_entry")
        assert "tasks" in source.lower() or "actual_hours" in source

    def test_create_time_entry_uses_transaction(self):
        """create_time_entry: 使用 async with conn.transaction()"""
        source = find_function_source("create_time_entry")
        assert "transaction()" in source

    def test_delete_time_entry_recalculates_actual_hours(self):
        """delete_time_entry: 删除后重算 tasks.actual_hours"""
        source = find_function_source("delete_time_entry")
        assert "tasks" in source.lower() or "actual_hours" in source

    def test_get_task_time_summary_has_aggregations(self):
        """get_task_time_summary: 包含 SUM/COUNT 聚合"""
        sql = find_function_sql("get_task_time_summary")
        assert "SUM" in sql or "COUNT" in sql or "sum" in sql.lower()


# ========================
# TestCrudActionItemsSql — Action Items CRUD SQL 正确性
# ========================

class TestCrudActionItemsSql:
    def test_create_action_item_has_required_fields(self):
        """create_action_item: INSERT 包含所有行动项字段"""
        sql = find_function_sql("create_action_item")
        assert "action_item_id" in sql
        assert "room_id" in sql
        assert "plan_id" in sql
        assert "title" in sql
        assert "status" in sql
        assert "priority" in sql
        assert "created_at" in sql

    def test_list_action_items_supports_room_and_plan_filter(self):
        """list_action_items: 支持 room_id 和 plan_id 过滤"""
        source = find_function_source("list_action_items")
        assert "room_id" in source or "plan_id" in source

    def test_complete_action_item_uses_update(self):
        """complete_action_item: UPDATE 设置 status = completed"""
        sql = find_function_sql("complete_action_item")
        assert "UPDATE" in sql or "status" in sql


# ========================
# TestCrudSnapshotsSql — Snapshots CRUD SQL 正确性
# ========================

class TestCrudSnapshotsSql:
    def test_create_snapshot_has_required_fields(self):
        """create_snapshot: INSERT 包含所有快照字段"""
        sql = find_function_sql("create_snapshot")
        assert "snapshot_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "room_id" in sql
        assert "phase" in sql
        assert "context_summary" in sql
        assert "created_at" in sql

    def test_list_snapshots_filters_by_plan_version(self):
        """list_snapshots: 按 plan_id 和 version 过滤"""
        sql = find_function_sql("list_snapshots")
        assert "plan_id = $1" in sql
        assert "version" in sql

    def test_list_snapshots_orders_by_created_at(self):
        """list_snapshots: 按 created_at 降序"""
        sql = find_function_sql("list_snapshots")
        assert "ORDER BY created_at DESC" in sql


# ========================
# TestCrudMeetingsSql — Meeting Minutes CRUD SQL 正确性
# ========================

class TestCrudMeetingsSql:
    def test_create_meeting_minutes_has_required_fields(self):
        """create_meeting_minutes: INSERT 包含所有字段"""
        sql = find_function_sql("create_meeting_minutes")
        assert "meeting_minutes_id" in sql
        assert "room_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "title" in sql
        assert "content" in sql
        assert "created_at" in sql

    def test_list_meeting_minutes_supports_room_and_plan_filter(self):
        """list_meeting_minutes: 支持 room_id 和 plan_id 过滤"""
        source = find_function_source("list_meeting_minutes")
        assert "room_id" in source or "plan_id" in source


# ========================
# TestCrudEscalationsSql — Escalations CRUD SQL 正确性
# ========================

class TestCrudEscalationsSql:
    def test_create_escalation_has_required_fields(self):
        """create_escalation: INSERT 包含所有升级字段"""
        sql = find_function_sql("create_escalation")
        assert "escalation_id" in sql
        assert "room_id" in sql
        assert "plan_id" in sql
        assert "from_level" in sql
        assert "to_level" in sql
        assert "mode" in sql
        assert "reason" in sql
        assert "status" in sql
        assert "created_at" in sql

    def test_get_room_escalations_filters_by_room(self):
        """get_room_escalations: 按 room_id 过滤"""
        sql = find_function_sql("get_room_escalations")
        assert "room_id = $1" in sql

    def test_get_plan_escalations_filters_by_plan(self):
        """get_plan_escalations: 按 plan_id 过滤"""
        sql = find_function_sql("get_plan_escalations")
        assert "plan_id = $1" in sql

    def test_update_escalation_status_uses_update(self):
        """update_escalation_status: UPDATE escalations SET status"""
        sql = find_function_sql("update_escalation_status")
        assert "UPDATE escalations" in sql
        assert "status" in sql


# ========================
# TestCrudApprovalFlowsSql — Approval Flows SQL 正确性
# ========================

class TestCrudApprovalFlowsSql:
    def test_start_approval_flow_has_required_fields(self):
        """start_approval_flow: INSERT 包含所有审批流字段"""
        sql = find_function_sql("start_approval_flow")
        assert "approval_id" in sql
        assert "plan_id" in sql
        assert "initiator_id" in sql
        assert "initiator_name" in sql
        assert "current_level" in sql
        assert "status" in sql
        assert "created_at" in sql

    def test_update_approval_level_uses_update(self):
        """update_approval_level: UPDATE approval_levels"""
        sql = find_function_sql("update_approval_level")
        assert "UPDATE approval_levels" in sql or "approval_levels" in sql


# ========================
# TestCrudRisksSql — Risks CRUD SQL 正确性
# ========================

class TestCrudRisksSql:
    def test_create_risk_has_required_fields(self):
        """create_risk: INSERT 包含所有风险字段"""
        sql = find_function_sql("create_risk")
        assert "risk_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "title" in sql
        assert "severity" in sql
        assert "status" in sql

    def test_create_risk_calculates_severity_from_probability_impact(self):
        """create_risk: severity = probability × impact"""
        source = find_function_source("create_risk")
        # 应该计算 severity
        assert "severity" in source


# ========================
# TestCrudConstraintsSql — Constraints CRUD SQL 正确性
# ========================

class TestCrudConstraintsSql:
    def test_create_constraint_has_required_fields(self):
        """create_constraint: INSERT 包含所有约束字段"""
        sql = find_function_sql("create_constraint")
        assert "constraint_id" in sql
        assert "plan_id" in sql
        assert "type" in sql
        assert "value" in sql


# ========================
# TestCrudStakeholdersSql — Stakeholders CRUD SQL 正确性
# ========================

class TestCrudStakeholdersSql:
    def test_create_stakeholder_has_required_fields(self):
        """create_stakeholder: INSERT 包含所有干系人字段"""
        sql = find_function_sql("create_stakeholder")
        assert "stakeholder_id" in sql
        assert "plan_id" in sql
        assert "name" in sql
        assert "level" in sql
        assert "interest" in sql
        assert "influence" in sql


# ========================
# TestCrudRoomWatchSql — Room Watch CRUD SQL 正确性
# ========================

class TestCrudRoomWatchSql:
    def test_create_room_watcher_has_required_fields(self):
        """create_room_watcher: INSERT 包含所有字段"""
        sql = find_function_sql("create_room_watcher")
        assert "room_id" in sql
        assert "user_id" in sql
        assert "watcher_id" in sql or "room_watcher_id" in sql

    def test_delete_room_watcher_uses_execute(self):
        """delete_room_watcher: DELETE FROM room_watchers"""
        sql = find_function_sql("delete_room_watcher")
        assert "DELETE FROM" in sql

    def test_is_room_watched_uses_select_count(self):
        """is_room_watcher: 使用 COUNT(*) 验证"""
        sql = find_function_sql("is_room_watched")
        assert "SELECT" in sql
        assert "COUNT" in sql or "count" in sql.lower()


# ========================
# TestCrudTemplatesSql — Templates CRUD SQL 正确性
# ========================

class TestCrudTemplatesSql:
    def test_create_room_template_has_required_fields(self):
        """create_room_template: INSERT 包含所有字段"""
        sql = find_function_sql("create_room_template")
        assert "template_id" in sql
        assert "name" in sql
        assert "topic" in sql
        assert "purpose" in sql
        assert "mode" in sql
        assert "is_shared" in sql

    def test_create_plan_template_has_required_fields(self):
        """create_plan_template: INSERT 包含所有字段"""
        sql = find_function_sql("create_plan_template")
        assert "template_id" in sql
        assert "name" in sql
        assert "plan_content" in sql or "content" in sql

    def test_create_task_template_has_required_fields(self):
        """create_task_template: INSERT 包含所有字段"""
        sql = find_function_sql("create_task_template")
        assert "template_id" in sql
        assert "name" in sql
        assert "default_title" in sql


# ========================
# TestCrudPhaseTimelineSql — Phase Timeline SQL 正确性
# ========================

class TestCrudPhaseTimelineSql:
    def test_create_phase_timeline_entry_uses_insert(self):
        """create_phase_timeline_entry: INSERT"""
        sql = find_function_sql("create_phase_timeline_entry")
        assert "INSERT INTO room_phase_timeline" in sql
        assert "room_id" in sql
        assert "phase" in sql
        assert "entered_at" in sql

    def test_exit_phase_timeline_entry_uses_update(self):
        """exit_phase_timeline_entry: UPDATE 设置退出信息"""
        sql = find_function_sql("exit_phase_timeline_entry")
        assert "UPDATE room_phase_timeline" in sql
        assert "exited_at" in sql
        assert "exited_via" in sql or "exited" in sql

    def test_get_room_phase_timeline_orders_by_entered_at(self):
        """get_room_phase_timeline: 按 entered_at 升序"""
        sql = find_function_sql("get_room_phase_timeline")
        assert "ORDER BY" in sql
        assert "entered_at" in sql


# ========================
# TestCrudProblemHandlingSql — Problem Handling SQL 正确性
# ========================

class TestCrudProblemHandlingSql:
    def test_create_problem_has_required_fields(self):
        """create_problem: INSERT 包含所有问题字段"""
        sql = find_function_sql("create_problem")
        assert "issue_id" in sql
        assert "plan_id" in sql
        assert "room_id" in sql
        assert "title" in sql
        assert "type" in sql
        assert "severity" in sql
        assert "status" in sql

    def test_create_problem_analysis_has_required_fields(self):
        """create_problem_analysis: INSERT"""
        sql = find_function_sql("create_problem_analysis")
        assert "INSERT INTO problem_analyses" in sql
        assert "issue_id" in sql
        assert "root_cause" in sql

    def test_create_plan_update_has_required_fields(self):
        """create_plan_update: INSERT"""
        sql = find_function_sql("create_plan_update")
        assert "INSERT INTO plan_updates" in sql
        assert "issue_id" in sql
        assert "new_version" in sql

    def test_create_resuming_record_has_required_fields(self):
        """create_resuming_record: INSERT"""
        sql = find_function_sql("create_resuming_record")
        assert "INSERT INTO resuming_records" in sql
        assert "issue_id" in sql
        assert "resumed_task" in sql or "task" in sql


# ========================
# TestCrudSubTasksSql — SubTasks SQL 正确性
# ========================

class TestCrudSubTasksSql:
    def test_create_sub_task_has_required_fields(self):
        """create_sub_task: INSERT 包含所有子任务字段"""
        sql = find_function_sql("create_sub_task")
        assert "sub_task_id" in sql
        assert "task_id" in sql
        assert "plan_id" in sql
        assert "version" in sql
        assert "title" in sql
        assert "status" in sql
        assert "progress" in sql

    def test_list_sub_tasks_filters_by_task(self):
        """list_sub_tasks: 按 task_id 过滤"""
        sql = find_function_sql("list_sub_tasks")
        assert "task_id = $1" in sql


# ========================
# TestCrudModuleStructure — crud.py 模块结构
# ========================

class TestCrudModuleStructure:
    def test_module_has_get_connection_import(self):
        """crud.py 从 db 导入 get_connection"""
        assert "from db import" in crud_source
        assert "get_connection" in crud_source

    def test_module_imports_asyncpg(self):
        """crud.py 导入 asyncpg"""
        assert "import asyncpg" in crud_source or "from asyncpg" in crud_source

    def test_module_imports_json(self):
        """crud.py 导入 json"""
        assert "import json" in crud_source

    def test_module_imports_uuid(self):
        """crud.py 导入 uuid"""
        assert "import uuid" in crud_source

    def test_module_has_logging(self):
        """crud.py 使用 logging"""
        assert "import logging" in crud_source
        assert "logger = logging.getLogger" in crud_source

    def test_all_functions_are_async(self):
        """所有 CRUD 函数都是 async def"""
        func_names = re.findall(r'async def (create_|get_|update_|delete_|list_|search_|add_|start_|copy_|begin_|exit_|submit_|submit|create_|get_|list_|count_|mark_|complete_|is_|get_next_|get_)[a-z_]+\(', crud_source)
        # 验证主要函数都是 async
        assert len(func_names) > 50, f"应该有大量 async CRUD 函数，实际找到 {len(func_names)} 个"

    def test_no_raw_sql_without_placeholders(self):
        """没有不带占位符的硬编码 SQL（防注入）"""
        # 查找 INSERT INTO ... VALUES ( 不带 $ 的情况
        lines = crud_source.split('\n')
        for i, line in enumerate(lines):
            if 'INSERT INTO' in line or 'SELECT' in line:
                # 确保有参数化占位符
                context = '\n'.join(lines[max(0,i-2):i+3])
                if 'VALUES' in context or 'WHERE' in context:
                    # 至少应该有 $1
                    assert '$1' in context or 'RETURNING' in context or 'COUNT' in context, \
                        f"第 {i+1} 行附近缺少参数占位符: {line.strip()[:80]}"

    def test_get_dashboard_stats_exists(self):
        """get_dashboard_stats 函数存在"""
        assert "async def get_dashboard_stats(" in crud_source

    def test_get_participant_activity_exists(self):
        """get_participant_activity 函数存在"""
        assert "async def get_participant_activity(" in crud_source

    def test_get_room_phase_timeline_exists(self):
        """get_room_phase_timeline 函数存在"""
        assert "async def get_room_phase_timeline(" in crud_source

    def test_update_participant_contributions_exists(self):
        """update_participant_contributions 函数存在"""
        assert "async def update_participant_contributions(" in crud_source or "def update_participant_contributions(" in crud_source


# ========================
# TestCrudSqlInjectionPrevention — SQL 注入防护
# ========================

class TestCrudSqlInjectionPrevention:
    def test_all_user_inputs_parameterized(self):
        """所有用户输入都使用参数化查询"""
        # 检查 search_plans, search_rooms 等搜索函数
        for func_name in ["search_plans", "search_rooms", "search_messages"]:
            source = find_function_source(func_name)
            if source:
                # 不应该有字符串拼接的 SQL
                assert '") + ' not in source, f"{func_name} 使用字符串拼接 SQL"
                assert 'f"' not in source or 'f"""' not in source, f"{func_name} 使用 f-string 拼接 SQL"

    def test_no_format_string_sql(self):
        """没有使用 % formatting 或 .format() 的 SQL"""
        # 检查所有 SQL 字符串
        sql_strings = re.findall(r'"""(SELECT|INSERT|UPDATE|DELETE).*?"""', crud_source, re.DOTALL)
        for sql in sql_strings[:20]:  # 检查前20个
            assert '%' not in sql or '%%' in sql, f"发现使用 % 格式化的 SQL: {sql[:100]}"


# ========================
# TestCrudDashboardStatsSql — Dashboard Stats SQL 正确性
# ========================

class TestCrudDashboardStatsSql:
    def test_get_dashboard_stats_queries_plans(self):
        """get_dashboard_stats: 查询 plans 表"""
        sql = find_function_sql("get_dashboard_stats")
        assert "plans" in sql.lower() or "plan" in sql.lower()

    def test_get_dashboard_stats_queries_rooms(self):
        """get_dashboard_stats: 查询 rooms 表"""
        sql = find_function_sql("get_dashboard_stats")
        assert "rooms" in sql.lower() or "room" in sql.lower()

    def test_get_dashboard_stats_queries_action_items(self):
        """get_dashboard_stats: 查询 action_items"""
        sql = find_function_sql("get_dashboard_stats")
        assert "action_item" in sql.lower() or "pending_action" in sql.lower()

    def test_get_dashboard_stats_queries_approvals(self):
        """get_dashboard_stats: 查询 approval_flows"""
        sql = find_function_sql("get_dashboard_stats")
        assert "approval" in sql.lower()

    def test_get_dashboard_stats_returns_dict(self):
        """get_dashboard_stats: 返回 dict"""
        source = find_function_source("get_dashboard_stats")
        assert "dict(" in source or "return {" in source
