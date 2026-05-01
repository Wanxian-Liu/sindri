"""
并行与多份 checkout 并存时，部分用例会把 ~/.openclaw/.../scripts 插到 sys.path 首位，
导致先加载旧版 circuit_breaker（例如 call() 无重试循环）。每个用例开始前强制以本仓库
scripts 为准并丢弃已缓存的错误模块副本。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def pytest_configure(config) -> None:  # noqa: ARG001
    """尽早注入占位 API key，避免 xdist 子进程/未推送新代码时 deepseek_call 在 mock 前失败。"""
    os.environ.setdefault(
        "DEEPSEEK_API_KEY",
        "pytest-ci-placeholder-not-a-real-secret",
    )

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_SCRIPTS = _REPO_ROOT / "scripts"
_EXPECTED_CB = (_REPO_SCRIPTS / "circuit_breaker.py").resolve()


def _ensure_repo_circuit_breaker() -> None:
    scripts = str(_REPO_SCRIPTS)
    if not sys.path or sys.path[0] != scripts:
        sys.path.insert(0, scripts)
    mod = sys.modules.get("circuit_breaker")
    if mod is None:
        return
    path = getattr(mod, "__file__", None)
    if not path:
        del sys.modules["circuit_breaker"]
        return
    try:
        if Path(path).resolve() != _EXPECTED_CB:
            del sys.modules["circuit_breaker"]
    except OSError:
        del sys.modules["circuit_breaker"]


@pytest.fixture(autouse=True)
def _sindris_repo_circuit_breaker_first() -> None:
    _ensure_repo_circuit_breaker()
    yield
