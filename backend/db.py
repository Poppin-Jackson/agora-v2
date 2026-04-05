"""
PostgreSQL 数据库连接与初始化
Agora-V2 使用 PostgreSQL 进行持久化存储
"""
import os
import uuid
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
from asyncpg import Pool

logger = logging.getLogger("agora.db")

# 全局连接池
_pool: Optional[Pool] = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://agora:agora_v2_secret@postgres:5432/agora_v2"
)


async def get_pool() -> Pool:
    """获取数据库连接池（延迟初始化）"""
    global _pool
    if _pool is None:
        # Lazy initialization - try to init DB if pool is not created
        # This handles cases where uvicorn --reload didn't trigger lifespan startup
        try:
            await init_db()
        except Exception:
            pass
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


async def init_db(database_url: str = None) -> Pool:
    """
    初始化数据库连接池并创建表结构
    在 main.py lifespan startup 时调用
    """
    global _pool
    url = database_url or DATABASE_URL

    # 解析 URL：postgresql+asyncpg://user:pass@host:port/db → user:pass@host:port/db
    # 提取组件用于 asyncpg.connect()
    import re
    m = re.match(
        r"postgresql\+asyncpg://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>.+)",
        url
    )
    if not m:
        raise ValueError(f"Cannot parse DATABASE_URL: {url}")

    user = m.group("user")
    password = m.group("password")
    host = m.group("host")
    port = int(m.group("port"))
    db_name = m.group("db")

    # 连接数据库（如果不存在则创建）
    sys_conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database="postgres"
    )
    try:
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"[DB] Created database: {db_name}")
    finally:
        await sys_conn.close()

    # 创建连接池
    _pool = await asyncpg.create_pool(
        host=host, port=port, user=user, password=password,
        database=db_name, min_size=2, max_size=10
    )

    # 创建表
    await _create_tables(_pool)
    logger.info("[DB] PostgreSQL 初始化完成")
    return _pool


async def close_db():
    """关闭数据库连接池"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("[DB] PostgreSQL 连接池已关闭")


async def _create_tables(pool: Pool):
    """创建所有表结构"""

    CREATE_TABLES_SQL = """
    -- plans 表
    CREATE TABLE IF NOT EXISTS plans (
        plan_id      UUID PRIMARY KEY,
        plan_number  TEXT UNIQUE,
        title        TEXT NOT NULL,
        topic        TEXT NOT NULL,
        requirements JSONB DEFAULT '[]',
        status       TEXT DEFAULT 'draft',
        hierarchy_id TEXT DEFAULT 'default',
        current_version TEXT DEFAULT 'v1.0',
        versions     JSONB DEFAULT '["v1.0"]',
        created_at   TIMESTAMPTZ DEFAULT NOW(),
        updated_at   TIMESTAMPTZ DEFAULT NOW()
    );

    -- rooms 表
    CREATE TABLE IF NOT EXISTS rooms (
        room_id          UUID PRIMARY KEY,
        room_number      TEXT UNIQUE,
        plan_id          UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        topic            TEXT NOT NULL,
        phase            TEXT DEFAULT 'selecting',
        coordinator_id   TEXT DEFAULT 'coordinator',
        current_version  TEXT DEFAULT 'v1.0',
        purpose          TEXT DEFAULT 'initial_discussion',
        mode             TEXT DEFAULT 'hierarchical',
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );

    -- participants 表
    CREATE TABLE IF NOT EXISTS participants (
        participant_id UUID PRIMARY KEY,
        room_id        UUID REFERENCES rooms(room_id) ON DELETE CASCADE,
        agent_id       TEXT NOT NULL,
        name           TEXT NOT NULL,
        level          INTEGER DEFAULT 5,
        role           TEXT DEFAULT 'Member',
        source         TEXT DEFAULT 'internal',
        joined_at      TIMESTAMPTZ DEFAULT NOW(),
        is_active      BOOLEAN DEFAULT TRUE
    );

    -- messages 表（讨论历史）
    CREATE TABLE IF NOT EXISTS messages (
        message_id  UUID PRIMARY KEY,
        room_id     UUID REFERENCES rooms(room_id) ON DELETE CASCADE,
        type        TEXT NOT NULL,
        agent_id    TEXT,
        content     TEXT,
        metadata    JSONB DEFAULT '{}',
        source      TEXT DEFAULT 'internal',
        timestamp   TIMESTAMPTZ DEFAULT NOW()
    );

    -- approval_flows 表
    CREATE TABLE IF NOT EXISTS approval_flows (
        plan_id         UUID PRIMARY KEY REFERENCES plans(plan_id) ON DELETE CASCADE,
        initiator_id    TEXT NOT NULL,
        initiator_name  TEXT NOT NULL,
        started_at      TIMESTAMPTZ DEFAULT NOW(),
        current_level   INTEGER DEFAULT 7,
        status          TEXT DEFAULT 'in_progress',
        skip_levels     JSONB DEFAULT '[]',
        history         JSONB DEFAULT '[]'
    );

    -- approval_levels 表
    CREATE TABLE IF NOT EXISTS approval_levels (
        id          SERIAL PRIMARY KEY,
        plan_id     UUID REFERENCES approval_flows(plan_id) ON DELETE CASCADE,
        level       INTEGER NOT NULL,
        status      TEXT DEFAULT 'pending',
        approver_id TEXT,
        approver_name TEXT,
        comment     TEXT,
        decided_at  TIMESTAMPTZ,
        escalated_to INTEGER
    );

    -- problems 表
    CREATE TABLE IF NOT EXISTS problems (
        issue_id        UUID PRIMARY KEY,
        plan_id         UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        room_id         UUID REFERENCES rooms(room_id) ON DELETE SET NULL,
        version         TEXT DEFAULT 'v1.0',
        type            TEXT NOT NULL,
        title           TEXT NOT NULL,
        description     TEXT,
        severity        TEXT NOT NULL,
        detected_by     TEXT,
        detected_at     TIMESTAMPTZ DEFAULT NOW(),
        affected_tasks  JSONB DEFAULT '[]',
        progress_delay  INTEGER DEFAULT 0,
        related_context JSONB DEFAULT '{}',
        status          TEXT DEFAULT 'detected'
    );

    -- problem_analyses 表
    CREATE TABLE IF NOT EXISTS problem_analyses (
        issue_id                    UUID PRIMARY KEY REFERENCES problems(issue_id) ON DELETE CASCADE,
        root_cause                  TEXT,
        root_cause_confidence       FLOAT DEFAULT 0.0,
        impact_scope                TEXT DEFAULT '局部',
        affected_tasks              JSONB DEFAULT '[]',
        progress_impact             TEXT DEFAULT '未知',
        severity_reassessment       TEXT,
        solution_options            JSONB DEFAULT '[]',
        recommended_option         INTEGER DEFAULT 0,
        requires_discussion         BOOLEAN DEFAULT FALSE,
        discussion_needed_aspects   JSONB DEFAULT '[]',
        analyzed_at                 TIMESTAMPTZ DEFAULT NOW()
    );

    -- problem_discussions 表
    CREATE TABLE IF NOT EXISTS problem_discussions (
        issue_id                UUID PRIMARY KEY REFERENCES problems(issue_id) ON DELETE CASCADE,
        participants            JSONB DEFAULT '[]',
        discussion_focus        JSONB DEFAULT '[]',
        proposed_solutions      JSONB DEFAULT '[]',
        votes                   JSONB DEFAULT '{}',
        final_recommendation    TEXT DEFAULT '',
        discussed_at            TIMESTAMPTZ DEFAULT NOW()
    );

    -- plan_updates 表
    CREATE TABLE IF NOT EXISTS plan_updates (
        plan_id          UUID PRIMARY KEY REFERENCES plans(plan_id) ON DELETE CASCADE,
        new_version      TEXT NOT NULL,
        parent_version   TEXT NOT NULL,
        update_type      TEXT DEFAULT 'fix',
        description      TEXT,
        changes          JSONB DEFAULT '{}',
        task_updates     JSONB DEFAULT '[]',
        new_tasks        JSONB DEFAULT '[]',
        cancelled_tasks  JSONB DEFAULT '[]',
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );

    -- resuming_records 表
    CREATE TABLE IF NOT EXISTS resuming_records (
        plan_id               UUID PRIMARY KEY REFERENCES plans(plan_id) ON DELETE CASCADE,
        new_version           TEXT NOT NULL,
        resuming_from_task    INTEGER DEFAULT 0,
        checkpoint            TEXT DEFAULT '',
        resume_instructions   JSONB DEFAULT '{}',
        resumed_at            TIMESTAMPTZ DEFAULT NOW()
    );

    -- snapshots 表
    CREATE TABLE IF NOT EXISTS snapshots (
        snapshot_id       UUID PRIMARY KEY,
        plan_id           UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version           TEXT NOT NULL,
        room_id           UUID REFERENCES rooms(room_id) ON DELETE SET NULL,
        phase             TEXT,
        context_summary   TEXT,
        participants      JSONB DEFAULT '[]',
        messages_summary  JSONB DEFAULT '[]',
        created_at        TIMESTAMPTZ DEFAULT NOW()
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_rooms_plan_id ON rooms(plan_id);
    CREATE INDEX IF NOT EXISTS idx_participants_room_id ON participants(room_id);
    CREATE INDEX IF NOT EXISTS idx_messages_room_id ON messages(room_id);
    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    CREATE INDEX IF NOT EXISTS idx_problems_plan_id ON problems(plan_id);
    -- tasks 表
    CREATE TABLE IF NOT EXISTS tasks (
        task_id           UUID PRIMARY KEY,
        plan_id           UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version           TEXT NOT NULL,
        task_number       INTEGER NOT NULL,
        title             TEXT NOT NULL,
        description       TEXT,
        owner_id          TEXT,
        owner_level       INTEGER,
        owner_role        TEXT,
        priority          TEXT DEFAULT 'medium',
        difficulty         TEXT DEFAULT 'medium',
        estimated_hours   REAL,
        actual_hours      REAL,
        progress          REAL DEFAULT 0,
        status            TEXT DEFAULT 'pending',
        dependencies      JSONB DEFAULT '[]',
        blocked_by        JSONB DEFAULT '[]',
        deadline          TIMESTAMPTZ,
        started_at        TIMESTAMPTZ,
        completed_at      TIMESTAMPTZ,
        created_at        TIMESTAMPTZ DEFAULT NOW(),
        updated_at        TIMESTAMPTZ DEFAULT NOW()
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_rooms_plan_id ON rooms(plan_id);
    CREATE INDEX IF NOT EXISTS idx_participants_room_id ON participants(room_id);
    CREATE INDEX IF NOT EXISTS idx_messages_room_id ON messages(room_id);
    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    CREATE INDEX IF NOT EXISTS idx_problems_plan_id ON problems(plan_id);
    CREATE INDEX IF NOT EXISTS idx_snapshots_plan_version ON snapshots(plan_id, version);
    CREATE INDEX IF NOT EXISTS idx_tasks_plan_version ON tasks(plan_id, version);

    -- decisions 表（决策记录，08-Data-Models-Details.md §3.1 Decision模型）
    CREATE TABLE IF NOT EXISTS decisions (
        decision_id           UUID PRIMARY KEY,
        plan_id               UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version               TEXT NOT NULL,
        decision_number       INTEGER NOT NULL,
        title                 TEXT NOT NULL,
        description           TEXT,
        decision_text         TEXT NOT NULL,
        rationale             TEXT,
        alternatives_considered JSONB DEFAULT '[]',
        agreed_by             JSONB DEFAULT '[]',
        disagreed_by          JSONB DEFAULT '[]',
        decided_by            TEXT,
        room_id               UUID REFERENCES rooms(room_id) ON DELETE SET NULL,
        created_at            TIMESTAMPTZ DEFAULT NOW()
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_decisions_plan_version ON decisions(plan_id, version);

    -- task_comments 表（任务评论，08-Data-Models-Details.md §3.1 Task模型 comments）
    CREATE TABLE IF NOT EXISTS task_comments (
        comment_id       UUID PRIMARY KEY,
        task_id          UUID REFERENCES tasks(task_id) ON DELETE CASCADE,
        plan_id          UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version          TEXT NOT NULL,
        author_id        TEXT,
        author_name      TEXT NOT NULL,
        author_level     INTEGER,
        content          TEXT NOT NULL,
        created_at       TIMESTAMPTZ DEFAULT NOW(),
        updated_at       TIMESTAMPTZ DEFAULT NOW()
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_task_comments_task_id ON task_comments(task_id);
    CREATE INDEX IF NOT EXISTS idx_task_comments_plan_version ON task_comments(plan_id, version);

    -- task_checkpoints 表（任务检查点，08-Data-Models-Details.md §3.1 Task模型 checkpoints）
    CREATE TABLE IF NOT EXISTS task_checkpoints (
        checkpoint_id    UUID PRIMARY KEY,
        task_id          UUID REFERENCES tasks(task_id) ON DELETE CASCADE,
        plan_id          UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version          TEXT NOT NULL,
        name             TEXT NOT NULL,
        status           TEXT DEFAULT 'pending',
        completed_at     TIMESTAMPTZ,
        created_at       TIMESTAMPTZ DEFAULT NOW(),
        updated_at       TIMESTAMPTZ DEFAULT NOW()
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_task_checkpoints_task_id ON task_checkpoints(task_id);

    -- sub_tasks 表（子任务，08-Data-Models-Details.md §3.1 Task模型 sub_tasks）
    CREATE TABLE IF NOT EXISTS sub_tasks (
        sub_task_id    UUID PRIMARY KEY,
        task_id        UUID REFERENCES tasks(task_id) ON DELETE CASCADE,
        plan_id        UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version        TEXT NOT NULL,
        title          TEXT NOT NULL,
        description    TEXT,
        status         TEXT DEFAULT 'pending',
        progress       FLOAT DEFAULT 0,
        created_at     TIMESTAMPTZ DEFAULT NOW(),
        updated_at     TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_sub_tasks_task_id ON sub_tasks(task_id);

    -- escalations 表（层级汇报/升级记录，05-Hierarchy-Roles.md §7.2）
    CREATE TABLE IF NOT EXISTS escalations (
        escalation_id     UUID PRIMARY KEY,
        room_id          UUID REFERENCES rooms(room_id) ON DELETE CASCADE,
        plan_id          UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version          TEXT DEFAULT 'v1.0',
        from_level       INTEGER NOT NULL,
        to_level         INTEGER NOT NULL,
        mode             TEXT NOT NULL,
        content          JSONB DEFAULT '{}',
        escalation_path  JSONB DEFAULT '[]',
        status           TEXT DEFAULT 'pending',
        escalated_by     TEXT,
        escalated_at     TIMESTAMPTZ DEFAULT NOW(),
        acknowledged_at  TIMESTAMPTZ,
        completed_at     TIMESTAMPTZ,
        notes            TEXT
    );

    -- 索引
    CREATE INDEX IF NOT EXISTS idx_escalations_room_id ON escalations(room_id);
    CREATE INDEX IF NOT EXISTS idx_escalations_plan_id ON escalations(plan_id);

    -- constraints 表（Plan约束，08-Data-Models-Details.md §2.1 Plan.constraints）
    CREATE TABLE IF NOT EXISTS constraints (
        constraint_id  UUID PRIMARY KEY,
        plan_id        UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        type           TEXT NOT NULL,
        value          TEXT NOT NULL,
        unit           TEXT,
        description    TEXT,
        created_at     TIMESTAMPTZ DEFAULT NOW(),
        updated_at     TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_constraints_plan_id ON constraints(plan_id);

    -- stakeholders 表（Plan干系人，08-Data-Models-Details.md §2.1 Plan.stakeholders）
    CREATE TABLE IF NOT EXISTS stakeholders (
        stakeholder_id UUID PRIMARY KEY,
        plan_id        UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        name           TEXT NOT NULL,
        level          INTEGER,
        interest       TEXT DEFAULT 'medium',
        influence      TEXT DEFAULT 'medium',
        description    TEXT,
        created_at     TIMESTAMPTZ DEFAULT NOW(),
        updated_at     TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_stakeholders_plan_id ON stakeholders(plan_id);

    -- risks 表（Version风险，08-Data-Models-Details.md §3.1 Version.risks）
    CREATE TABLE IF NOT EXISTS risks (
        risk_id        UUID PRIMARY KEY,
        plan_id        UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version        TEXT NOT NULL,
        title          TEXT NOT NULL,
        description    TEXT,
        probability    TEXT DEFAULT 'medium',
        impact         TEXT DEFAULT 'medium',
        severity       TEXT,
        mitigation     TEXT,
        contingency    TEXT,
        status         TEXT DEFAULT 'identified',
        created_at     TIMESTAMPTZ DEFAULT NOW(),
        updated_at     TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_risks_plan_version ON risks(plan_id, version);

    -- edicts 表（圣旨/下行 decree from L7，01-Edict-Reference.md）
    -- Edict = L7正式颁布的政令，下行至各层级执行
    CREATE TABLE IF NOT EXISTS edicts (
        edict_id          UUID PRIMARY KEY,
        plan_id           UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version           TEXT NOT NULL,
        edict_number      INTEGER NOT NULL,
        title             TEXT NOT NULL,
        content           TEXT NOT NULL,
        decision_id       UUID REFERENCES decisions(decision_id) ON DELETE SET NULL,
        issued_by         TEXT NOT NULL,
        issued_at         TIMESTAMPTZ DEFAULT NOW(),
        effective_from    TIMESTAMPTZ,
        recipients        JSONB DEFAULT '[]',
        status            TEXT DEFAULT 'published',
        created_at        TIMESTAMPTZ DEFAULT NOW(),
        updated_at        TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_edicts_plan_version ON edicts(plan_id, version);
    CREATE INDEX IF NOT EXISTS idx_edicts_decision ON edicts(decision_id);

    -- Step 38: Edict Acknowledgments（圣旨签收记录）
    CREATE TABLE IF NOT EXISTS edict_acknowledgments (
        ack_id          UUID PRIMARY KEY,
        edict_id        UUID REFERENCES edicts(edict_id) ON DELETE CASCADE,
        plan_id         UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version         TEXT NOT NULL,
        acknowledged_by TEXT NOT NULL,
        level           INTEGER NOT NULL,
        comment         TEXT,
        acknowledged_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_edict_acks_edict ON edict_acknowledgments(edict_id);

    -- Step 31: Activity Audit Log
    CREATE TABLE IF NOT EXISTS activities (
        activity_id   UUID PRIMARY KEY,
        plan_id       UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version       TEXT,
        room_id       UUID REFERENCES rooms(room_id) ON DELETE SET NULL,
        action_type   TEXT NOT NULL,
        actor_id      TEXT,
        actor_name    TEXT,
        target_type   TEXT,
        target_id     TEXT,
        target_label  TEXT,
        details       JSONB DEFAULT '{}',
        occurred_at   TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_activities_plan ON activities(plan_id);
    CREATE INDEX IF NOT EXISTS idx_activities_room ON activities(room_id);
    CREATE INDEX IF NOT EXISTS idx_activities_action_type ON activities(action_type);
    CREATE INDEX IF NOT EXISTS idx_activities_actor ON activities(actor_id);
    CREATE INDEX IF NOT EXISTS idx_activities_occurred_at ON activities(occurred_at);

    -- Step 34: Notification System
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id  UUID PRIMARY KEY,
        plan_id          UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
        version          TEXT,
        room_id          UUID REFERENCES rooms(room_id) ON DELETE SET NULL,
        task_id          TEXT,
        recipient_id     TEXT NOT NULL,
        recipient_level  INTEGER,
        type             TEXT NOT NULL,
        title            TEXT NOT NULL,
        message          TEXT,
        read             BOOLEAN DEFAULT FALSE,
        created_at       TIMESTAMPTZ DEFAULT NOW(),
        read_at          TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_plan ON notifications(plan_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_room ON notifications(room_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_task ON notifications(task_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);
    CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
    """

    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
        logger.info("[DB] 表结构创建完成")

    # Migration: add plan_number/room_number columns if they don't exist
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                ALTER TABLE plans ADD COLUMN IF NOT EXISTS plan_number TEXT UNIQUE;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS room_number TEXT UNIQUE;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS purpose TEXT DEFAULT 'initial_discussion';
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'hierarchical';
                ALTER TABLE problems ADD COLUMN IF NOT EXISTS issue_number TEXT UNIQUE;
                -- Step 24: Room hierarchy + Participant contributions
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS parent_room_id UUID REFERENCES rooms(room_id) ON DELETE SET NULL;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS child_rooms JSONB DEFAULT '[]';
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS related_rooms JSONB DEFAULT '[]';
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS ended_at TIMESTAMPTZ;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS duration_seconds INTEGER;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS messages_count INTEGER DEFAULT 0;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS last_message_at TIMESTAMPTZ;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS summary TEXT;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS conclusion TEXT;
                ALTER TABLE rooms ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}';
                CREATE INDEX IF NOT EXISTS idx_rooms_tags ON rooms USING GIN(tags);
                ALTER TABLE participants ADD COLUMN IF NOT EXISTS thinking_complete BOOLEAN DEFAULT FALSE;
                ALTER TABLE participants ADD COLUMN IF NOT EXISTS sharing_complete BOOLEAN DEFAULT FALSE;
                ALTER TABLE participants ADD COLUMN IF NOT EXISTS last_activity TIMESTAMPTZ;
                ALTER TABLE participants ADD COLUMN IF NOT EXISTS contributions JSONB DEFAULT '{"speech_count":0,"challenge_count":0,"response_count":0}';
                ALTER TABLE messages ADD COLUMN IF NOT EXISTS sequence INTEGER;
            """)
            logger.info("[DB] Step 24 列迁移完成: rooms hierarchy + participants contributions + messages sequence")

        # Step 31: activities table
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    ALTER TABLE activities ADD COLUMN IF NOT EXISTS version TEXT;
                    ALTER TABLE activities ADD COLUMN IF NOT EXISTS target_type TEXT;
                    ALTER TABLE activities ADD COLUMN IF NOT EXISTS target_id TEXT;
                    ALTER TABLE activities ADD COLUMN IF NOT EXISTS target_label TEXT;
                """)
                logger.info("[DB] Step 31 列迁移完成: activities table")
        except Exception as e:
            logger.warning(f"[DB] activities 列迁移跳过（可能已存在）: {e}")

        # Step 34: Notification System - create table if not exists
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        notification_id  UUID PRIMARY KEY,
                        plan_id          UUID REFERENCES plans(plan_id) ON DELETE CASCADE,
                        version          TEXT,
                        room_id          UUID REFERENCES rooms(room_id) ON DELETE SET NULL,
                        task_id          TEXT,
                        recipient_id     TEXT NOT NULL,
                        recipient_level  INTEGER,
                        type             TEXT NOT NULL,
                        title            TEXT NOT NULL,
                        message          TEXT,
                        read             BOOLEAN DEFAULT FALSE,
                        created_at       TIMESTAMPTZ DEFAULT NOW(),
                        read_at          TIMESTAMPTZ
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_id);
                    CREATE INDEX IF NOT EXISTS idx_notifications_plan ON notifications(plan_id);
                    CREATE INDEX IF NOT EXISTS idx_notifications_room ON notifications(room_id);
                    CREATE INDEX IF NOT EXISTS idx_notifications_task ON notifications(task_id);
                    CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);
                    CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);
                """)
                logger.info("[DB] Step 34 表迁移完成: notifications table")
        except Exception as e:
            logger.warning(f"[DB] notifications 表迁移跳过（可能已存在）: {e}")

        # Step 57: Room Templates
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS room_templates (
                        template_id   UUID PRIMARY KEY,
                        name          TEXT NOT NULL,
                        description   TEXT,
                        purpose       TEXT DEFAULT 'initial_discussion',
                        mode          TEXT DEFAULT 'hierarchical',
                        default_phase TEXT DEFAULT 'selecting',
                        settings      JSONB DEFAULT '{}',
                        created_by    TEXT,
                        is_shared     BOOLEAN DEFAULT FALSE,
                        created_at    TIMESTAMPTZ DEFAULT NOW(),
                        updated_at    TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_room_templates_name ON room_templates(name);
                    CREATE INDEX IF NOT EXISTS idx_room_templates_purpose ON room_templates(purpose);
                """)
                # Insert default templates if none exist
                row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM room_templates")
                if row["cnt"] == 0:
                    defaults = [
                        (str(uuid.uuid4()), "问题诊断室", "用于深入诊断和解决问题，从 PROBLEM_DETECTED 到 RESUMING 的完整流程", "problem_solving", "hierarchical", "selecting", json.dumps({"auto_progression": True, "consensus_threshold": 0.7}), "system", True),
                        (str(uuid.uuid4()), "战略决策室", "用于高层战略决策，侧重 DECISION 到 EXECUTING", "decision_making", "hierarchical", "selecting", json.dumps({"require_l7_approval": True, "min_debate_rounds": 3}), "system", True),
                        (str(uuid.uuid4()), "初始讨论室", "用于团队初始讨论，自由发言和辩论", "initial_discussion", "flat", "selecting", json.dumps({"allow_skip_thinking": False}), "system", True),
                        (str(uuid.uuid4()), "评审回顾室", "用于方案评审和回顾，包含 DEBATE 到 CONVERGING", "review", "collaborative", "selecting", json.dumps({"voting_enabled": True}), "system", True),
                    ]
                    for t in defaults:
                        await conn.execute("""
                            INSERT INTO room_templates (template_id, name, description, purpose, mode, default_phase, settings, created_by, is_shared)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """, *t)
                    logger.info("[DB] Step 57: 默认 Room Templates 已插入")
                logger.info("[DB] Step 57 表迁移完成: room_templates table")
        except Exception as e:
            logger.warning(f"[DB] Step 57 表迁移跳过（可能已存在）: {e}")

        # Step 63: Room Phase Timeline（阶段时间线）
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS room_phase_timeline (
                        entry_id     UUID PRIMARY KEY,
                        room_id      UUID REFERENCES rooms(room_id) ON DELETE CASCADE,
                        phase        TEXT NOT NULL,
                        entered_at    TIMESTAMPTZ NOT NULL,
                        exited_at     TIMESTAMPTZ,
                        exited_via    TEXT,
                        duration_secs INTEGER
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_phase_timeline_room ON room_phase_timeline(room_id);
                    CREATE INDEX IF NOT EXISTS idx_phase_timeline_entered ON room_phase_timeline(entered_at);
                """)
                logger.info("[DB] Step 63 表迁移完成: room_phase_timeline table")
        except Exception as e:
            logger.warning(f"[DB] Step 63 表迁移跳过（可能已存在）: {e}")

        # ── Step 65: task_time_entries 表 ─────────────────────────────────────────
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS task_time_entries (
                        time_entry_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        task_id        UUID NOT NULL,
                        plan_id        UUID NOT NULL,
                        version        TEXT NOT NULL,
                        user_name      TEXT NOT NULL DEFAULT '',
                        hours          DECIMAL(10,2) NOT NULL DEFAULT 0,
                        description    TEXT NOT NULL DEFAULT '',
                        notes          TEXT NOT NULL DEFAULT '',
                        logged_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_time_entries_task
                        ON task_time_entries(task_id);
                    CREATE INDEX IF NOT EXISTS idx_time_entries_plan_version
                        ON task_time_entries(plan_id, version);
                """)
                logger.info("[DB] Step 65 表迁移完成: task_time_entries table")
        except Exception as e:
            logger.warning(f"[DB] Step 65 表迁移跳过（可能已存在）: {e}")

        # ── Step 68: plan_templates 表 ─────────────────────────────────────────
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS plan_templates (
                        template_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name          TEXT NOT NULL,
                        description   TEXT,
                        plan_content  JSONB DEFAULT '{}',
                        tags          TEXT[] DEFAULT '{}',
                        created_by    TEXT,
                        is_shared     BOOLEAN DEFAULT FALSE,
                        created_at    TIMESTAMPTZ DEFAULT NOW(),
                        updated_at    TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_plan_templates_name ON plan_templates(name);
                    CREATE INDEX IF NOT EXISTS idx_plan_templates_tags ON plan_templates USING GIN(tags);
                """)
                logger.info("[DB] Step 68 表迁移完成: plan_templates table")
        except Exception as e:
            logger.warning(f"[DB] Step 68 表迁移跳过（可能已存在）: {e}")

    except Exception as e:
        logger.warning(f"[DB] 列迁移跳过（可能已存在）: {e}")


@asynccontextmanager
async def get_connection():
    """获取数据库连接的上下文管理器"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
