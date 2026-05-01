# 个人用 · Sindris 编排最小检查表

仅主会话里的 Agent 执行；**每轮**子任务按顺序自检。完整说明与代码模板见根目录 `SKILL.md`（「主 Agent 编排模板」）。

1. 规划后记下 **`_trace_id`**（`execute()` 返回值）。
2. **`sessions_spawn`** 返回后立刻记下 **`runId`**、**`childSessionKey`**，并调用 **`record_spawn_result`**。
3. **`sessions_yield` 前**调用 **`record_yield_boundary(..., phase="before_yield")`**；子结果到齐后再 **`after_yield`**。
4. 子任务结束：**`complete_subtask` / `fail_subtask`**，并 **`mark_action_complete(..., trace_id=...)`**。
5. 在仓库根执行 **`python3 scripts/trace_report.py --latest`**（或带上具体 `trace_id`），确认 **`summary.complete`** 或明确缺哪一项。
6. 有代码改动：**跑测试并 commit**（与 `SKILL.md` 强制规则一致）。
7. 需要干净子上下文时 spawn 用 **`context: "isolated"`**；否则默认 **`fork`**。
