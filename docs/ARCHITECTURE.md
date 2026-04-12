# Sindri's 架构说明

## 1. 设计原则

### 1.1 工具调用是 Agent 的能力

`sessions_spawn` 是工具，只有 Agent 能调用。sindris_executor 是**规划辅助工具**，返回结构化数据帮助规划，不直接启动子代理。

### 1.2 分离关注点

```
规划（sindris_executor.plan()）
    ↓ 返回subtasks
执行（主Agent调用 sessions_spawn）
    ↓
验收（主Agent外部验收）
    ↓
记录（OMX持久化）
```

---

## 2. 三层状态机

### Team层

```python
class SindrisExecutor:
    workers: List[Worker]     # 所有Worker
    tasks: List[Task]         # 所有任务
    current_round: RoundContext  # 当前Round上下文
```

### Worker层

```python
class Worker:
    id: str                  # 唯一标识
    agent_id: str            # 代理ID（来自178库）
    role: str                # 角色名
    role_type: str           # researcher/developer/verifier/recorder
    status: WorkerStatus     # IDLE/BUSY/STALE/OFFLINE
    runtime_backend: str     # openclaw/tmux/mock
```

### Task层

```python
class Task:
    id: str
    title: str
    kind: str                 # round1/round2/round3/executor
    phase: str                # round1/round2/round3/round4
    status: TaskStatus        # PENDING/IN_PROGRESS/COMPLETED/FAILED
    owner: Optional[str]      # worker_id
    verify: List[str]        # 验收条件
    dependencies: List[str]  # 依赖关系
```

---

## 3. 模块依赖关系

```
sindris_executor.py
    ├── match_roles.py          # 角色匹配
    ├── omx_integrator.py       # OMX集成
    │   ├── omx_tasks.py        # 任务图
    │   ├── omx_ledger.py        # 执行日志
    │   ├── omx_reviews.py       # 审查队列
    │   └── omx_contract.py     # 路径定义
    ├── sindris_tmux_manager.py # tmux Worker运行时
    ├── circuit_breaker.py       # 熔断器
    ├── consensus_officer.py    # 共识投票官
    ├── worktree_officer.py     # Worktree隔离官
    ├── ch16_stages.py          # 任务分类器
    └── ralph_loop.py           # Ralph验证模块

织界中枢（按需）
    ├── consensus_officer.py
    ├── worktree_officer.py
    └── monitor.py (含CircuitBreaker)
```

---

## 4. Round1-4 流程

### Round1: 规划轮

```
round1_planning(task)
    │
    ├── TaskClassifier.classify(task)    # 任务分类
    ├── match_roles(keywords)             # 178角色匹配
    ├── create_team(workers)             # 创建tmux worker team
    ├── _decompose_task()                # 任务分解
    └── omx.on_round1_start/complete()   # OMX记录
```

### Round2: 执行轮

```
round2_execution()
    │
    ├── omx.on_round2_start()
    ├── for each task:
    │   ├── _spawn_subagent()            # 启动子Agent
    │   ├── _execute_task_with_timeout() # 带超时执行
    │   ├── _verify_task()               # 验收
    │   └── omx.on_action_start/complete()
    └── omx.on_round2_complete()
```

### Round3: 审查轮

```
round3_review(results)
    │
    ├── omx.on_round3_start()
    ├── for each result:
    │   ├── omx.on_review_submit()
    └── omx.on_round3_complete()
```

### Round4: 完成

```
round4_completion(results, all_verified)
    │
    ├── omx.on_round4_complete()
    ├── worktree.cleanup()
    └── return final report
```

---

## 5. tmux Worker运行时架构

基于 oh-my-codex team.ts + claw-code worker_boot.rs 设计：

```
SindrisWorkerManager
    ├── TmuxManager          # 低层tmux操作
    ├── Worker registry      # 内存worker注册表
    └── Event sourcing       # append-only事件日志
```

### Worker生命周期

```
SPAWNING → TRUST_REQUIRED → READY → RUNNING → COMPLETED/FAILED
                        ↑                    │
                        +----- restart ------+

SPAWNING:        进程启动，未完成初始化
TRUST_REQUIRED:  等待信任门批准 (Do you trust...)
READY:           准备接收任务
RUNNING:         任务执行中
COMPLETED:       任务成功完成
FAILED:          任务失败或终端错误
```

### 优雅降级

无tmux时自动降级到mock模式，状态机和事件日志照常运行。

---

## 6. 熔断器设计

每个角色维护一个熔断器：

```python
self._circuit_breakers: Dict[str, CircuitBreaker] = {
    "researcher": CircuitBreaker(task_id="session_xxx_researcher", role="researcher"),
    "developer": CircuitBreaker(...),
    "verifier": CircuitBreaker(...),
    "recorder": CircuitBreaker(...),
}
```

### 熔断状态

- **Closed**: 正常状态，失败计数累加
- **Open**: 熔断打开，拒绝新任务
- **Half-Open**: 半开状态，允许一个测试请求

### 超时配置

| 角色类型 | 超时时间 |
|---------|---------|
| researcher | 300s |
| developer | 600s |
| verifier | 180s |
| recorder | 60s |

---

## 7. OMX持久化架构

```
.omx/
├── state/
│   ├── sindris_phases.json   # Round阶段记录
│   ├── sindris_actions.json  # 动作执行记录
│   ├── tasks.json            # OMX任务图
│   └── reviews.json          # OMX审查队列
└── logs/
    └── ledger.json           # OMX执行日志
```

### Round与OMX模块映射

| Round | OMX模块 | 功能 |
|-------|---------|------|
| Round1 | `omx_tasks` | 任务创建、状态转换、计划记录 |
| Round2 | `omx_ledger` | 动作执行日志、会话事件 |
| Round3 | `omx_reviews` | 审查队列、审查结果 |
| Round4 | `omx_tasks` | 最终状态更新 |

---

## 8. 共识投票机制

```python
consensus = ConsensusOfficer()

# 解析输出中的共识标签
result = consensus.parse_consensus(agent_output)
# result.has_consensus: bool
# result.vote: YES/NO/UNKNOWN

# Round1完成后检查
all_yes = await round1_consensus_check(agent_outputs)
```

标签格式：`[CONSENSUS: YES]` 或 `[CONSENSUS: NO]`

---

## 9. 执行日志格式

```jsonl
{"type":"session_start","task_id":"xxx","timestamp":"..."}
{"type":"round","round":1,"phase":"planning","status":"start"}
{"type":"agent","id":"Architect","role":"engineering_software_architect","state":"create","tools":["read","glob","grep"]}
{"type":"verification","agent":"Architect","output":"/tmp/architecture.json","result":"pass","checks":["file_exists","content_valid"]}
{"type":"round","round":2,"phase":"execution","status":"start"}
{"type":"agent","id":"Developer","role":"engineering_senior_developer","state":"create"}
{"type":"retry","agent":"Developer","attempt":1,"reason":"file_not_found"}
{"type":"verification","agent":"Developer","file":"interfaces/imemory_vault.py","result":"pass"}
{"type":"round_complete","round":3,"status":"success"}
{"type":"session_end","status":"success"}
```

---

## 10. 类图

```
SindrisExecutor
├── omx: OMXIntegrator
├── consensus: ConsensusOfficer
├── worktree: WorktreeOfficer
├── _circuit_breakers: Dict[str, CircuitBreaker]
├── workers: List[Worker]
├── tasks: List[Task]
├── current_round: RoundContext
└── worker_manager: SindrisWorkerManager

RoundContext
├── round: int
├── phase: RoundPhase
├── task: str
├── matched_roles: List[Dict]
├── tasks: List[Task]
├── workers: List[Worker]
└── consensus_reached: bool

Worker
├── id: str
├── agent_id: str
├── role: str
├── role_type: str
├── status: WorkerStatus
└── assigned_task_ids: List[str]

Task
├── id: str
├── title: str
├── kind: str
├── phase: str
├── status: TaskStatus
├── owner: Optional[str]
├── verify: List[str]
└── dependencies: List[str]
```

---

*Architecture v1.2 — 模块化、分层、可观测*
