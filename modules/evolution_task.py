"""
Sindri进化任务：MimirAether向Hermes 1:1进化

命令词：进化MimirAether → Hermes

触发方式：
    说"进化MimirAether → Hermes"，Sindri自动执行

执行流程：
    Round1: 研究
        - 研究Hermes核心组件设计
        - 研究MimirAether当前实现
        - 对比差距
        
    Round2: 方案
        - 列出1:1进化清单
        - 优先级排序
        - 预估工作量
        
    Round3: 执行（刘哥同意后）
        - 按优先级逐步改进
        
    Round4: 验证
        - 测试改进效果
        - Git commit
"""

# 进化任务配置
EVOLUTION_TASK_CONFIG = {
    "name": "MimirAether Hermes Evolution",
    "command": "进化MimirAether → Hermes",
    "description": "将MimirAether向Hermes进行1:1结构进化",
    "target": "MimirAether",
    "reference": "Hermes",
    "mode": "study_then_execute",  # 先研究后执行，需要刘哥确认
}

# Hermes核心组件清单（用于对比）
HERMES_CORE_COMPONENTS = [
    "agent/core_loop.py",
    "agent/context_compressor.py",
    "agent/insights.py",
    "agent/credential_pool.py",
    "agent/prompt_builder.py",
    "tools/skills_tool.py",
    "tools/skill_manager_tool.py",
    "scheduler/cron.py",
]

# MimirAether对应组件（当前状态）
MIMIR_AETHER_COMPONENTS = [
    "agent/core_loop.py",
    "agent/context_compressor.py",
    "agent/insights.py",
    "agent/credential_pool.py",
    "agent/prompt_builder.py",
    "skills/skills_loader.py",
    "skills/skill_manager.py",
    "scheduler/jobs.py",
]

# 进化对比模板
EVOLUTION_COMPARISON_TEMPLATE = """
## {component_name}

### Hermes设计
{hermes_design}

### MimirAether现状
{mimir_current}

### 差距
{gap}

### 进化建议
{suggestion}

### 优先级
{priority}
"""

# 进化报告模板
EVOLUTION_REPORT_TEMPLATE = """
# MimirAether向Hermes 1:1进化方案

## 总体评估
{total_assessment}

## 进化清单

{evolution_list}

## 执行计划

{execution_plan}

## 预估工作量
{estimated_effort}

---
请确认后说"执行进化"开始执行。
"""

# Sindri进化任务Prompt
EVOLUTION_TASK_PROMPT = """
# MimirAether向Hermes 1:1进化任务

## 命令词
```
进化MimirAether → Hermes
```

## 任务目标
将MimirAether向Hermes进行**1:1结构进化**，学习Hermes的架构设计，**但不使用Hermes的代码**。

## 核心原则
- **学结构**：模块划分、接口设计、数据流
- **不抄代码**：自己实现，不复制粘贴
- **刘哥确认**：方案确认后再执行

## 执行流程

### Round1: 研究
1. 研究Hermes核心组件设计
   - agent/core_loop.py
   - agent/context_compressor.py
   - agent/insights.py
   - agent/credential_pool.py
   - tools/skills_tool.py

2. 研究MimirAether当前实现
   - 对比相同组件的实现差异

3. 对比差距
   - 架构差距
   - 功能差距
   - 完整性差距

### Round2: 方案
1. 列出1:1进化清单
   - 组件名
   - 当前状态
   - 目标状态
   - 进化方式（自学/参考Hermes）

2. 优先级排序
   - P0: 核心功能缺陷
   - P1: 重要功能缺失
   - P2: 优化改进

3. 预估工作量

### Round3: 执行（刘哥同意后）
1. 按优先级逐步改进
2. 每个组件改进后验证
3. 及时汇报进度

### Round4: 验证
1. 测试改进效果
2. Git commit
3. 更新文档

## 输出格式

### 研究报告
```
## {组件名}

### Hermes设计
- 架构：
- 核心逻辑：
- 数据流：

### MimirAether现状
- 当前实现：
- 差距：

### 进化建议
- 需要做什么
- 如何做（不抄代码）
```

### 进化方案
```
## 进化清单

| 优先级 | 组件 | 当前状态 | 目标状态 | 工作量 |
|--------|------|---------|---------|--------|
| P0 | ... | ... | ... | ... |

## 执行计划
1. ...
2. ...

请确认后说"执行进化"开始执行。
```

## 注意事项
- 重点关注：自进化机制、skill系统、上下文压缩
- 不要复制Hermes代码
- 保持MimirAether的独特性
"""
