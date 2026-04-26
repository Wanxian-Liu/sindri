#!/usr/bin/env python3
"""Release contract checks for Sindris v4.1."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = ROOT / "SKILL.md"
EXECUTOR = ROOT / "sindris_executor.py"
REGISTER_ROLES = ROOT / "scripts" / "register_roles.py"
INSTALL_SCRIPT = ROOT / "install_sindri.sh"


def _extract_version(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.MULTILINE)
    assert match, f"Pattern not found: {pattern}"
    return match.group(1)


def test_skill_and_executor_version_are_aligned():
    """SKILL.md version must match sindris_executor.VERSION."""
    skill_text = SKILL_MD.read_text(encoding="utf-8")
    executor_text = EXECUTOR.read_text(encoding="utf-8")

    skill_version = _extract_version(skill_text, r'^version:\s*"([^"]+)"')
    code_version = _extract_version(executor_text, r'^VERSION\s*=\s*"([^"]+)"')

    assert skill_version == code_version == "4.1"


def test_skill_has_no_a2_terminology():
    """Public skill docs should not use A2 naming anymore."""
    skill_text = SKILL_MD.read_text(encoding="utf-8")
    assert "A2" not in skill_text
    assert "A2v3" not in skill_text


def test_runtime_scripts_have_no_user_specific_absolute_paths():
    """Runtime scripts should avoid hardcoded local user paths."""
    register_text = REGISTER_ROLES.read_text(encoding="utf-8")
    assert "/home/rayliu/.openclaw/skills/sindris" not in register_text


def test_install_script_uses_sindris_naming():
    """Installer guidance should use Sindris naming only."""
    install_text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "执行A2" not in install_text
    assert "执行Sindris" in install_text
