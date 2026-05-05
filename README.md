# Sindris

**织界统一协调系统** — OpenClaw 多 Agent 编排技能：`plan` / `execute`、Spawn 公约、`trace_id`、yield 与 OMX 可追溯落盘。

| | |
|---|---|
| **规范真源** | [`SKILL.md`](SKILL.md) |
| **执行引擎** | [`sindris_executor.py`](sindris_executor.py) |
| **版本与变更** | [`CHANGELOG.md`](CHANGELOG.md) |
| **记忆 ↔ OMX** | [`docs/MEMORY_OMX_CONTRACT.md`](docs/MEMORY_OMX_CONTRACT.md) |
| **English** | [`README.en.md`](README.en.md) |
| **参与贡献** | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| **CI** | [![CI](https://github.com/Wanxian-Liu/sindri/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Wanxian-Liu/sindri/actions) |

## 本地测试

```bash
pip install pytest pytest-anyio
python -m pytest tests/ -q
```

## 装入 OpenClaw

1. **克隆仓库**（远程名是 **`sindri`**，不要写成 `sindris`）：  
   `git clone git@github.com:Wanxian-Liu/sindri.git`
2. **放入 skills 路径**：例如将仓库目录链到或复制到  
   `~/.openclaw/skills/sindri`（本地文件夹名可与远程不同，但 **`origin` 应指向上述 `sindri` 仓库**）。
3. **在 OpenClaw / 网关中启用**该 skill（与其它 `skills/` 条目相同方式）。
4. 编排规则、触发词与版本以 [`SKILL.md`](SKILL.md) 为准。

## 许可证

见 `SKILL.md` frontmatter（MIT）。
