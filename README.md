# Sindris

**Zhijie unified orchestration** — an OpenClaw skill for multi-agent workflows: `plan` / `execute`, spawn conventions, `trace_id`, yield, and OMX-friendly persistence.

| | |
|---|---|
| **Spec** | [`SKILL.md`](SKILL.md) |
| **Runtime** | [`sindris_executor.py`](sindris_executor.py) |
| **Changelog** | [`CHANGELOG.md`](CHANGELOG.md) |
| **Memory ↔ OMX** | [`docs/MEMORY_OMX_CONTRACT.md`](docs/MEMORY_OMX_CONTRACT.md) |
| **Contributing** | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| **CI** | [![CI](https://github.com/Wanxian-Liu/sindri/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/Wanxian-Liu/sindri/actions) |

## Install (OpenClaw)

1. Clone this repo (the GitHub name is **`sindri`**, not `sindris`):  
   `git clone git@github.com:Wanxian-Liu/sindri.git`
2. Symlink or copy the folder into your OpenClaw skills directory, e.g.  
   `~/.openclaw/skills/sindri` (the local folder name may differ; **`origin` should point at the `sindri` repo above**).
3. Enable the skill in your OpenClaw / gateway configuration (same as other `skills/` entries).
4. Use [`SKILL.md`](SKILL.md) for triggers, spawn rules, and version notes.

## Local tests

```bash
pip install pytest pytest-anyio
python -m pytest tests/ -q
```

## License

MIT — see `SKILL.md` frontmatter.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
