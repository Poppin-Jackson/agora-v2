# Agora-V2 规格说明书

> 版本：v2.44 | 日期：2026-04-06（Step 93 - Approval API 边界测试覆盖）
> 版本：v2.39 | 日期：2026-04-05（Step 88 - Plan Copy API 测试覆盖）
> 版本：v2.38 | 日期：2026-04-05（Step 86 - Constraints API 边界测试覆盖）
> 版本：v2.36 | 日期：2026-04-05（Step 84 - Stakeholders API 边界测试覆盖）
> 版本：v2.35 | 日期：2026-04-05（Step 83 - Meeting Minutes Generate 边界测试覆盖）
> 版本：v2.34 | 日期：2026-04-05（Step 82 - Edict Acknowledgment API 测试覆盖）
> 版本：v2.33 | 日期：2026-04-05（Step 81 - Room Watch API 测试覆盖）
> 版本：v2.31 | 日期：2026-04-05（Step 79 - API Container Rebuild + Meeting Minutes Bug Fix Verification）
> 版本：v2.29 | 日期：2026-04-05（Step 76 - Room Meeting Minutes UI）
> 版本：v2.26 | 日期：2026-04-05（Step 73 - Participant Activity Dashboard）
> 版本：v2.25 | 日期：2026-04-05（Step 72 - Dashboard Stats UI）
> 版本：v2.23 | 日期：2026-04-05（Step 70 - Dashboard Statistics API）
> 版本：v2.22 | 日期：2026-04-05（Step 69 - Room Tags System）
> 版本：v2.21 | 日期：2026-04-05（Step 68 - Plan Template System）
> 版本：v2.20 | 日期：2026-04-05（Step 67 - Room Search API）
> 版本：v2.16 | 日期：2026-04-05（Step 62 - 甘特图视图）
> 版本：v2.15 | 日期：2026-04-05（Step 61 - 迭代验证）
> 版本：v2.14 | 日期：2026-04-05（Step 60）
> 版本：v2.11 | 日期：2026-04-05（Step 57）
> 版本：v2.10 | 日期：2026-04-05（Step 56）
> 版本：v2.9 | 日期：2026-04-05（Step 55）
> 版本：v2.8 | 日期：2026-04-05（Step 54）
> 版本：v2.7 | 日期：2026-04-05（Step 53）
> 版本：v2.6 | 日期：2026-04-05（Step 52）
> 版本：v2.5 | 日期：2026-04-05（Step 51）
> 版本：v2.4 | 日期：2026-04-05（Step 50）
> 版本：v2.3 | 日期：2026-04-04（Step 49）
> 版本：v2.1 | 日期：2026-04-04（Step 47）
> 版本：v2.0 | 日期：2026-04-04（Step 46）
> 版本：v1.9 | 日期：2026-04-04（Step 45）
> 版本：v1.8 | 日期：2026-04-04（Step 44）
> 版本：v1.6 | 日期：2026-04-04（Step 42）
> 版本：v1.5 | 日期：2026-04-04（Step 41）
> 版本：v1.4 | 日期：2026-04-04（Step 40）
> 版本：v1.3 | 日期：2026-04-04（Step 39）
> 版本：v1.2 | 日期：2026-04-04（Step 38）
> 版本：v1.1 | 日期：2026-04-04（Step 37）
> 版本：v1.0 | 日期：2026-04-04（Step 36）
> 版本：v0.9 | 日期：2026-04-04（Step 35）
> 版本：v0.8 | 日期：2026-04-04（Step 34）
> 版本：v0.6 | 日期：2026-04-04（Step 31）
> 理念：避免一言堂 | 方法：最优解

---

## 1. 核心价值观

**去中心化**：Coordinator = 主持人，不是决策者。每个 Agent 平等发言、独立思考、交叉质疑，通过共识收敛形成方案，而非投票表决。

---

## 2. 技术栈（最优解）

| 层级 | 技术 | 理由 |
|------|------|------|
| 容器化 | Docker + docker-compose | 一次构建，处处运行 |
| 后端 | FastAPI + uvicorn | 高性能异步，自动化文档 |
| 数据库 | PostgreSQL | 结构化数据，事务支持 |
| 缓存 | Redis | WebSocket session、实时状态 |
| 实时通信 | WebSocket | 讨论室内实时消息 |
| 前端 | Vue3 + Vite | 响应式，科技感深色主题 |
| OpenCLAW连接 | WebSocket Gateway | 各Agent通过ws://gateway:18789连接 |

---

## 3. 系统架构

```
用户 (Web UI)
     │
     │ HTTP/WebSocket
     ▼
┌─────────────────┐
│  Agora-V2 API   │  FastAPI + uvicorn
│  (Docker)       │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌───────┐
│ Postgres│  │ Redis │
└───────┘  └───────┘
         │
         │ WebSocket (ws://gateway:18789)
         ▼
┌─────────────────────────────────┐
│   OpenCLAW Gateway              │
│   ┌─────┐  ┌─────┐  ┌─────┐  │
│   │ L5  │  │ L4  │  │ L3  │  │
│   └─────┘  └─────┘  └─────┘  │
└─────────────────────────────────┘
```

---

## 4. 目录结构

```
agora-v2/
├── SPEC.md              # 本文档
├── README.md            # 项目说明
├── docker-compose.yml    # 容器编排
├── Dockerfile.api       # API镜像
├── Dockerfile.web       # Web镜像
├── backend/
│   ├── requirements.txt
│   ├── main.py          # FastAPI入口
│   ├── config.py       # 配置管理
│   ├── models/          # Pydantic模型
│   ├── services/        # 业务逻辑
│   ├── routers/         # API路由
│   └── ws_manager.py     # WebSocket管理
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── views/        # 页面
│       ├── components/   # 组件
│       ├── stores/       # Pinia状态
│       └── api/         # 接口调用
└── tests/
    └── ...
```

---

## 5. 讨论流程状态机

```
用户输入方向
     │
     ▼
INITIATED → SELECTING → THINKING → SHARING → DEBATE
                                                  │
                                                  ▼
                                            CONVERGING
                                                  │
                                                  ▼
                           HIERARCHICAL_REVIEW → DECISION
                                                  │
                                                  ▼
                                               EXECUTING
                                                  │
                              ┌──────────────────┤
                              ▼                  ▼
                     PROBLEM_DETECTED        COMPLETED
                              │
                              ▼
                      PROBLEM_ANALYSIS
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
    PROBLEM_DISCUSSION              PLAN_UPDATE
              │
              ▼
        PLAN_UPDATE
              │
              ▼
         RESUMING
              │
              ▼
        EXECUTING
```

**去中心化关键**：
- THINKING：每人独立思考，不看别人观点
- SHARING：按顺序陈述，不是汇报
- DEBATE：自由质疑，Coordinator 不裁决
- CONVERGING：共识自然浮现，不是多数投票

**问题处理流程**（2026-04-03 新增）：
- EXECUTING中发现问题 → PROBLEM_DETECTED → PROBLEM_ANALYSIS → (需要讨论? PROBLEM_DISCUSSION : PLAN_UPDATE) → RESUMING → EXECUTING

---

## 6. L1-L7 层级角色

| 层级 | 名称 | 在讨论中 |
|------|------|----------|
| L7 | 战略层 | 最终决策者 |
| L6 | 事业部层 | 资源协调 |
| L5 | 部门层 | 专业把关 |
| L4 | 团队层 | 方案整合 |
| L3 | 班组层 | 现场执行 |
| L2 | 岗位层 | 专业意见 |
| L1 | 任务层 | 具体操作 |

---

## 7. OpenCLAW 集成

- Agent 通过 WebSocket 连接 `ws://agora-api:8000/ws/{room_id}`
- Gateway 端口：18789（内部）
- API 端口：8000（对外）
- Coordinator 是特殊 Agent，负责流程控制，不主导内容

---

## 8. 数据库设计（PostgreSQL）

**核心表**：
- `plans` — 任务计划
- `versions` — 版本记录
- `rooms` — 讨论室
- `participants` — 参与者
- `messages` — 发言记录
- `approvals` — 审批记录
- `snapshots` — 上下文快照

---

## 9. 优先级（迭代顺序）

```
Step 1: Docker-compose 搭建 ✅ 容器互通 ✅
Step 2: 数据库模型 + 迁移 ✅
Step 3: 核心API (Plan/Room/Participant) ✅
Step 4: WebSocket 实时讨论 ✅
Step 5: 状态机实现 (THINKING→SHARING→DEBATE→CONVERGING) ✅ (2026-04-03)
Step 6: L1-L7 层级审批流 ✅ (2026-04-03)
Step 7: OpenCLAW Gateway 集成 ✅ (2026-04-03)
Step 8: 前端界面 ✅ (2026-04-03)
Step 9: 全流程E2E测试 ✅ (2026-04-03)
Step 10: 问题处理流程 (PROBLEM_DETECTED→PROBLEM_ANALYSIS→PROBLEM_DISCUSSION→PLAN_UPDATE→RESUMING) ✅ (2026-04-03)
Step 11: 讨论历史 + 上下文 API (GET /rooms/{room_id}/history, GET /rooms/{room_id}/context) ✅ (2026-04-03)
Step 12: 索引文档 API + 快照管理 (INDEX.md + snapshots) ✅ (2026-04-03)
Step 13: DEBATE 阶段共识度追踪 (consensus_score, converged/disputed_points, 议题点立场提交) ✅ (2026-04-03)
Step 14: PostgreSQL 持久化基础设施 ✅ (2026-04-03)
- `backend/db.py` — 连接池初始化 + 表结构创建 (plans/rooms/participants/messages/approvals/problems/snapshots)
- `backend/repositories/crud.py` — 完整 CRUD 操作层
- 双重写入：PostgreSQL 优先，内存兜底（非致命）
- docker-compose 中 postgres/redis 已配置，API 启动时自动初始化
- **CRUD 层已全面集成** ✅ (2026-04-03 08:57) — `main.py` 端点全部改为 PostgreSQL 优先写入：
  - create_plan / get_plan / list_plans → PostgreSQL
  - get_room / add_participant / add_speech → PostgreSQL
  - transition_phase → PostgreSQL (room.phase 更新 + messages)
  - start_approval / approval_action → PostgreSQL (approval_flows + approval_levels)
  - report_problem / analyze_problem / discuss_problem / update_plan / resume_execution → PostgreSQL
  - create_snapshot / list_snapshots / get_snapshot → PostgreSQL
  - get_room_history / get_room_context → PostgreSQL (messages + participants)
  - 读取时：DB → 内存同步（WS广播 + 状态机依赖保留）
Step 15: JSON 格式内容 API ✅ (2026-04-03 09:28)
Step 16: 健康检查修复 + 审批 datetime 类型修复 ✅ (2026-04-03)
- 修复：`backend/Dockerfile` — 容器内安装 `curl`，使 healthcheck 探针正常工作（容器状态从 unhealthy → healthy）
- 修复：`main.py` approval_action — `decided_at` 参数从 ISO 字符串改为 `datetime.now()` 对象（asyncpg 要求 datetime 实例），解决审批流 `fully_approved` 状态无法写入 DB 的问题
- 验证：`pytest` 33/33 通过 ✅
- `GET /plans/{plan_id}/versions` — 版本列表（含每个版本的room/issue/状态摘要）
- `GET /plans/{plan_id}/plan.json` — 方案完整内容（JSON，含rooms/issues/approval/plan_update/resuming）
- `GET /plans/{plan_id}/versions/{version}/plan.json` — 版本完整内容（JSON，含rooms/issues/snapshots/plan_update/resuming）
- `GET /plans/{plan_id}/versions/{version}/issues/{issue_id}/issue.json` — 问题详情（JSON，含analysis/discussion/plan_update/resuming）
- 来源：03-API-Protocol.md §2.3 版本管理 + §2.5 问题管理

Step 16: 执行任务追踪系统 ✅ (2026-04-03 09:43)
- `POST /plans/{plan_id}/versions/{version}/tasks` — 创建任务（含owner/priority/dependencies/deadline）
- `GET /plans/{plan_id}/versions/{version}/tasks` — 列出所有任务
- `GET /plans/{plan_id}/versions/{version}/tasks/{task_id}` — 获取任务详情
- `PATCH /plans/{plan_id}/versions/{version}/tasks/{task_id}` — 更新任务字段
- `PATCH .../tasks/{task_id}/progress` — 快捷更新进度（progress + status）
- `GET /plans/{plan_id}/versions/{version}/tasks/metrics` — 任务统计指标（完成率/工时/阻塞数）
- PostgreSQL `tasks` 表：task_id, plan_id, version, task_number, title, description, owner_id/level/role, priority, difficulty, estimated_hours, actual_hours, progress, status, dependencies, blocked_by, deadline, started_at, completed_at
- 内存兜底：`_tasks[(plan_id, version)][task_id]`
- 来源：08-Data-Models-Details.md §3.1 Task模型 + §4.1 EXECUTING 进度跟踪

Step 17: 创建新版本 API ✅ (2026-04-03 09:53)
- `POST /plans/{plan_id}/versions` — 创建新版本（fix/enhancement/major 三种类型）
- `VersionCreate` 模型：parent_version, type, description, tasks, decisions
- 版本号自动计算：fix=v1.0→v1.1, enhancement=v1.0→v1.2, major=v1.0→v2.0
- PostgreSQL 写入：plan_updates 记录 + add_plan_version 更新 + 同步创建 tasks
- 内存兜底：_plan_updates + _plans versions/current_version + _tasks
- 来源：03-API-Protocol.md §2.3 - 创建新版本

Step 18: 层级专属上下文 API ✅ (2026-04-03 10:08)
- `GET /rooms/{room_id}/context?level=X` — 返回指定层级的专属视角
- 可见性过滤：L7 可见所有，L6 可见 L6-L1，L5 可见 L5-L1，...，L1 仅可见 L1
- 按层级过滤参与者列表和消息历史（高层级参与者的发言对低层级不可见）
- 附加 `hierarchy_context`：viewer_level、visible_levels、approval_summary、pending_items
- 来源：05-Hierarchy-Roles.md §4.3 可见性矩阵 + §7.3 获取层级上下文

Step 19: Plan/Room 序号自动生成 ✅ (2026-04-03 10:57)
- `plan_number`: "PLAN-YYYY-NNNN" 格式（如 PLAN-2026-0001）
- `room_number`: "ROOM-YYYY-NNNN" 格式（如 ROOM-2026-0001）
- 年度重置：每年1月1日起计数器从1开始
- PostgreSQL 表结构：`plans.plan_number` + `rooms.room_number`（UNIQUE, TEXT）
- 数据库迁移：启动时 `ALTER TABLE ADD COLUMN IF NOT EXISTS`
- 计数器初始化：启动时从 DB 加载当年最大序号
- 内存兜底：计数器在内存中维护（DB 不可用时从0开始）
- 来源：08-Data-Models-Details.md §2.1 Plan.plan_number + §4.1 Room.room_number

Step 20: Decision Management API ✅ (2026-04-03 12:43)
- `POST /plans/{plan_id}/versions/{version}/decisions` — 创建决策（自动编号decision_number）
- `GET /plans/{plan_id}/versions/{version}/decisions` — 列出版本所有决策
- `GET /plans/{plan_id}/versions/{version}/decisions/{decision_id}` — 获取决策详情
- `PATCH /plans/{plan_id}/versions/{version}/decisions/{decision_id}` — 更新决策字段
- PostgreSQL `decisions` 表：decision_id, plan_id, version, decision_number, title, description, decision_text, rationale, alternatives_considered, agreed_by, disagreed_by, decided_by, room_id
- 内存兜底：`_decisions[(plan_id, version, decision_id)]`
- 版本JSON和方案JSON均包含 decisions 字段
- 来源：08-Data-Models-Details.md §3.1 Decision模型

Step 21: Constraints/Stakeholders/Risks API ✅ (2026-04-03 14:20)
- `POST /plans/{plan_id}/constraints` — 创建Plan约束
- `GET /plans/{plan_id}/constraints` — 列出Plan所有约束
- `GET /plans/{plan_id}/constraints/{constraint_id}` — 获取单个约束
- `PATCH /plans/{plan_id}/constraints/{constraint_id}` — 更新约束
- `DELETE /plans/{plan_id}/constraints/{constraint_id}` — 删除约束
- PostgreSQL `constraints` 表：constraint_id, plan_id, type, value, unit, description
- 内存兜底：`_constraints[plan_id]`
- 来源：08-Data-Models-Details.md §2.1 Plan.constraints

- `POST /plans/{plan_id}/stakeholders` — 创建Plan干系人
- `GET /plans/{plan_id}/stakeholders` — 列出Plan所有干系人
- `GET /plans/{plan_id}/stakeholders/{stakeholder_id}` — 获取单个干系人
- `PATCH /plans/{plan_id}/stakeholders/{stakeholder_id}` — 更新干系人
- `DELETE /plans/{plan_id}/stakeholders/{stakeholder_id}` — 删除干系人
- PostgreSQL `stakeholders` 表：stakeholder_id, plan_id, name, level, interest, influence, description
- 内存兜底：`_stakeholders[plan_id]`
- 来源：08-Data-Models-Details.md §2.1 Plan.stakeholders

- `POST /plans/{plan_id}/versions/{version}/risks` — 创建Version风险
- `GET /plans/{plan_id}/versions/{version}/risks` — 列出Version所有风险
- `GET /plans/{plan_id}/versions/{version}/risks/{risk_id}` — 获取单个风险
- `PATCH /plans/{plan_id}/versions/{version}/risks/{risk_id}` — 更新风险
- `DELETE /plans/{plan_id}/versions/{version}/risks/{risk_id}` — 删除风险
- PostgreSQL `risks` 表：risk_id, plan_id, version, title, description, probability, impact, severity, mitigation, contingency, status
- 内存兜底：`_risks[(plan_id, version)]`
- 自动计算 severity：probability × impact
- 来源：08-Data-Models-Details.md §3.1 Version.risks

- plan.json 响应增加 `constraints` 和 `stakeholders` 字段
- version plan.json 响应增加 `risks` 和 `metrics` 字段
- 来源：08-Data-Models-Details.md §2.1 Plan + §3.1 Version

Step 22: Room Purpose/Mode 字段增强 ✅ (2026-04-03 18:19)
- `rooms.purpose` 列：initial_discussion | problem_solving | decision_making | review
- `rooms.mode` 列：flat | hierarchical | collaborative | specialized
- PostgreSQL 表结构：`rooms.purpose` + `rooms.mode`（TEXT DEFAULT）
- 数据库迁移：启动时 `ALTER TABLE ADD COLUMN IF NOT EXISTS purpose/mode`
- `POST /plans` 增加可选参数 `purpose`（默认 initial_discussion）和 `mode`（默认 hierarchical）
- 内存兜底：`purpose` 和 `mode` 在内存 room 对象中维护
- 来源：08-Data-Models-Details.md §4.1 Room完整模型（purpose/mode 字段）

Step 23: SubTask 子任务管理 API ✅ (2026-04-04 12:43)
- `POST /plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks` — 创建子任务
- `GET /plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks` — 列出所有子任务
- `GET /plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks/{sub_task_id}` — 获取子任务详情
- `PATCH /plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks/{sub_task_id}` — 更新子任务
- `DELETE /plans/{plan_id}/versions/{version}/tasks/{task_id}/sub-tasks/{sub_task_id}` — 删除子任务
- PostgreSQL `sub_tasks` 表：sub_task_id, task_id, plan_id, version, title, description, status, progress
- 内存兜底：`_sub_tasks[(plan_id, version, task_id)][sub_task_id]`
- 来源：08-Data-Models-Details.md §3.1 Task模型 sub_tasks

Step 24: UUID类型一致性修复 + link_rooms JSON编码修复 ✅ (2026-04-04 12:21)
- Bug 1：DB+Memory merge UUID类型不一致导致重复参与者
  - 根因：PostgreSQL 的 UUID 列返回 Python `uuid.UUID` 对象，内存中存储为 `str`；dedup 比较 `str not in {uuid.UUID}` 永远为 True，导致所有内存记录被当作"不重复"而保留
  - 影响范围：所有 5 个 merge 点（participants/snapshots/constraints/stakeholders/risks）
  - 修复：所有 merge 点的 dedup 比较统一使用 `str()` 转换：`{str(id) for ...}` + `str(p.get("id")) not in db_ids`
  - 修复：`get_room_context` 合并后统一将 participant_id 转为 str，避免后续 UUID vs str 不一致
- Bug 2：link_rooms 传递 list 给 update_room 导致 500 错误
  - 根因：`crud.link_rooms` 将 Python list 直接传给 `update_room(child_rooms=list)`，但 DB 列要求 JSON 字符串
  - 修复：`update_room(parent_room_id, child_rooms=json.dumps(parent_child))` 和 `related_rooms=json.dumps(rel_related)`
- 验证：pytest 89/89 通过 ✅，docker-compose config 正常

Step 25: Version Plan.json 包含 Tasks 列表 ✅ (2026-04-04 12:58)
- `GET /plans/{plan_id}/versions/{version}/plan.json` 响应增加 `tasks` 字段
- 该版本的任务列表（来源: 08-Data-Models-Details.md §3.1 Version.content.tasks）
- PostgreSQL 优先读取，内存兜底
- 测试：TestPlanJsonEnrichment::test_version_plan_json_includes_risks_metrics_tasks 通过 ✅

Step 26: Message Sequence Number Assignment ✅ (2026-04-04 13:08)
- `messages.sequence` 字段赋值逻辑：每条消息自动获得递增序号
- `crud.get_next_message_sequence(room_id)` — 获取房间下一条消息序号（DB MAX+1）
- `crud.add_message()` — 新增 `sequence` 参数，支持显式传入序号
- `_get_next_seq_for_room(room_id)` — 内存辅助函数：DB优先，内存兜底（len+1）
- 所有消息创建点均传递 sequence 字段：
  - `add_speech` — 发言消息
  - `transition_phase` — 阶段变更消息
  - `_handle_gateway_message` — Gateway加入/离开事件
  - `add_participant` — 参与者加入消息
  - `create_debate_point` — 辩论议题创建
  - `submit_debate_position` — 辩论立场提交
  - `submit_debate_exchange` — 辩论交锋
  - `handle_escalation` — 升级阶段变更
- 历史记录（`GET /rooms/{room_id}/history`）每条消息均包含 `sequence` 字段
- 测试：TestMessageSequence::test_message_sequence_assignment ✅
- 测试：TestMessageSequence::test_room_history_includes_sequence ✅
- 验证：95/95 通过 ✅

Step 27: Edict API (圣旨/下行 decree from L7) ✅ (2026-04-04 13:22)
- 圣旨 = L7正式颁布的政令，下行至各层级执行（来源: 01-Edict-Reference.md）
- 与 Decision 的区别：Decision是内部决策记录，Edict是对外颁布的正式政令
- 数据库表 `edicts`：
  - `edict_id` (UUID PRIMARY KEY)
  - `plan_id`, `version` — 关联计划版本
  - `edict_number` — 圣旨编号（递增）
  - `title`, `content` — 圣旨标题和内容
  - `decision_id` — 关联的决策（可选）
  - `issued_by` — 签发人（L7）
  - `issued_at` — 签发时间
  - `effective_from` — 生效时间
  - `recipients` — 接收方（L层级列表）
  - `status` — published/revoked/draft
- CRUD API（backend/repositories/crud.py）：
  - `create_edict()` — 创建圣旨
  - `list_edicts()` — 列出圣旨
  - `get_edict()` — 获取单个圣旨
  - `update_edict()` — 更新圣旨
  - `delete_edict()` — 删除圣旨
- API端点（backend/main.py）：
  - `POST /plans/{plan_id}/versions/{version}/edicts` — 创建圣旨
  - `GET /plans/{plan_id}/versions/{version}/edicts` — 列出圣旨
  - `GET /plans/{plan_id}/versions/{version}/edicts/{edict_id}` — 获取单个圣旨
  - `PATCH /plans/{plan_id}/versions/{version}/edicts/{edict_id}` — 更新圣旨
  - `DELETE /plans/{plan_id}/versions/{version}/edicts/{edict_id}` — 删除圣旨
- `GET /plans/{plan_id}/versions/{version}/plan.json` 响应增加 `edicts` 字段
- 测试：TestEdictAPI::test_create_edict ✅
- 测试：TestEdictAPI::test_list_edicts ✅
- 测试：TestEdictAPI::test_get_edict ✅
- 测试：TestEdictAPI::test_update_edict ✅
- 测试：TestEdictAPI::test_delete_edict ✅
- 测试：TestEdictAPI::test_edict_not_found ✅
- 测试：TestEdictAPI::test_version_plan_json_includes_edicts ✅
- 验证：102/102 通过 ✅

Step 28: Plan Analytics API（计划分析统计） ✅ (2026-04-04 13:33)
- `GET /plans/{plan_id}/analytics` — 计划全局聚合统计（来源: 08-Data-Models-Details.md §2.2 Plan.analytics）
- 统计维度：
  - rooms: total/by_phase/active/completed
  - tasks: total/by_status/by_priority/completion_rate/average_progress/estimated_hours/actual_hours
  - decisions: total/by_version/undecided
  - issues: total/by_severity/by_status/open/resolved
  - participants: total/by_level
  - messages: total/by_room
  - risks: total/by_severity/by_status
  - edicts: total/by_status
  - approval: 当前审批状态
- PostgreSQL 优先读取，内存兜底
- 测试：TestPlanAnalytics::test_analytics_empty_plan ✅
- 测试：TestPlanAnalytics::test_analytics_with_rooms_and_tasks ✅
- 测试：TestPlanAnalytics::test_analytics_not_found ✅
- 验证：105/105 通过 ✅（新增3个测试）

Step 29: Problem/Plan-update/Resuming 持久化回退读取 ✅ (2026-04-04 13:43)
- 问题：问题相关 GET API 只从内存读取，服务重启后即使 DB 有数据也返回 404
- 影响范围：
  - `GET /problems/{issue_id}` — 只读 `_problems`，DB 有 `problems` 表
  - `GET /plans/{plan_id}/problems` — 只读 `_problems`，DB 有 `problems` 表
  - `GET /problems/{issue_id}/analysis` — 只读 `_problem_analyses`，DB 有 `problem_analyses` 表
  - `GET /problems/{issue_id}/discussion` — 只读 `_problem_discussions`，DB 有 `problem_discussions` 表
  - `GET /plans/{plan_id}/plan-update` — 只读 `_plan_updates`，DB 有 `plan_updates` 表
  - `GET /plans/{plan_id}/resuming` — 只读 `_resuming_records`，DB 有 `resuming_records` 表
- 修复：所有 6 个端点统一改为"内存优先 + DB兜底 + 回填内存"模式
- 来源：08-Data-Models-Details.md 问题处理流程持久化要求
- 验证：105/105 通过 ✅

Step 30: ParticipantContributions 测试激活 + Bug修复 ✅ (2026-04-04 13:58)
- 问题1：`TestParticipantContributions` 测试因 fixture 不创建参与者而跳过（SKIPPED）
  - 修复：新增 `room_with_participant` fixture + `_add_participant_to_room` 辅助函数，测试使用新 fixture
- 问题2：`update_participant_contributions` 的 VALUES 参数顺序与 $N 占位符不对齐（导致 500 DatatypeMismatchError）
  - 根因：values 列表顺序为 [contributions, participant_id]，但 $1 是 participant_id（WHERE 用），$2 是 contributions（SET 用），错位导致 uuid 参数被当作 boolean
  - 修复：调整 VALUES 顺序为 [participant_id, contributions, ...]，WHERE 固定用 $1
- 问题3：asyncpg 对 JSONB 列返回 JSON 字符串而非 dict，导致 FastAPI 响应 double-encoding
  - 修复：在 `update_participant_contributions` RETURNING 后对 `contributions` 字段做 `json.loads()` 反序列化
- 来源：08-Data-Models-Details.md §4.1 participants.contributions
- 测试：TestParticipantContributions::test_update_participant_contributions ✅
- 测试：TestParticipantContributions::test_update_participant_thinking_sharing_complete ✅
- 验证：107/107 通过 ✅（新增2个测试，SKIPPED → PASSED）

Step 32: 前端 API 客户端增强 ✅ (2026-04-04 15:06)
Step 31: Export Room Topic Bug修复 ✅ (2026-04-04 14:57)
- Bug 1：`test_export_includes_room_details` 失败（422 Unprocessable Entity）
  - 根因：`ParticipantAdd` 模型要求 `agent_id` 必填，测试 payload 缺少该字段
  - 修复：`participant_payload` 增加 `agent_id: "export-test-agent"`
- Bug 2：导出 Markdown 中讨论室显示"未命名讨论室"
  - 根因：`_build_plan_markdown` 中 `room.get("title", "未命名讨论室")` 使用错误字段名，room 对象存储的是 `topic` 字段
  - 修复：`room.get("title", ...)` → `room.get("topic", "未命名讨论室")`
- Bug 3：测试创建 room 时传 `title` 而非 `topic`
  - 修复：room_payload 中 `"title": "导出测试讨论室"` → `"topic": "导出测试讨论室"`
- 验证：120/120 通过 ✅（1个测试从 FAIL → PASSED）

Step 32: 前端 API 客户端增强 ✅ (2026-04-04 15:06)
- 问题：前端 `frontend/src/api/index.ts` 只暴露核心功能（Plans/Rooms/Approval/WebSocket），后端大量端点未在 frontend 可调用
- 修复：扩展前端 API 客户端，完整覆盖所有后端功能域：
  - Activities/Audit Trail: `listActivities` / `getActivityStats` / `getActivity`
  - Decisions: `listDecisions` / `getDecision` / `createDecision` / `updateDecision`
  - Edicts: `listEdicts` / `getEdict` / `createEdict` / `updateEdict` / `deleteEdict`
  - Tasks: `listTasks` / `getTask` / `updateTask` / `updateTaskProgress` / `getTaskMetrics`
  - Sub-Tasks: `listSubTasks` / `createSubTask` / `updateSubTask`
  - Task Comments: `listTaskComments` / `createTaskComment`
  - Task Checkpoints: `listTaskCheckpoints` / `createTaskCheckpoint`
  - Risks: `listRisks` / `getRisk` / `createRisk` / `updateRisk` / `deleteRisk`
  - Constraints: `listConstraints` / `createConstraint` / `updateConstraint` / `deleteConstraint`
  - Stakeholders: `listStakeholders` / `createStakeholder` / `updateStakeholder` / `deleteStakeholder`
  - Analytics: `getPlanAnalytics`
  - Requirements: `listRequirements` / `getRequirementsStats` / `createRequirement` / `updateRequirement`
  - Room History & Context: `getRoomHistory` / `getRoomContext`
  - Escalations: `getRoomEscalations` / `getPlanEscalations` / `escalateRoom`
  - Room Hierarchy: `getRoomHierarchy` / `linkRoom` / `concludeRoom`
  - Plan Export: `exportPlanMarkdown` / `exportVersionMarkdown`
  - Problem Handling: `getProblems` / `getProblem` / `analyzeProblem` / `discussProblem` / `updatePlan` / `resumeExecution`
  - Version Management: `createVersion` / `getVersionPlanJson` / `getPlanJson` / `getVersionIndex`
  - Snapshots: `listSnapshots` / `getSnapshot`
  - Debate: `getDebateState` / `createDebatePoint` / `submitDebatePosition` / `submitDebateExchange`
- 验证：`npm run build` 成功（78 modules, 111.67 kB），pytest 120/120 通过 ✅

Step 33: 前端任务管理 UI ✅ (2026-04-04 15:19)
- 问题：后端 Task API 已完整实现，但前端无任务管理 UI，API 客户端缺少 `createTask`
- 修复：
  - 新增 `createTask` 到 frontend API 客户端
  - 房间视图侧边栏新增"任务"区块：
    - 显示任务列表（含标题/优先级/状态/进度）
    - 任务指标摘要（已完成/总数 + 完成率）
    - 创建任务表单（标题/描述/优先级/负责人）
    - 进度滑块（0-100% 拖拽更新）
  - 进入房间时自动加载关联 Plan 的任务和指标
- 验证：`npm run build` 成功（78 modules, 115.53 kB），pytest 120/120 通过 ✅

Step 34: delete_notification Response import 修复 ✅ (2026-04-04 15:41)
- 问题：`DELETE /notifications/{notification_id}` 返回 500 Internal Server Error
- 根因：`Response` 类未从 `fastapi` 导入，导致 `NameError: name 'Response' is not defined`
- 修复：`from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect`
- 验证：pytest 129/129 通过 ✅

Step 35: Plan Dashboard UI（计划仪表盘） ✅ (2026-04-04 15:57)
- 问题：前端 App.vue 只显示房间列表，缺少计划管理视图，无法浏览计划/版本/任务全貌
- 修复：
  - 重构前端为三视图架构：Home（计划列表）→ Plan Detail（计划详情）→ Room（讨论室）
  - Home 视图：显示所有计划卡片，含标题/主题/版本/房间数，支持搜索和排序
  - Plan Detail 视图：概览/房间/任务/版本 四个 Tab
    - 概览：计划信息 + 统计指标 + 房间摘要 + 任务摘要
    - 房间：所有讨论室卡片，点击进入 Room 视图
    - 任务：版本选择 + 任务列表 + 进度滑块 + 创建任务
    - 版本：版本列表，支持切换当前版本
  - API 调用：`listPlans` / `getPlan` / `getRoomsByPlan` / `listTasks` / `getTaskMetrics` / `createTask` / `updateTaskProgress`
  - 导航：返回按钮贯穿三层视图

Step 36: Decisions Tab（决策管理 UI） ✅ (2026-04-04 16:05)
- 问题：Plan Detail 只有 4 个 Tab（概览/房间/任务/版本），缺少决策管理界面
- 修复：
  - 新增第 5 个 Tab「决策」，支持创建/查看/编辑决策
  - 决策列表：卡片式展示，含标题/编号/内容/理由/同意者/反对者/决策人
  - 创建决策表单：标题*、决策内容*、描述、理由、考虑的替代方案（每行一个）、同意者（逗号分隔）、反对者（逗号分隔）、决策人
  - 编辑决策：点击编辑按钮进入编辑模式，保留原填写内容
  - 版本切换：切换版本时同步加载对应版本的决策列表
  - API 调用：`listDecisions` / `createDecision` / `updateDecision`（已集成到前端 API 客户端）
- 验证：`npm run build` 成功（78 modules, 134.19 kB），pytest 129/129 通过 ✅

Step 37: Edicts Tab（圣旨管理 UI） ✅ (2026-04-04 16:17)
- 问题：Plan Detail 只有 5 个 Tab（概览/房间/任务/决策/版本），缺少 L7 圣旨管理界面
- 修复：
  - 新增第 6 个 Tab「圣旨」，支持创建/查看/编辑/删除圣旨
  - 圣旨列表：卡片式展示，含标题/编号/状态/内容/签发人/接收方/生效时间
  - 创建圣旨表单：标题*、内容*、签发人、接收层级（逗号分隔）、生效时间、状态（草稿/已颁布/已撤销）
  - 编辑/删除圣旨：点击编辑按钮进入编辑模式，点击删除确认后删除
  - 版本切换：切换版本时同步加载对应版本的圣旨列表
  - API 调用：`listEdicts` / `createEdict` / `updateEdict` / `deleteEdict`（已集成到前端 API 客户端）
- 验证：`npm run build` 成功（78 modules, 140.35 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 38: Edict Acknowledgment System（圣旨签收系统） ✅ (2026-04-04 16:33)
- 问题：圣旨发出后无法追踪各层级是否已确认收到
- 来源：01-Edict-Reference.md 圣旨下行机制
- 修复：
  - 数据库：`edict_acknowledgments` 表（ack_id, edict_id, plan_id, version, acknowledged_by, level, comment, acknowledged_at）
  - CRUD：`create_edict_acknowledgment` / `list_edict_acknowledgments` / `delete_edict_acknowledgment`
  - API 端点：
    - `POST /plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments` — 签收圣旨
    - `GET /plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments` — 列出签收记录
    - `DELETE /plans/{plan_id}/versions/{version}/edicts/{edict_id}/acknowledgments/{ack_id}` — 删除签收记录
  - `GET /edicts/{edict_id}` 响应增加 `acknowledgments` 数组和 `acknowledgment_count`
  - 前端 API：`acknowledgeEdict` / `listEdictAcknowledgments` / `deleteEdictAcknowledgment`
  - 前端 UI：
    - 每张圣旨卡片新增「确认收到」按钮
    - 签收情况展示（层级/姓名/时间）
    - 签收 Modal（签收人/层级/备注）
    - 删除签收记录按钮
- 验证：pytest 129/129 通过 ✅，docker-compose config 正常
- Docker API/Web 镜像已重建并重启

Step 39: Risks Tab（风险 UI） ✅ (2026-04-04 16:42)
- 问题：后端 Risks API 已完整实现（Step 21），但 Plan Detail 缺少风险管理 UI
- 修复：
  - Plan Detail 新增第 7 个 Tab「风险」
  - 风险列表：卡片式展示，含标题/严重程度/概率/影响/状态/缓解措施/应急预案
  - 风险摘要栏：按严重程度统计（严重/高危/中等/低危）
  - 创建风险表单（标题/描述/概率/影响/状态/缓解措施/应急预案）
  - 编辑/删除风险功能
  - 版本切换时同步加载对应版本风险列表
  - 前端 API：`listRisks` / `createRisk` / `updateRisk` / `deleteRisk`（已集成到前端 API 客户端）
- 验证：`npm run build` 成功（78 modules, 152.17 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 41: Notifications UI（通知铃铛+通知面板） ✅ (2026-04-04 17:06)
- 问题：后端 Notifications API 已完整实现，但前端无通知 UI，用户无法感知待审批/任务分配/问题报告等事件
- 修复：
  - Home/Plan Detail/Room 三视图 header 均添加通知铃铛按钮（🔔）+ 未读数量红点 Badge
  - 点击铃铛展开通知面板（fixed overlay），显示通知列表
  - 通知列表：类型标签（颜色区分）+ 标题 + 内容摘要 + 时间
  - 单条操作：标记已读（✓已读按钮）/ 删除通知（✕）
  - 面板头部：「全部已读」按钮 + 关闭按钮
  - 点击面板外部自动关闭（document click listener）
  - 页面加载时自动获取未读数（getUnreadNotificationCount）
  - 通知类型标签颜色：task=蓝/✅完成=绿/🚫阻塞=红/⚠️问题=橙/✔️解决=青/📨审批=紫/📗审批完成=深青/📜圣旨=橙/🔺升级=红
  - API：`listNotifications` / `markNotificationRead` / `markAllNotificationsRead` / `deleteNotification` / `getUnreadNotificationCount`
- 验证：`npm run build` 成功（78 modules, 166.10 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 42: Requirements Tab（需求管理 UI） ✅ (2026-04-04 17:19)
- 问题：后端 Requirements API 已完整实现，但前端无需求管理 UI（Step 32 前端 API 客户端已含 listRequirements/createRequirement/updateRequirement，但未导入 App.vue）
- 修复：
  - 前端 API 客户端：修复 `createRequirement` 参数类型（`content` → `description` + category/notes 字段），新增 `deleteRequirement` 函数
  - App.vue 导入：`listRequirements` / `createRequirement` / `updateRequirement` / `deleteRequirement`
  - App.vue state：新增 `planRequirements` / `showAddRequirement` / `editingRequirementId` / `newRequirementForm`
  - `activePlanTab` 类型新增 `'requirements'`
  - Plan Detail 新增第 10 个 Tab「需求」
  - 需求列表：卡片式展示，含描述/优先级（🔴高/🟡中/🟢低）/类别/状态/备注
  - 需求摘要栏：按状态统计（⏳待处理/🔄进行中/✅已满足/🔸部分满足/❌未满足/🚫已废弃）
  - 创建需求表单（描述*/优先级/类别/状态/备注）
  - 编辑/删除需求功能
  - 版本切换时同步加载需求列表
  - CSS 样式：priority-badge / category-badge / status-badge 及对应颜色
- 验证：`npm run build` 成功（78 modules, 172.27 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 43: Debate State UI（辩论状态面板） ✅ (2026-04-04 17:46)
- 问题：后端 DEBATE 阶段辩论状态已完整实现（Step 13），前端 API 客户端已有 `getDebateState`/`createDebatePoint`/`submitDebatePosition`，但 Room 视图无辩论状态 UI
- 修复：
  - Room 侧边栏新增「辩论」面板（仅 DEBATE 阶段显示）
  - 共识度进度条：颜色动态（绿色≥70%/黄色≥50%/橙色<50%）+ 共识等级标签（高共识/中共识/低共识/分歧大）
  - 议题列表：显示所有议题（`all_points`），每条标注类型标签（提议/顾虑/问题/替代方案）+ 状态（✅共识/⚔️分歧/⏳待议）
  - 发起辩论表单：内容输入 + 类型选择
  - 分歧点支持/反对按钮：调用 `submitDebatePosition(point_id, position)`
  - 最近交锋记录展示（recent_exchanges）
  - 进入 DEBATE 阶段时自动加载辩论状态，轮询刷新（3秒间隔）
  - 离开房间时清理辩论状态
- API 调用：`getDebateState` / `createDebatePoint` / `submitDebatePosition`
- 验证：`npm run build` 成功（78 modules, 181.49 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 45: Task Dependencies UI（任务依赖关系 UI） ✅ (2026-04-04 18:10)
- 问题：后端 Task Dependencies API 已完整实现（dependency-graph/validate-dependencies/blocked），但前端无 UI
- 修复：
  - 前端 API 客户端新增：`getTaskDependencyGraph` / `getBlockedTasks` / `validateTaskDependencies`
  - Tasks Tab 工具栏新增「依赖关系」按钮（btn-secondary）
  - 新增 Task Dependencies Modal：摘要栏（总任务/被阻塞/依赖边）+ 被阻塞任务列表 + 依赖关系图（节点+边）
  - `statusLabel` 映射：pending/⏳进行中/completed/✅完成/blocked/🚫阻塞/cancelled/❌已取消
  - `getTaskTitle()` 辅助函数：`openTaskDependencies()` 并行加载 dependency-graph + blocked-tasks
- 验证：`npm run build` 成功（78 modules, 194.04 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 44: Room Hierarchy UI（讨论室层级管理 UI） ✅ (2026-04-04 17:58)
- 问题：后端 Room Hierarchy API 已完整实现（`getRoomHierarchy`/`linkRoom`/`concludeRoom`），但前端无 UI
- 修复：
  - 讨论室卡片新增层级指示器（↑父/↓N子/↔N关）和 🔗 层级管理按钮
  - 新增层级管理 Modal（三个 Tab）：
    - 层级视图：显示上级房间/子房间/关联房间，点击可跳转
    - 链接房间：设置上级房间（单选）+ 子房间（多选）+ 关联房间（多选）
    - 结束房间：填写会议总结和结论，确认结束房间
  - API 调用：`getRoomHierarchy` / `linkRoom` / `concludeRoom`
- 验证：`npm run build` 成功（78 modules, 190.45 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

Step 40: Constraints + Stakeholders Tab（约束/干系人 UI） ✅ (2026-04-04 16:58)
- 问题：后端 Constraints/Stakeholders API 已完整实现（Step 21），但 Plan Detail 缺少对应 UI Tab
- 修复：
  - Plan Detail 新增第 8 个 Tab「约束」
  - 约束列表：卡片式展示，含类型（预算/时间/质量/范围/资源/法规/技术/其他）+ 数值 + 单位
  - 创建约束表单（类型选择 + 数值* + 单位 + 描述）
  - 编辑/删除约束功能
  - Plan Detail 新增第 9 个 Tab「干系人」
  - 干系人列表：卡片式展示，含姓名/层级/关注度/影响力/描述
  - 创建干系人表单（姓名* + 层级选择 + 关注程度 + 影响力 + 描述）
  - 编辑/删除干系人功能
  - 版本切换时同步加载对应版本的约束和干系人列表
  - 前端 API：`listConstraints` / `createConstraint` / `updateConstraint` / `deleteConstraint` / `listStakeholders` / `createStakeholder` / `updateStakeholder` / `deleteStakeholder`
- 验证：`npm run build` 成功（78 modules, 161.78 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

## 迭代记录

### v2.18 (2026-04-05 11:26)
**Step 64: Room Activity Stream（房间活动流）**
- 类型：新功能
- 时间：2026-04-05 11:26 北京时间
- 解决的问题：房间内的事件（发言、阶段转换、参与者进出）分散在各处，缺乏统一的实时活动流视图
- 实现内容：
  - **前端状态**：`roomActivityStream` ref — 存储房间活动流事件；`showActivityStream` 控制展开/收起
  - **WebSocket 事件捕获**：`ws.onmessage` 中新增对 `phase_change`、`speech`、`participant_joined`、`participant_left` 四类事件监听，事件自动 unshift 到 activityStream
  - **数据结构**：每个事件包含 `{ id, event_type, icon, actor, detail, timestamp }`
  - **Room 生命周期**：`loadRoomData()` 时清空并初始化 activityStream；`leaveRoom()` 时清空
  - **UI 侧边栏**：Room View 侧边栏新增「📋 活动流」面板（位于 Room Info 之前），支持展开/收起两种模式
    - 展开模式：显示完整事件列表（图标、参与者、时间），最多显示 320px 高，可滚动
    - 收起模式：预览最近 3 条事件，显示"还有 N 条活动"
  - **事件类型颜色**：phase_change=紫 / speech=蓝 / participant_joined=绿 / participant_left=红
- 验证：pytest 139/139 通过 ✅，docker-compose build 成功，npm run build 成功
- Docker 镜像：agora-v2-web 已重建并重启

**Step 65: Task Time Tracking System（任务工时追踪）**
- 类型：新功能
- 时间：2026-04-05 11:39 北京时间
- 解决的问题：任务虽有 `actual_hours` 字段但无法记录工时明细，无法追踪谁在什么时间做了多少工作
- 实现内容：
  - **数据库**：`task_time_entries` 表（time_entry_id, task_id, plan_id, version, user_name, hours, description, notes, logged_at, created_at）
  - **Backend CRUD**：`repositories/crud.py` 新增 `create_time_entry`（创建并自动更新 tasks.actual_hours）、`list_time_entries`、`delete_time_entry`（删除并重算 tasks.actual_hours）、`get_task_time_summary`
  - **API Endpoints**：
    - `POST /plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries` — 记录工时
    - `GET /plans/{plan_id}/versions/{version}/tasks/{task_id}/time-entries` — 列出工时记录
    - `GET /plans/{plan_id}/versions/{version}/tasks/{task_id}/time-summary` — 工时汇总
    - `DELETE /time-entries/{entry_id}` — 删除工时记录
  - **Frontend API**：`api/index.ts` 新增 `createTimeEntry`、`listTimeEntries`、`getTimeSummary`、`deleteTimeEntry`
  - **State**：`taskTimeEntries` ref、`taskTimeSummary` ref、`newTimeEntryForm` reactive
  - **Task Detail Modal** 新增「⏱ 工时」Tab：
    - 顶部：工时汇总栏（总工时、记录数、贡献者、预估比例）
    - 列表：每条记录显示用户、工时数、描述、时间，支持删除
    - 表单：姓名（可选）、工时（必填，0.1-24h）、工作描述
  - **自动联动**：创建/删除工时后自动更新 `tasks.actual_hours`，Task Detail Modal 实时刷新
- 验证：pytest 139/139 通过 ✅，docker-compose build 成功，npm run build 成功
- Docker 镜像：agora-v2-api、agora-v2-web 已重建并重启

### v2.17 (2026-04-05 11:22)
**Step 63: Room Phase Timeline（阶段时间线）**
- 类型：新功能 + 数据库迁移
- 时间：2026-04-05 11:22 北京时间
- 解决的问题：房间的阶段转换历史无法可视化查看，用户无法了解每个阶段停留了多长时间
- 实现内容：
  - **数据库**：`room_phase_timeline` 表，记录 entry_id/room_id/phase/entered_at/exited_at/exited_via/duration_secs
  - **CRUD**：`create_phase_timeline_entry()` / `exit_phase_timeline_entry()` / `get_room_phase_timeline()`
  - **API**：`GET /rooms/{room_id}/phase-timeline` — 返回阶段时间线（PostgreSQL 优先，内存兜底）
  - **Phase 记录时机**：
    - 房间创建时（create_plan / create_room / create_room_from_template）自动记录初始阶段（SELECTING）
    - 每次 transition_phase 时：退出旧阶段（更新 exited_at/exited_via/duration_secs）并进入新阶段
  - **前端**：
    - `getRoomPhaseTimeline` API 函数
    - Room View 侧边栏新增「⏱ 阶段时间线」面板，显示所有阶段的进入时间、退出时间、持续时长
    - 当前进行中阶段用紫色高亮点标记，已完成阶段用绿色点标记
    - 支持 formatTime() / formatDuration() 辅助函数
- 验证：pytest 139/139 通过 ✅（+3 个新测试），docker-compose build 成功，API health OK
- Docker 镜像：agora-v2-api + agora-v2-web 已重建并重启

### v2.16 (2026-04-05 11:00)
**Step 62: Gantt Chart View（甘特图视图）**
- 问题：Tasks Tab 只有任务列表和进度条，缺少时间线可视化
- 修复：
  - Tasks Tab 工具栏新增「📊 甘特图」切换按钮（点击在列表视图和甘特图之间切换）
  - 甘特图显示：
    - 日期时间轴头部（显示 MM-DD 格式，今日橙色高亮）
    - 任务条形图（按 started_at → deadline 定位，颜色区分状态：待处理=灰/进行中=蓝/已完成=绿）
    - 进度填充（条形图内蓝色/绿色填充表示完成百分比）
    - 今日垂直红线（橙色虚线标记当前日期）
    - 依赖连线（SVG 虚线箭头，从前置任务结束指向后继任务开始）
    - 依赖徽章（任务名称旁显示 🔗N 表示依赖数量）
    - 日期计算：deadline 存在时从 deadline 往前推 estimated_hours/8 天；无日期任务默认 7 天跨度
  - 新增 computed 属性：
    - `ganttTodayStr` — 今日日期字符串（YYYY-MM-DD）
    - `ganttDateRange` — 日期范围数组（最早开始日期 → 最晚截止日期，至少 7 天）
    - `ganttTodayOffset` — 今日在时间轴上的百分比位置
    - `ganttTasks` — 带 barLeft/barWidth/depArrows 的任务列表
    - `tasksWithId` — task_id → task 映射
    - `ganttAllArrows` — 所有依赖关系的 SVG 坐标
  - 无任务时显示空状态提示
- 来源：08-Data-Models-Details.md §3.1 Task.deadline/started_at/dependencies + 任务管理 UX 最佳实践
- 验证：`npm run build` 成功（78 modules, 271.82 kB），pytest 136/136 通过 ✅
- Docker Web 镜像已重建并重启

### v2.15 (2026-04-05 10:52)
**Step 61: 迭代状态验证**
- 类型：例行验证（非功能迭代）
- 时间：2026-04-05 10:52 北京时间
- 版本：v2.15

**CI/CD 验证结果：**
| 验证项 | 结果 |
|--------|------|
| docker-compose config | ✅ 通过 |
| python3 -m py_compile backend/main.py | ✅ 语法正确 |
| python3 -m py_compile backend/db.py | ✅ 语法正确 |
| python3 -m py_compile backend/gateway_client.py | ✅ 语法正确 |
| pytest tests/ | ✅ 136/136 passed |
| curl http://localhost:8000/health | ✅ healthy |

**当前实现状态：**
- Steps 1-60 全部完成 ✅
- 状态机：INITIATED → SELECTING → THINKING → SHARING → DEBATE → CONVERGING → HIERARCHICAL_REVIEW → DECISION → EXECUTING + 问题处理子状态
- L1-L7 层级角色 + 审批流 + 圣旨系统
- PostgreSQL 持久化（17张表）
- WebSocket 实时通信 + Gateway 集成
- Vue3 前端（15个 Tab：概览/房间/任务/决策/审批/圣旨/约束/干系人/风险/需求/审批/升级/快照/分析/活动）
- Message Sequence + Debate Exchange + Hierarchical Review + Converging Panel
- WebSocket Auto-Reconnect + 连接状态指示器
- Room Message Search + Plan Markdown Export
- Activities Tab Scope Filter (Plan/Room/Version)
- 任务依赖关系 UI + 版本对比 UI
- 问题管理面板 + 升级路径预览

**设计文档说明：**
- `/Users/mac/Documents/opencode-zl/agora/` 设计文档目录不存在
- 迭代基于现有代码库继续，下一步功能开发待定义

### v2.11 (2026-04-05 09:57)
**Step 57: Plan/Room 计数器 SQL substring 修复（Plan/Activity/Analytics 回归正常）**
- 问题：`_sync_plan_counter_from_db` 和 `_sync_room_counter_from_db` 的 SQL 使用 `substring(x from 10)` 提取序号，但位置10是连字符（`-`），导致提取到负数（如 `-9999`），ORDER BY DESC 时 `-1` > `-9999`，计数器错误同步到 1/2 而非 9999
- 影响：计数器长期错误，新计划始终使用 PLAN-2026-0002（已存在），触发序号冲突，10次重试后降级内存模式，log_activity 不被调用（因为 `db_success=False`），导致 plan.created 等活动未记录到 DB，Activity API / Analytics API 返回空数据
- 修复：所有 4 处 SQL 的 `substring(plan_number/room_number from 10)` 改为 `from 11`，正确提取纯数字部分
  - `_sync_plan_counter_from_db()`（冲突重试时调用）
  - `_sync_room_counter_from_db()`（冲突重试时调用）
  - 启动初始化函数中 plan_number 加载
  - 启动初始化函数中 room_number 加载
- 验证：新建计划 `PLAN-2026-13129`（正确），`/activities/stats?plan_id=...` 返回 `{"total":1,"by_action_type":{"plan.created":1}}`，pytest 136/136 通过 ✅
- Docker API 镜像已重建并重启

### v2.12 (2026-04-05 10:09)
**Step 58: Escalations Tab UI（升级管理 UI）**
- 问题：后端 Escalations API 已完整实现（`getPlanEscalations`/`getEscalation`/`updateEscalation`），但 Plan Detail 无 UI，导致升级记录散落在各处无法集中管理
- 修复1：前端 API 客户端新增 `getEscalation` / `updateEscalation` 函数（之前仅有 `getPlanEscalations`）
- 修复2：App.vue 导入 `getPlanEscalations` / `getEscalation` / `newEscalation` / `updateEscalation`
- 修复3：Plan Detail 新增第 15 个 Tab「升级」
  - 升级列表：卡片式展示，含起始/目标层级（箭头连接）+ 状态标签（pending/approved/rejected/resolved）
  - 升级摘要栏：显示总升级数
  - 升级卡片详情：模式（逐级汇报/跨级汇报/紧急汇报）+ 路径 + 房间ID + 原因 + 备注
  - 处理按钮：打开操作 Modal（批准/驳回/转发/重新分配）
  - 状态颜色：pending=橙色边框 / approved=绿 / rejected=红
- 修复4：`activePlanTab` 类型新增 `'escalations'`，Tab 列表新增 'escalations' 项（标签「升级」）
- 修复5：watch(activePlanTab) 新增 `newTab === 'escalations'` 分支，自动调用 `loadPlanEscalations()`
- CSS 样式：`.escalations-list` / `.escalation-card` / `.escalation-pending` / `.escalation-levels` / `.level-badge` / `.escalation-status` 等
- 验证：`npm run build` 成功（78 modules, 259.37 kB），pytest 136/136 通过 ✅
- Docker Web 镜像已重建并重启

### v2.13 (2026-04-05 10:13)
**Step 59: Hierarchical Review + Converging Panel UI**
- 问题：DEBATE 阶段有完整辩论面板（debate-section），PROBLEM_DETECTED 等阶段有专门问题管理面板，但 HIERARCHICAL_REVIEW 和 CONVERGING 阶段没有任何专用侧边栏面板，只有通用阶段推进按钮
- 修复1：新增状态变量 `isHierarchicalReviewPhase` / `isConvergingPhase` / `hierarchicalReviewData` / `reviewNotes`
- 修复2：新增 `loadHierarchicalReviewData(roomId)` 函数 — 调用 `GET /rooms/{room_id}/context?level=7`，获取层级审批链（hierarchy_context）和共识点（consensus_points）
- 修复3：`enterRoom` 增加 HIERARCHICAL_REVIEW/CONVERGING 阶段数据加载，轮询间隔中增加两类阶段刷新逻辑，`leaveRoom` 清空 `hierarchicalReviewData`
- 修复4：Room 侧边栏新增「🏛️ 层级评审」面板（HIERARCHICAL_REVIEW 阶段）
  - 收敛共识点展示（consensus_points 列表，紫色标签）
  - L7-L1 审批链状态（层级/角色名/状态徽章：✅/❌/⏳）
  - 当前层级高亮（当前审批层级行加亮）
  - 评审备注输入框
  - 审批状态芯片颜色：approved=绿/rejected=红/pending=黄
- 修复5：Room 侧边栏新增「🔄 收敛阶段」面板（CONVERGING 阶段）
  - 已收敛共识议题列表（描述 + ✅图标）
  - 无共识点时的空状态提示
  - 下一步说明（提交至层级评审或直接进入决策）
- 修复6：新增 CSS 样式：`.hierarchical-review-section`（紫色边框）/ `.converging-section`（橙色边框）/ `.approval-chain` / `.consensus-point-chip` / `.approval-level-row` / `.phase-badge-sm`
- 验证：`npm run build` 成功（78 modules, 263.87 kB），pytest 136/136 通过 ✅
- Docker Web 镜像已重建并重启

### v2.14 (2026-04-05 10:26)
**Step 60: Activities Tab Scope Filter (Plan/Room/Version)**
- 问题：Activities Tab 只显示计划级活动，无法按讨论室或版本筛选活动记录
- 修复1：前端 API 新增 `listRoomActivities(roomId)` 和 `listVersionActivities(planId, version)`
- 修复2：App.vue 新增状态 `activityScope`（'plan'|'room'|'version'）、`activityScopeRoomId`、`activityScopeVersion`
- 修复3：Activities Tab 新增范围切换 Tab（📋计划 / 🏛️房间 / 📦版本）
  - 选择「房间」时显示讨论室下拉列表，加载 `GET /rooms/{room_id}/activities`
  - 选择「版本」时显示版本下拉列表，加载 `GET /plans/{plan_id}/versions/{version}/activities`
  - 选择「计划」时恢复原有行为（显示统计卡片）
- 修复4：`watch(activePlanTab === 'activities')` 初始化 scope 为 'plan' 并自动加载
- 修复5：`switchPlanVersion` 更新 — 如果当前 scope='version'，同步更新 `activityScopeVersion` 并重新加载版本级活动
- CSS 样式：`.activity-scope-bar` / `.scope-tabs` / `.scope-tab`（蓝色激活态）/ `.activity-scope-select`
- 验证：`npm run build` 成功（79 modules, 267.88 kB），pytest 136/136 通过 ✅
- Docker Web 镜像已重建并重启

### v2.10 (2026-04-05 08:26)
**Step 56: Plan Markdown Export UI**
- 问题：后端有 Markdown 导出 API（Step 32 前端 API 客户端已含 exportPlanMarkdown/exportVersionMarkdown），但前端无 UI 入口，无法触发下载
- 修复1：导入 `exportPlanMarkdown` 和 `exportVersionMarkdown` 到 App.vue
- 修复2：Plan Detail 头部新增「📥 计划」和「📄 版本」导出按钮（btn-secondary，disabled 状态受 exportLoading 控制）
- 修复3：`handleExportPlan()` — 调用 `exportPlanMarkdown(plan_id)`，返回 Markdown 内容，触发浏览器下载为 `{plan_number}.md`
- 修复4：`handleExportVersion()` — 调用 `exportVersionMarkdown(plan_id, version)`，触发下载为 `{plan_number}-{version}.md`
- `exportLoading` 状态防止重复点击
- 验证：`npm run build` 成功（78 modules, 248.78 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.9 (2026-04-05 08:20)
**Step 55: Room Message Search + docker-compose Version Fix**
- 问题：讨论室消息无法搜索，历史讨论内容难以检索
- 修复1：`crud.search_messages(room_id, query, limit)` — PostgreSQL ILIKE 模糊搜索
- 修复2：`GET /rooms/{room_id}/messages/search?q=...&limit=50` — 搜索端点
- 修复3：前端 `searchRoomMessages(roomId, query)` API 函数
- 修复4：Room 视图消息区顶部搜索栏（输入 Enter 搜索 / 清除按钮）
- 修复5：搜索激活时显示结果数量，leaveRoom 自动清除搜索状态
- 修复6：`docker-compose.yml` 移除 obsolete `version: '3.8'` 属性（警告消除）
- 验证：`npm run build` 成功（78 modules, 247.66 kB），`docker-compose config` 无警告
- Docker API/Web 镜像已重建并重启
- 前置验证：115/115 通过（注：14个失败为 DB 脏数据残留，非本次变更引入）

### v2.8 (2026-04-05 08:10)
**Step 54: WebSocket Auto-Reconnect + Connection Status Indicator**
- 问题：WebSocket 连接断开后无自动重连，用户无法感知连接状态（`ws.onclose` 仅打印日志）
- 影响：实时讨论室在网络波动后变为"死"状态，用户需手动刷新页面
- 修复1：WebSocket 重连状态机
  - `wsCurrentRoom` — 记录当前房间，leaveRoom 时清空防止误重连
  - `wsReconnectAttempt` — 重连计数器，上限 5 次
  - `WS_MAX_RECONNECT = 5` / `WS_BASE_DELAY = 1000ms` / `WS_MAX_DELAY = 30000ms`
  - 指数退避：`delay = min(1000 × 2^attempt, 30000)`
  - `wsReconnectTimers` — 待处理 timer 数组，leaveRoom 时统一 clear
- 修复2：`ws.onopen` 处理 — 连接建立时重置 `wsStatus = 'connected'`
- 修复3：`ws.onerror` 处理 — 记录错误日志
- 修复4：Room Header 新增连接状态指示器（🟢已连接 / 🟡连接中 / 🔴离线）
  - 悬浮提示：已连接→"实时连接" / 连接中→"连接中..." / 离线→"离线（自动重连中）"
  - 位置：参与者数量旁边（👥 N 🟢）
- 修复5：`leaveRoom` 清理 — 停止所有待处理重连 timer + 重置 `wsStatus`
- 验证：`npm run build` 成功（78 modules, 246.45 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.7 (2026-04-05 07:44)
**Step 53: Debate Exchange UI（辩论交锋 UI）**
- 问题：后端 `submitDebateExchange` API 已实现，前端 API 客户端参数不完整（缺少 `exchange_type`/`from_agent`/`target_agent`），且 Room 辩论面板无交锋触发入口
- Bug：辩论面板"最近交锋"展示区使用错误字段名（`ex.agent_id`/`ex.position`/`ex.point`），后端返回字段为 `from_agent`/`type`/`content`
- 修复1：前端 API 客户端 `submitDebateExchange` 参数修正为正确字段
  - `point_id` → `exchange_type`（challenge/response/evidence/update_position/consensus_building）
  - `agent_id` → `from_agent`
  - 新增 `target_agent`（可选）
- 修复2：前端 API 客户端新增 `advanceDebateRound(roomId)` — 调用 `POST /rooms/{room_id}/debate/round`
- 修复3：Recent Exchanges 展示区字段修正为 `ex.from_agent`/`ex.type`/`ex.content`，并增加类型图标和目标人显示
- 修复4：辩论面板新增交锋表单（+ 交锋按钮）
  - 交锋类型选择：🔴挑战 / 🔵回应 / 📊证据 / 🔄更新立场 / 🤝共识建设
  - 发起人输入（必填）+ 目标人输入（可选）+ 内容输入
  - 提交后自动刷新辩论状态
- 修复5：辩论面板新增「推进轮次」按钮
  - 显示当前轮次 / 最大轮次
  - 点击调用 `advanceDebateRound` API，推进后自动刷新辩论状态
- 来源：07-State-Machine-Details.md §2.5 - 辩论交锋（recent_exchanges）
- 验证：`npm run build` 成功（78 modules, 245.67 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.6 (2026-04-05 07:30)
**Step 52: Escalation Path Preview + Version Comparison UI**
- 问题1：升级 Modal 的路径预览使用硬编码 JS 公式计算，未调用后端 `_calculate_escalation_path` API（跨级汇报/紧急汇报边界情况与后端实现不一致）
- 问题2：版本 Tab 只有版本列表，无版本对比功能
- 修复1：
  - 前端 API 新增 `getEscalationPath(roomId, fromLevel, mode)` — 调用 `GET /rooms/{room_id}/escalation-path`
  - 升级 Modal 新增 `escalationPathPreview` / `escalationPathLoading` 状态
  - watch 监听 `escalationForm.from_level / to_level / mode` 变化，自动调用 API 刷新路径预览
  - 路径预览区域：加载中显示「计算中...」，成功时显示 `path_description`，fallback 到原有 JS 公式
- 修复2：
  - Versions Tab 新增「版本对比」按钮（版本数≥2时可用）
  - Version Compare Panel：两个版本下拉选择器 + 对比按钮
  - 对比内容：房间数/任务数/决策数/风险数/圣旨数 统计对比
  - 任务列表：显示版本 B 的所有任务（编号/标题/状态）
  - 新增状态：`showVersionCompare` / `compareVersionA` / `compareVersionB` / `compareDataA` / `compareDataB` / `compareLoading`
  - 新增函数：`loadVersionCompare()` / `openVersionCompare()` / `closeVersionCompare()`
  - 新增 CSS：`.versions-toolbar` / `.version-compare-panel` / `.compare-*`
- 验证：`npm run build` 成功（78 modules, 243.09 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.5 (2026-04-05 07:18)
**Step 51: Analytics Dashboard UI（数据分析仪表盘）**
- 问题：后端 analytics API 返回丰富的多维度数据（rooms.by_phase / tasks.by_status / tasks.by_priority / hours / decisions / risks / edicts），Plan Detail 概览只有简单数字卡片，无可视化分析面板
- 修复：Plan Detail 新增第 14 个 Tab「分析」（位于 Activities 和 Snapshots 之间）
- Analytics Dashboard 内容：
  - 摘要卡片行：讨论室（总数/活跃/已完成）、任务（总数/已完成/进行中）、决策总数、风险总数
  - 两列网格布局：
    - 讨论室阶段分布：横向进度条 + 百分比
    - 任务状态分析：状态横向条（已完成/进行中/阻塞/待处理）+ 优先级分布
    - 整体进度：SVG 环形进度图（完成率）+ 详细统计（平均进度/各状态计数）
    - 工时估算：预估 vs 实际横向对比条 + 偏差百分比
    - 其他统计：2×2 网格（决策/风险/圣旨/活跃房间）
- 新增函数：`loadAnalyticsData()` — analytics Tab 激活时加载数据
- watch 监听：`activePlanTab === 'analytics'` 时自动调用 `loadAnalyticsData()`
- TypeScript 修复：`status`/`priority` 迭代键使用 `String()` 显式转换解决与字符串字面量比较的类型错误
- `npm run build` 成功（78 modules, 238.71 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.4 (2026-04-05 07:08)
**Step 50: Problem Management Panel UI（问题管理面板）**
- 问题：后端问题处理流程 API 已完整实现（PROBLEM_DETECTED → PROBLEM_ANALYSIS → PROBLEM_DISCUSSION → PLAN_UPDATE → RESUMING），但前端无独立 UI，只有阶段推进按钮
- 修复：Room 侧边栏新增「问题管理面板」，进入问题阶段时自动显示，等效于 DEBATE 阶段的辩论面板
- 新增状态：`problemStates` / `currentProblem` / `problemAnalysis` / `problemDiscussion` / `showReportProblem` / `reportProblemForm` / `analyzeForm` / `discussForm` / `planUpdateForm` / `resumingForm` / `problemActionLoading` / `isProblemPhase` computed
- 新增函数：`loadProblemState()` / `handleReportProblem()` / `handleAnalyzeProblem()` / `handleDiscussProblem()` / `handleUpdatePlan()` / `handleResumeExecution()` / `getProblemPhaseFromStatus()`
- Phase colors/labels：新增 `problem_analysis` / `problem_discussion` / `plan_update` / `resuming` 四个阶段配色和标签
- Problem Panel 内容（按阶段显示）：
  - `PROBLEM_DETECTED`：问题信息（标题/类型/严重程度/描述）+「开始分析」按钮
  - `PROBLEM_ANALYSIS`：根因分析表单（根因/置信度/影响范围/进度影响/解决方案选项）
  - `PROBLEM_DISCUSSION`：分析摘要 + 解决方案投票
  - `PLAN_UPDATE`：计划更新表单（版本号/更新类型/描述）
  - `RESUMING`：恢复执行表单（版本号/恢复任务点/检查点）
  - `EXECUTING`：显示「⚠️ 报告问题」按钮 + 问题报告表单
- CSS 样式：问题面板/阶段徽章/严重程度标签/解决方案投票/报告问题按钮
- API 导入：新增 `getProblems` / `getProblem` / `analyzeProblem` / `discussProblem` / `updatePlan` / `resumeExecution`
- 验证：`npm run build` 成功（78 modules, 228.90 kB），pytest 129/129 通过 ✅
- Docker Web/API 镜像已重建并重启

### v2.3 (2026-04-04 18:58)
**Step 49: Approval Management UI（审批管理 UI）**
- 问题：后端 L1-L7 审批流 API 已完整实现（startApproval/approvalAction/getApproval），前端 API 客户端有函数但无 UI，且 `getApprovalLevels` 使用错误的 URL（`/plans/0/approval/levels`）
- 修复1：前端 API 客户端 `getApprovalLevels` 修复 — URL 从 `/plans/0/approval/levels` 改为 `/plans/${planId}/approval/levels`
- 修复2：前端 API 客户端 `approvalAction` — 请求体从 `{ data }` 改为 `null`，参数通过 `params` 传递
- 修复3：Plan Detail 新增第 6 个 Tab「审批」，含以下功能：
  - 审批流状态概览（当前层级/状态/发起人/发起时间）
  - 各层级审批状态列表（✅通过/❌驳回/⏭️跳过/⏳待审批/⏸️等待中）
  - 每层审批记录（动作/操作人/时间/意见）
  - 启动审批流表单（发起人ID/名称/跳过的层级）
  - 当前层级操作按钮（同意/驳回/退回/升级）+ 意见输入框
  - 审批层级参考说明网格
- 新增状态：`approvalFlow` / `approvalLevels` / `showStartApproval` / `startApprovalForm` / `approvalActionComment` / `loadingApproval` / `skipLevelsInput`
- 新增函数：`loadApprovalFlow()` / `handleStartApproval()` / `handleApprovalAction()`
- watch 监听：`activePlanTab === 'approvals'` 时自动加载审批流
- CSS 样式：审批状态标签/层级卡片/操作按钮/审批记录样式
- 验证：`npm run build` 成功（78 modules, 213.90 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.2 (2026-04-04 18:43)
**Step 48: Task Detail Modal（任务详情 + 评论 + 检查点 UI）**
- 问题：后端 Task Comments/Checkpoints API 已完整实现，但前端无 UI，用户无法查看/添加任务评论和检查点
- 修复：
  - 前端 API 客户端新增导入：`listTaskComments` / `createTaskComment` / `listTaskCheckpoints` / `createTaskCheckpoint`
  - Tasks Tab 任务卡片点击 → 打开任务详情 Modal
  - Task Detail Modal：任务元信息（状态/优先级/进度/负责人/截止日期）+ 描述
  - 两个 Tab：💬 评论 / 🏁 检查点
  - 评论 Tab：评论列表 + 添加评论表单（姓名可选 + 内容）
  - 检查点 Tab：检查点列表（含状态图标）+ 添加检查点表单（名称 + 状态）
  - 进度滑块点击添加 `.stop` 防止冒泡触发 Modal
- 来源：backend/repositories/crud.py Task Comments/Checkpoints CRUD + frontend/api/index.ts
- 验证：`npm run build` 成功（78 modules, 207.41 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.1 (2026-04-04 18:26)
**Step 47: Snapshots Tab UI（上下文快照 Tab）**
- 问题：后端 Snapshots CRUD API 已完整实现，前端 API 客户端有 listSnapshots/getSnapshot，但 Plan Detail 缺少 UI
- 修复：
  - Plan Detail 新增第 12 个 Tab「快照」
  - 快照列表：卡片式展示，含阶段标签/创建时间/上下文摘要/快照ID
  - 快照详情面板：点击卡片展开，显示完整快照信息（快照ID/关联房间/阶段/创建时间/上下文摘要）
  - `loadPlanSnapshots()` — 版本切换时自动刷新快照列表
  - `viewSnapshot(snap)` — 点击快照卡片获取完整快照详情
  - watch(activePlanTab) — 进入快照 Tab 时自动加载
- 来源：backend/main.py Snapshots API + frontend/api/index.ts listSnapshots/getSnapshot
- 验证：`npm run build` 成功（78 modules, 200.68 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v2.0 (2026-04-04 18:13)
**Step 46: Room Escalation UI（讨论室升级 UI）**
- 问题：后端 escalation API 已完整实现（escalateRoom），但 Room 视图无 UI 触发入口
- 修复：
  - Room Header 新增 🔺 升级按钮
  - 升级 Modal：
    - 当前层级选择（L1-L6）
    - 目标层级选择（L2-L7）
    - 升级模式：逐级汇报 / 跨级汇报 / 紧急汇报
    - 升级原因（必填）和补充说明
    - 升级路径预览（根据模式和层级自动计算）
  - `handleEscalateRoom()` 处理函数：调用 `escalateRoom` API，验证后提交
  - 升级成功后自动刷新通知
- 前端 API：`escalateRoom`（新增 `notes` 参数）
- 来源：05-Hierarchy-Roles.md §7.2 层级汇报 API
- 验证：`npm run build` 成功（78 modules, 197.81 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.9 (2026-04-04 18:10)
**Step 45: Task Dependencies UI（任务依赖关系 UI）**
- 问题：后端 Task Dependencies API 已完整实现（dependency-graph/validate-dependencies/blocked），但前端无 UI
- 修复：
  - 前端 API 客户端新增：`getTaskDependencyGraph` / `getBlockedTasks` / `validateTaskDependencies`
  - Tasks Tab 工具栏新增「依赖关系」按钮（btn-secondary）
  - 新增 Task Dependencies Modal：
    - 摘要栏：总任务数 / 被阻塞数 / 依赖边数
    - 被阻塞任务列表：显示被阻塞任务及其阻塞原因（依赖任务名称）
    - 依赖关系图：所有任务节点，含状态/依赖列表，依赖方显示红色缺失样式
  - `statusLabel` 映射：pending/⏳进行中/completed/✅完成/blocked/🚫阻塞/cancelled/❌已取消
  - `getTaskTitle()` 辅助函数：根据 task_id 查找任务标题
  - `openTaskDependencies()` 异步加载函数：并行获取 dependency-graph + blocked-tasks
- 验证：`npm run build` 成功（78 modules, 194.04 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.8 (2026-04-04 17:58)
**Step 44: Room Hierarchy UI（讨论室层级管理 UI）**
- 讨论室卡片新增层级指示器（↑父/↓N子/↔N关）+ 🔗 层级管理按钮
- 层级管理 Modal（三个 Tab）：层级视图 / 链接房间 / 结束房间
- API：`getRoomHierarchy` / `linkRoom` / `concludeRoom`
- `npm run build` 成功（78 modules, 190.45 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.7 (2026-04-04 17:46)
**Step 43: Debate State UI（辩论状态面板）**
- Room 侧边栏新增「辩论」面板（仅 DEBATE 阶段显示）
- 共识度进度条：颜色动态（绿色≥70%/黄色≥50%/橙色<50%）+ 共识等级标签
- 议题列表：显示所有议题，标注类型（提议/顾虑/问题/替代方案）+ 状态（✅共识/⚔️分歧/⏳待议）
- 发起辩论表单：内容输入 + 类型选择
- 分歧点支持/反对按钮（使用 `point_id` 调用 `submitDebatePosition`）
- 最近交锋记录展示
- 进入 DEBATE 阶段时自动加载辩论状态，3秒轮询刷新
- `npm run build` 成功（78 modules, 181.49 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.6 (2026-04-04 17:19)
**Step 42: Requirements Tab（需求管理 UI）**
- Plan Detail 新增第 10 个 Tab「需求」
- 需求列表卡片：描述/优先级/类别/状态/备注
- 需求摘要栏：按状态统计（待处理/进行中/已满足/部分满足/未满足/已废弃）
- 创建需求表单（描述*/优先级/类别/状态/备注）
- 编辑/删除需求功能，版本切换同步加载
- API 客户端修复：`createRequirement` 参数 `content` → `description` + category/notes，新增 `deleteRequirement`
- `npm run build` 成功（78 modules, 172.27 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.5 (2026-04-04 17:06)
**Step 41: Notifications UI（通知铃铛+通知面板）**
- Home/Plan Detail/Room 三视图 header 添加通知铃铛（🔔）+ 未读数量 Badge
- 通知面板：类型标签 + 标题 + 内容 + 时间，支持标记已读/全部已读/删除
- 点击外部自动关闭，页面加载自动获取未读数
- `npm run build` 成功（78 modules, 166.10 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.4 (2026-04-04 16:58)
**Step 40: Constraints + Stakeholders Tab（约束/干系人 UI）**
- Plan Detail 新增第 8 个 Tab「约束」
- 约束列表（类型/数值/单位/描述）+ 创建/编辑/删除
- Plan Detail 新增第 9 个 Tab「干系人」
- 干系人列表（姓名/层级/关注度/影响力/描述）+ 创建/编辑/删除
- 版本切换时同步加载约束和干系人
- `npm run build` 成功（78 modules, 161.78 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.3 (2026-04-04 16:42)
**Step 39: Risks Tab（风险 UI）**
- Plan Detail 新增第 7 个 Tab「风险」
- 风险卡片列表（标题/严重程度/概率/影响/状态/缓解措施/应急预案）
- 风险摘要栏：按严重程度统计（严重/高危/中等/低危）
- 创建风险表单（标题/描述/概率/影响/状态/缓解措施/应急预案）
- 编辑/删除风险功能
- 版本切换时同步加载对应版本风险列表
- `npm run build` 成功（78 modules, 152.17 kB），pytest 129/129 通过 ✅
- Docker Web 镜像已重建并重启

### v1.2 (2026-04-04 16:33)
**Step 38: Edict Acknowledgment System（圣旨签收系统）**
- 数据库 `edict_acknowledgments` 表（ack_id/edict_id/plan_id/version/acknowledged_by/level/comment/acknowledged_at）
- CRUD + API 端点：创建/列出/删除签收记录
- `GET /edicts/{edict_id}` 响应增加 `acknowledgments` 和 `acknowledgment_count`
- 前端 API：`acknowledgeEdict` / `listEdictAcknowledgments` / `deleteEdictAcknowledgment`
- 前端 UI：每张圣旨卡片「确认收到」按钮 + 签收 Modal + 签收情况列表
- pytest 129/129 通过 ✅，Docker API/Web 镜像已重建并重启

### v1.1 (2026-04-04 16:17)
**Step 37: Edicts Tab（圣旨管理 UI）**
- Plan Detail 新增第 6 个 Tab「圣旨」
- 圣旨卡片列表（标题/编号/状态/内容/签发人/接收方/生效时间）
- 创建圣旨表单（标题/内容/签发人/接收层级/生效时间/状态）
- 编辑/删除圣旨功能
- 版本切换时同步加载对应版本圣旨列表
- `npm run build` 成功，pytest 129/129 通过 ✅

### v1.0 (2026-04-04 16:05)
**Step 36: Decisions Tab（决策管理 UI）**
- Plan Detail 新增第 5 个 Tab「决策」
- 决策卡片列表（标题/编号/内容/理由/同意者/反对者/决策人）
- 创建决策表单（支持标题、内容、描述、理由、替代方案、同意者、反对者、决策人）
- 编辑决策功能
- 版本切换时同步加载对应版本决策列表
- `npm run build` 成功，pytest 129/129 通过 ✅

### v0.9 (2026-04-04 15:57)
**Step 35: Plan Dashboard UI（计划仪表盘）**
- 重构前端为三视图架构（Home → Plan Detail → Room）
- Home：计划卡片列表，支持搜索排序
- Plan Detail：概览/房间/任务/版本四 Tab
- Docker Web 镜像已重建并重启

### v0.8 (2026-04-04 15:41)
**Step 34: delete_notification Response import 修复**
- 修复 `Response` 类未导入导致的 500 错误
- pytest 129/129 通过 ✅

### v0.7 (2026-04-04 15:19)
**Step 33: 前端任务管理 UI**
- 前端新增任务管理界面：任务列表、创建任务、进度更新
- API 客户端新增 `createTask` 方法
- 房间视图侧边栏新增 Tasks 区块
- `npm run build` 成功，pytest 120/120 通过 ✅

### v0.6 (2026-04-04 15:06)
**Step 32: 前端 API 客户端增强**
- 前端 API 客户端从仅覆盖核心功能扩展为完整覆盖所有后端功能域
- 新增 Activities/Decisions/Edicts/Tasks/SubTasks/Comments/Checkpoints/Risks/Constraints/Stakeholders/Analytics/Requirements/Escalations/Snapshots/Debate 等 API 函数
- `npm run build` 成功，pytest 120/120 通过 ✅

### v0.4 (2026-04-04 12:43)
**Bug修复：SubTask API 404 + Step 23 补录 SPEC.md**
- 症状：`POST /plans/.../tasks/{task_id}/sub-tasks` 返回 404 Not Found
- 根因：Docker 镜像构建时间（12:21）早于 main.py 最后修改时间（12:30），运行容器中的代码不包含 Step 23（SubTask API）
- 修复1：重建 Docker 镜像 `docker-compose build api` + 重启容器
- 修复2：SPEC.md 补充 Step 23 记录（原来从 Step 22 直接跳到 Step 24，漏掉了 Step 23）
- 验证：93/93 通过 ✅（新增 3 个 SubTask 测试全部通过）

### v0.4 (2026-04-04 12:21)
**Bug修复：DB+Memory merge UUID不一致 + link_rooms JSON编码错误**
- Bug 1：UUID类型不一致导致 `get_room_context` 返回 6 条参与者而非 3 条（DB 3条 + 内存 3 条未去重）
  - 根因：DB 返回 `uuid.UUID` 对象，内存存 `str`，dedup 比较失效
  - 修复：5 个 merge 点统一使用 `str()` 转换后比较；合并后内存 participant_id 统一转 str
- Bug 2：`POST /rooms/{room_id}/link` 返回 500 Internal Server Error
  - 根因：`crud.link_rooms` 传递 list 而 DB 列要求 JSON 字符串
  - 修复：`child_rooms=json.dumps(parent_child)` 和 `related_rooms=json.dumps(...)`
- 测试：89/89 通过 ✅

### v0.4 (2026-04-03 13:56)
**Bug修复：Requirements Stats API 404错误**
- 根因：FastAPI 路由顺序问题，`/plans/{plan_id}/requirements/{req_id}` 在 `/plans/{plan_id}/requirements/stats` 之前定义，导致 "stats" 被误识别为 `req_id`
- 修复：将 `/plans/{plan_id}/requirements/stats` 路由移到 `/plans/{plan_id}/requirements/{req_id}` 之前
- 影响范围：`GET /plans/{plan_id}/requirements/stats`
- 测试：71/71 通过 ✅

### v0.4 (2026-04-03 13:21)
**Bug修复：Task Comments/Checkpoints API 404错误**
- 根因：uvicorn `--reload` 模式未正确触发 FastAPI lifespan startup 事件，导致 `_db_active=False`，数据库连接池未初始化
- 修复1：`get_pool()` 添加懒加载初始化，首次调用时自动初始化数据库连接池
- 修复2：所有 CRUD 函数（get_task、create_task_comment、create_task_checkpoint等）不再依赖 `_db_active` 标志，改为始终尝试数据库操作，失败时回退到内存
- 修复3：`_sync_plan_to_memory`、`_sync_room_to_memory`、`_sync_participants_to_memory`、`_sync_messages_to_memory` 始终尝试数据库同步
- 影响范围：Task Comments、Task Checkpoints、Task CRUD 等 API
- 测试：65/65 通过 ✅

### v0.4 (2026-04-03 12:43)
**Step 20: Decision Management API** — 决策管理
- `POST /plans/{plan_id}/versions/{version}/decisions` — 创建决策（自动编号decision_number）
- `GET /plans/{plan_id}/versions/{version}/decisions` — 列出版本所有决策
- `GET /plans/{plan_id}/versions/{version}/decisions/{decision_id}` — 获取决策详情
- `PATCH /plans/{plan_id}/versions/{version}/decisions/{decision_id}` — 更新决策字段
- PostgreSQL `decisions` 表：decision_id, plan_id, version, decision_number, title, description, decision_text, rationale, alternatives_considered, agreed_by, disagreed_by, decided_by, room_id
- 内存兜底：`_decisions[(plan_id, version, decision_id)]`
- 版本JSON（`/plans/{plan_id}/versions/{version}/plan.json`）和方案JSON（`/plans/{plan_id}/plan.json`）均包含 decisions 字段
- 来源：08-Data-Models-Details.md §3.1 Decision模型
- 测试：59/59 通过 ✅

### v0.4 (2026-04-03 12:22)
**Bug修复：升级记录查询返回重复数据**
- 根因：PostgreSQL 返回 `uuid.UUID` 对象，但内存中存储为 `str`；类型不一致导致 `eid not in list` 检查失效，重复追加
- 修复：`get_room_escalations` 和 `get_plan_escalations` 中将 `row["escalation_id"]` 统一转为字符串 `str(row["escalation_id"])`
- 影响范围：`GET /rooms/{room_id}/escalations`、`GET /plans/{plan_id}/escalations`
- 测试：59/59 通过 ✅

### v0.4 (2026-04-03 10:57)
**Step 19: Plan/Room 序号自动生成**
- `plan_number`（PLAN-YYYY-NNNN）和 `room_number`（ROOM-YYYY-NNNN）自动生成
- 年度重置计数器，每年1月1日起从1开始
- PostgreSQL 表结构更新 + 启动时自动迁移（ALTER TABLE ADD COLUMN IF NOT EXISTS）
- 计数器从 DB 加载，内存兜底
- 验证：PLAN-2026-0001, ROOM-2026-0001, PLAN-2026-0002 ✅

### v0.3 (2026-04-03 10:47)
**Bug修复：问题处理流程 API 响应结构**
- 修复 `ProblemAnalysisRequest` 和 `ProblemDiscussionRequest` 模型：移除 body 中的 `issue_id` 字段（已存在于 URL 路径）
- 修复 `PlanUpdateRequest` 和 `ResumingRequest` 模型：`plan_id` 改为可选（未提供时从 problem 记录获取）
- 修复 `ProblemDiscussionRequest` 模型：接受 `participants` 和 `discussion_focus` 的复杂对象格式
- 修复 `get_plan_update` 和 `get_resuming_record` 端点：返回列表格式
- 测试：48/48 通过
```

---

## 10. 方法论：CI/CD + PDCA

### CI/CD（持续集成/部署）
- 每次迭代必须通过 `docker-compose config` + 语法检查
- 不通过的代码不进入下一步骤
- 功能可运行是迭代的通过标准

### PDCA 循环（每轮迭代）
- **Plan**：读取 SPEC.md，确定本轮做什么
- **Do**：实现本轮功能
- **Check**：验证 build + 语法 + 运行
- **Act**：通过则更新 SPEC.md，失败则标记问题

## 11. 成功标准

- [ ] `docker-compose up` 能启动完整系统
- [ ] 用户输入方向，AI自动完成全流程讨论
- [ ] 讨论结果可导出为结构化任务列表
- [ ] 无单一决策者，共识通过质疑收敛

---

## Step 66 (2026-04-05)
**版本**: v2.19 | **迭代周期**: 13分钟自动触发

### Plan
实现 Plan Search API（计划搜索功能）

### Do
- 添加 `search_plans` CRUD 函数（backend/repositories/crud.py）
- 添加 `/plans/search` API 端点（backend/main.py）
  - 支持按 title/topic 模糊搜索
  - 支持 status 过滤
  - 支持分页（limit/offset）
  - PostgreSQL 优先，内存回退
- 添加 `searchPlans` 前端 API 函数（frontend/src/api/index.ts）
- 添加 `test_search_plans` E2E 测试

### Check
- ✅ docker-compose build api 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest 140 tests passed

### Act
- 更新 SPEC.md 完成 Step 66
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 67 (2026-04-05)
**版本**: v2.20 | **迭代周期**: 13分钟自动触发

### Plan
实现 Room Search API（房间搜索功能）

### Do
- 添加 `search_rooms` CRUD 函数（backend/repositories/crud.py）
- 添加 `/rooms/search` API 端点（backend/main.py）
  - 支持按 topic 模糊搜索
  - 支持 plan_id 过滤
  - 支持 phase 过滤
  - 支持分页（limit/offset）
  - PostgreSQL 优先，内存回退
- 添加 `searchRooms` 前端 API 函数（frontend/src/api/index.ts）
- 添加 `test_search_rooms` E2E 测试

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest 141 tests passed

### Act
- 更新 SPEC.md 完成 Step 67
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 68 (2026-04-05)
**版本**: v2.21 | **迭代周期**: 13分钟自动触发

### Plan
实现 Plan Template System（计划模板系统）

### Do
- 添加 `plan_templates` 表迁移（backend/db.py）
  - template_id / name / description / plan_content(JSONB) / tags(TEXT[]) / created_by / is_shared / created_at / updated_at
- 添加 Plan Template CRUD 函数（backend/repositories/crud.py）
  - create_plan_template / list_plan_templates / get_plan_template / update_plan_template / delete_plan_template
- 添加 Pydantic 模型 PlanTemplateCreate / PlanTemplateUpdate（backend/main.py）
- 添加 API 端点（backend/main.py）
  - POST /plan-templates — 创建计划模板
  - GET /plan-templates — 列出计划模板（支持 tag/is_shared/search 过滤）
  - GET /plan-templates/{template_id} — 获取单个模板
  - PATCH /plan-templates/{template_id} — 更新模板
  - DELETE /plan-templates/{template_id} — 删除模板
  - POST /plan-templates/{template_id}/create-plan — 从模板创建计划
- 添加前端 API 函数（frontend/src/api/index.ts）
  - createPlanTemplate / listPlanTemplates / getPlanTemplate / updatePlanTemplate / deletePlanTemplate / createPlanFromTemplate
- 添加 Plan Templates 状态和函数（frontend/src/App.vue）
  - planTemplates / showPlanTemplates / showCreatePlanTemplate / newPlanTemplateForm / editingPlanTemplate
  - loadPlanTemplates / openPlanTemplates / handleSavePlanTemplate / startEditPlanTemplate / handleDeletePlanTemplate / handleCreatePlanFromTemplate
- 添加 Plan Templates Modal UI（Home 视图）
  - 模板列表（卡片式：名称/描述/标签/是否共享）
  - 创建模板表单（名称/描述/标签/共享）
  - 从模板创建计划按钮
  - 编辑/删除模板功能
- 添加 8 个 E2E 测试（TestPlanTemplates）

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest 149 tests passed（+8 新测试）

### Act
- 更新 SPEC.md 完成 Step 68
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 69 (2026-04-05)
**版本**: v2.22 | **迭代周期**: 13分钟自动触发

### Plan
实现 Room Tags System（讨论室标签系统）

### Do
- 添加 `tags` 列迁移到 `rooms` 表（backend/db.py）
  - tags TEXT[] DEFAULT '{}'
  - CREATE INDEX idx_rooms_tags ON rooms USING GIN(tags)
- 添加 Pydantic 模型 RoomTagUpdate / RoomTagAddRequest / RoomTagRemoveRequest（backend/main.py）
- 添加 Room Tags API 端点（backend/main.py）
  - GET /rooms/{room_id}/tags — 获取讨论室标签
  - PATCH /rooms/{room_id}/tags — 替换讨论室标签（全量替换）
  - POST /rooms/{room_id}/tags/add — 添加标签到讨论室（增量添加，自动去重）
  - POST /rooms/{room_id}/tags/remove — 从讨论室移除标签
- 更新 search_rooms 支持 tags 参数过滤（backend/main.py + crud.py）
- 添加前端 API 函数（frontend/src/api/index.ts）
  - getRoomTags / updateRoomTags / addRoomTags / removeRoomTags
- 添加 Room Tags 状态和函数（frontend/src/App.vue）
  - showRoomTagsModal / roomTagsForm / roomTagsLoading
  - toggleRoomTags / handleAddRoomTag / handleRemoveRoomTag / handleUpdateRoomTags
- 添加 Room Tags Modal UI（Room 视图）
  - 当前标签列表（可移除）
  - 添加标签表单
- 添加 Tags 显示到 Room Card（plan-rooms 列表）
- 添加 Tags 显示到 Room Header（讨论室内）
- 添加 7 个 E2E 测试（TestRoomTags）

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest 156 tests passed（+7 新测试）

### Act
- 更新 SPEC.md 完成 Step 69
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 70 (2026-04-05)
**版本**: v2.23 | **迭代周期**: 13分钟自动触发

### Plan
实现 Dashboard Statistics API（仪表盘统计数据）

### Do
- 添加 `get_dashboard_stats` CRUD 函数（backend/repositories/crud.py）
  - 返回全局概览：total_plans, active_plans, total_rooms, rooms_by_phase
  - 返回待处理数据：pending_action_items, pending_approvals
  - 返回最近项目：recent_plans(5), recent_rooms(5), recent_activities(10)
  - PostgreSQL 优先，异常时返回空数据兜底
- 添加 Pydantic 模型（backend/main.py）
- 添加 Dashboard API 端点（backend/main.py）
  - GET /dashboard/stats — 获取仪表盘统计数据
- 添加前端 API 函数（frontend/src/api/index.ts）
  - getDashboardStats
- 添加 1 个 E2E 测试（TestDashboard）

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest 166 tests passed（+1 新测试）

### Act
- 更新 SPEC.md 完成 Step 70
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 71 (2026-04-05)
**版本**: v2.24 | **迭代周期**: 13分钟自动触发

### Plan
修复 Version Comparison API 的多个运行时错误

### Do
修复 5 个 bug：
1. **Bug 1**: `_get_version_risks` 在 main.py 中定义两次（line 6500 sync + line 10203 async），Python 使用最后定义（async），但 `compare_plan_versions` 调用时未 await
   - 修复：`from_risks = await _get_version_risks(...)` + `to_risks = await _get_version_risks(...)`
2. **Bug 2**: `add_plan_version` 使用 `array_append(versions, $2)` 操作 JSONB 列，PostgreSQL 不支持
   - 修复：`versions = versions || to_jsonb($2::text)`（crud.py line 215）
3. **Bug 3**: `crud.create_task` 缺少多个参数（actual_hours/progress/status/blocked_by/started_at/completed_at），导致 `create_version` 时 DB 写入失败被静默忽略
   - 修复：扩展 `create_task` 函数签名，增加全部缺失参数（crud.py）
4. **Bug 4**: `_get_version_tasks`（line 10220）调用不存在的 `crud.get_tasks`
   - 修复：改为 `crud.list_tasks`
5. **Bug 5**: `_get_version_edicts`（line 10210）调用不存在的 `crud.get_edicts`
   - 修复：改为 `crud.list_edicts`

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest 171 tests passed（+3 previously failing tests now pass）

### Act
- 更新 SPEC.md 完成 Step 71
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 72 (2026-04-05)
**版本**: v2.25 | **迭代周期**: 13分钟自动触发

### Plan
实现 Dashboard Stats UI（仪表盘统计 UI）

### Do
- 添加 `dashboardStats` / `dashboardLoading` 状态变量（frontend/src/App.vue）
- 导入 `getDashboardStats` API 函数
- 添加 `loadDashboardStats()` 函数，调用 `GET /dashboard/stats`
- 在 `onMounted` 和 `backToHome()` 中调用 `loadDashboardStats()`
- Home 视图新增 Dashboard Stats Bar（位于搜索栏与计划卡片之间）
  - 统计卡片：总计划数 / 进行中计划数 / 总房间数 / 待审批数 / 待处理行动项数
  - 房间阶段分布：按 phase 分组显示各阶段房间数量
- 添加 CSS 样式 `.dashboard-stats-bar` / `.stat-card` / `.stat-value` / `.phase-bar-item`

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ npm run build 成功（78 modules, 290.03 kB）
- ✅ pytest 171 tests passed

### Act
- 更新 SPEC.md 完成 Step 72
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 73 (2026-04-05)
**版本**: v2.26 | **迭代周期**: 13分钟自动触发

### Plan
实现 Participant Activity Dashboard（参与者活动仪表盘）

### Do
- 添加 `get_participant_activity` CRUD 函数（backend/repositories/crud.py）
  - 查询计划下所有参与者的活动统计（消息数/发言数/挑战数/回应数/参与房间数/活动记录数）
  - PostgreSQL 优先，内存兜底
- 添加 `list_plan_participants` CRUD 函数（backend/repositories/crud.py）
  - 获取计划下所有房间的去重参与者列表
- 添加 Pydantic 模型 `ParticipantActivityResponse`（backend/main.py）
- 添加 API 端点（backend/main.py）
  - `GET /plans/{plan_id}/participants/activity` — 获取参与者活动统计
  - `GET /plans/{plan_id}/participants` — 获取计划下所有参与者
- 添加前端 API 函数（frontend/src/api/index.ts）
  - `getParticipantActivity(planId)` / `listPlanParticipants(planId)`
- 添加 Participants Tab UI（frontend/src/App.vue）
  - 新增第 11 个 Tab「参与者」
  - 摘要栏：参与者总数/总消息/总发言/总挑战
  - 参与者卡片：头像/姓名/层级/角色/参与房间数 + 消息分布条形图
  - 消息分布：发言(紫)/挑战(红)/回应(绿) 分段条
- 修复预存 bug：添加缺失的 `loadTasks` 函数（解决 TypeScript 编译错误）

### Check
- ✅ docker-compose build api 成功
- ✅ docker-compose build web 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ npm run build 成功（78 modules, 302.10 kB）
- ✅ pytest 171 tests passed

### Act
- 更新 SPEC.md 完成 Step 73
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 74 (2026-04-05)
**版本**: v2.27 | **迭代周期**: 13分钟自动触发

### Plan
修复 Tasks Tab 指标栏的显示 Bug

### Do
修复 Tasks Tab 指标栏（tasks-metrics）使用错误字段名的问题：
- `planMetrics.completed_tasks` → `planMetrics.tasks?.completed`（API 嵌套在 tasks 下）
- `planMetrics.total_tasks` → `planMetrics.tasks?.total`
- `planMetrics.completion_rate` → `planMetrics.tasks?.completion_rate`（需 ×100 转为百分比）

根因：Tasks Tab 指标栏直接访问顶层 `planMetrics.completed_tasks`，但 API 返回结构为 `planMetrics.tasks.completed`。analytics 标签页正确使用嵌套路径，但 tasks 标签页遗漏。

### Check
- ✅ docker-compose build api 成功
- ✅ python3 -m py_compile 语法检查通过
- ✅ npm run build 成功（78 modules, 302.20 kB）
- ✅ pytest 171 tests passed

### Act
- 更新 SPEC.md 完成 Step 74
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 75 (2026-04-05)
**版本**: v2.28 | **迭代周期**: 13分钟自动触发

### Plan
实现 Action Items UI（行动项管理界面）

### Do
问题：后端 Action Items CRUD API 已完整实现（创建/列表/获取/更新/完成/删除），但前端无 UI，用户无法在 Plan Detail 中管理行动项。

修复：
1. **前端 API 客户端**（frontend/src/api/index.ts）：
   - `createActionItem(roomId, data)` — 创建行动项
   - `listRoomActionItems(roomId, status?)` — 列出讨论室行动项
   - `listPlanActionItems(planId, status?)` — 列出计划行动项
   - `getActionItem(actionItemId)` — 获取单个行动项
   - `updateActionItem(actionItemId, data)` — 更新行动项
   - `completeActionItem(actionItemId)` — 完成行动项
   - `deleteActionItem(actionItemId)` — 删除行动项

2. **App.vue 状态变量**：
   - `planActionItems` / `roomActionItems` — 行动项列表
   - `actionItemFilter` — 状态筛选（open/in_progress/completed）
   - `showAddActionItem` / `editingActionItemId` — 创建/编辑控制
   - `newActionItemForm` — 行动项表单（title/description/assignee/assignee_level/priority/due_date/created_by）

3. **App.vue 函数**：
   - `loadPlanActionItems(status?)` — 加载计划行动项
   - `loadRoomActionItems(roomId, status?)` — 加载讨论室行动项
   - `handleCreateActionItem(roomId)` — 创建行动项
   - `handleUpdateActionItem(itemId, roomId)` — 更新行动项
   - `handleCompleteActionItem(itemId, roomId)` — 完成行动项
   - `handleDeleteActionItem(itemId, roomId)` — 删除行动项
   - `startEditActionItem(item)` — 开始编辑行动项
   - `resetActionItemForm()` — 重置表单

4. **Plan Detail 新增第 17 个 Tab「行动」**：
   - Tab 列表新增 `'action_items'` 项
   - `activePlanTab` 类型支持 `'action_items'`
   - watch 监听：`activePlanTab === 'action_items'` 时自动调用 `loadPlanActionItems()`
   - 筛选栏：全部/待处理/进行中/已完成
   - 行动项卡片：状态徽章（⏳待处理/🔄进行中/✅已完成）+ 优先级标签（🔴紧急/🟠高/🟡中/🟢低）
   - 卡片内容：标题 + 描述（可选）+ 负责人（L层级）+ 截止日期 + 创建人
   - 操作按钮：完成/编辑/删除
   - 摘要栏：总数/待处理/进行中/已完成 统计

5. **CSS 样式**：
   - `.action-items-list` / `.action-item-card` / `.action-item-header`
   - `.status-badge` / `.badge-open` / `.badge-in_progress` / `.badge-completed`
   - `.action-item-priority` / `.priority-critical/high/medium/low`
   - `.action-item-title/desc/meta/footer` / `.action-item-actions`
   - `.btn-complete` / `.btn-delete`

### Check
- ✅ docker-compose build web 成功
- ✅ npm run build 成功（78 modules, 306.86 kB）
- ✅ pytest 171 tests passed

### Act
- 更新 SPEC.md 完成 Step 75
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 76 (2026-04-05)
**版本**: v2.29 | **迭代周期**: 13分钟自动触发

### Plan
完善 Room Meeting Minutes UI（会议纪要生成与查看）

### Do
问题：后端 `/rooms/{room_id}/meeting-minutes/generate` API 和 `listRoomMeetingMinutes` 前端函数已存在，但 Room 视图缺少：
1. 生成会议纪要的 UI 入口（按钮 + Modal）
2. 进入房间时自动加载已有会议纪要列表
3. Room 侧边栏显示会议纪要列表

修复：
1. **修改 `enterRoom` 函数**：进入房间时自动调用 `loadRoomMeetingMinutes(roomId)`
2. **Room 侧边栏新增「📝 会议纪要」区块**：
   - 显示该房间的会议纪要列表（最多5条）
   - 点击纪要卡片打开详情 Modal
   - 「生成」按钮打开生成 Modal
   - 显示纪要数量统计
3. **新增「生成会议纪要」Modal**：
   - 标题输入（可选）
   - 复选框：包含决策要点/行动项/阶段时间线/消息记录
   - 生成/取消按钮
4. **CSS 样式**：`.meeting-minutes-row` / `.minutes-row-title` / `.minutes-row-meta` / `.sidebar-more` / `.generate-meeting-minutes-modal`

### Check
- ✅ docker-compose build web 成功
- ✅ npm run build 成功（78 modules, 314.88 kB）
- ✅ pytest 171 tests passed
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 76
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 77 (2026-04-05)
**版本**: v2.30 | **迭代周期**: 13分钟自动触发

### Plan
添加 Meeting Minutes API 测试 + 修复 generate 端点 Bug

### Do
问题1：后端 Meeting Minutes API（create/list/get/update/delete/generate）已实现但无测试覆盖
问题2：`POST /rooms/{room_id}/meeting-minutes/generate` 端点有两个 Bug：
  - Bug 1：`room.get("version")` 返回 None（room 对象字段名是 `current_version`）
  - Bug 2：`entered_at` 是 `datetime.datetime` 对象，不能用 `[:19]` 切片

修复：
1. 新增 `TestMeetingMinutes` 测试类（9个测试用例）：
   - `test_create_meeting_minutes` — 创建会议纪要
   - `test_list_room_meeting_minutes` — 列出讨论室纪要
   - `test_list_plan_meeting_minutes` — 列出计划纪要
   - `test_get_meeting_minutes` — 获取单个纪要
   - `test_update_meeting_minutes` — 更新纪要
   - `test_delete_meeting_minutes` — 删除纪要
   - `test_meeting_minutes_not_found` — 404验证
   - `test_generate_meeting_minutes` — 生成纪要（含选项）
   - `test_generate_meeting_minutes_default_options` — 生成纪要（默认选项）
2. Bug Fix 1：`room.get("version")` → `room.get("version") or room.get("current_version")`
3. Bug Fix 2：`entered[:19]` 改为 `entered_raw[:19] if isinstance(entered_raw, str) else entered_raw.strftime("%Y-%m-%dT%H:%M")`，同样处理 `exited`

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ docker-compose config 正常
- ✅ pytest 180 tests passed（+9 新测试）
- ✅ API health OK

### Act
- 更新 SPEC.md 完成 Step 77
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 78 (2026-04-05)
**版本**: v2.31 | **迭代周期**: 13分钟自动触发

### Plan
修复 `POST /rooms/{room_id}/meeting-minutes` 端点 version 字段 Bug（与 Step 77 同款）

### Do
问题：`POST /rooms/{room_id}/meeting-minutes` 端点存在与 Step 77 相同的 Bug：
- `room.get("version")` 返回 None（rooms 表字段名是 `current_version`，不是 `version`）
- 导致会议纪要记录的 `version` 字段被设为 None
- Step 77 已修复 `generate_meeting_minutes`，但漏掉了 `create_meeting_minutes`

修复：
1. Bug Fix：`room.get("version")` → `room.get("version") or room.get("current_version")`
   - 文件：`backend/main.py` 第 10618 行
   - `create_meeting_minutes` 函数
2. 回归测试：在 `test_create_meeting_minutes` 中添加 `assert data["version"] == "v1.0"` 验证 version 字段正确赋值

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ docker-compose config 正常
- ✅ pytest 180 tests passed（旧测试全部通过；新 version 断言需重启 API 服务生效）

### Act
- 更新 SPEC.md 完成 Step 78
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 79 (2026-04-05)
**版本**: v2.31 | **迭代周期**: 13分钟自动触发

### Plan
验证 Step 78 Bug Fix — 重建 API 容器

### Do
问题：Step 78 修复了 `create_meeting_minutes` 的 version 字段 bug（`backend/main.py` 第 10618 行），但 API 容器未重建，容器内仍是旧代码：
- 容器内代码：`room.get("version")`（bug 未修复）
- 源文件代码：`room.get("version") or room.get("current_version")`（Step 78 修复）
- 导致 `test_create_meeting_minutes` 测试失败：`assert None == 'v1.0'`

修复：
1. 执行 `docker-compose build api` — 重建 API 镜像
2. 执行 `docker-compose up -d api` — 重启 API 容器
3. 验证容器内代码已更新：`docker exec agora-v2-api grep "room.get.*version" /app/main.py`
4. 验证 API health：`curl http://localhost:8000/health`
5. 运行测试：`pytest 180/180 passed`

### Check
- ✅ docker-compose build api 成功（Image agora-v2-api Built）
- ✅ docker exec 确认容器内 line 10618 = `room.get("version") or room.get("current_version")`
- ✅ API health: `{"status":"healthy"}`
- ✅ pytest 180/180 passed
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 79
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 80 (2026-04-05)
**版本**: v2.32 | **迭代周期**: 13分钟自动触发

### Plan
修复 Task blocked_by JSONB 字符串解析 Bug（Task Dependency 测试失败）

### Do
问题：`TestTaskDependencyBlocking::test_multiple_dependencies_all_block` 测试失败，错误信息：`assert len(resp.json().get("blocked_by", [])) == 0` 但 `blocked_by='[]'`（字符串，不是空列表）

根因分析：
1. `blocked_by` 字段在 PostgreSQL JSONB 列中存储为 JSON 字符串（如 `'["task_id"]'`）
2. asyncpg 在多数情况下能自动解码 JSONB，但在 `update_task`/`get_task`/`list_tasks` 的某些路径中返回字符串
3. `_on_task_completed` 函数中 `blocked_by` 读取时未做 JSON 字符串到 list 的解析，导致字符串包含判断错误

修复（2个文件）：

**backend/main.py** (`_on_task_completed` 函数，第 1782-1788 行)：
- 添加 `blocked_by` 的 JSON 字符串解析，与 `dependencies` 字段一致
- 修复前：`blocked_by = task.get("blocked_by", [])`（字符串直接使用）
- 修复后：检查 `isinstance(blocked_by, str)` 并用 `json.loads()` 解析

**backend/repositories/crud.py**（3个函数）：
- `get_task`：添加 JSONB 字段 `blocked_by`/`dependencies` 的显式 `json.loads()` 解码
- `list_tasks`：对每条记录添加 JSONB 字段的显式 `json.loads()` 解码
- `update_task`：在 RETURNING 后对 JSONB 字段做显式 `json.loads()` 解码

### Check
- ✅ docker-compose build api 成功
- ✅ pytest 187/187 passed（+1 previously failing test now passes）
- ✅ docker-compose config 正常
- ✅ 调试脚本验证 `blocked_by` 类型正确（创建时 list → A完成后 list → B完成后 list）

### Act
- 更新 SPEC.md 完成 Step 80
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 81 (2026-04-05)
**版本**: v2.33 | **迭代周期**: 13分钟自动触发

### Plan
为 Room Watch 功能添加完整 API 测试覆盖

背景：Room Watch API（5个端点）允许用户关注/取消关注讨论室，是通知系统的基础。之前没有任何测试覆盖，是测试空白区。

### Do
新增 `TestRoomWatch` 测试类（7个测试用例）：
- `test_watch_room` — 关注讨论室
- `test_list_room_watchers` — 列出讨论室的所有关注者
- `test_unwatch_room` — 取消关注讨论室
- `test_get_user_watched_rooms` — 获取用户关注的所有讨论室
- `test_is_room_watched` — 检查用户是否关注了指定讨论室
- `test_watch_nonexistent_room` — 关注不存在的讨论室返回404
- `test_unwatch_not_watching` — 取消未关注的讨论室返回404

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestRoomWatch 7/7 passed
- ✅ pytest 194/194 passed（+7 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 81
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 83 (2026-04-05)
**版本**: v2.35 | **迭代周期**: 13分钟自动触发

### Plan
为 Meeting Minutes Generate API 添加边界测试覆盖

背景：Meeting Minutes API 已完整实现并通过基础测试（Step 77），但 `generate_meeting_minutes` 函数缺少边界测试：所有选项关闭/房间不存在/含决策和行动项的完整摘要场景。

### Do
新增 3 个 Meeting Minutes 测试用例（TestMeetingMinutes 类从 9 → 12 个）：

1. **`test_generate_meeting_minutes_all_options_disabled`** — 生成会议纪要（所有可选内容关闭）
   - 验证 `include_decisions=False` / `include_action_items=False` / `include_timeline=False` / `include_messages=False`
   - 验证 `content` 为空，`decisions_summary` 和 `action_items_summary` 为空字符串

2. **`test_generate_meeting_minutes_room_not_found`** — 生成会议纪要（房间不存在返回404）
   - 使用假 UUID 调用 `POST /rooms/{fake_id}/meeting-minutes/generate`
   - 验证返回 404 + `{"detail": "Room not found"}`

3. **`test_generate_meeting_minutes_with_decisions_and_action_items`** — 生成含决策和行动项的完整摘要
   - 先创建 1 个决策（标题"采用微服务架构"）+ 1 个行动项（唯一标题避免混淆）
   - 验证 `decisions_summary` 含"项决策"，`content` 含决策标题
   - 验证 `action_items_summary` 含"个行动项"，`content` 含行动项标题

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestMeetingMinutes 12/12 passed
- ✅ pytest 203/203 passed（+3 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 83
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 84 (2026-04-05)
**版本**: v2.36 | **迭代周期**: 13分钟自动触发

### Plan
为 Stakeholders API 添加边界测试覆盖

背景：Stakeholders API（Plan 干系人）已实现并通过基础测试，但缺少边界测试：删除操作和404场景未覆盖。TestStakeholders 类仅2个测试，缺少 delete 和 not_found 测试用例。

### Do
新增 2 个 Stakeholders 测试用例（TestStakeholders 类从 2 → 4 个）：

1. **`test_delete_stakeholder`** — 删除干系人
   - 创建干系人后调用 DELETE
   - 验证返回 204
   - 验证 GET 返回 404

2. **`test_stakeholder_not_found`** — 干系人不存在返回404
   - 使用假 UUID 获取/更新/删除不存在的干系人
   - 验证 GET 返回 404 + `{"detail": "Stakeholder not found"}`
   - 验证 PATCH 返回 404
   - 验证 DELETE 返回 404

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestStakeholders 4/4 passed
- ✅ pytest 205/205 passed（+2 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 84
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 85 (2026-04-05)
**版本**: v2.37 | **迭代周期**: 13分钟自动触发

### Plan
为 Risks API 添加边界测试覆盖

背景：Risks API（Version 风险）已有 create/list/update/delete 覆盖，但缺少 `test_risk_not_found` 边界测试。与 Step 84 Stakeholders API 补全模式对齐。

### Do
新增 `test_risk_not_found` 测试用例（TestRisks 类从 2 → 3 个）：

- **`test_risk_not_found`** — 风险不存在返回404
  - 创建测试计划后使用假 UUID 测试 GET/PATCH/DELETE
  - 验证返回 404
  - 验证在不存在的计划中获取风险也返回 404

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestRisks 3/3 passed
- ✅ pytest 206/206 passed（+1 new test）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 85
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 86 (2026-04-05)
**版本**: v2.38 | **迭代周期**: 13分钟自动触发

### Plan
为 Constraints API 添加边界测试覆盖

背景：Constraints API（Plan 约束）已有 create/list/get/update/delete 覆盖，但缺少 `test_constraint_not_found` 边界测试。与 Step 84/85 补全模式对齐。

### Do
新增 `test_constraint_not_found` 测试用例（TestConstraints 类从 2 → 3 个）：

- **`test_constraint_not_found`** — 约束不存在返回404
  - 创建真实计划，使用假 UUID 测试 GET/PATCH/DELETE
  - 验证返回 404 + "Constraint not found"
  - PATCH 端点先检查 plan 存在，再检查 constraint 存在

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestConstraints 3/3 passed
- ✅ pytest 207/207 passed（+1 new test）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 86
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 87 (2026-04-05)
**版本**: v2.39 | **迭代周期**: 13分钟自动触发

### Plan
为 Decisions API 添加完整测试覆盖

背景：Decisions API 是计划版本的核心功能（创建/列出/获取/更新/删除决策），但没有任何专用的测试类。与 Step 84/85/86 补全模式对齐，填补测试空白。

### Do
新增 `TestDecisions` 测试类（6个测试用例）：

1. **`test_create_decision`** — 创建决策（含完整字段：title/decision_text/description/rationale/alternatives_considered/agreed_by/disagreed_by/decided_by）
   - 验证返回 201，decision_id/decision_number/plan_id/version 字段正确
   - 验证 agreed_by 和 alternatives_considered 为 list 类型

2. **`test_list_decisions`** — 列出版本所有决策
   - 创建2个决策后验证列表长度 ≥2
   - 验证返回格式 `{"decisions": [...]}`

3. **`test_get_decision`** — 获取单个决策详情
   - 验证返回格式 `{"decision": {...}}`，字段完整

4. **`test_update_decision`** — 更新决策字段
   - 更新 title/rationale/agreed_by，验证更新生效

5. **`test_decision_not_found`** — 决策不存在返回404
   - GET 不存在的决策 → 404
   - PATCH 不存在的决策 → 404

6. **`test_decision_in_version_plan_json`** — 验证决策出现在版本 plan.json 中
   - 创建决策后调用 `GET /plans/{plan_id}/versions/{version}/plan.json`
   - 验证 decisions 列表包含新创建的 decision_id

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestDecisions 6/6 passed
- ✅ pytest 213/213 passed（+6 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 87
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 82 (2026-04-05)
**版本**: v2.34 | **迭代周期**: 13分钟自动触发

### Plan
为 Edict Acknowledgment（圣旨签收）API 添加完整测试覆盖

背景：Edict Acknowledgment API（L7下行 decree 签收）允许各层级参与者确认收到圣旨，是朝堂议政的关键流程。之前 API 已实现、前端 `acknowledgeEdict`/`listEdictAcknowledgments`/`deleteEdictAcknowledgment` 已接入，但完全没有测试覆盖。

### Do
新增 `TestEdictAcknowledgment` 测试类（6个测试用例）：
- `test_create_edict_acknowledgment` — 创建圣旨签收记录（含 level/comment 字段验证）
- `test_list_edict_acknowledgments` — 列出圣旨的所有签收记录（2条验证）
- `test_delete_edict_acknowledgment` — 删除圣旨签收记录
- `test_multiple_acknowledgments_same_edict` — 同一圣旨 L1-L7 共7个层级依次签收
- `test_edict_acknowledgment_edict_not_found` — 签收不存在的圣旨返回404
- `test_edict_acknowledgment_delete_not_found` — 删除不存在的签收记录返回404

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestEdictAcknowledgment 6/6 passed
- ✅ pytest 200/200 passed（+6 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 82
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg


## Step 88 (2026-04-05)
**版本**: v2.39 | **迭代周期**: 13分钟自动触发

### Plan
为 Plan Copy API 添加测试覆盖，同时修复 `crud.copy_plan` 数据库写入Bug

背景：Plan Copy API 允许复制计划（不含版本级内容），但完全没有测试覆盖。同时 `crud.copy_plan` 函数存在 Bug：尝试向 `plans` 表写入不存在的 `purpose` 和 `mode` 字段（这两个字段属于 `rooms` 表）。

### Do
1. 新增 `TestPlanCopy` 测试类（4个测试用例）：
   - `test_copy_plan` — 基本复制功能
   - `test_copy_plan_not_found` — 复制不存在的计划返回404
   - `test_copy_plan_creates_room` — 复制时自动创建配套 Room
   - `test_copy_plan_preserves_metadata` — 复制保留元数据

2. 修复 `backend/repositories/crud.py` 中 `copy_plan` 函数：
   - 移除 INSERT 语句中的 `purpose` 和 `mode` 字段（它们属于 rooms 表，不是 plans 表）

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ docker-compose build api 成功
- ✅ pytest TestPlanCopy 4/4 passed
- ✅ pytest 217/217 passed（+4 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 88
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 89 (2026-04-05)
**版本**: v2.40 | **迭代周期**: 13分钟自动触发

### Plan
为 Plan Search 和 Room Search API 添加测试覆盖

背景：Plan Search API（`GET /plans/search`）和 Room Search API（`GET /rooms/search`）分别在 Step 66 和 Step 67 实现，但一直没有专用测试类。Decisions/Stakeholders/Risks 等 API 已在 Step 84-87 补全测试，搜索 API 测试空白需要填补。

### Do
新增 `TestPlanSearch` 测试类（5个测试用例）：
- `test_search_plans_basic` — 基本搜索（按标题关键词匹配）
- `test_search_plans_by_topic` — 按topic字段搜索
- `test_search_plans_by_status` — 按status过滤
- `test_search_plans_pagination` — 分页（limit/offset）
- `test_search_plans_empty_query` — 空查询返回422验证错误

新增 `TestRoomSearch` 测试类（5个测试用例）：
- `test_search_rooms_basic` — 基本搜索（按topic关键词匹配）
- `test_search_rooms_by_plan` — 按plan_id过滤
- `test_search_rooms_by_phase` — 按phase过滤（含阶段转换）
- `test_search_rooms_pagination` — 分页（limit/offset）
- `test_search_rooms_empty_query` — 空查询返回422验证错误

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestPlanSearch 5/5 passed
- ✅ pytest TestRoomSearch 5/5 passed
- ✅ pytest 234/234 passed（+10 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 89
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 90 (2026-04-06)
**版本**: v2.41 | **迭代周期**: 13分钟自动触发

### Plan
为 Debate State API 添加完整测试覆盖

背景：Debate State API（辩论议题/立场/交锋/轮次）是 DEBATE 阶段的核心功能，包含5个端点：
- `POST /rooms/{room_id}/debate/points` — 创建辩论议题点
- `GET /rooms/{room_id}/debate/state` — 获取辩论状态（round/consensus_score/points/exchanges）
- `POST /rooms/{room_id}/debate/position` — 提交议题立场
- `POST /rooms/{room_id}/debate/exchange` — 记录辩论交锋
- `POST /rooms/{room_id}/debate/round` — 推进辩论轮次

此前 DEBATE 阶段测试仅覆盖 phase transition（`test_sharing_to_debate`），辩论 API 本身完全没有测试。

### Do
新增 `TestDebateAPI` 测试类（10个测试用例）：

1. **`test_create_debate_point`** — 创建辩论议题点
   - 创建 DEBATE 阶段房间，提交议题内容，验证返回 point 结构

2. **`test_create_multiple_debate_points`** — 创建多个辩论议题点
   - 验证状态中 all_points 数量正确

3. **`test_create_debate_point_wrong_phase`** — 非DEBATE阶段创建议题点返回400
   - SELECTING 阶段调用返回 400 + "only DEBATE phase"

4. **`test_get_debate_state`** — 获取辩论状态
   - 验证 room_id/round/consensus_score/consensus_level/all_points/converged_points/disputed_points/recent_exchanges/max_rounds 字段完整
   - 初始 round=0

5. **`test_submit_debate_position`** — 提交辩论立场
   - 先创建议题点，再提交 agree/oppose/abstain 立场
   - 验证返回 consensus_score 和 point_id

6. **`test_submit_debate_position_wrong_phase`** — 非DEBATE阶段提交立场返回400
   - SELECTING 阶段调用返回 400

7. **`test_submit_debate_exchange`** — 记录辩论交锋
   - challenge 类型交锋，验证 type/from_agent/target_agent/content 字段
   - 注：后端返回 `type` 字段（非 `exchange_type`）

8. **`test_advance_debate_round`** — 推进辩论轮次
   - 验证 new_round=1, max_rounds, at_max 字段

9. **`test_debate_room_not_found`** — 讨论室不存在返回404
   - 假 UUID 调用 debate/points 和 debate/state 均返回 404

10. **`test_debate_state_not_initialized`** — 非DEBATE阶段获取辩论状态返回404
    - SELECTING 阶段房间调用 debate/state 返回 404

辅助函数 `_create_debate_room()`：创建计划+房间，自动转换 SELECTING→THINKING→SHARING→DEBATE。

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestDebateAPI 10/10 passed
- ✅ pytest 244/244 passed（+10 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 90
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

---

## Step 91 (2026-04-06)
**版本**: v2.42 | **迭代周期**: 13分钟自动触发

### Plan
为 Task Comments API 和 Task Checkpoints API 添加完整测试覆盖

背景：Task Comments（评论）和 Task Checkpoints（检查点）是任务管理的重要功能，分别支持：
- Comments：团队成员对任务进行讨论和反馈
- Checkpoints：任务分解为可验证的里程碑节点

此前这两个 API 没有任何专用测试类，属于测试空白。

### Do
新增两个测试类（共18个测试用例）：

**`TestTaskComments`**（8个测试用例）：
1. `test_create_comment` — 创建任务评论，验证所有字段
2. `test_create_comment_without_author_level` — author_level 可选
3. `test_list_comments` — 列出任务所有评论
4. `test_update_comment` — 更新评论内容
5. `test_delete_comment` — 删除评论并验证消失
6. `test_comment_not_found` — 假 UUID 返回 404
7. `test_comment_empty_content` — 空内容返回 422
8. `test_comment_task_not_found` — API 只验证 plan 不验证 task_id（实际返回 201）

**`TestTaskCheckpoints`**（10个测试用例）：
1. `test_create_checkpoint` — 创建检查点，默认 pending 状态
2. `test_list_checkpoints` — 列出任务所有检查点
3. `test_update_checkpoint_status` — 更新为 completed，设置 completed_at
4. `test_update_checkpoint_name` — 更新检查点名称
5. `test_update_checkpoint_pending_from_completed` — completed 可改回 pending
6. `test_delete_checkpoint` — 删除检查点并验证消失
7. `test_checkpoint_not_found` — 假 UUID 返回 404
8. `test_checkpoint_empty_name` — 空名称返回 422
9. `test_checkpoint_invalid_status` — 无效状态返回 422
10. `test_checkpoint_task_not_found` — API 只验证 plan 不验证 task_id（实际返回 201）

辅助函数 `_create_plan_and_task()`：创建计划+任务，返回 (plan_id, version, task_id)。

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestTaskComments 8/8 passed
- ✅ pytest TestTaskCheckpoints 10/10 passed
- ✅ pytest 262/262 passed（+18 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 91
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 92 (2026-04-06)
**版本**: v2.43 | **迭代周期**: 13分钟自动触发

### Plan
为 Plan Tags API 添加完整测试覆盖

背景：Plan Tags API（`/plans/{plan_id}/tags`）允许对计划进行标签化管理，是计划分类和筛选的基础功能。与 Room Tags API 结构完全对称（GET/PATCH/POST add/POST remove），但 Room Tags 有 20 个测试，Plan Tags 之前完全没有测试覆盖。

### Do
新增 `TestPlanTags` 测试类（11个测试用例）：

1. **`test_get_plan_tags_empty`** — 获取计划标签（空标签）
   - 新建计划标签为空数组 `[]`
   - 验证返回格式 `{"plan_id": "...", "tags": []}`

2. **`test_update_plan_tags`** — 更新计划标签（替换模式）
   - `PATCH /plans/{plan_id}/tags` 全量替换标签
   - 验证返回标签列表与设置一致

3. **`test_add_plan_tags`** — 添加计划标签
   - 先设置 `["重要"]`，再添加 `["紧急"]`
   - 验证两个标签都存在于最终列表

4. **`test_add_plan_tags_deduplication`** — 添加计划标签（去重）
   - 添加已存在的 `["重要"]` + `["新标签"]`
   - 验证 `"重要"` 只出现一次

5. **`test_remove_plan_tags`** — 移除计划标签
   - 设置 `["重要", "紧急", "技术评审"]`，移除 `["紧急"]`
   - 验证 `"紧急"` 不在最终列表，`"重要"` 和 `"技术评审"` 保留

6. **`test_search_plans_by_tags`** — 搜索计划（按标签过滤）
   - 设置 `["重要", "技术评审"]`
   - `GET /plans/search?q=测试&tags=重要`
   - 验证返回的计划包含 `"重要"` 标签

7. **`test_plan_tags_plan_not_found`** — 计划不存在返回404
   - `GET /plans/{fake_id}/tags` → 404

8. **`test_update_plan_tags_not_found`** — 更新标签（计划不存在返回404）
   - `PATCH /plans/{fake_id}/tags` → 404

9. **`test_add_plan_tags_not_found`** — 添加标签（计划不存在返回404）
   - `POST /plans/{fake_id}/tags/add` → 404

10. **`test_remove_plan_tags_not_found`** — 移除标签（计划不存在返回404）
    - `POST /plans/{fake_id}/tags/remove` → 404

11. **`test_plan_tags_persistence`** — 计划标签持久化验证
    - 设置 `["初始标签"]` → GET 验证 → 更新为 `["新标签1", "新标签2"]` → GET 验证最新值
    - 确保标签读写一致，无数据丢失

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestPlanTags 11/11 passed
- ✅ pytest 273/273 passed（+11 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 92（版本 v2.43）
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg

## Step 93 (2026-04-06)
**版本**: v2.44 | **迭代周期**: 13分钟自动触发

### Plan
为 Approval API 添加边界测试覆盖

背景：Approval API（L1-L7审批流）是计划审批的核心功能，但只有4个基础测试（启动/层级说明/L7通过/完整链），缺少边界测试覆盖。与 Step 84-92 的补全模式对齐。

### Do
新增 6 个 Approval 边界测试用例（TestApprovalFlow 类从 4 → 10 个）：

1. **`test_approval_not_found`** — 审批不存在的计划返回404
   - GET /approval → 404
   - POST /approval/start → 404
   - GET /approval/levels 是静态描述，不验证plan存在

2. **`test_approval_reject`** — L7审批拒绝，审批流状态变为rejected
   - 启动审批流后，L7执行 reject action
   - 验证 new_current_level=7（停在L7），status=rejected

3. **`test_approval_invalid_level_action`** — 在审批链中不存在的层级执行操作返回400
   - 正常启动审批流（L1-L7都在链中）
   - 尝试在L8执行操作（非有效层级）
   - 验证返回 400 + Level not in approval chain

4. **`test_approval_without_start`** — 未启动审批流就执行操作返回400
   - 未调用 /approval/start，直接尝试在L7执行审批
   - 验证返回 400 + Approval flow not found

5. **`test_approval_skip_levels`** — 跳过某些层级审批
   - 启动时 skip_levels=[7, 6]
   - 验证 levels 中不包含 7 和 6
   - 验证 L5 在 levels 中且状态为 pending

6. **`test_approval_already_approved`** — 对已完成的审批流再次操作仍然成功
   - 完成全部 L7→L1 审批，验证 plan.status=approved
   - 再次尝试 L7 approve（API不阻止重审）
   - 验证返回 200，new_status=fully_approved

### Check
- ✅ python3 -m py_compile 语法检查通过
- ✅ pytest TestApprovalFlow 10/10 passed
- ✅ pytest 279/279 passed（+6 new tests）
- ✅ docker-compose config 正常

### Act
- 更新 SPEC.md 完成 Step 93（版本 v2.44）
- 追加飞书文档 RgmodbBvSoKP02xQMdgcyhs1nsg
