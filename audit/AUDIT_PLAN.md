# Sindris 自我审计计划 v1.0

> [!NOTE]
> **状态更新（2026-04-27）**
> - 本文是历史审计计划，适合作为问题发现方法论，不应直接视为当前待办清单。
> - 其中部分条目（如旧版命名、文档不一致、测试契约问题）已在 v4.1 阶段完成修复。
> - 执行修复请优先参考当前源码、`SKILL.md`、`tests/test_release_contract.py` 及全量回归结果。

**创建时间**: 2026-04-21 08:15 GMT+8  
**角色**: Architect  
**版本**: sindris_executor.py v4.1, modules/ 共14个Python文件  
**目标**: 制定发现问题清单（非修复），为 Step 2 实施团队提供方向

---

## 一、审计范围

### 1.1 文件清单

| 文件 | 行数 | 审计优先级 |
|------|------|-----------|
| `sindris_executor.py` | 587 | P0 |
| `modules/plan_engine.py` | 656 | P0 |
| `modules/verify_engine.py` | 802 | P0 |
| `modules/fusion_planner.py` | 517 | P0 |
| `modules/role_matcher.py` | 469 | P1 |
| `modules/scheduler.py` | 453 | P1 |
| `modules/round_manager.py` | 288 | P1 |
| `modules/gstack_integration.py` | 382 | P1 |
| `modules/task_decomposer.py` | 377 | P1 |
| `modules/role_hierarchical_matcher.py` | 223 | P2 |
| `modules/evolution_task.py` | 190 | P2 |
| `modules/evolution_verifier.py` | 211 | P2 |
| `modules/health_score.py` | 155 | P2 |
| `modules/role_manager.py` | 142 | P2 |
| `modules/report_generator.py` | 189 | P2 |
| `SKILL.md` | 1508 | P1 |
| `scripts/` 目录 | 若干 | P2 |

### 1.2 已知审计历史

| 审计报告 | 时间 | 主要发现 |
|----------|------|----------|
| code_reviewer_report.md | 2026-04-21 02:38 | 裸except、静默失败、版本混乱 |
| security_report.md | 2026-04-21 02:39 | (需读取) |
| qa_report.md | 2026-04-21 02:45 | (需读取) |
| docs_report.md | 2026-04-21 02:39 | (需读取) |
| tmp/sindri_architecture_audit.md | 2026-04-21 05:25 | 双重verify_engine、RoleMatcher双重调用、OMX断裂 |

---

## 二、审计目标（发现问题清单）

### 🔴 P0 - 必须发现

#### A. 双重引擎文件（engines/ vs modules/）

**已知问题**：
- `engines/verify_engine.py` (375行) vs `modules/verify_engine.py` (802行) 重名
- `engines/plan_engine.py` 存在但未被sindris_executor使用
- `modules/` 下也存在 `plan_engine.py`，与 `engines/plan_engine.py` 可能冲突

**审计目标**：
- [ ] 确认 `engines/` 目录下所有文件的使用情况（哪些被导入，哪些从未被导入）
- [ ] 确认 `modules/` 和 `engines/` 是否有继承或引用关系
- [ ] 评估删除 `engines/` 目录对系统的冲击
- [ ] 检查 `modules/plan_engine.py` 和 `engines/plan_engine.py` 的类/函数是否同名

#### B. RoleMatcher 双重调用

**已知问题**：
- `fusion_planner.py` 第137行调用 `self.role_matcher.match(task)`
- `task_decomposer.get_roles()` 内部再次调用 `RoleMatcher.match()`
- 导致角色匹配被执行两次，第二次忽略已有结果

**审计目标**：
- [ ] 追踪 `match_roles()` 的完整调用链（从 fusion_planner → task_decomposer → role_matcher）
- [ ] 确认第二次调用时传入的 `auto_roles` 参数是否真的被忽略
- [ ] 评估这是否导致性能下降（RoleMatcher 是否有昂贵的 LLM 调用）
- [ ] 检查 `role_matcher.py` 中是否有副作用（状态修改）导致双重调用产生错误结果

#### C. OMX 集成器断裂

**已知问题**：
- `_get_omx_integrator()` 在导入失败时返回 None
- `use_omx` 默认为 False
- 文档承诺的 OMX 持久化体系实际不可用

**审计目标**：
- [ ] 确认 `scripts/omx_integrator.py` 相对于 sindris 的实际导入路径
- [ ] 统计所有 `if use_omx` 和 `if _OMXIntegrator` 的检查点数量
- [ ] 评估 `use_omx=True` 会对现有流程产生什么影响
- [ ] 检查 OMX state 文件是否真实存在且被正确写入

#### D. verify_with_ralph 接口签名不匹配

**已知问题**：
- `modules/verify_engine.py` 定义：`async def verify_with_ralph(self, task, result, verify_items)`
- `sindris_executor.py` 暴露：`async def verify_with_ralph(self, task_name, verify_items, execute_fn=None)`
- `result` 参数丢失，`execute_fn` 从未传递

**审计目标**：
- [ ] 追踪 `sindris_executor.verify_with_ralph()` 的所有调用方
- [ ] 确认 `result` 参数缺失是否导致验证逻辑失效
- [ ] 确认 `execute_fn` 参数是否从未被使用（dead code）

---

### 🟠 P1 - 重要发现

#### E. CircuitBreaker 状态未联动

**已知问题**：
- `fusion_planner.record_execution_result()` 存在但从未被调用
- `complete_subtask()` / `fail_subtask()` 不触发熔断器更新

**审计目标**：
- [ ] 追踪 `record_execution_result()` 的所有调用点
- [ ] 确认熔断器状态是否真实反映执行历史
- [ ] 评估熔断器打开时系统的降级行为

#### F. SKILL.md 与实际代码脱节

**已知问题**：
- SKILL.md 描述了 v3.9 流程，但实际代码已到 v4.1
- 描述的 `agent_executor.py` 不存在于代码库
- 描述的 `roles_registry.json` 路径与实际不符

**审计目标**：
- [ ] 对比 SKILL.md 中每个引用文件与实际文件系统
- [ ] 列出 SKILL.md 承诺但代码中缺失的功能
- [ ] 统计 SKILL.md 中版本号与代码 VERSION 的差异数量

#### G. 裸 except 和静默失败

**已知问题**：
- `code_reviewer_report.md` 记录了多处 `except:` 捕获所有异常
- `SafetyPolicy` / `Telemetry` 导入失败静默

**审计目标**：
- [ ] 精确统计所有 `except:` （按文件、按行号）
- [ ] 区分：必要的异常类型 vs 过度宽泛的异常
- [ ] 检查 import 失败时的 fallback 是否合理

#### H. Task/Subtask/FusionPlan 多类型混乱

**已知问题**：
- `PlanEngine.Task` / `PlanEngine.Subtask` / `FusionPlan` / `TaskDecomposer.Task` 4种类型
- `_tasks_to_subtasks()` 转换时 metadata 部分丢失

**审计目标**：
- [ ] 绘制所有类型的继承/组合关系图
- [ ] 确认哪些 metadata 字段在类型转换中丢失
- [ ] 评估这是否会导致验证或执行阶段的逻辑错误

---

### 🟡 P2 - 次要发现

#### I. Timeout 配置未差异化
- 所有优先级映射到 300 秒

#### J. JSONL 日志冗余
- info 级别同时输出到文件和控制台

#### K. 版本号混乱
- docstring 与 VERSION 常量不一致

#### L. Async/Sync 混用
- `_plan_fallback()` 是"假异步"（无 await）

#### M. GStackPro 集成状态
- `sindri_gstack_hybrid/` vs `skills/gstack-pro/` 关系不清

#### N. scripts/ 目录可用性
- `sindris_tmux_manager.py` 等在 sessions_spawn 存在下是否还有价值

---

## 三、审计方法

### 3.1 静态分析
- AST 解析所有 Python 文件的 import 语句
- 追踪所有函数调用链（特别是跨文件的）
- 正则匹配 `except:` 位置和类型
- 对比 VERSION 常量与 docstring 版本号

### 3.2 动态验证
- 实际导入所有模块，验证无 ImportError
- 检查 OMXIntegrator 实际路径
- 运行 `sindris plan <task>` 验证端到端流程

### 3.3 交叉验证
- 对比 SKILL.md 文件引用与实际文件系统
- 对比代码注释与实际行为

---

## 四、交付物

| 交付物 | 内容 | 给谁用 |
|--------|------|--------|
| `audit_issues_p0.md` | P0 问题详细清单（带行号、代码片段） | Step 2 修复团队 |
| `audit_issues_p1.md` | P1 问题详细清单 | Step 2 修复团队 |
| `audit_cross_ref.md` | import 调用链图 + 文件依赖矩阵 | Architect 复审 |
| `audit_skills_gap.md` | SKILL.md vs 代码差异清单 | Technical Writer |

---

## 五、执行计划（900秒约束）

```
[0-120s]   文件扫描：import分析、except统计、版本对比
[120-300s] P0问题深挖：双重引擎、RoleMatcher调用链、OMX路径
[300-480s] P1问题深挖：CircuitBreaker、SKILL.md差异、静默失败
[480-600s] P2问题收集：timeout、日志、版本等
[600-720s] 交叉验证：运行验证、动态导入测试
[720-900s] 汇总输出：4份交付物文档
```

**超时策略**：每阶段设置超时标记，到时未完成则将当前结果直接输出
