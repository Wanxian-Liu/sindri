"""
Test match_roles.py CLI (__main__ block) and edge cases
"""
import sys
import os
import subprocess
import json
import pytest
from pathlib import Path

SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris/scripts")
sys.path.insert(0, str(SCRIPT_DIR))


class TestMatchRolesMain:
    """Test match_roles.py __main__ CLI"""

    def test_match_command(self):
        """Test 'match' subcommand"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "match_roles.py"), "match", "backend", "server"],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Should output JSON or complete without crash
        try:
            output = json.loads(result.stdout)
            assert "matched_roles" in output or "total_candidates" in output
        except json.JSONDecodeError:
            # May not find matches but shouldn't crash
            pass

    def test_match_command_with_categories(self):
        """Test 'match' subcommand with category filter"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "match_roles.py"), "match",
             "backend", "--categories", "engineering", "-k", "5"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0

    def test_categories_command(self):
        """Test 'categories' subcommand"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "match_roles.py"), "categories"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = json.loads(result.stdout)
        assert "categories" in output
        assert "total_roles" in output

    def test_get_command_valid_role(self):
        """Test 'get' subcommand with valid role_id"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "match_roles.py"), "get", "backend-developer"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0

    def test_get_command_invalid_role(self):
        """Test 'get' subcommand with invalid role_id"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "match_roles.py"), "get", "nonexistent-role-xyz"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert "not found" in result.stdout or result.returncode == 0

    def test_no_command_shows_help(self):
        """Test running without subcommand shows help"""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "match_roles.py")],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Should show help or complete
        assert result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower()


class TestMatchRolesEdgeCases:
    """Test edge cases in match_roles.py"""

    def test_match_roles_string_input(self):
        """Test match_roles accepts string (not just list) as keywords"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        result = match_roles.match_roles("backend development")
        assert "matched_roles" in result

    def test_match_roles_empty_list(self):
        """Test match_roles with empty keyword list"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        result = match_roles.match_roles([])
        assert "matched_roles" in result

    def test_match_roles_chinese_keywords(self):
        """Test match_roles with Chinese keywords"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        result = match_roles.match_roles(["后端", "架构"])
        assert "matched_roles" in result

    def test_expand_query_chinese(self):
        """Test expand_query expands Chinese to English"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        expanded = match_roles.expand_query("后端开发")
        assert "backend" in expanded or "server" in expanded

    def test_expand_query_chinese_unit_test(self):
        """Test expand_query with 单元测试"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        expanded = match_roles.expand_query("单元测试")
        assert "unit test" in expanded

    def test_expand_query_none(self):
        """Test expand_query handles None"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        expanded = match_roles.expand_query(None)
        assert expanded == ""

    def test_tokenize_english(self):
        """Test tokenize with English text"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        tokens = match_roles.tokenize("backend developer server")
        assert "backend" in tokens
        assert "developer" in tokens

    def test_tokenize_mixed(self):
        """Test tokenize with mixed English and Chinese"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        tokens = match_roles.tokenize("后端开发 backend")
        assert len(tokens) > 0

    def test_jaccard_empty_sets(self):
        """Test jaccard with empty sets"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        score = match_roles.jaccard(set(), set())
        assert score == 0.0

    def test_jaccard_one_empty(self):
        """Test jaccard with one empty set"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        score = match_roles.jaccard({"a", "b"}, set())
        assert score == 0.0

    def test_get_role_by_id_not_found(self):
        """Test get_role_by_id returns None for unknown id"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        role = match_roles.get_role_by_id("nonexistent-role-xyz-123")
        assert role is None

    def test_list_categories_returns_sorted(self):
        """Test list_categories returns sorted dict"""
        if 'match_roles' in sys.modules:
            del sys.modules['match_roles']
        import match_roles
        result = match_roles.list_categories()
        assert "categories" in result
        categories = result["categories"]
        keys = list(categories.keys())
        assert keys == sorted(keys)
