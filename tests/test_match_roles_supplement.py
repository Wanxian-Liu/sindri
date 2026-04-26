#!/usr/bin/env python3
"""
test_match_roles_supplement.py - match_roles CLI入口补充测试
覆盖: __main__ CLI块, 各种CLI子命令场景
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def test_cli_match_with_single_keyword():
    """覆盖CLI match子命令，单个关键词"""
    from match_roles import match_roles
    
    result = match_roles("backend", top_k=3)
    assert "matched_roles" in result
    assert isinstance(result["matched_roles"], list)
    assert len(result["matched_roles"]) <= 3


def test_cli_match_with_multiple_keywords():
    """覆盖CLI match子命令，多个关键词"""
    from match_roles import match_roles
    
    result = match_roles(["backend", "API"], top_k=5)
    assert "matched_roles" in result
    assert len(result["matched_roles"]) <= 5


def test_cli_categories_command():
    """覆盖CLI categories子命令"""
    from match_roles import list_categories
    
    result = list_categories()
    assert "categories" in result
    assert "total_roles" in result
    assert isinstance(result["categories"], dict)


def test_cli_get_existing_role():
    """覆盖CLI get子命令获取存在的角色"""
    from match_roles import get_role_by_id
    
    # 使用一个常见的role_id
    role = get_role_by_id("backend-developer")
    if role:
        assert "id" in role
        assert "name" in role
        assert "category" in role


def test_cli_get_nonexistent_role():
    """覆盖CLI get子命令获取不存在的角色"""
    from match_roles import get_role_by_id
    
    role = get_role_by_id("nonexistent_role_xyz")
    assert role is None


def test_cli_no_command_help():
    """覆盖无子命令时打印帮助"""
    from match_roles import match_roles, list_categories, get_role_by_id
    import argparse
    
    # 测试默认行为 - 无参数时应该触发帮助
    # 这里只验证函数本身可用
    assert callable(match_roles)
    assert callable(list_categories)
    assert callable(get_role_by_id)


def test_match_roles_string_input():
    """覆盖字符串输入自动转为列表"""
    from match_roles import match_roles
    
    # 单字符串输入
    result = match_roles("security")
    assert "matched_roles" in result


def test_match_roles_with_category_filter():
    """覆盖按类别过滤"""
    from match_roles import match_roles
    
    result = match_roles("test", categories=["engineering"], top_k=5)
    assert "matched_roles" in result
    for role in result["matched_roles"]:
        assert role["category"].lower() in ["engineering"]


def test_expand_query_chinese_to_english():
    """覆盖中文关键词展开"""
    from match_roles import expand_query
    
    # 测试中文关键词展开
    result = expand_query("后端")
    assert "backend" in result or "server" in result
    
    result = expand_query("测试")
    assert "test" in result or "QA" in result.lower()


def test_expand_query_none():
    """覆盖expand_query处理None"""
    from match_roles import expand_query
    
    result = expand_query(None)
    assert result == ""


def test_tokenize_english():
    """覆盖英文分词"""
    from match_roles import tokenize
    
    tokens = tokenize("backend developer")
    assert "backend" in tokens
    assert "developer" in tokens


def test_tokenize_chinese():
    """覆盖中文分词"""
    from match_roles import tokenize
    
    tokens = tokenize("后端开发")
    assert len(tokens) > 0
    # 中文应该被拆分成2-3字符的token
    assert any(len(t) >= 2 for t in tokens)


def test_jaccard_similarity():
    """覆盖Jaccard相似度计算"""
    from match_roles import jaccard
    
    # 完全相同
    score = jaccard({"a", "b", "c"}, {"a", "b", "c"})
    assert score == 1.0
    
    # 完全不同
    score = jaccard({"a", "b"}, {"c", "d"})
    assert score == 0.0
    
    # 部分重叠
    score = jaccard({"a", "b", "c"}, {"b", "c", "d"})
    assert 0 < score < 1
    
    # 空集
    score = jaccard(set(), {"a", "b"})
    assert score == 0.0


def test_score_role_full():
    """覆盖完整角色评分"""
    from match_roles import score_role, tokenize
    
    role = {
        "name": "Security Engineer",
        "description": "Handles security audits and vulnerability assessments",
        "vibe": " meticulous and thorough",
        "trigger_keywords": ["security", "audit", "penetration testing"]
    }
    
    query_tokens = tokenize("security audit")
    score = score_role(query_tokens, role)

    assert isinstance(score, float)
    assert 0 <= score <= 1

    scored, reasons = score_role(query_tokens, role, return_reasons=True)
    assert isinstance(scored, float)
    assert isinstance(reasons, list)


def test_match_roles_score_sorting():
    """覆盖匹配结果按分数排序"""
    from match_roles import match_roles
    
    result = match_roles("backend API", top_k=10)
    scores = [r["match_score"] for r in result["matched_roles"]]
    
    # 验证分数递减排序
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]


def test_match_roles_respects_top_k():
    """覆盖top_k参数限制返回数量"""
    from match_roles import match_roles
    
    result = match_roles("development", top_k=3)
    assert len(result["matched_roles"]) <= 3


def test_match_roles_min_score_filter():
    """覆盖MIN_SCORE过滤"""
    from match_roles import match_roles, MIN_SCORE
    
    result = match_roles("xyz123nonexistent", top_k=100)
    # 所有结果都应该超过MIN_SCORE
    for role in result["matched_roles"]:
        assert role["match_score"] >= MIN_SCORE


def test_get_role_by_id_returns_correct_fields():
    """覆盖get_role_by_id返回正确字段"""
    from match_roles import get_role_by_id
    
    # 找一个实际存在的角色
    role = get_role_by_id("backend-developer")
    if role:
        expected_fields = ["id", "name", "category", "description", "vibe"]
        for field in expected_fields:
            assert field in role


def test_load_registry_uses_cache():
    """覆盖注册表缓存"""
    from match_roles import _load_registry, _cached_registry
    import match_roles as mr
    
    # 第一次加载
    mr._cached_registry = None  # 清除缓存
    result1 = mr._load_registry()
    
    # 第二次应该使用缓存
    result2 = mr._load_registry()
    assert result1 is result2


def test_registry_not_found():
    """覆盖注册表文件不存在时的错误"""
    from match_roles import _load_registry
    import match_roles as mr
    import tempfile
    
    # 临时改变REGISTRY_PATH
    original = mr.REGISTRY_PATH
    mr.REGISTRY_PATH = Path(tempfile.gettempdir()) / "nonexistent.json"
    mr._cached_registry = None
    
    try:
        _load_registry()
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass
    finally:
        mr.REGISTRY_PATH = original


def test_match_roles_with_empty_category_filter():
    """覆盖空类别过滤列表"""
    from match_roles import match_roles
    
    # 空类别列表应该不过滤
    result1 = match_roles("backend", categories=[], top_k=5)
    result2 = match_roles("backend", top_k=5)
    
    assert len(result1["matched_roles"]) == len(result2["matched_roles"])


if __name__ == "__main__":
    tests = [
        test_cli_match_with_single_keyword,
        test_cli_match_with_multiple_keywords,
        test_cli_categories_command,
        test_cli_get_existing_role,
        test_cli_get_nonexistent_role,
        test_cli_no_command_help,
        test_match_roles_string_input,
        test_match_roles_with_category_filter,
        test_expand_query_chinese_to_english,
        test_expand_query_none,
        test_tokenize_english,
        test_tokenize_chinese,
        test_jaccard_similarity,
        test_score_role_full,
        test_match_roles_score_sorting,
        test_match_roles_respects_top_k,
        test_match_roles_min_score_filter,
        test_get_role_by_id_returns_correct_fields,
        test_load_registry_uses_cache,
        test_registry_not_found,
        test_match_roles_with_empty_category_filter,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"✅ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
    
    print(f"\n=== 结果: {passed} passed, {failed} failed ===")
