# Sindris 改进计划
_生成时间: 2026-04-14_
_来源: Ralph沙盒测试 + 日常使用发现_

---

## 测试发现的问题

### 问题1: 角色匹配错误

**现象**: 任务"记忆殿堂设计知识发现自动化流程"匹配到了UI Designer/Brand Guardian

**应该匹配**: Software Architect, Senior Developer, API Tester

**根因**: TaskDecomposer的任务类型识别不准确，"记忆殿堂"被误解为UI/UX任务

---

### 问题2: run()只规划不执行

**现象**: `sindris.run()`只返回执行计划，不自动执行subtasks

**代码位置**: sindris_executor.py line 182-204

```python
async def run(self, task: str, verify: bool = False) -> Dict[str, Any]:
    """
    执行完整Round1-4流程
    
    注意：这个方法返回执行计划，不是自动执行。
    真正的执行需要主Agent调用 sessions_spawn 工具。
    """
    # Round1: 规划
    plan_result = await self.plan(task)
    
    if not plan_result.get("success"):
        return plan_result
    
    # 返回执行计划 - 没有实际执行！
    return {
        "success": True,
        "session_id": self.session_id,
        "plan_summary": plan_result.get("plan_summary"),
        "subtasks": plan_result.get("subtasks", []),
        ...
    }
```

---

## 改进方案

### 改进1: 任务类型自动识别 ✅ 已完成

**实现**: 
- 新增 `modules/task_classifier.py`
- TaskClassifier支持6种任务类型
- RoleMatcher集成TaskClassifier

**验证**:
```
记忆殿堂设计流程 → engineering → 固定团队 ✅
优化sindris → engineering → 固定团队 ✅
设计界面 → design → UI Designer ✅
```

---

### 改进2: run()返回完整执行计划 ✅ 已完成

**实现**:
- run()返回`ready_to_execute: True`信号
- `execution_guide`包含每个subtask的详细参数
- 主Agent看到结果后可自动执行

**验证**:
```
run()返回:
  ready_to_execute: True
  execution_guide.round2.subtasks: 11个subtask
  roles: Software Architect, Senior Developer, API Tester, Reality Checker
```

---

## 实施优先级

| 优先级 | 改进项 | 难度 | 影响 |
|--------|--------|------|------|
| P0 | 任务类型识别 | 中 | 角色匹配正确性 |
| P1 | run()自动执行 | 高 | 真正自动化 |
| P2 | 执行结果收集 | 中 | 完整性 |

---

## 验证方法

1. **改进1验证**: 同样的任务"记忆殿堂设计知识发现"应该匹配Engineering角色
2. **改进2验证**: `run()`执行后应该能看到实际的执行结果

---

_最后更新: 2026-04-14_
