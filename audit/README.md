# Sindris 审计入口（当前有效结论）

本文件是 `audit/` 目录的**唯一推荐入口**。  
目标：避免直接引用历史报告导致误判，统一以当前版本事实决策。

---

## 当前基线（生效）

- **产品/技能名**: `Sindris`
- **当前版本**: `v4.1`
- **代码版本源**: `sindris_executor.py` 中 `VERSION = "4.1"`
- **技能版本源**: `SKILL.md` 中 `version: "4.1"`
- **质量门禁**:
  - 全量回归：`python3 -m pytest tests/`
  - 发布契约：`python3 -m pytest tests/test_release_contract.py`
- **CI（GitHub）**: `.github/workflows/ci.yml` — 对 `main` / `master` 的 push 与 PR 在 Python 3.11、3.12 上运行上述命令。

---

## 报告分层规则

### 1) 当前有效结论（用于执行）

只接受以下来源作为当前执行依据：

- 当前源码实现（`sindris_executor.py`、`modules/`、`scripts/`）
- `SKILL.md`（已对齐 v4.1）
- 测试结果（全量回归 + release contract）

### 2) 历史快照（用于追踪）

以下报告均为历史审计快照，主要用于“为什么当时做过这些改动”：

- `security_report.md`
- `qa_report.md`
- `docs_report.md`
- `code_reviewer_report.md`
- `AUDIT_PLAN.md`

这些文件顶部已添加“归档状态/状态更新”。  
**禁止**直接把历史条目当作当前阻断项，必须先与当前源码和测试交叉验证。

---

## 快速检查清单（每次改动后）

1. 版本一致性：
   - `SKILL.md` 版本 = `sindris_executor.VERSION`
2. 命名一致性：
   - 禁止回引 `A2/A2v3`，统一使用 `Sindris v4.1`
3. 路径可迁移性：
   - 禁止引入用户机器绝对路径（例如 `/home/<user>/.openclaw/...`）
4. 门禁通过：
   - `tests/test_release_contract.py` 通过
   - 全量 `tests/` 通过

---

## 个人编排自检（单人使用）

OpenClaw 下 spawn / yield / trace 的**最短清单**：[`docs/personal-orchestration-checklist.md`](../docs/personal-orchestration-checklist.md)

---

## 维护约定

- 当版本升级（例如 `v4.2`）时，先改版本源，再更新本 README 的“当前基线”。
- 当历史报告与现状冲突时：
  1) 先更新代码/测试事实；
  2) 再在历史报告顶部追加归档说明；
  3) 最后更新本 README 的注意事项。

