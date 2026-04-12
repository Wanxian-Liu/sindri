# Sindri's API 参考

## SindrisExecutor

主执行引擎类。

### 构造函数

```python
SindrisExecutor(
    workspace_root: Optional[str] = None,
    workspace_id: Optional[str] = None,
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| workspace_root | str | 工作区根目录，默认为 `~/.openclaw/workspace` |
| workspace_id | str | 工作区ID，默认为 `ws_{随机8位}` |

### plan()

**规划阶段：返回子任务列表，供主Agent调用sessions_spawn执行**

```python
async def plan(self, task: str) -> Dict[str, Any]
```

**参数**:
- `task: str` — 任务描述

**返回**:
```python
{
    "success": True,
    "task_id": "xxx",           # 任务ID
    "subtasks": [
        {
            "task_id": "xxx",
            "role": "Code Reviewer",
            "role_type": "developer",
            "title": "[Code Reviewer] 修复Python代码bug",
            "timeout": 600,         # 秒
            "allowed_tools": ["read", "exec", "edit", "write"]
        }
    ],
    "plan_summary": "分解为3个子任务"
}
```

**注意**: 这个方法只做规划，不执行真实任务。主Agent根据返回的subtasks列表，自己调用sessions_spawn执行。

---

### run()

**执行完整Round1-4流程**

```python
async def run(
    self,
    task: str,
    verify: bool = False,
) -> Dict[str, Any]
```

**参数**:
- `task: str` — 任务描述
- `verify: bool` — 是否在Round4后自动运行Ralph Loop验证（默认关闭）

**返回**:
```python
{
    "success": True,
    "session_id": "session_xxx",
    "results": [
        {"success": True, "task_id": "t1", "output": {...}, "verification": {...}},
        {"success": False, "task_id": "t2", "error": "..."},
    ],
    "summary": {...},           # OMX session summary
    "ralph_verified": True,     # 仅当 verify=True 时
}
```

---

### run_with_consensus()

**带共识检查的完整流程**

```python
async def run_with_consensus(
    self,
    task: str,
    agent_outputs: List[str],
) -> Dict[str, Any]
```

**参数**:
- `task: str` — 任务描述
- `agent_outputs: List[str]` — 各Agent的输出列表（用于共识检查）

**返回**: 同 `run()`

**共识标签格式**: Agent输出中需包含 `[CONSENSUS: YES]` 或 `[CONSENSUS: NO]`

---

### round1_planning()

**Round1: 规划轮**

```python
async def round1_planning(self, task: str) -> RoundContext
```

**流程**:
1. 任务分类（TaskClassifier）
2. 角色匹配（178角色库）
3. 创建tmux worker team
4. 任务分解
5. OMX记录

---

### round2_execution()

**Round2: 执行轮**

```python
async def round2_execution(self) -> List[ExecutionResult]
```

**流程**:
1. 为每个角色创建Worker
2. 分配任务
3. 并行/串行执行
4. 逐个验收
5. OMX记录

---

### round3_review()

**Round3: 审查轮**

```python
async def round3_review(self, results: List[ExecutionResult]) -> bool
```

**参数**:
- `results: List[ExecutionResult]` — Round2的执行结果

**返回**: `True` if all approved, `False` otherwise

---

### round4_completion()

**Round4: 完成**

```python
async def round4_completion(
    self,
    results: List[ExecutionResult],
    all_verified: bool,
) -> Dict[str, Any]
```

---

### verify_with_ralph()

**使用Ralph Loop进行多轮验证**

```python
async def verify_with_ralph(
    self,
    task: Task,
    result: ExecutionResult,
    verify_items: List[Dict],
) -> RalphResult
```

---

### get_status()

**获取当前状态**

```python
def get_status(self) -> Dict[str, Any]
```

**返回**:
```python
{
    "session_id": "session_xxx",
    "current_round": 2,
    "workers": [{"id": "w1", "role": "developer", "status": "BUSY"}],
    "tasks": [{"id": "t1", "title": "...", "status": "COMPLETED"}],
    "omx_summary": {...},
}
```

---

### shutdown()

**关闭team和清理资源**

```python
def shutdown(self) -> None
```

---

## 数据类型

### TaskStatus

```python
class TaskStatus(str):
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### WorkerStatus

```python
class WorkerStatus(str):
    IDLE = "idle"
    BUSY = "busy"
    STALE = "stale"
    OFFLINE = "offline"
```

### RoundPhase

```python
class RoundPhase(str):
    PLANNING = "planning"     # Round1
    EXECUTING = "executing"  # Round2
    REVIEW = "review"         # Round3
    COMPLETION = "completion" # Round4
```

### Worker

```python
@dataclass
class Worker:
    id: str
    agent_id: str
    role: str
    role_type: str           # researcher/developer/verifier/recorder
    status: WorkerStatus
    assigned_task_ids: List[str]
    lease_expires_at: Optional[str]
    last_heartbeat_at: Optional[str]
    runtime_backend: str     # openclaw/tmux/mock
    session_name: Optional[str]
    log_file: Optional[str]
```

### Task

```python
@dataclass
class Task:
    id: str
    title: str
    kind: str                # round1/round2/round3/executor
    phase: str               # round1/round2/round3/round4
    status: TaskStatus
    priority: str            # low/medium/high
    owner: Optional[str]      # worker_id
    metadata: Dict
    verify: List[str]        # 验收条件
    notes: List[str]
    dependencies: List[str]
    blockers: List[str]
    review_status: str       # none/pending/approved/changes_requested
    result: Optional[str]
    history: List[Dict]
    created_at: str
    updated_at: str
```

### ExecutionResult

```python
@dataclass
class ExecutionResult:
    success: bool
    task_id: str
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    verification: Optional[Dict[str, bool]]
```

### RoundContext

```python
@dataclass
class RoundContext:
    round: int
    phase: RoundPhase
    task: str
    matched_roles: List[Dict]
    tasks: List[Task]
    workers: List[Worker]
    plan_summary: Optional[str]
    consensus_reached: bool
    verification_results: Dict[str, bool]
```

---

## OMXIntegrator

OMX持久化集成器。

### 构造函数

```python
OMXIntegrator(workspace_root: Optional[str] = None)
```

### Round1方法

```python
def on_round1_start(
    self,
    task_description: str,
    matched_roles: List[Dict],
) -> str  # 返回session_id

def on_round1_complete(
    self,
    plan_summary: str,
    task_id: Optional[str] = None,
    verified: bool = True,
) -> Task
```

### Round2方法

```python
def on_round2_start(
    self,
    task_id: str,
    actions: List[Dict],
) -> None

def on_action_start(
    self,
    action_id: str,
    agent_id: str,
    action_name: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None

def on_action_complete(
    self,
    action_id: str,
    verified: bool,
    verify_results: Optional[Dict] = None,
    error: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None

def on_round2_complete(
    self,
    task_id: str,
    all_verified: bool,
    failed_actions: Optional[List[str]] = None,
) -> None
```

### Round3方法

```python
def on_round3_start(
    self,
    task_id: str,
    review_items: List[Dict],
) -> List[ReviewItem]

def on_review_submit(
    self,
    review_id: str,
    status: str,           # approved / changes_requested / rejected
    summary: str,
) -> None

def on_round3_complete(
    self,
    task_id: str,
    all_approved: bool,
) -> None
```

### Round4方法

```python
def on_round4_complete(
    self,
    task_id: str,
    final_output: Dict[str, Any],
    success: bool,
) -> None
```

### 查询方法

```python
def get_session_summary(self) -> Dict[str, Any]
def get_pending_reviews(self) -> List[ReviewItem]
def get_failed_actions(self) -> List[ActionRecord]
```

---

## SindrisWorkerManager

tmux Worker运行时管理器。

### create_team()

工厂方法，创建并启动全队：

```python
@staticmethod
def create_team(
    team_name: str,
    worker_specs: List[Dict],
    workspace_root: Optional[str] = None,
) -> Tuple[SindrisWorkerManager, List[Worker]]
```

**示例**:
```python
mgr, workers = SindrisWorkerManager.create_team(
    team_name="dev-squad",
    workspace_root="/path/to/workspace",
    worker_specs=[
        {"role": "researcher", "agent_id": "agent-1"},
        {"role": "engineering_senior_developer"},
        {"role": "reviewer"},
    ],
)
```

### 核心方法

| 方法 | 说明 |
|------|------|
| `create_worker(role, agent_id?)` | 注册worker记录 |
| `spawn_worker(wid, command?)` | 启动tmux窗口或mock进程 |
| `send_command(wid, cmd)` | 向worker发送命令 |
| `observe(wid)` | 捕获pane输出，更新状态 |
| `resolve_trust(wid)` | 手动解决trust gate |
| `heartbeat(wid, msg)` | 心跳保活 |
| `reconcile()` | 检测过期lease，标记stale |
| `restart_worker(wid)` | 重启worker |
| `complete(wid, result)` | 标记worker完成 |
| `terminate(wid)` | 终止单个worker |
| `shutdown()` | 关闭全队 |

### Worker状态

```python
class WorkerStatus(Enum):
    SPAWNING       = auto()   # 进程启动，未完成初始化
    TRUST_REQUIRED = auto()   # 等待信任门批准
    READY          = auto()   # 准备接收任务
    RUNNING        = auto()   # 任务执行中
    COMPLETED      = auto()   # 任务成功完成
    FAILED         = auto()   # 任务失败
```

---

## 便捷函数

### run_sindris()

```python
async def run_sindris(task: str) -> Dict[str, Any]
```

快速运行sindris，等同于 `SindrisExecutor().run(task)`

### run_sindris_with_consensus()

```python
async def run_sindris_with_consensus(
    task: str,
    agent_outputs: List[str],
) -> Dict[str, Any]
```

带共识检查的快速运行

---

## 常量

### 角色超时配置

```python
TIMEOUT_MAP = {
    "researcher": 300,   # 5分钟
    "developer": 600,     # 10分钟
    "verifier": 180,      # 3分钟
    "recorder": 60,      # 1分钟
}
```

### 角色默认工具

```python
ROLE_TOOL_DEFAULTS = {
    "developer": ["read", "exec", "edit", "write", "browser", "pdf", "image"],
    "researcher": ["read", "exec", "web_search", "web_fetch", "browser"],
    "verifier": ["read", "exec", "browser"],
    "recorder": ["read", "write", "edit"],
}
```

---

## 异常处理

sindris_executor 所有公开方法返回 `Dict` 而非抛出异常，结构如下：

```python
# 成功
{"success": True, ...}

# 失败
{"success": False, "error": "错误描述", "session_id": "..."}
```

---

*API v1.2*
