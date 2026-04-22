---
name: sindris
version: "3.10"
license: MIT
copyright: "2026 琬弦 (Wanxian)"
description: |
  织界统一协调系统 v3.10 - 多Agent协作执行引擎
  
  基于sindris Round1-4流程，参考oh-my-codex v2设计，
  整合织界中枢模块（熔断/投票/worktree）和OMX持久化。
  
  ⚠️ 重要：sindris是规划器+协调器，执行必须由主代理调用sessions_spawn
  ⚠️ 重要：启动子代理后必须调用sessions_yield()等待结果
  ⚠️ 重要：OMX锤炼在每次子代理完成后自动触发
  
  完整版本历史见 [CHANGELOG.md](CHANGELOG.md)
---

# Sindri's A2v3 多Agent协作流程


> **Sindri's** — 冰岛语"真挚、纯粹" | 意为每个协作都是真诚的、有目的的

---

## 零、审计状态

> **最新审计**: 2026-04-22 | **版本**: v3.10

### 当前状态

| 级别 | 问题数 | 已修复 |
|------|--------|--------|
| P0 | 4 | 4 ✅ |
| P1 | 6 | 6 ✅ |
| P2 | 3 | 3 ✅ |

> 详细历史见 [CHANGELOG.md](CHANGELOG.md)

---

## 一、强制规则

### 核心检查表

| # | 检查点 | 操作 |
|---|--------|------|
| 1 | 审计完成 | 结果写入OMX |
| 2 | 代码修复 | 必须写测试 |
| 3 | 子代理执行 | 必须调用sessions_yield() |
| 4 | 任务完成 | 必须端到端验证 |
| 5 | Git修改 | 必须commit |

> 详细规则见 [audit_20260420.md](modules/audit_20260420.md)

## 二、架构说明

### 核心原则

**sindris_executor.py 不是子代理启动器**，它是**规划辅助工具**。

根据 Claude Code 的设计：
> "Spawn a subagent? That's a tool (AgentTool)"

子代理启动是**工具调用**（sessions_spawn），不是 Python 函数调用。

### 正确架构

```
主Agent (我)
    ↓
读取 sindris SKILL.md
    ↓
调用 sindris_executor.py 做规划（返回配置）
    ↓
使用 sessions_spawn 工具启动子Agent
    ↓
子Agent执行任务
    ↓
主Agent收集结果，继续 Round3-4
```

### 为什么这样设计

1. **工具调用是 Agent 的能力** - sessions_spawn 是工具，只有 Agent 能调用
2. **sindris_executor 是辅助** - 返回结构化数据帮助规划
3. **分离关注点** - 规划与执行分离，更灵活

### plan()方法使用

```python
# 主Agent调用方式
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

# 主Agent根据subtasks列表，自己调用sessions_spawn执行：
for subtask in plan['subtasks']:
    sessions_spawn(
        task=subtask['title'],
        runtime="subagent",
        timeoutSeconds=subtask['timeout']
    )
```

---

## 三、快速开始

### 触发方式

在对话中说出以下任一关键词即可激活Sindri's流程：

| 触发词 | 说明 |
|--------|------|
| `启动Sindri's` | 开始完整A2v3流程 |
| `A2流程` | 开始A2v3协作 |
| `多Agent协作` | 启动团队协作 |
| `执行A2` | 快速启动 |
| `审计` | **启动审计专业团队** |

### 激活示例

```
用户：解决Mimir-Core两套并行路径问题
    ↓
主Agent识别触发词 → 启动Sindri's Round1

用户：审计sindris角色质量
    ↓
主Agent识别"审计" → 启动审计专业团队
```

### 审计团队配置

当任务包含"审计"、"评估"、"审查"、"review"、"audit"等关键词时，自动使用**审计专业团队**：

| 角色 | 职责 |
|------|------|
| **Code Reviewer** | 代码审查 |
| **Security Engineer** | 安全审计 |
| **QA Lead** | 质量评估 |
| **Technical Writer** | 文档审计 |

**审计团队触发条件**：
- 任务包含"审计"、"评估"、"审查"、"review"、"audit"、"assess"
- 任务包含"质量检查"、"代码检查"、"安全检查"
- 任务包含"评分"、"评级"、"打分"、"评价"、"评审"

**审计团队 vs 开发团队**：

| 维度 | 开发团队 | 审计团队 |
|------|---------|---------|
| 核心角色 | Staff Engineer, Debugger | Code Reviewer, Security Engineer |
| 目标 | 实现功能 | 发现问题 |
| 视角 | 如何做出来 | 哪里有问题 |
| 适用场景 | 功能开发、代码实现 | 代码审计、质量评估、安全审查 |

---

### 角色改进分配规则（Role Evolution Distributor）

当sindris识别到"改进角色"任务时，自动应用以下分配规则：

#### 分配矩阵

| 被改进角色category | 问题类型 | 改进角色 | 负责改进 |
|-------------------|----------|----------|----------|
| coordination | 架构不匹配sindri | **Software Architect** | Agents Orchestrator |
| product | 文档结构/工作流 | **Technical Writer** | Product Manager |
| engineering | 代码质量/接口契约 | **Code Reviewer** | Staff Engineer, Frontend Developer |
| engineering | 安全调试/多语言 | **Security Engineer** | Debugger |
| testing | 测试方法论/sindri集成 | **QA Lead** | Reality Checker, API Tester |

#### 分配决策树

```
被改进角色是什么category？
    ↓
该category对应什么问题？
    ↓
分配最合适的改进角色
```

**决策优先级**：
1. **架构问题** → Software Architect（最高优先级）
2. **安全问题** → Security Engineer
3. **文档问题** → Technical Writer
4. **代码质量问题** → Code Reviewer
5. **测试问题** → QA Lead

#### 改进团队组建模板

```
改进任务：改进{被改进角色}
    ↓
根据分配矩阵确定改进角色
    ↓
组建改进团队：
  - Round1: Software Architect 规划改进方案
  - Round2: 各改进角色并行执行
  - Round3: Technical Writer 验收文档质量
```

#### 触发条件

当任务包含以下关键词时，触发角色改进分配：
- "改进角色"
- "优化角色"
- "升级角色"
- "完善角色"
- "修复角色"
- 刘哥说"用sindri流程改进"

### 角色匹配规则

#### 规则一：固定小组优先

**编程开发类任务**，直接使用**固定小组**，不自动匹配：

| 小组 | 角色 | 用途 |
|------|------|------|
| **架构组** | engineering_software_architect | 系统架构设计 |
| **开发组** | engineering_senior_developer | 核心代码开发 |
| **验证组** | testing_api_tester + testing_reality_checker | 测试验证 |

**触发词**：编程开发 / sindris进化 / MIMIR升级 / 代码任务

#### 规则二：其他任务类型自动匹配

| 任务类型 | 自动匹配 |
|----------|----------|
| 架构设计类 | Software Architect |
| 代码开发类 | Senior Developer |
| 评审验证类 | API Tester / Reality Checker |
| 写作文档类 | Technical Writer |
| 工作流设计 | Workflow Architect |

### 执行流程概览

```
Step 1: 审计规划 → 角色匹配 → 并行分析 → 验收
Step 2: 修复执行 → 动作拆分 → 串行写入 → 逐个验收
Step 3: Ralph验证（强制机制）→ 3轮验证 → 验证修复是否真实
Step 4: 审查完成 → 整体验证 → 模块集成
Step 5: Git + MEMORY → 交付 + 记录
```

> ⚠️ **Step 3 = Ralph验证**：这是强制机制，不能跳过。Ralph确保修复真的被完成，而不是报告完成。

### Step 3 代码示例

```python
# subtask.verify 是 List[str]，包含验证点描述
verify_items = []
for v in subtask.verify:
    verify_items.append({
        "name": v,
        "description": v,
        "check_fn": sindris._default_impl_check  # 白名单内的默认检查
    })

result = await sindris.verify_with_ralph(
    task_name=subtask.title,
    verify_items=verify_items
)

# result = {
#     "passed": True/False,
#     "total_checks": N,
#     "passed_checks": N,
#     "issues": [...]
# }

if not result["passed"]:
    # 验证失败 → 重试或上报
```

---

## 四、核心概念

### 1.1 角色+类型化工具约束

每个角色继承178角色库，但需要声明**工具类型约束**：

```python
class RoleConfig:
    name: str                    # 来自178库，如 "engineering_software_architect"
    subagent_type: str          # Explore | Plan | Verification | General
    allowed_tools: List[str]    # 工具白名单
    max_retries: int          # 最大重试次数（默认1）
```

**工具类型定义**（来自claw-code）：

| 类型 | 可用工具 | 说明 |
|------|---------|------|
| `Explore` | read, glob, grep, web_fetch, web_search | 探索研究 |
| `Plan` | + TodoWrite, sessions_send | 规划分解 |
| `Verification` | + bash, exec (只读测试) | 验证测试 |
| `General` | 全部工具 | 通用执行 |
| `ReadOnly` | read, glob, grep | 只读观察 |

### 1.2 子代理生命周期

外部子代理通过子代理状态机管理：

```python
class SubAgentState(Enum):
    CREATE = "create"           # 创建
    OBSERVE = "observe"        # 观察（检测信任门）
    READY = "ready"             # 就绪
    RUNNING = "running"        # 执行中
    RESTART = "restart"        # 重启
    COMPLETE = "complete"      # 完成
    FAILED = "failed"          # 失败
```

**信任门（Trust Gate）**：每个任务的验收条件

### 1.3 JSONL执行日志

```jsonl
{"type":"round","round":1,"phase":"planning","status":"start"}
{"type":"agent","id":"SoftwareArchitect","role":"engineering_software_architect","state":"create"}
{"type":"verification","agent":"SoftwareArchitect","output":"/tmp/decouple_architecture.json","result":"pass"}
{"type":"agent","id":"Developer","role":"engineering_senior_developer","state":"create"}
{"type":"verification","agent":"Developer","file":"interfaces/imemory_vault.py","result":"fail","reason":"file_not_found"}
{"type":"retry","agent":"Developer","attempt":1,"reason":"file_not_found"}
{"type":"agent","id":"Developer","role":"engineering_senior_developer","state":"restart"}
```

---

## 五、执行流程

### 流程概览

```
Step 1: 规划 → sindris.plan(task) → subtasks（含role/title/verify）
Step 2: 执行 → sessions_spawn子代理 → sessions_yield等待
Step 3: 验证 → verify_with_ralph() → 强制（失败则重试/上报）
Step 4: 完成 → Git提交 + MEMORY更新
```

**⚠️ 核心原则**：sindris执行必须由主代理协调，不能只调用plan()就结束！

### 代码模板

```python
# Step 1: 规划
plan = await sindris.plan("任务描述")

# Step 2: 按Round执行
for subtask in plan['subtasks']:
    spawn(
        task=f"你是{subtask.role}。请完成：{subtask.title}",
        runtime="subagent",
        timeoutSeconds=subtask.get('timeout', 300)
    )
    sessions_yield()  # ← 必须调用！等待子代理完成

# Step 3: 强制验证
verify_items = [{"name": v, "description": v, "check_fn": sindris._default_impl_check}
                for v in subtask.verify]
result = await sindris.verify_with_ralph(task_name=subtask.title, verify_items=verify_items)

# Step 4: Git提交 + MEMORY更新
```

### sessions_yield() 关键说明

**作用**：结束当前turn → 等待completion事件 → 结果返回下一条消息

| 错误做法 | 正确做法 |
|----------|----------|
| `plan() → spawn() → 直接返回` | `plan() → spawn() → yield() → 收集结果` |

**⚠️ yield后必须验证**：文件存在？内容正确？trust_gate通过？

### 会话工具对照

| 工具 | 作用 |
|------|------|
| `sessions_spawn` | 启动子代理 |
| `sessions_yield` | 等待completion（启动后必须调用） |
| `sessions_send` | 向子代理发消息（干预时） |
| `sessions_list` | 查看子代理状态 |

### 关键约束

- ⚠️ Step 3验证是强制步骤，不能跳过
- ⚠️ sessions_yield()后必须验证文件/代码真实存在
- ⚠️ 验证失败则自动重试（1次），还失败则上报刘哥
- ⚠️ OMX锤炼：每次子代理完成后自动触发GStackPro Review

---

## 八、恢复策略（6种）

来自Claude Code的自动恢复机制：

| 恢复策略 | 触发条件 | 恢复方式 |
|----------|----------|----------|
| `retry_file_not_found` | 文件不存在 | 重试创建 |
| `retry_verification_fail` | 验收失败 | 诊断+重试 |
| `escalate_permission` | 权限问题 | 立即上报 |
| `escalate_timeout` | 超时 | 延长+重试 |
| `diagnose_interface_mismatch` | 接口不匹配 | 诊断+修复建议 |
| `report_unknown` | 未知错误 | 记录+上报 |

---

## 九、角色库集成

> 共37个有MD文档的核心角色（完整列表在 roles/ 目录）
> 来源：~/.openclaw/skills/sindris/roles/

### 常用角色

| 角色 | ID | 说明 |
|------|-----|------|
| Software Architect | engineering_software_architect | 系统设计、DDD |
| Senior Developer | engineering_senior_developer | Laravel/FluxUI, Three.js |
| Code Reviewer | engineering_code_reviewer | 代码审查 |
| Frontend Developer | engineering_frontend_developer | React/Vue/Angular |
| DevOps Automator | engineering_devops_automator | CI/CD、基础设施自动化 |
| SRE | engineering_sre | SLO、错误预算、可观测性 |
| Technical Writer | engineering_technical_writer | 开发文档 |
| Staff Engineer | engineering_staff_engineer | 技术战略 |
| Release Engineer | engineering_release_engineer | 发布管理 |
| Incident Response Commander | engineering_incident_response_commander | 事故管理 |
| Security Engineer | engineering_security_engineer | 威胁建模、漏洞评估 |
| AI Engineer | engineering_ai_engineer | ML模型开发、部署 |
| AI/ML Engineer | engineering_ai_ml_engineer | 机器学习系统 |
| QA Lead | testing_qa_lead | 测试策略、质量把控 |
| QA Engineer | testing_qa_engineer | 测试用例、自动化 |
| API Tester | testing_api_tester | API验证 |
| Performance Benchmarker | testing_performance_benchmarker | 性能测量 |
| Performance Engineer | testing_performance_engineer | 性能优化 |
| Reality Checker | testing_reality_checker | 证据基验证（sindri Round3默认） |
| QA Reporter | testing_qa_reporter | 测试报告 |
| QA Automator | testing_autoplan | 测试规划 |
| SRE | testing_sre | 测试SRE |
| Product Manager | product_manager | 产品生命周期 |
| Experiment Tracker | project_management_experiment_tracker | A/B测试管理 |
| Agents Orchestrator | agents_orchestrator | 管道协调 |
| GStack Auto Plan | gstack_autoplan | GStack自动规划 |
| GStack CSO | gstack_cso | GStack首席战略官 |
| GStack Debugger | gstack_debugger | GStack调试 |
| GStack Second Opinion | gstack_second_opinion | GStack第二意见 |
| Strategy CEO/Founder | strategy_ceo_founder | 战略CEO/Founder |
| Strategy CSO | strategy_cso | 首席战略官 |
| Strategy Second Opinion | strategy_second_opinion | 第二意见 |
| Strategy Technical Writer | strategy_technical_writer | 技术写作 |
| Strategy YC Office Hours | strategy_yc_office_hours | YC Office Hours |
| Sindri QA Lead | sindri_qa_lead | sindri QA Lead |
| Sindri Canary Monitor | sindri_canary_monitor | 金丝雀监控 |


## 十、执行日志格式

### 6.1 JSONL格式
```jsonl
{"type":"plan_complete","task_id":"xxx","subtasks":5}
{"type":"subtask_start","role":"architect","title":"分析架构"}
{"type":"subtask_complete","role":"architect","verified":true}
```
```

### 6.2 日志位置

```
~/.openclaw/skills/sindris/.logs/sindris_YYYYMMDD.jsonl
```

**日志格式**：
```json
{"timestamp": "2026-04-18T03:31:18.166161", "session_id": "sindris_xxx", "event_type": "plan_complete", ...}
{"timestamp": "2026-04-18T03:31:18.166503", "session_id": "sindris_xxx", "event_type": "execution", ...}
```

**事件类型**：
- `plan_start` - 规划开始
- `plan_complete` - 规划完成
- `execution` - 子代理执行
- `verification` - 验收结果
- `error` - 错误

---

## 十五、OMX持久化集成

sindris与OMX深度集成，提供任务清单和执行追踪：

| 功能 | OMX模块 |
|------|---------|
| 任务清单 | omx_tasks |
| 执行日志 | omx_ledger |
| 审查队列 | omx_reviews |

详细API见 [omx_integrator.py](scripts/omx_integrator.py)

*Sindri's v1.1*

---


