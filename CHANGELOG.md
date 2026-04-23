# Changelog - sindris 版本历史

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
