# Contributing to Sindris

## Quick checks

```bash
pip install pytest pytest-anyio ruff bandit
python -m pytest tests/ -q
ruff check scripts modules validators contracts sindris_executor.py tests
```

CI runs Python **3.11** and **3.12** on Ubuntu; match that before opening a PR.

## Pull requests

- One logical change per PR when possible.
- Update [`CHANGELOG.md`](CHANGELOG.md) for user-visible behavior or version bumps.
- If you change `VERSION` in `sindris_executor.py`, align `SKILL.md` `version:` and [`tests/test_release_contract.py`](tests/test_release_contract.py).

## Security

- Do not commit secrets (API keys, tokens). Tests use mocks or `DEEPSEEK_API_KEY=ci_dummy_key` in CI.
- Prefer extending the Ralph `check_fn` allowlist in code rather than disabling safety checks in tests.

## Docs

- Chinese overview: [`README.md`](README.md)
- English overview: [`README.en.md`](README.en.md)
- Memory / OMX bridge: [`docs/MEMORY_OMX_CONTRACT.md`](docs/MEMORY_OMX_CONTRACT.md)
