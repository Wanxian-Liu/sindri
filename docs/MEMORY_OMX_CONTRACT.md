# 任务记忆（MemoryManager）与 OMX `.omx/memory` 契约

> B1：仅约定 sindris 仓库内可测行为；不修改 OMX `tasks.json` 语义。

## 路径

| 概念 | 路径 |
|------|------|
| OMX 根 | 工作区根目录（含 `.omx/` 的目录），由调用方传入 `omx_root` |
| OMX 记忆文件 | `.omx/memory/{namespace}.json`，由 `omx_contract.memory_file(root, namespace)` 解析 |
| 默认导出命名空间 | `sindris_tasks`（可改，但需在调用与文档中一致） |
| MemoryManager 文件记忆 | `workspace/memory/sindris-tasks/YYYY-MM.md`（Markdown 追加） |
| MemoryManager 索引 | `workspace/memory/sindris-tasks/index.jsonl`（每行一条 `TaskMemory` JSON） |

## `TaskMemory`（index 行 / `entries[]` 元素）

与 `memory_manager.TaskMemory.to_dict()` 一致，典型字段：

| 字段 | 说明 |
|------|------|
| `id` | 记忆 id，如 `mem_{task_id}` |
| `task_id` | 关联任务 id |
| `memory_type` | `task_summary` / `lesson_learned` / `decision_record` 等 |
| `content` | 正文摘要或记录 |
| `tags` | 字符串列表 |
| `created_at` | ISO 时间 |
| `importance` | 1–5 |

## OMX 聚合文档（`schema_version: 1`）

由 `memory_omx_bridge.sync_memory_index_to_omx` 写入，顶层结构：

```json
{
  "schema_version": 1,
  "source": "sindris.memory_manager",
  "updated_at": "2026-05-06T12:00:00",
  "entries": [ { "...": "TaskMemory 字典" } ]
}
```

- **幂等**：每次同步覆盖该 `namespace` 下整文件（全量快照，MVP）。
- **与任务 Markdown**：`.md` 为人类可读；**检索与 OMX 导出以 `index.jsonl` 为准**。

## 检索 MVP

- `MemoryManager.search_keyword(query, limit, max_scan)`：在 `index.jsonl` 尾部最多 `max_scan` 行内子串匹配 `content` + `tags`（从新到旧）。

## 后续（非本轮）

- FTS5 / 跨会话索引：保留为独立阶段，不改变上述 JSON 形状时可增量添加字段。
