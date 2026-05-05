# Changelog - sindris 版本历史

## 版本升级检查清单（v4.1 起）

发布新版本时按顺序完成，避免 SKILL 与代码脱节：

1. **`sindris_executor.py`**：更新 `VERSION = "x.y"`。
2. **`SKILL.md`**：frontmatter `version: "x.y"` 与正文涉及版本号的句子。
3. **`tests/test_release_contract.py`**（若存在）：将其中期望版本改为 `x.y`（或与 `VERSION` 常量统一）。
4. **`audit/README.md`**：「当前基线」中的版本号。
5. **本文件**：在顶部增加 `## vx.y` 小节，记录变更摘要。
6. **合并前**：本地或通过 CI 运行 `python3 -m pytest tests/test_release_contract.py` 与 `python3 -m pytest tests/`。

CI：仓库 `.github/workflows/ci.yml` 在 push/PR 至 `main` 或 `master` 时对 Python 3.11 / 3.12 运行上述测试。

---

## v4.2 维护记录（测试门禁与仓库卫生）

- SKILL：**负一、自警条款**（琬弦 2026-05-06）— 执行前自审，与 v4.1 编排规则并存。
- 执行器：`VERSION` 与 `SKILL.md` frontmatter 对齐为 **4.2**。
- `CircuitBreaker.call`：同步路径下失败时指数退避**重试**后再抛出（与测试及韧性预期一致）。
- 测试：Ralph 用例统一使用 `MockSindrisExecutor` 绑定方法，满足 `check_fn` 白名单；`asyncio.run` 隔离 gstack 异步用例事件循环；`score_role` 与返回 `(score, reasons)` 对齐。
- 工程：新增 `tests/conftest.py`、`tests/ralph_mock_executor.py`；根目录 `README.md`；`.github/workflows/ci.yml`（Python 3.11 / 3.12，`pytest` + `pytest-anyio`）。
- 仓库：从 Git 索引移除误跟踪的 `tests/__pycache__/*.pyc`（仍由 `.gitignore` 忽略）。
- **B1 记忆桥接**：`MemoryManager.search_keyword`（索引尾部子串检索 MVP）；`memory_omx_bridge` 将 `index.jsonl` 全量快照同步到 `.omx/memory/{namespace}.json`；契约见 `docs/MEMORY_OMX_CONTRACT.md`；`README.en.md`、`CONTRIBUTING.md`、Issue 模板。

## v4.1 维护记录（OpenClaw 对齐与门禁）

- SKILL：**Sindris 独立编排 + Foundry 硬绑定** — 主代理须以 Sindris 为唯一可追溯主线；Foundry 不得单独替代；平台自动 Foundry 时须在同一任务内补全 Sindris 链。
- SKILL：**任务类型 A/B**（交付物 vs 只读/学习）— 明确 Ralph、yield 后验证、Git 的强制边界与类型 B 豁免须显式声明；**主代理自审五问**；消除「Step 3」与角色改进子流程的命名混淆；规划入口须 `plan` 或 `execute`。
- 执行器：`audit_keywords` 与 SKILL「审计团队触发条件」对齐（含 `评估`、`review`、`质量检查` 等）。
- SKILL：**Spawn 公约**（单一真源）— 经常 spawn 时的三要素、`trace_id`、yield/失败 yield、主会话与所有权、并行度与收束四问；编排模板与之交叉引用。`docs/personal-orchestration-checklist.md` 与 `audit/README.md` 同步指向该节。
- SKILL：增加 OpenClaw 运行时契约与 **plan() → sessions_spawn / sessions_yield 映射表**；统一 Sindris 命名，去除 A2 代号。
- 工程：`tests/test_release_contract.py` 发布契约；`audit/README.md` / `audit/PROMPT_MAINTAINER.md`；历史审计报告归档声明。
- 脚本：`register_roles.py` 使用仓库相对路径；`install_sindri.sh` 触发词与 Sindris 一致。
- 质量：全量 `pytest` + CI 工作流。

## v3.11更新（角色MD文件加载修复）
- ⚠️ P0: sindris_executor.py添加find_role_md_file()函数 - 根据role名称查找MD文件路径
- ⚠️ P0: plan()返回的subtasks添加md_file字段 - 包含角色MD文件完整路径
- ⚠️ P0: SKILL.md Step 2添加角色MD加载逻辑 - sessions_spawn前读取MD文件内容加入task
- **问题**: 子代理只收到"你是Code Reviewer"，不知道如何审计（MD文件未被加载）
- **解决**: plan()提供md_file路径，sessions_spawn时读取MD内容加入task提示

## v3.10更新（Technical Writer Round4审计文档更新）
- ⚠️ P0: 添加FIXED_TEAM状态映射 - 规范化修复流程状态定义
- ⚠️ P1: Reality Checker保持原名testing_reality_checker - sindri使用testing_reality_checker
- P2: 更新执行示例 - 补充testing_reality_checker使用场景

## v3.9更新（AUDIT_TEAM Round4审计发现）
- ⚠️ P0: 修复sindris.plan()方法缺失问题 - 需import并正确调用
- ⚠️ P0: 修复SKILL.md与实际脚本不一致 - roles_registry.json路径确认
- ⚠️ P1: 完善角色匹配逻辑 - match_roles.py依赖sindris_executor.py
- ⚠️ P1: 添加审计团队Round4职责 - Technical Writer文档更新
- P2: 优化README结构 - 更清晰的快速开始
- P2: 补充执行示例 - 添加完整执行日志格式

## v3.8更新（角色完善任务暴露的问题）
- ⚠️ 强制验证检查点：sessions_yield()后必须检查文件是否真的被修改
- ⚠️ 验证条件具体化：不只是"验证完成"，而是列出具体文件
- P0: 修复evolution流程验证无效问题（子代理报告完成但文件未修改）
- P0: 添加文件存在性检查（ls -la, stat mtime）
- P0: 添加行数/大小变化检查

## v3.7更新（自我审计后迭代）
- P0: 修复verify_with_ralph空转问题 - 添加DEFAULT_CHECK_FUNCTIONS
- P0: SafetyPolicy集成 - check_dangerous_command()危险命令检查
- P1: 修复SKILL.md章节编号（零~十五连续编号）

## v3.6更新
- Phase 1: OpenClaw Hook深度集成（sindri-executor-reminder v2.0）
- Phase 2: runTimeoutSeconds参数确认正确
- Phase 3: 真正集成Ralph 3轮验证机制

## 核心组件
1. sindris_executor.py - 唯一执行引擎（含plan/run两个方法）
2. scripts/safety_policy.py - 危险操作拦截（已集成）
3. scripts/ralph_loop.py - 3轮验证机制（已集成）
4. scripts/telemetry_collector.py - 运行时遥测收集（v3.8已集成）
5. scripts/omx_integrator.py - OMX持久化层（v3.8已集成）

## scripts/目录下的其他模块（可选集成）
- sindris_tmux_manager.py - tmux Worker运行时（OpenClaw sessions_spawn已提供）
- task_queue.py - 任务队列管理（可选）
- memory_manager.py - 任务记忆（MEMORY.md已够用）
- sindris_hud.py - 实时显示（session_status已够用）

## 角色库
- 178角色库 - 专业角色匹配
- roles/ - sindris专用角色定义

## 触发条件
- 复杂任务需要拆分为子任务
- 需要多角色协作（178角色库匹配）
- 需要外部验收机制保证质量
- 需要失败自动恢复能力

## v1.9更新
- match_roles.py: 优化角色匹配逻辑
  * 添加GENERAL_TERMS通用词列表
  * 通用词匹配大幅降低分数
  * 避免"python, bug"触发Blender等问题

## v1.8更新
- 完善任务理解与fallback机制

## v1.5更新（执行层增强）
- agent_executor.py: 三级降级执行器
  * Level 1: sessions_spawn（OpenClaw内置）
  * Level 2: DeepSeek API直接调用
  * Level 3: 本地代码执行（兜底）
  * 绕过sessions_spawn的20%失败率问题

## v1.3更新（Phase1+Phase2+Phase3+Phase4）
- Phase1: safety_policy + review_logger
- Phase2: telemetry_collector + memory_manager
- Phase3: task_queue + blocked管理
- Phase4: sindris_hud

## v1.2更新
- 新增plan()方法，返回subtasks列表供sessions_spawn执行
- 修复sessions_spawn对接问题（真实执行）
