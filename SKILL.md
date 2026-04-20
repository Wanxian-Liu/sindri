---
name: sindris
version: "3.6"
license: MIT
copyright: "2026 琬弦 (Wanxian)"
description: |
  织界统一协调系统 v3.6 - 多Agent协作执行引擎
  
  基于sindris Round1-4流程，参考oh-my-codex v2设计，
  整合织界中枢模块（熔断/投票/worktree）和OMX持久化。
  
  v3.6更新：
  - Phase 1: OpenClaw Hook深度集成（sindri-executor-reminder v2.0）
  - Phase 2: runTimeoutSeconds参数确认正确
  - Phase 3: 真正集成Ralph 3轮验证机制
  - verify_with_ralph()方法真正调用RalphLoop
  - verify_subtask_result()用于子任务验证
  - 不再是假的验证通过
  
  ⚠️ 重要：sindris是规划器+协调器，执行必须由主代理调用sessions_spawn
  ⚠️ 重要：启动子代理后必须调用sessions_yield()等待结果
  ⚠️ 重要：OMX锤炼在每次子代理完成后自动触发
  
  核心组件：
  1. sindris_executor.py - 唯一执行引擎（含plan/run两个方法）
  2. agent_executor.py - 三级降级执行器
  3. omx_integrator.py - OMX持久化层
  4. sindris_tmux_manager.py - tmux Worker运行时
  5. 织界中枢模块 - 熔断/投票/worktree
  6. 178角色库 - 专业角色匹配
  7. safety_policy.py - 危险操作拦截（任务级别）
  8. review_logger.py - 结果review记录
  9. telemetry_collector.py - 运行时遥测收集
  10. memory_manager.py - 任务记忆管理
  11. task_queue.py - 任务队列和阻塞管理
  12. sindris_hud.py - 实时状态显示
  
  触发条件：
  - 复杂任务需要拆分为子任务
  - 需要多角色协作（178角色库匹配）
  - 需要外部验收机制保证质量
  - 需要失败自动恢复能力
  
  v1.9更新：
  - match_roles.py: 优化角色匹配逻辑
    * 添加GENERAL_TERMS通用词列表
    * 通用词匹配大幅降低分数
    * 避免"python, bug"触发Blender等问题
  
  v1.8更新：
  - 完善任务理解与fallback机制
  
  v1.5更新（执行层增强）：
  - agent_executor.py: 三级降级执行器
    * Level 1: sessions_spawn（OpenClaw内置）
    * Level 2: DeepSeek API直接调用
    * Level 3: 本地代码执行（兜底）
    * 绕过sessions_spawn的20%失败率问题
  
  v1.3更新（Phase1+Phase2+Phase3+Phase4）：
  - Phase1: safety_policy + review_logger
  - Phase2: telemetry_collector + memory_manager
  - Phase3: task_queue + blocked管理
  - Phase4: sindris_hud
  
  v1.2更新：
  - 新增plan()方法，返回subtasks列表供sessions_spawn执行
  - 修复sessions_spawn对接问题（真实执行）
---

# Sindri's A2v3 多Agent协作流程

> **Sindri's** — 冰岛语"真挚、纯粹" | 意为每个协作都是真诚的、有目的的

---

## 零、架构说明

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

## 一、快速开始

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
Round1: 规划 → 角色匹配 → 并行分析 → 验收
Round2: 执行 → 动作拆分 → 串行写入 → 逐个验收
Round3: 集成 → 整体验证
Round4: 完成 → 交付 + Git提交
```

---

## 二、核心概念

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

## 三、执行流程

### 2.1 流程概览

```
用户请求
    ↓
【Round1: 规划】FastPath检查
    ↓ 缓存命中? → 直接用缓存
    ↓ 缓存未命中
    ↓ 角色匹配（178库）→ 选3-5个
    ↓ 并行分析（带工具约束）
    ↓ [主Agent验收] → 写入JSONL
    ↓
【Round2: 执行】动作拆分
    ↓ 角色+精确动作（1角色=1动作）
    ↓ 并行（只读）+ 串行（写入）
    ↓ [子代理管理] → 失败自动Restart
    ↓ [逐个验收] → 写入JSONL
    ↓
【Round3: 集成】
    ↓ [最终验收] → 写入JSONL
    ↓
【Round4: 完成】
```

### 2.2 Round1：规划阶段

**步骤**：
1. 检查FastPath缓存
2. 匹配178角色库，选3-5个专业角色
3. 并行分析（每个角色一个精确任务）
4. 汇总方案
5. **主Agent外部验收**
6. 写入JSONL

**角色匹配示例**：
```
任务：解决Mimir-Core两套并行路径

匹配角色：
- Software Architect (engineering_software_architect) → 架构设计
- Workflow Architect (specialized_workflow_architect) → 工作流规范
- Agents Orchestrator (agents_orchestrator) → 协调评审
```

### 2.3 Round2：执行阶段

**核心原则**：1角色=1精确动作

**动作拆分示例**：
```
旧方式（粒度太粗）：
  子代理 → "创建interfaces目录和所有文件"（1个任务含5个步骤）

新方式（精细化）：
  子代理A1 → "创建interfaces目录"
  子代理A2 → "创建imemory_vault.py"
  子代理A3 → "创建file_system_adapter.py"
  子代理A4 → "验证接口契约"
```

**并行策略**：
```
只读动作（分析、验证、检查）→ 并行执行（最多3-5个）
写入动作（创建文件、修改代码）→ 串行执行
```

**子代理管理**：
```python
def execute_with_worker(task, config):
    worker = create_worker(config)
    for attempt in range(config.max_retries):
        agent.state = SubAgentState.RUNNING
        result = worker.execute(task)
        if verify(result):  # 信任门
            agent.state = SubAgentState.COMPLETE
            return result
        else:
            agent.state = SubAgentState.RESTART
    agent.state = SubAgentState.FAILED
    return result
```

### 2.4 Round3：集成阶段

- 验证模块间集成
- 检查依赖关系
- 执行集成测试

### 2.5 Round4：完成阶段

- 输出最终成果
- 更新MEMORY.md
- 清理临时文件

---

## 四、完整执行流程（⚠️ 必须严格执行）

### ⚠️ 核心原则

**sindris执行必须由主代理（你）协调，不能只调用plan()就结束！**

### 2.1 完整流程图

```
主代理（琬弦）
    ↓
① 调用 sindris.plan(task)
    ↓ 获取subtasks列表（含role/title/verify）
    ↓
② Round1：sessions_spawn(Round1任务)
    ↓ 启动Software Architect/Product Manager
    ↓
③ sessions_yield() ← 等待子代理完成
    ↓ 接收completion事件
    ↓
④ 收集Round1结果 → 决定Round2
    ↓
⑤ Round2：sessions_spawn(Round2任务)
    ↓ 启动Senior Developer（可并行多个）
    ↓
⑥ sessions_yield() ← 等待子代理完成
    ↓
⑦ OMX锤炼：自动触发GStackPro Review
    ↓
⑧ 收集Round2结果 → 决定Round3
    ↓
⑨ Round3：sessions_spawn(Round3任务)
    ↓ 启动API Tester + Reality Checker
    ↓
⑩ sessions_yield() ← 等待子代理完成
    ↓
⑪ 收集Round3结果 → 最终报告
    ↓
⑫ 更新MEMORY.md + Git提交
```

### 2.2 关键点：sessions_yield()

**这是我一直忘记调用的！**

`sessions_yield()` 的作用：
- 故意结束当前turn
- 等待子代理的completion事件
- 结果作为下一条消息返回

**错误做法：**
```
plan() → spawn() → 直接返回 → 子代理还在跑
```

**正确做法：**
```
plan() → spawn() → yield() → 等待completion → 收集结果 → 继续
```

### 2.3 OMX锤炼集成

每次子代理完成后自动触发：
```python
# gstack_hook.on_worker_complete() 自动调用
# 触发GStackPro Paranoid Review
# 审查代码质量和安全问题
```

### 2.4 实际代码模板

```python
# ===== sindris完整执行模板 =====

# ① 规划
plan = await sindris.plan("你的任务描述")
print(f"生成了 {len(plan['subtasks'])} 个子任务")

# ② Round1：规划阶段
round1_tasks = [s for s in plan['subtasks'] if s['phase'] == 'round1']
for task in round1_tasks:
    spawn(
        task=f"你是{task['role']}。请完成：{task['title']}",
        runtime="subagent",
        timeoutSeconds=task.get('timeout', 300)
    )

# ③ 必须yield！
yield()  # 等待Round1完成

# ④ Round2：执行阶段
round2_tasks = [s for s in plan['subtasks'] if s['phase'] == 'round2']
for task in round2_tasks:
    spawn(
        task=f"你是{task['role']}。请完成：{task['title']}",
        runtime="subagent",
        timeoutSeconds=task.get('timeout', 600)
    )

# ⑤ 必须yield！
yield()  # 等待Round2完成 + OMX锤炼自动触发

# ⑥ Round3：审查阶段
round3_tasks = [s for s in plan['subtasks'] if s['phase'] == 'round3']
for task in round3_tasks:
    spawn(
        task=f"你是{task['role']}。请验证：{task['title']}",
        runtime="subagent",
        timeoutSeconds=task.get('timeout', 300)
    )

# ⑦ 必须yield！
yield()  # 等待Round3完成

# ⑧ 完成！
print("sindris执行完成")
```

### 2.5 会话工具对照表

| 工具 | 作用 | 何时使用 |
|------|------|----------|
| `sessions_spawn` | 启动子代理 | 每个Round开始时 |
| `sessions_yield` | 等待completion | 启动子代理后必须调用！|
| `sessions_send` | 向子代理发消息 | 需要干预时 |
| `sessions_list` | 查看子代理状态 | 调试时 |
| `sessions_history` | 获取执行历史 | 审查结果时 |
| `subagents` | 控制子代理 | steer/kill时 |

### 2.6 重要约束

| 约束 | 说明 |
|------|------|
| sessions_yield | 启动子代理后必须调用，否则结果丢失 |
| 会话管理 | 子Agent在独立session运行，完成后announce |
| 工具限制 | 子Agent工具由 agentId 决定，不是 sindris 决定 |
| 生命周期 | 主Agent监控子Agent状态，失败时决定重试或放弃 |
| OMX锤炼 | 每次子代理完成后自动触发GStackPro Review |

---

## 五、验收机制

### 3.1 主Agent外部验收原则

**核心**：不让子代理验证自己的成果

```
子代理执行 → 主Agent验收（不是子代理自验）
    ↓ 通过
    ↓ 失败 → 自动重试（1次）→ 还失败则上报
```

### 3.2 验收检查清单

| 检查项 | 方法 |
|--------|------|
| 文件存在 | exec: `ls -la path` |
| 内容正确 | read: 抽查关键代码 |
| 导入成功 | exec: `python3 -c "import module"` |
| 功能正常 | exec: `python3 -c "test_function()"` |

### 3.3 信任门定义

每个任务必须有明确的**信任门条件**：

```python
trust_gate = {
    "file_created": "interfaces/imemory_vault.py",
    "interface_complete": "IMemoryVault定义了5个方法",
    "import_success": "from interfaces.imemory_vault import IMemoryVault"
}
```

---

## 六、恢复策略（6种）

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

## 七、角色库集成

### 5.1 角色库完整详情

> 来源：~/.openclaw/skills/sindris/scripts/roles_registry.json
> 共178个角色，按category分类

#### ACADEMIC

**Psychologist** (`academic_psychologist`) — Expert in human behavior, personality theory, motivation, and cognitive patterns
**Historian** (`academic_historian`) — Expert in historical analysis, periodization, material culture
**Narratologist** (`academic_narratologist`) — Expert in narrative theory, story structure, character arcs
**Geographer** (`academic_geographer`) — Expert in physical and human geography, climate systems
**Anthropologist** (`academic_anthropologist`) — Expert in cultural systems, rituals, kinship, belief systems

#### BLENDER

**Blender Add-on Engineer** (`blender_addon_engineer`) — Builds Python add-ons, asset validators, exporters

#### COORDINATION

**Handoff Templates** (`handoff_templates`) — Coordination templates
**Agent Activation Prompts** (`agent_activation_prompts`) — Agent coordination prompts

#### DESIGN

**UI Designer** (`design_ui_designer`) — Visual design systems, component libraries
**Brand Guardian** (`design_brand_guardian`) — Brand identity development, consistency maintenance
**Inclusive Visuals Specialist** (`design_inclusive_visuals_specialist`) — Defeats systemic AI biases
**UX Architect** (`design_ux_architect`) — CSS systems, implementation guidance
**Whimsy Injector** (`design_whimsy_injector`) — Adding personality, delight, playful elements
**Visual Storyteller** (`design_visual_storyteller`) — Visual narratives, multimedia content
**Image Prompt Engineer** (`design_image_prompt_engineer`) — AI image generation prompts
**UX Researcher** (`design_ux_researcher`) — User behavior analysis, usability testing

#### ENGINEERING

**Mobile App Builder** (`engineering_mobile_app_builder`) — iOS/Android, cross-platform frameworks
**Threat Detection Engineer** (`engineering_threat_detection_engineer`) — SIEM, MITRE ATT&CK, threat hunting
**Software Architect** (`engineering_software_architect`) — System design, domain-driven design
**Frontend Developer** (`engineering_frontend_developer`) — React/Vue/Angular, UI implementation
**Data Engineer** (`engineering_data_engineer`) — Data pipelines, lakehouse, ETL/ELT
**AI Engineer** (`engineering_ai_engineer`) — ML model development, deployment
**Incident Response Commander** (`engineering_incident_response_commander`) — Production incident management
**WeChat Mini Program Developer** (`engineering_wechat_mini_program_developer`) — WXML/WXSS/WXS, WeChat API
**Code Reviewer** (`engineering_code_reviewer`) — Constructive feedback on correctness
**Backend Architect** (`engineering_backend_architect`) — Scalable system design, database architecture
**Security Engineer** (`engineering_security_engineer`) — Threat modeling, vulnerability assessment
**Filament Optimization Specialist** (`engineering_filament_optimization_specialist`) — PHP admin interfaces
**Technical Writer** (`engineering_technical_writer`) — Developer documentation, API references
**Git Workflow Master** (`engineering_git_workflow_master`) — Git workflows, branching strategies
**Email Intelligence Engineer** (`engineering_email_intelligence_engineer`) — Email data extraction
**AI Data Remediation Engineer** (`engineering_ai_data_remediation_engineer`) — Self-healing data pipelines
**Embedded Firmware Engineer** (`engineering_embedded_firmware_engineer`) — ESP32, ARM Cortex-M, FreeRTOS
**Feishu Integration Developer** (`engineering_feishu_integration_developer`) — Feishu bots, Bitable, Webhooks
**DevOps Automator** (`engineering_devops_automator`) — Infrastructure automation, CI/CD
**CMS Developer** (`engineering_cms_developer`) — Drupal, WordPress, custom plugins
**Autonomous Optimization Architect** (`engineering_autonomous_optimization_architect`) — API shadow-testing
**Senior Developer** (`engineering_senior_developer`) — Laravel/Livewire/FluxUI, Three.js
**Solidity Smart Contract Engineer** (`engineering_solidity_smart_contract_engineer`) — EVM, gas optimization
**SRE** (`engineering_sre`) — SLOs, error budgets, observability
**Database Optimizer** (`engineering_database_optimizer`) — PostgreSQL, MySQL, query optimization
**Rapid Prototyper** (`engineering_rapid_prototyper`) — Proof-of-concept, MVP creation

#### GAME-DEVELOPMENT

**Game Designer** (`game_designer`) — GDD authorship, player psychology, economy balancing
**Level Designer** (`level_designer`) — Layout theory, pacing, encounter design
**Game Audio Engineer** (`game_audio_engineer`) — FMOD/Wwise, adaptive music systems
**Technical Artist** (`technical_artist`) — Shaders, VFX, LOD pipelines
**Narrative Designer** (`narrative_designer`) — Branching dialogue, lore architecture

#### GODOT

**Godot Shader Developer** (`godot_shader_developer`) — Godot Shading Language, VisualShader
**Godot Gameplay Scripter** (`godot_gameplay_scripter`) — GDScript 2.0, node-based architecture
**Godot Multiplayer Engineer** (`godot_multiplayer_engineer`) — MultiplayerAPI, ENet/WebRTC

#### MARKETING

**Content Creator** (`marketing_content_creator`) — Multi-platform campaigns, brand storytelling
**Douyin Strategist** (`marketing_douyin_strategist`) — Douyin algorithm, viral video planning
**AI Citation Strategist** (`marketing_ai_citation_strategist`) — AEO/GEO, AI recommendation optimization
**LinkedIn Content Creator** (`marketing_linkedin_content_creator`) — Thought leadership, personal brand
**Reddit Community Builder** (`marketing_reddit_community_builder`) — Reddit culture navigation
**Livestream Commerce Coach** (`marketing_livestream_commerce_coach`) — Douyin, Kuaishou, Taobao Live
**Growth Hacker** (`marketing_growth_hacker`) — Viral loops, conversion funnels
**SEO Specialist** (`marketing_seo_specialist`) — Technical SEO, content optimization
**Instagram Curator** (`marketing_instagram_curator`) — Visual storytelling, community building
**Weibo Strategist** (`marketing_weibo_strategist`) — Trending topics, Super Topic
**Baidu SEO Specialist** (`marketing_baidu_seo_specialist`) — Chinese search engine ranking
**Xiaohongshu Specialist** (`marketing_xiaohongshu_specialist`) — Lifestyle content, trend strategies
**Podcast Strategist** (`marketing_podcast_strategist`) — Xiaoyuzhou, Ximalaya
**Bilibili Content Strategist** (`marketing_bilibili_content_strategist`) — UP主 growth, danmaku culture
**WeChat Official Account Manager** (`marketing_wechat_official_account`) — Subscriber engagement
**Kuaishou Strategist** (`marketing_kuaishou_strategist`) — Lower-tier city markets, grassroots growth
**Twitter Engager** (`marketing_twitter_engager`) — Real-time engagement, thought leadership
**Carousel Growth Engine** (`marketing_carousel_growth_engine`) — TikTok/Instagram carousel generation
**Video Optimization Specialist** (`marketing_video_optimization_specialist`) — YouTube optimization
**Private Domain Operator** (`marketing_private_domain_operator`) — WeCom private domain ecosystems
**TikTok Strategist** (`marketing_tiktok_strategist`) — Viral content, algorithm optimization
**China Market Localization Strategist** (`marketing_china_market_localization_strategist`) — Full-stack China localization
**Cross-Border E-Commerce Specialist** (`marketing_cross_border_ecommerce`) — Amazon, Shopee, Lazada
**Zhihu Strategist** (`marketing_zhihu_strategist`) — Question-answering strategy
**Short-Video Editing Coach** (`marketing_short_video_editing_coach`) — CapCut Pro, Premiere Pro
**App Store Optimizer** (`marketing_app_store_optimizer`) — ASO, conversion optimization
**China E-Commerce Operator** (`marketing_china_ecommerce_operator`) — Taobao, Tmall, JD
**Book Co-Author** (`marketing_book_co_author`) — Thought-leadership books
**Social Media Strategist** (`marketing_social_media_strategist`) — LinkedIn, Twitter campaigns

#### PAID-MEDIA

**Ad Creative Strategist** (`paid_media_creative_strategist`) — Ad copywriting, RSA optimization
**Paid Social Strategist** (`paid_media_paid_social_strategist`) — Meta, LinkedIn, TikTok
**Search Query Analyst** (`paid_media_search_query_analyst`) — Negative keyword architecture
**Paid Media Auditor** (`paid_media_auditor`) — Google Ads, Microsoft Ads audit
**Programmatic & Display Buyer** (`paid_media_programmatic_buyer`) — DV360, trade desk
**Tracking & Measurement Specialist** (`paid_media_tracking_specialist`) — GTM, GA4, attribution
**PPC Campaign Strategist** (`paid_media_ppc_strategist`) — Large-scale search, shopping

#### PLAYBOOKS

**Phase 0-6** — Discovery, Strategy, Foundation, Build, Hardening, Launch, Operate

#### PRODUCT

**Behavioral Nudge Engine** (`product_behavioral_nudge_engine`) — User motivation maximization
**Trend Researcher** (`product_trend_researcher`) — Emerging trends, competitive analysis
**Product Manager** (`product_manager`) — Full product lifecycle ownership
**Sprint Prioritizer** (`product_sprint_prioritizer`) — Agile sprint planning
**Feedback Synthesizer** (`product_feedback_synthesizer`) — User feedback extraction

#### PROJECT-MANAGEMENT

**Studio Producer** (`project_management_studio_producer`) — Multi-project portfolio management
**Studio Operations** (`project_management_studio_operations`) — Day-to-day efficiency
**Project Shepherd** (`project_management_project_shepherd`) — Cross-functional coordination
**Senior Project Manager** (`project_manager_senior`) — Specs to tasks conversion
**Experiment Tracker** (`project_management_experiment_tracker`) — A/B test management
**Jira Workflow Steward** (`project_management_jira_workflow_steward`) — Jira-linked Git workflows

#### ROBLOX-STUDIO

**Roblox Avatar Creator** (`roblox_avatar_creator`) — UGC item creation, accessory rigging
**Roblox Experience Designer** (`roblox_experience_designer`) — Engagement loop, monetization
**Roblox Systems Scripter** (`roblox_systems_scripter`) — Luau, RemoteEvents, DataStore

#### RUNBOOKS

**Scenario Incident Response** (`scenario_incident_response`) — Incident response playbooks
**Scenario Enterprise Feature** (`scenario_enterprise_feature`) — Enterprise feature scenarios
**Scenario Marketing Campaign** (`scenario_marketing_campaign`) — Marketing campaign scenarios
**Scenario Startup Mvp** (`scenario_startup_mvp`) — Startup MVP scenarios

#### SALES

**Discovery Coach** (`sales_discovery_coach`) — Elite discovery methodology
**Deal Strategist** (`sales_deal_strategist`) — MEDDPICC qualification, win planning
**Sales Coach** (`sales_coach`) — Rep development, pipeline review
**Account Strategist** (`sales_account_strategist`) — Land-and-expand execution
**Pipeline Analyst** (`sales_pipeline_analyst`) — Pipeline health diagnostics
**Sales Engineer** (`sales_engineer`) — Technical discovery, demo engineering
**Proposal Strategist** (`sales_proposal_strategist`) — RFP transformation
**Outbound Strategist** (`sales_outbound_strategist`) — Multi-channel prospecting

#### SPATIAL-COMPUTING

**Terminal Integration Specialist** (`terminal_integration_specialist`) — SwiftTerm integration
**XR Cockpit Interaction Specialist** (`xr_cockpit_interaction_specialist`) — Cockpit-based XR controls
**macOS Spatial/Metal Engineer** (`macos_spatial_metal_engineer`) — Swift, Metal, visionOS
**XR Interface Architect** (`xr_interface_architect`) — AR/VR/XR interface design
**XR Immersive Developer** (`xr_immersive_developer`) — WebXR development
**visionOS Spatial Engineer** (`visionos_spatial_engineer`) — SwiftUI volumetric interfaces

#### SPECIALIZED

**Blockchain Security Auditor** (`blockchain_security_auditor`) — Smart contract auditing
**Agentic Identity & Trust Architect** (`agentic_identity_trust`) — Identity for AI agents
**Civil Engineer** (`specialized_civil_engineer`) — Eurocode, ACI, structural analysis
**Recruitment Specialist** (`recruitment_specialist`) — Hiring platforms, talent assessment
**Identity Graph Operator** (`identity_graph_operator`) — Shared identity graph
**Sales Data Extraction Agent** (`sales_data_extraction_agent`) — Excel monitoring, sales metrics
**Corporate Training Designer** (`corporate_training_designer`) — Training needs analysis
**Salesforce Architect** (`specialized_salesforce_architect`) — Multi-cloud design
**Accounts Payable Agent** (`accounts_payable_agent`) — Payment processing
**LSP/Index Engineer** (`lsp_index_engineer`) — Language Server Protocol
**Automation Governance Architect** (`automation_governance_architect`) — n8n automation audits
**Agents Orchestrator** (`agents_orchestrator`) — Pipeline manager, development orchestration
**Supply Chain Strategist** (`supply_chain_strategist`) — Supplier development
**ZK Steward** (`zk_steward`) — Zettelkasten knowledge-base
**Cultural Intelligence Strategist** (`specialized_cultural_intelligence_strategist`) — CQ for exclusion detection
**Developer Advocate** (`specialized_developer_advocate`) — Community building, DX
**Healthcare Marketing Compliance Specialist** (`healthcare_marketing_compliance`) — China healthcare compliance
**Korean Business Navigator** (`specialized_korean_business_navigator`) — Korean business culture
**Document Generator** (`specialized_document_generator`) — PDF, PPTX, DOCX generation
**Report Distribution Agent** (`report_distribution_agent`) — Sales report distribution
**Compliance Auditor** (`compliance_auditor`) — SOC 2, ISO 27001, HIPAA
**Government Digital Presales Consultant** (`government_digital_presales_consultant`) — China ToG market
**Workflow Architect** (`specialized_workflow_architect`) — Complete workflow trees
**Model QA Specialist** (`specialized_model_qa`) — ML model auditing
**MCP Builder** (`specialized_mcp_builder`) — Model Context Protocol servers
**French Consulting Market Navigator** (`specialized_french_consulting_market`) — French ESN/SI ecosystem
**Study Abroad Advisor** (`study_abroad_advisor`) — US, UK, Canada applications
**Data Consolidation Agent** (`data_consolidation_agent`) — Live reporting dashboards

#### STRATEGY

**Nexus Strategy** (`nexus_strategy`) — Strategy coordination
**Quickstart** (`QUICKSTART`) — Quick start guides
**Executive Brief** (`EXECUTIVE_BRIEF`) — Executive briefing

#### SUPPORT

**Infrastructure Maintainer** (`support_infrastructure_maintainer`) — System reliability
**Analytics Reporter** (`support_analytics_reporter`) — Dashboards, KPIs
**Executive Summary Generator** (`support_executive_summary_generator`) — McKinsey SCQA frameworks
**Legal Compliance Checker** (`support_legal_compliance_checker`) — Multi-jurisdiction compliance
**Finance Tracker** (`support_finance_tracker`) — Financial planning, budget management
**Support Responder** (`support_support_responder`) — Multi-channel support

#### TESTING

**Performance Benchmarker** (`testing_performance_benchmarker`) — Performance measurement
**Tool Evaluator** (`testing_tool_evaluator`) — Technology assessment
**Reality Checker** (`testing_reality_checker`) — Evidence-based certification
**Workflow Optimizer** (`testing_workflow_optimizer`) — Process improvement
**Test Results Analyzer** (`testing_test_results_analyzer`) — Quality metrics
**Accessibility Auditor** (`testing_accessibility_auditor`) — WCAG, screen reader testing
**Evidence Collector** (`testing_evidence_collector`) — Screenshot-based QA
**API Tester** (`testing_api_tester`) — API validation, performance testing

#### UNITY

**Unity Shader Graph Artist** (`unity_shader_graph_artist`) — Shader Graph, HLSL
**Unity Multiplayer Engineer** (`unity_multiplayer_engineer`) — Netcode, Unity Gaming Services
**Unity Editor Tool Developer** (`unity_editor_tool_developer`) — Custom EditorWindows
**Unity Architect** (`unity_architect`) — ScriptableObjects, decoupled systems

#### UNREAL-ENGINE

**Unreal Multiplayer Architect** (`unreal_multiplayer_architect`) — Actor replication, GameMode
**Unreal Systems Engineer** (`unreal_systems_engineer`) — Nanite, Lumen, GAS
**Unreal World Builder** (`unreal_world_builder`) — World Partition, Landscape
**Unreal Technical Artist** (`unreal_technical_artist`) — Material Editor, Niagara

### 5.2 常用角色映射

| 任务类型 | 推荐角色 | ID |
|---------|---------|-----|
| 架构设计 | Software Architect | `engineering_software_architect` |
| 工作流设计 | Workflow Architect | `specialized_workflow_architect` |
| 协调管理 | Agents Orchestrator | `agents_orchestrator` |
| 接口验证 | API Tester | `testing_api_tester` |
| 质量审计 | Reality Checker | `testing_reality_checker` |
| 测试分析 | Test Results Analyzer | `testing_test_results_analyzer` |
| 研究分析 | Academic Psychologist | `academic_psychologist` |

### 5.3 角色+工具约束示例

```python
# 架构分析角色（只读工具）
architect_config = RoleConfig(
    name="engineering_software_architect",
    subagent_type="Explore",
    allowed_tools=["read", "glob", "grep", "exec"],
    max_retries=1
)

# 开发执行角色（全工具）
developer_config = RoleConfig(
    name="engineering_senior_developer",
    subagent_type="General",
    allowed_tools=["read", "write", "edit", "exec", "glob"],
    max_retries=2
)

# 验证角色（测试工具）
verifier_config = RoleConfig(
    name="testing_api_tester",
    subagent_type="Verification",
    allowed_tools=["read", "exec", "bash"],
    max_retries=1
)
```

---

## 八、执行日志格式

### 6.1 JSONL格式

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
{"type":"session_end","status":"success","outputs":["..."],"note":"outputs truncated for documentation"}
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

## 九、FastPath缓存

### 7.1 缓存检查点

```
Round1开始
    ↓
检查缓存：~/.openclaw/sessions/{session_id}/round1_cache.json
    ↓ 命中?
    ↓ 是 → 直接使用缓存结果，跳过分析
    ↓ 否 → 执行Round1
```

### 7.2 缓存失效条件

- 任务目标变更
- 角色配置变更
- 超过24小时

---

## 十、使用示例

### 8.1 完整执行示例

```
用户：解决Mimir-Core两套并行路径问题

【Round1】规划
    ↓ 匹配角色：Software Architect, Workflow Architect, Agents Orchestrator
    ↓ 并行分析
    ↓ 验收方案
    ↓
【Round2】执行
    ↓ 拆分动作：
    ↓   A1: 创建interfaces目录
    ↓   A2: 创建imemory_vault.py
    ↓   A3: 创建file_system_adapter.py
    ↓   A4: 验证接口（并行）
    ↓   A5: 改造gateway.py（串行）
    ↓   A6: 改造cli/commands.py（串行）
    ↓ 逐个验收
    ↓
【Round3】集成
    ↓ 验证整体集成
    ↓
【完成】
```

### 8.2 失败恢复示例

```
Developer执行：创建interfaces目录
    ↓
验证失败：文件不存在
    ↓
自动重试（attempt=1）
    ↓
再次失败
    ↓
上报主Agent：刘哥，Developer在创建interfaces目录时失败，需要手动介入
```

---

## 十一、与原A2流程对比

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

## 十二、注意事项

1. **信任门必须明确**：每个任务开始前定义清楚验收条件
2. **动作必须单一**：1角色=1动作，避免粒度太粗
3. **只读并行，写入串行**：遵循claw-code的编排策略
4. **保留178角色优势**：角色匹配是核心，不要为了拆分而拆分
5. **日志用于恢复**：失败时可以从JSONL恢复上下文

### 10.6 正确使用流程（重要）

**sindris_executor.py 提供两个核心方法**：

| 方法 | 作用 | 执行者 |
|------|------|--------|
| `plan()` | 返回子任务列表 | sindris内部 |
| `execute_sindris()` | 返回完整执行计划 | sindris内部 |
| `sessions_spawn()` | **执行子任务** | **主Agent（你）** |

**重要**：sindris只返回计划，**真正执行需要主Agent调用sessions_spawn**

```python
# 正确流程：

# 1. 获取执行计划
plan = await execute_sindris("任务描述", workspace_root="/path")

# 2. 主Agent按steps执行（sessions_spawn是工具调用，不是Python）
for step in plan["plan"]["round2"]["steps"]:
    # 在这里，主Agent调用sessions_spawn工具
    sessions_spawn(
        task=step["task"],
        timeout=step["timeout"]
    )

# 3. 汇总结果，完成Round3-4
```

**为什么不直接执行**：
- `sessions_spawn`是OpenClaw工具，不是Python API
- sindris_executor是Python库，运行在exec环境中
- 主Agent有sessions_spawn工具调用能力
- 所以：sindris规划 → 主Agent执行

---

*Sindri's v1.0 — 真诚、纯粹的多Agent协作*


---

## 十四、OMX持久化集成 (v1.1)

### 11.1 概述

sindris Round1-4 与 OMX 持久化模块深度集成，实现：
- **Round1**: `omx_tasks` 记录任务分解
- **Round2**: `omx_ledger` 记录执行日志
- **Round3**: `omx_reviews` 记录审查队列
- **Round4**: `omx_tasks` 更新任务状态

### 11.2 集成架构

```
sindris Round1-4
     │
     ├── Round1 (规划轮)
     │   └── omx_integrator.on_round1_start/complete()
     │       └── omx_tasks: 创建/更新任务记录
     │
     ├── Round2 (执行轮)
     │   └── omx_integrator.on_round2_start()
     │   └── omx_integrator.on_action_start/complete()
     │       └── omx_ledger: 记录动作执行日志
     │
     ├── Round3 (审查轮)
     │   └── omx_integrator.on_round3_start()
     │   └── omx_integrator.on_review_submit()
     │       └── omx_reviews: 创建/更新审查条目
     │
     └── Round4 (完成)
         └── omx_integrator.on_round4_complete()
             └── omx_tasks: 更新最终状态
```

### 11.3 使用方法

```python
from omx_integrator import OMXIntegrator, get_integrator

# 初始化（可指定workspace_root）
integrator = OMXIntegrator(workspace_root="/path/to/workspace")

# Round1: 规划
integrator.on_round1_start(
    task_description="设计用户认证系统",
    matched_roles=["engineering_software_architect", ...],
)
# ... 角色分析后 ...
task = integrator.on_round1_complete(
    plan_summary="采用JWT+RefreshToken方案",
    verified=True,
)

# Round2: 执行
integrator.on_round2_start(
    task_id=task.id,
    actions=[
        {"action_id": "A1", "action_name": "创建User模型", "agent_id": "Dev1", "role": "engineering_senior_developer"},
        ...
    ],
)
# ... 每个动作执行 ...
integrator.on_action_start(action_id="A1", agent_id="Dev1")
integrator.on_action_complete(
    action_id="A1",
    verified=True,
    verify_results={"file_created": True},
)
integrator.on_round2_complete(task_id=task.id, all_verified=True)

# Round3: 审查
reviews = integrator.on_round3_start(
    task_id=task.id,
    review_items=[{"task_id": task.id, "reviewer": "Reviewer", "summary": "检查实现"}],
)
integrator.on_review_submit(reviews[0].id, "approved", "代码质量良好")
integrator.on_round3_complete(task_id=task.id, all_approved=True)

# Round4: 完成
integrator.on_round4_complete(
    task_id=task.id,
    final_output={"files_created": 5},
    success=True,
)
```

### 11.4 OMX模块对应关系

| Round | OMX模块 | 功能 |
|-------|---------|------|
| Round1 | `omx_tasks` | 任务创建、状态转换、计划记录 |
| Round2 | `omx_ledger` | 动作执行日志、会话事件 |
| Round3 | `omx_reviews` | 审查队列、审查结果 |
| Round4 | `omx_tasks` | 最终状态更新 |

### 11.5 状态持久化

所有状态变更立即写入磁盘（`.omx/` 目录）：

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

### 11.6 向后兼容

sindris流程可完全独立于OMX运行：
- 不调用 `omx_integrator` 时，sindris原流程保持不变
- OMX模块（`omx_ledger`, `omx_tasks`, `omx_reviews`）可独立使用
- 集成仅在显式使用 `OMXIntegrator` 时生效

### 11.7 文件清单

| 文件 | 说明 |
|------|------|
| `scripts/sindris_tmux_manager.py` | tmux Worker运行时（Phase 2新增） |
| `scripts/test_sindris_tmux_manager.py` | Worker运行时测试（17个测试用例） |
| `scripts/omx_contract.py` | OMX路径定义和布局 |
| `scripts/omx_ledger.py` | 执行日志系统 |
| `scripts/omx_tasks.py` | 任务图系统 |
| `scripts/omx_reviews.py` | 审查队列系统 |
| `scripts/omx_integrator.py` | sindris Round1-4集成器 |
| `scripts/test_omx_integrator.py` | 集成测试（9个测试用例） |

### 12. tmux Worker运行时 (Phase 2)

**sindris_tmux_manager.py** 提供独立的Worker进程管理，基于oh-my-codex team.ts + claw-code worker_boot.rs设计。

#### 架构

```
SindrisWorkerManager
    ├── TmuxManager          # 低层tmux操作（session/window/send-keys）
    ├── Worker registry      # 内存worker注册表
    └── Event sourcing       # append-only事件日志
```

#### Worker生命周期

```
SPAWNING → TRUST_REQUIRED → READY → RUNNING → COMPLETED/FAILED
                        ↑                    │
                        +----- restart ------+```

#### 核心能力

| 方法 | 说明 |
|------|------|
| `create_worker(role, agent_id?)` | 注册worker记录 |
| `spawn_worker(wid, command?)` | 启动tmux窗口或mock进程 |
| `send_command(wid, cmd)` | 向worker发送命令 |
| `observe(wid)` | 捕获pane输出，更新状态 |
| `resolve_trust(wid)` | 手动解决trust gate |
| `heartbeat(wid)` | 心跳保活 |
| `reconcile()` | 检测过期lease，标记stale |
| `restart_worker(wid)` | 重启worker |
| `terminate(wid)` / `shutdown()` | 终止worker或全队 |
| `create_team(name, specs)` | 工厂方法，创建并启动全队 |

#### 优雅降级

无tmux时自动降级到mock模式，状态机和事件日志照常运行。

#### 检测机制（claw-code风格）

- Trust gate检测：Do you trust... / Allow and continue / Yes, proceed
- Ready信号检测：Ready for input / Ready for prompt / ❯ › >
- 运行中检测：Thinking / Working / Running tests

#### 使用示例

```python
from sindris_tmux_manager import SindrisWorkerManager

mgr, workers = SindrisWorkerManager.create_team(
    team_name="dev-squad",
    workspace_root="/path/to/workspace",
    worker_specs=[
        {"role": "researcher", "agent_id": "agent-1"},
        {"role": "engineering_senior_developer"},
        {"role": "reviewer"},
    ],
)

# 发送命令
mgr.send_command(workers[0].id, "research the caching issue")

# 检测状态
status = mgr.observe(workers[0].id)

# 心跳
mgr.heartbeat(workers[0].id, "work in progress")

# 完成
mgr.complete(workers[0].id, "found 3 solutions")

# 关闭
mgr.shutdown()
```

*Sindri's v1.1 — OMX持久化集成*

---

## 十五、Sindri OpenClaw执行模式（v2.22新增）

### 问题

`sindris_executor.run()`在Python脚本中无法使用sessions_spawn（因为sessions_spawn是OpenClaw工具）。

### 解决方案

在OpenClaw会话中，主Agent调用`sindris.plan()`后，使用sessions_spawn执行subtasks。

### 执行流程

```
主Agent (我)
    ↓
sindris.plan("任务") → 获取subtasks列表
    ↓
for subtask in subtasks:
    sessions_spawn(
        task=subtask['title'],
        runtime="subagent",
        timeoutSeconds=subtask.get('timeout', 300)
    )
    ↓
sessions_yield() → 等待子Agent完成
    ↓
收集结果，继续Round3-4
```

### 触发词

| 触发词 | 说明 |
|--------|------|
| `Sindri执行` | 执行完整Round1-4流程 |
| `Sindri规划` | 仅执行Round1规划 |
| `Sindri审查` | 执行Round3审查 |

### 代码示例

```python
# 在OpenClaw会话中执行
plan = await sindris.plan("分析并改进 context_compressor")

# 检查规划结果
print(f"生成了 {len(plan['subtasks'])} 个子任务")

# 使用sessions_spawn执行
for subtask in plan['subtasks']:
    spawn_result = sessions_spawn(
        task=subtask['title'],
        runtime="subagent",
        timeoutSeconds=subtask.get('timeout', 300)
    )
    # 记录run_id
    print(f"启动: {subtask['role']} - {subtask['title'][:30]}...")
```

### Level降级说明

| Level | 执行方式 | 状态 |
|-------|---------|------|
| Level 1 | sessions_spawn | ✅ OpenClaw中可用 |
| Level 2 | DeepSeek API | ⚠️ API配置问题 |
| Level 3 | 本地模板 | ✅ 兜底可用 |
