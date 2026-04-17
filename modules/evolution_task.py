"""
Sindri进化任务：MimirAether向Hermes 1:1进化

命令词：进化MimirAether → Hermes

重要：此任务需要刘哥确认方案后才能执行！
"""

# ============================================================================
# 源代码路径配置（必须准确）
# ============================================================================

HERMES_ROOT = "/home/rayliu/.openclaw/projects/hermes-agent"
MIMIR_AETHER_ROOT = "/home/rayliu/.openclaw/projects/MimirAether"

# Hermes核心组件（用于对比）
# Hermes核心组件（用于对比）
HERMES_CORE_COMPONENTS = [
    ("agent/core_loop.py", "核心执行循环"),
    ("agent/context_compressor.py", "上下文压缩"),
    ("agent/insights.py", "数据洞察"),
    ("agent/credential_pool.py", "凭证池"),
    ("agent/prompt_builder.py", "Prompt构建"),
    ("tools/skills_tool.py", "技能工具"),
]

# MimirAether对应组件
MIMIR_AETHER_COMPONENTS = [
    ("agent/core_loop.py", "核心执行循环"),
    ("agent/context_compressor.py", "上下文压缩"),
    ("agent/insights.py", "数据洞察"),
    ("agent/credential_pool.py", "凭证池"),
    ("agent/prompt_builder.py", "Prompt构建"),
    ("skills/skills_loader.py", "技能加载器"),
]

# ============================================================================
# 进化任务配置
# ============================================================================

EVOLUTION_TASK_CONFIG = {
    "name": "MimirAether Hermes Evolution",
    "command": "进化MimirAether → Hermes",
    "description": "将MimirAether向Hermes进行1:1结构进化",
    "mode": "study_then_execute",  # 先研究后执行
    "require_approval": True,  # 需要刘哥确认
}

# ============================================================================
# 进化报告模板
# ============================================================================

EVOLUTION_REPORT_TEMPLATE = """
# MimirAether向Hermes 1:1进化方案

**源代码路径**：
- Hermes: `{hermes_root}`
- MimirAether: `{mimir_root}`

## 总体评估
{total_assessment}

## 进化清单

{evolution_list}

## 执行计划

{execution_plan}

## 预估工作量
{estimated_effort}

---
## ⚠️ 刘哥确认

请审查以上方案。

**确认后说**：`执行进化` 或 `开始执行`

**拒绝说**：`取消` 或 `重新规划`
"""

# ============================================================================
# Sindri进化任务Prompt（完整版）
# ============================================================================

EVOLUTION_TASK_PROMPT = """
# MimirAether向Hermes 1:1进化任务

## ⚠️ 重要提醒

此任务**必须先出方案，刘哥确认后才能执行**。

## 源代码路径

- **Hermes**: `{hermes_root}`
- **MimirAether**: `{mimir_root}`

## 任务目标

将MimirAether向Hermes进行**1:1结构进化**：
- 学习Hermes的架构设计
- 不使用Hermes的代码（自己实现）
- 保持MimirAether的独特性

## 执行流程（3阶段）

### 阶段1: 研究（自动执行）
1. 读取Hermes核心组件源码
2. 读取MimirAether对应组件源码
3. 对比架构差距

### 阶段2: 出方案（自动执行）
1. 列出进化清单（组件名、当前状态、目标状态）
2. 优先级排序（P0/P1/P2）
3. 预估工作量

### 阶段3: 执行（**需要刘哥确认**）
刘哥说"执行进化"后才执行：
1. 按优先级逐步改进
2. 每个组件改进后测试
3. Git commit

## 对比组件清单

{HERMES_CORE_COMPONENTS}

对应MimirAether组件：
{MIMIR_AETHER_COMPONENTS}

## 输出要求

### 研究阶段输出
对每个组件输出：
```
## {component_name}

### Hermes设计（来自 {hermes_root}/{component_path}）
- 架构：
- 核心逻辑：
- 数据流：

### MimirAether现状（来自 {mimir_root}/{component_path}）
- 当前实现：
- 差距：

### 进化建议
- 需要做什么
- 如何做（不抄代码）
```

### 方案阶段输出
```
## 进化清单

| 优先级 | Hermes组件 | MimirAether组件 | 差距 | 工作量 |
|--------|-----------|----------------|------|--------|
| P0 | ... | ... | ... | ... |

## 执行计划
1. ...
2. ...

## 预估工作量
- 总计: X小时
- P0: X小时
- P1: X小时
- P2: X小时
```

## ⚠️ 刘哥确认

方案出来后请刘哥审查。

**确认后说**：`执行进化` 或 `开始执行`

**拒绝说**：`取消` 或 `重新规划`

## 注意事项

1. **不抄代码** - 只学架构设计，自己实现
2. **保持独特性** - MimirAether有自己特色不要改
3. **先方案后执行** - 必须先出方案
4. **刘哥确认** - 必须刘哥确认后才能执行
"""

# 路径常量（供外部使用）
HERMES_SOURCE_ROOT = HERMES_ROOT
MIMIR_AETHER_SOURCE_ROOT = MIMIR_AETHER_ROOT
