# Sindris

**织界统一协调系统** — OpenClaw 多 Agent 编排技能：`plan` / `execute`、Spawn 公约、`trace_id`、yield 与 OMX 可追溯落盘。

| | |
|---|---|
| **规范真源** | [`SKILL.md`](SKILL.md) |
| **执行引擎** | [`sindris_executor.py`](sindris_executor.py) |
| **版本与变更** | [`CHANGELOG.md`](CHANGELOG.md) |
| **CI** | [![CI](https://github.com/Wanxian-Liu/sindris/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Wanxian-Liu/sindris/actions) |

## 本地测试

```bash
pip install pytest pytest-anyio
python -m pytest tests/ -q
```

## 装入 OpenClaw

将本仓库置于 OpenClaw 的 `skills` 目录（或你的 skills 搜索路径），并在配置中启用该 skill；细节以 `SKILL.md` 为准。

## 许可证

见 `SKILL.md` frontmatter（MIT）。
