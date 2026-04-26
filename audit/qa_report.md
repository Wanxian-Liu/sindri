# QA Audit Report - sindris v3.7

> [!WARNING]
> **归档状态（2026-04-27）**
> - 本报告是 **2026-04-21 / v3.7** 历史快照，测试结论与当前 **v4.1** 已不完全对应。
> - 报告内关于旧 API（如 v1.1/v3.x 兼容性）的问题，主要用于历史背景，不作为现行阻断条件。
> - 当前质量状态请以 `tests/` 全量回归结果与 `test_release_contract.py` 为准。

**审计时间**: 2026-04-21
**审计范围**: sindris_executor.py (v3.7) + tests/
**审计工具**: 人工代码审查 + 测试覆盖率分析

---

## 一、测试覆盖完整性分析

### 1.1 测试文件概览

| 测试文件 | 测试数 | 覆盖模块 |
|---------|-------|---------|
| test_sindris.py | ~12 | 主执行器 |
| test_circuit_breaker.py | 30 | circuit_breaker.py |
| test_ralph_loop.py | ~40 | ralph_loop.py |
| test_supplement_gaps.py | 11 | 覆盖缺口 |
| test_uncovered_main_blocks.py | 12 | __main__块 |
| test_match_roles*.py | ~15 | match_roles.py |
| test_omx_*.py | ~20 | omx_*.py |
| test_worktree_officer*.py | ~10 | worktree_officer.py |
| test_memory_manager.py | ~8 | memory_manager.py |
| test_telemetry_collector.py | ~5 | telemetry_collector.py |
| test_task_queue.py | ~5 | task_queue.py |
| test_consensus_officer.py | ~5 | consensus_officer.py |

**总计**: 约 **170+** 测试用例，42个测试文件（.py）

### 1.2 关键发现：test_sindris.py 严重过时

**问题**: `test_sindris.py` 是为 v1.1 编写的，但 sindris_executor 已在 v3.3 重构为纯规划器。

```
test_sindris.py 中调用的方法（已在 v3.3 删除）:
- executor.round1_planning()       ← 已删除
- executor.round2_execution_mock() ← 已删除
- executor.round3_review()         ← 已删除
- executor.round4_completion()      ← 已删除
- executor.workers                  ← 不存在
- executor.tasks                   ← 不存在
- executor.consensus               ← 不存在
- executor.worktree                ← 不存在
```

**影响**: `test_executor_init()` 断言失败:
```python
assert_eq(len(executor.workers), 0)   # AttributeError: 'SindrisExecutor' has no 'workers'
assert_eq(len(executor.tasks), 0)    # AttributeError
assert_true(executor.consensus)       # AttributeError
assert_true(executor.worktree)        # AttributeError
```

**建议**: 重写 test_sindris.py 以匹配 v3.7 API。现有唯一公开方法是 `plan()`。

### 1.3 未覆盖的核心代码路径

| 代码路径 | 说明 | 风险 |
|---------|------|------|
| `_find_role_file()` 精确/包含/部分三级匹配 | 仅靠手动测试 | 中 |
| `_run_auto_verification() fallback` | SafetyPolicy/EvolutionVerifier导入失败时 | 高 |
| `_setup_subagent_state_machine()` | 状态机初始化但无外部调用 | 中 |
| `check_dangerous_command()` | SafetyPolicy集成 | 低 |
| FastPath cache 读写 | `_check_fastpath_cache` / `_save_fastpath_cache` | 中 |
| `update_subagent_state()` / `get_subagent_state()` | 子代理状态管理 | 低 |
| `_get_check_fn_for_item()` | DEFAULT_CHECK_FUNCTIONS映射逻辑 | 中 |
| `verify_with_ralph()` ImportError分支 | RalphLoop不可用时的fallback | 高 |

---

## 二、边界条件处理

### 2.1 plan() 输入验证覆盖

sindris_executor.py L268-289 已实现基础输入验证：

```python
# ✅ 已覆盖的边界
- task非字符串类型 → {"success": False, "phase": "rejected"}
- task长度<3 → {"success": False, "phase": "rejected"}
- task长度>5000 → {"success": False, "phase": "rejected"}
- TaskDecomposer/RoldManager导入失败 → _plan_fallback()
```

**未覆盖的边界**:

| 边界条件 | 当前行为 | 风险 |
|---------|---------|------|
| task.strip()后恰好等于""（全空格） | 通过（长度<3会拦截）| 低 |
| 特殊Unicode字符（如\u0000） | 未处理，可能在RoleMatcher中出问题 | 中 |
| task含非常长连续字符（如10000个'a'） | 通过验证，但RoleMatcher可能超时 | 中 |
| 导入TaskDecomposer成功，但方法调用失败 | 无处理，异常上抛 | 高 |
| _find_role_file() roles_dir不存在 | 返回None（优雅降级）| 低 |

### 2.2 _find_role_file() 匹配优先级

代码实现（优先级：精确 > 包含 > 部分）：

```python
# 优先级1: 精确匹配 (normalized == stem)
# 优先级2: 包含匹配 (normalized in stem)  
# 优先级3: 部分匹配 (any part in stem)
```

**未测试的边界**:
- normalized名称含特殊字符（中文、emoji）
- 多个文件同时匹配同一优先级
- role_file为相对路径时子代理访问

### 2.3 状态机边界

```python
SubagentState = {
    "PENDING": "pending",
    "RUNNING": "running", 
    "COMPLETE": "complete",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
    "TIMEOUT": "timeout",
}
```

**问题**: 状态机已初始化，但**没有任何外部调用**更新状态。状态机完全是内部stub。

---

## 三、异常情况处理

### 3.1 异常处理覆盖

| 代码路径 | 异常类型 | 处理方式 | 测试覆盖 |
|---------|---------|---------|---------|
| `_run_auto_verification()` | ImportError/通用Exception | 返回 `verified=False` + error | ❌ 无 |
| `verify_with_ralph()` | ImportError | 返回 `success=False` + error | ❌ 无 |
| `verify_with_ralph()` | 通用Exception | 返回 `success=False` + error | ❌ 无 |
| `_plan_fallback()` | 通用Exception | 静默使用默认角色 | ❌ 无 |
| `_log_jsonl()` | 通用Exception | 无处理（可能吞掉）| ❌ 无 |
| `check_dangerous_command()` | SafetyPolicy不存在 | 返回safe=True | ❌ 无 |

### 3.2 关键问题：虚假验证通过

**P0问题**: `_run_auto_verification()` 在 ImportError 时返回：
```python
except Exception as e:
    return {
        "verified": False,
        "task_type": task_type,
        "error": str(e),
    }
```

但 `plan()` 中：
```python
verification_result = self._run_auto_verification("evolution")
verification_success = verification_result.get("success", False)  # ❌ 无success键
result = {
    "success": verification_success,  # 永远是None/False
    ...
}
```

**问题**: 当EvolutionVerifier不可用时，verification_result没有`success`键，`get("success", False)`正确返回False，但错误信息可能丢失。

### 3.3 版本注释不一致

代码中存在多个版本号标记，但版本号跳跃（v3.3→v3.7→v3.8），可能表明：
- 部分v3.8代码已合并但版本号未更新
- 或存在未完成的版本升级

**示例**:
```python
# L116: "# v3.8改进：根据subtasks生成具体的验证条件"
# L146: "# v3.8: 真正调用验证器（传入role_id）"  
# L200: "# v3.8: 记录遥测 - 安全拦截"
# L217: "# v3.8: 初始化OMXIntegrator持久化"
```

---

## 四、验证机制有效性

### 4.1 三层验证架构

```
plan() 输出
    │
    ├── _add_verification_step()     → 添加验证步骤到subtasks
    │       └── verify: List[str]条件
    │
    ├── _run_auto_verification()     → 调用EvolutionVerifier
    │       └── returned: verified + success
    │
    └── verify_with_ralph()           → 3轮循环验证（可选）
            └── RalphLoop.run()
```

### 4.2 EvolutionVerifier 验证

**调用链**:
```python
if task_type == "audit":
    target = "AUDIT_TEAM"
    improver_id = "engineering_code_reviewer"
elif task_type == "evolution":
    target = "EVOLUTION_DISTRIBUTOR"
    improver_id = "engineering_software_architect"
else:
    target = "FIXED_TEAM"
    improver_id = "engineering_senior_developer"

verification_result = verifier.verify(target, improver_id=improver_id)
passed = verification_result.get("passed", False)  # ✅ 使用passed而非success
```

**问题**:
1. **role_id硬编码**: "engineering_code_reviewer"等hardcoded，可能与实际角色ID不匹配
2. **ImportError静默**: 导入失败时用户不知道验证被跳过
3. **无超时控制**: EvolutionVerifier.verify()可能永久阻塞

### 4.3 RalphLoop 验证

```python
# verify_with_ralph() 返回结构
{
    "success": bool,
    "total_rounds": int,
    "consecutive_passed": int,
    "final_report": {
        "round_num": int,
        "state": str,
        "passed_count": int,
        "failed_count": int,
        "conclusion": str,
    }
}
```

**问题**:
1. **ImportError静默处理**: 返回error dict但不抛异常
2. **无调用点**: `verify_with_ralph()` 在 sindris_executor 中定义但**从未被调用**
3. **返回值未序列化**: `ralph_result`对象包含循环引用风险（代码已用dict处理）

### 4.4 DEFAULT_CHECK_FUNCTIONS

```python
DEFAULT_CHECK_FUNCTIONS = {
    "file_exists": lambda ctx: Path(ctx["file_path"]).exists(),
    "file_not_empty": lambda ctx: Path(ctx["file_path"]).stat().st_size > 0,
    "code_importable": lambda ctx: any(Path(ctx["workspace_root"]).glob(f"**/{ctx['module_name']}.py")),
    "no_placeholder": lambda ctx: "MOCK" not in content and "TODO" not in content,
    "function_defined": lambda ctx: f"def {ctx['function_name']}" in Path(ctx["file_path"]).read_text(),
}
```

**问题**:
1. **无测试**: 此字典完全无测试覆盖
2. **路径穿越风险**: `glob("**/*.py")` 在workspace_root为"/"时危险
3. **read_text()无编码**: 多字节文件名可能失败
4. **lambda捕获ctx**: 闭包引用外部变量，调试困难

---

## 五、测试质量评估

### 5.1 测试架构优点

✅ **pytest混合**: 既有pytest类风格，也有手写run_all_tests()  
✅ **TestContext模式**: 临时目录+环境隔离  
✅ **覆盖率覆盖**: 专门有test_coverage_gaps.py补缺口  
✅ **subprocess测试**: __main__块通过subprocess覆盖  
✅ **边界测试**: circuit_breaker有30个详细边界测试

### 5.2 测试架构问题

❌ **test_sindris.py完全过时**: 测试v1.1 API，当前为v3.7  
❌ **大量重复测试**: test_circuit_breaker.py + test_circuit_breaker_main.py等  
❌ **无mock隔离**: 大多直接调用真实模块，测试间可能有副作用  
❌ **无参数化测试**: pytest.mark.parametrize使用较少  
❌ **断言风格不统一**:混用assert_eq/assert_true/assert_raises  

### 5.3 关键测试缺失

| 缺失测试 | 影响 |
|---------|------|
| plan() 端到端测试（输入→输出→subtasks） | 高 |
| _plan_fallback() 降级路径 | 高 |
| SafetyPolicy未加载时check_dangerous_command | 中 |
| OMX未加载时所有OMX调用 | 高 |
| TelemetryCollector未加载时的日志 | 低 |
| session_id生成唯一性 | 低 |

---

## 六、风险矩阵

| 风险项 | 概率 | 影响 | 严重度 | 建议 |
|-------|------|------|--------|------|
| test_sindris.py运行必失败 | 确定 | 高 | 🔴严重 | 重写或删除 |
| EvolutionVerifier导入失败静默 | 中 | 高 | 🔴严重 | 添加warning日志 |
| _run_auto_verification无超时 | 低 | 高 | 🟠高 | 添加asyncio.timeout |
| verify_with_ralph从未被调用 | 确定 | 中 | 🟡中 | 文档说明或删除代码 |
| 状态机stub代码 | 确定 | 低 | 🟢低 | 删除或实现 |
| DEFAULT_CHECK_FUNCTIONS路径穿越 | 低 | 高 | 🟠高 | 添加输入验证 |
| 版本号混乱 | 中 | 低 | 🟢低 | 统一版本管理 |

---

## 七、建议改进

### P0（必须修复）

1. **重写test_sindris.py**以匹配v3.7 API
   - 移除round1_planning/round2_execution等删除的方法
   - 专注于plan()方法的输入输出测试
   - 测试_add_verification_step和_run_auto_verification

2. **添加plan()端到端测试**
   - 有效任务 → 验证返回结构
   - 无效任务 → 验证错误返回
   - 缓存命中 → 验证from_cache标志

3. **修复_run_auto_verification返回值一致性**
   - 添加success键到所有返回路径
   - 添加warning日志当EvolutionVerifier不可用

### P1（强烈建议）

4. **添加验证机制测试**
   - test EvolutionVerifier fallback路径
   - test RalphLoop ImportError路径
   - test DEFAULT_CHECK_FUNCTIONS边界

5. **清理stub代码**
   - 删除未使用的状态机（_subagent_states）
   - 或实现完整的状态机功能

6. **统一版本号**
   - 扫描所有"v3.x"注释，统一到VERSION

### P2（建议优化）

7. **添加pytest参数化测试**减少重复代码
8. **添加集成测试**验证plan()→subtasks→verify流程
9. **文档化验证机制**说明何时用哪种验证

---

## 八、总结

| 维度 | 评分 | 说明 |
|-----|------|------|
| 测试覆盖 | 65/100 | 基础覆盖良好，但核心plan()测试缺失 |
| 边界处理 | 55/100 | 基础验证有，特殊字符/超长输入无 |
| 异常处理 | 40/100 | ImportError有catch但静默，通用Exception有遗漏 |
| 验证机制 | 50/100 | 三层验证但两层是stub/未调用 |

**整体评估**: sindris v3.7是一个**功能设计完整但测试严重滞后**的系统。核心的`plan()`方法没有有效的端到端测试，而test_sindris.py是针对v1.1的"幽灵测试"。需要紧急重构测试套件以匹配当前架构。

---

*审计人: QA Lead Subagent*  
*审计时间: 2026-04-21 02:43 GMT+8*
