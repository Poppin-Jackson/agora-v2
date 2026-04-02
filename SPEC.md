# Agora-V2 规格说明书

> 版本：v0.1 | 日期：2026-04-03
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
                      (新讨论 → 修复版本)
```

**去中心化关键**：
- THINKING：每人独立思考，不看别人观点
- SHARING：按顺序陈述，不是汇报
- DEBATE：自由质疑，Coordinator 不裁决
- CONVERGING：共识自然浮现，不是多数投票

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
Step 3: 核心API (Plan/Room/Participant)
Step 4: WebSocket 实时讨论
Step 5: 状态机实现 (THINKING→SHARING→DEBATE→CONVERGING)
Step 6: L1-L7 层级审批流
Step 7: OpenCLAW Gateway 集成
Step 8: 前端界面
Step 9: 全流程E2E测试
```

---

## 10. 成功标准

- [ ] `docker-compose up` 能启动完整系统
- [ ] 用户输入方向，AI自动完成全流程讨论
- [ ] 讨论结果可导出为结构化任务列表
- [ ] 无单一决策者，共识通过质疑收敛
