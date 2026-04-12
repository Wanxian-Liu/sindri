# Sindri's — 织界统一协调系统

> **Sindri's** — 冰岛语"真挚、纯粹" | 意为每个协作都是真诚的、有目的的

**版本**: v1.2  
**定位**: 多Agent协作执行引擎

---

## 核心定位

`sindris_executor.py` 是**规划辅助工具**，不是子代理启动器。

```
主Agent
    ↓
调用 sindris_executor.plan() 做规划（返回subtasks配置）
    ↓
主Agent使用 sessions_spawn 工具启动子Agent
    ↓
子Agent执行任务
    ↓
主Agent收集结果，继续 Round3-4
```

**为什么这样设计**：
- 工具调用（sessions_spawn）是 Agent 的能力，只有 Agent 能调用
- sindris_executor 是辅助，返回结构化数据帮助规划
- 分离关注点，规划与执行分离，更灵活

---

## 核心组件

| 组件 | 文件 | 作用 |
|------|------|------|
| 唯一执行引擎 | `sindris_executor.py` | 含 `plan()` 和 `run()` 两个方法 |
| OMX持久化层 | `scripts/omx_integrator.py` | Round1-4状态记录 |
| tmux Worker运行时 | `scripts/sindris_tmux_manager.py` | Phase 2新增，基于oh-my-codex设计 |
| 熔断器 | `scripts/circuit_breaker.py` | 角色超时/失败熔断 |
| 共识投票官 | `scripts/consensus_officer.py` | 解析`[CONSENSUS: YES/NO]`标签 |
| Worktree隔离官 | `scripts/worktree_officer.py` | git worktree独立工作目录管理 |
| 178角色库 | `~/.openclaw/projects/agency-agents/roles_registry.json` | 专业角色匹配 |

---

## 触发方式

在对话中说出以下任一关键词即可激活：

| 触发词 | 说明 |
|--------|------|
| `启动Sindri's` | 开始完整A2v3流程 |
| `A2流程` | 开始A2v3协作 |
| `多Agent协作` | 启动团队协作 |
| `执行A2` | 快速启动 |

---

## 执行流程概览

```
Round1: 规划 → 角色匹配 → 并行分析 → 验收
Round2: 执行 → 动作拆分 → 串行写入 → 逐个验收
Round3: 集成 → 整体验证
Round4: 完成 → 交付 + Git提交
```

---

## 快速使用

### plan() 方法（推荐）

只做规划，返回subtasks列表供主Agent调用 sessions_spawn 执行：

```python
plan = await sindris.plan("修复Python代码bug")

# 返回结构：
{
    "success": True,
    "task_id": "task_xxx",
    "subtasks": [
        {
            "task_id": "xxx",
            "role": "Code Reviewer",
            "role_type": "developer",
            "title": "[Code Reviewer] 修复Python代码bug",
            "timeout": 600,
            "allowed_tools": ["read", "exec", "edit", "write"]
        }
    ]
}
```

### run() 方法

执行完整 Round1-4 流程（需要用户确认CONSENSUS）：

```python
result = await sindris.run("开发一个用户认证系统")
```

---

## 角色+工具约束

每个角色继承178角色库，声明**工具类型约束**：

| 类型 | 可用工具 | 说明 |
|------|---------|------|
| `Explore` | read, glob, grep, web_fetch, web_search | 探索研究 |
| `Plan` | + TodoWrite, sessions_send | 规划分解 |
| `Verification` | + bash, exec (只读测试) | 验证测试 |
| `General` | 全部工具 | 通用执行 |
| `ReadOnly` | read, glob, grep | 只读观察 |

---

## 熔断规则

| 角色 | 超时时间 | 说明 |
|------|---------|------|
| 研究员 (researcher) | 300s | 探索分析任务 |
| 开发者 (developer) | 600s | 代码开发任务 |
| 验证者 (verifier) | 180s | 测试验证任务 |
| 记录员 (recorder) | 60s | 文档记录任务 |

熔断触发后自动拒绝该角色新任务，需等待半开恢复。

---

## JSONL执行日志

```jsonl
{"type":"round","round":1,"phase":"planning","status":"start"}
{"type":"agent","id":"SoftwareArchitect","role":"engineering_software_architect","state":"create"}
{"type":"verification","agent":"SoftwareArchitect","output":"/tmp/decouple_architecture.json","result":"pass"}
{"type":"round","round":2,"phase":"execution","status":"start"}
{"type":"agent","id":"Developer","role":"engineering_senior_developer","state":"create"}
{"type":"verification","agent":"Developer","file":"interfaces/imemory_vault.py","result":"fail","reason":"file_not_found"}
{"type":"retry","agent":"Developer","attempt":1,"reason":"file_not_found"}
```

---

## 与原A2流程对比

| 维度 | 原A2 | Sindri's A2v3 |
|------|------|---------------|
| 任务粒度 | Round含多步骤 | 角色=1精确动作 |
| 验收 | Round结束验收 | **每动作完成后立即验收** |
| 验证者 | 子代理自验 | **主Agent外部验收** |
| 并行 | Round内串行 | **读写分离，只读并行** |
| 恢复 | 失败上报 | **自动重试+6种恢复策略** |
| 角色 | 角色=整个任务 | **角色=专长+动作集合** |
| 日志 | 无 | **JSONL执行日志** |
| 缓存 | 无 | **FastPath缓存** |

---

## 目录结构

```
~/.openclaw/skills/sindris/
├── SKILL.md                      # 使用流程文档
├── sindris_executor.py           # 唯一执行引擎
├── docs/                         # 技术文档
│   ├── README.md                 # 本文档
│   ├── ARCHITECTURE.md           # 架构说明
│   └── API.md                   # API参考
└── scripts/
    ├── sindris_tmux_manager.py   # tmux Worker运行时
    ├── omx_integrator.py        # OMX持久化集成器
    ├── omx_ledger.py            # 执行日志
    ├── omx_tasks.py             # 任务图
    ├── omx_reviews.py           # 审查队列
    ├── omx_contract.py          # OMX路径定义
    ├── circuit_breaker.py        # 熔断器
    ├── consensus_officer.py      # 共识投票官
    ├── worktree_officer.py      # Worktree隔离官
    ├── match_roles.py           # 角色匹配
    └── ralph_loop.py            # Ralph验证模块
```

---

*Sindri's v1.2 — 真诚、纯粹的多Agent协作*
