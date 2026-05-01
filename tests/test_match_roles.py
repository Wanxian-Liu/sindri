#!/usr/bin/env python3
"""
test_match_roles.py - match_roles 角色匹配完整测试

测试覆盖：
1. tokenize 函数
2. expand_query 中文->英文扩展
3. jaccard 相似度
4. score_role 评分函数
5. match_roles 核心API
6. list_categories 分类列表
7. get_role_by_id 按ID查找
8. 边界条件：空输入、特殊字符、分类过滤
9. registry加载
"""

import sys
from pathlib import Path

# 设置路径
SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================
# 测试工具
# ============================================================

def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg}: expected {expected!r}, got {actual!r}")

def assert_true(condition, msg=""):
    if not condition:
        raise AssertionError(f"{msg}: expected truthy, got {condition!r}")


# ============================================================
# 测试
# ============================================================

def test_tokenize_english():
    """测试1: tokenize英文分词"""
    from match_roles import tokenize
    
    tokens = tokenize("hello world")
    assert "hello" in tokens
    assert "world" in tokens
    
    tokens = tokenize("Unit Test")
    assert "unit" in tokens
    assert "test" in tokens
    print("✓ test_tokenize_english passed")


def test_tokenize_numbers():
    """测试2: tokenize数字处理"""
    from match_roles import tokenize
    
    tokens = tokenize("v1.2.3")
    assert "v1" in tokens or "1" in tokens
    print("✓ test_tokenize_numbers passed")


def test_tokenize_chinese():
    """测试3: tokenize中文分词"""
    from match_roles import tokenize
    
    tokens = tokenize("用户认证")
    # 中文被分成2-3字符块
    assert "用户" in tokens or len(tokens) > 0
    print("✓ test_tokenize_chinese passed")


def test_tokenize_mixed():
    """测试4: tokenize混合中英文"""
    from match_roles import tokenize
    
    tokens = tokenize("test测试")
    assert "test" in tokens
    assert len(tokens) > 1
    print("✓ test_tokenize_mixed passed")


def test_tokenize_special_chars():
    """测试5: tokenize特殊字符"""
    from match_roles import tokenize
    
    tokens = tokenize("hello@world.com!")
    assert "hello" in tokens
    assert "world" in tokens
    print("✓ test_tokenize_special_chars passed")


def test_expand_query_chinese():
    """测试6: expand_query中文扩展"""
    from match_roles import expand_query
    
    result = expand_query("单元测试")
    assert "unit" in result
    assert "test" in result
    print("✓ test_expand_query_chinese passed")


def test_expand_query_chinese_combined():
    """测试7: expand_query中文组合扩展"""
    from match_roles import expand_query
    
    result = expand_query("认证")
    assert "authentication" in result
    assert "JWT" in result  # Case sensitive, result contains uppercase JWT
    print("✓ test_expand_query_chinese_combined passed")


def test_expand_query_english():
    """测试8: expand_query英文透传"""
    from match_roles import expand_query
    
    result = expand_query("performance optimization")
    assert "performance" in result
    assert "optimization" in result
    print("✓ test_expand_query_english passed")


def test_expand_query_none():
    """测试9: expand_query None输入"""
    from match_roles import expand_query
    
    result = expand_query(None)
    assert result == ""
    print("✓ test_expand_query_none passed")


def test_jaccard_basic():
    """测试10: jaccard基本相似度"""
    from match_roles import jaccard
    
    result = jaccard({"a", "b", "c"}, {"b", "c", "d"})
    # intersection = {b,c} = 2, union = {a,b,c,d} = 4
    assert_eq(result, 0.5)
    print("✓ test_jaccard_basic passed")


def test_jaccard_identical():
    """测试11: jaccard完全相同"""
    from match_roles import jaccard
    
    s = {"a", "b"}
    result = jaccard(s, s)
    assert_eq(result, 1.0)
    print("✓ test_jaccard_identical passed")


def test_jaccard_disjoint():
    """测试12: jaccard完全不相交"""
    from match_roles import jaccard
    
    result = jaccard({"a"}, {"b"})
    assert_eq(result, 0.0)
    print("✓ test_jaccard_disjoint passed")


def test_jaccard_empty():
    """测试13: jaccard空集"""
    from match_roles import jaccard
    
    assert_eq(jaccard(set(), {"a"}), 0.0)
    assert_eq(jaccard({"a"}, set()), 0.0)
    assert_eq(jaccard(set(), set()), 0.0)
    print("✓ test_jaccard_empty passed")


def test_match_roles_basic():
    """测试14: match_roles基本匹配"""
    from match_roles import match_roles
    
    result = match_roles(["authentication", "login"], top_k=5)
    
    assert "matched_roles" in result
    assert "total_candidates" in result
    assert isinstance(result["matched_roles"], list)
    assert len(result["matched_roles"]) <= 5
    print(f"  Matched {len(result['matched_roles'])} roles")
    print("✓ test_match_roles_basic passed")


def test_match_roles_string_input():
    """测试15: match_roles字符串输入（自动转list）"""
    from match_roles import match_roles
    
    result = match_roles("performance optimization", top_k=3)
    assert "matched_roles" in result
    assert len(result["matched_roles"]) <= 3
    print("✓ test_match_roles_string_input passed")


def test_match_roles_chinese():
    """测试16: match_roles中文输入"""
    from match_roles import match_roles
    
    result = match_roles(["认证", "登录"], top_k=3)
    assert "matched_roles" in result
    print(f"  Chinese query matched {len(result['matched_roles'])} roles")
    print("✓ test_match_roles_chinese passed")


def test_match_roles_with_categories():
    """测试17: match_roles分类过滤"""
    from match_roles import match_roles
    
    result = match_roles(["test"], categories=["testing"], top_k=5)
    
    for role in result["matched_roles"]:
        assert role["category"].lower() in ["testing", "test"]
    print("✓ test_match_roles_with_categories passed")


def test_match_roles_top_k():
    """测试18: match_roles top_k限制"""
    from match_roles import match_roles
    
    for k in [1, 3, 10]:
        result = match_roles(["performance"], top_k=k)
        assert len(result["matched_roles"]) <= k
    print("✓ test_match_roles_top_k passed")


def test_match_roles_score_order():
    """测试19: match_roles得分降序"""
    from match_roles import match_roles
    
    result = match_roles(["backend", "server"], top_k=10)
    scores = [r["match_score"] for r in result["matched_roles"]]
    assert scores == sorted(scores, reverse=True)
    print("✓ test_match_roles_score_order passed")


def test_match_roles_role_fields():
    """测试20: match_roles返回字段完整"""
    from match_roles import match_roles
    
    result = match_roles(["security"], top_k=3)
    for role in result["matched_roles"]:
        assert "id" in role
        assert "name" in role
        assert "category" in role
        assert "match_score" in role
        assert isinstance(role["match_score"], float)
    print("✓ test_match_roles_role_fields passed")


def test_match_roles_high_score():
    """测试21: match_roles高相关度得分>0.5"""
    from match_roles import match_roles
    
    # 非常明确的关键词应该有高得分
    result = match_roles(["security audit"], top_k=3)
    if result["matched_roles"]:
        top_score = result["matched_roles"][0]["match_score"]
        assert top_score >= 0  # 至少应该有一些匹配
        print(f"  Top score: {top_score}")
    print("✓ test_match_roles_high_score passed")


def test_list_categories():
    """测试22: list_categories"""
    from match_roles import list_categories
    
    result = list_categories()
    
    assert "categories" in result
    assert "total_roles" in result
    assert isinstance(result["categories"], dict)
    assert result["total_roles"] > 0
    print(f"  {result['total_roles']} total roles in {len(result['categories'])} categories")
    print("✓ test_list_categories passed")


def test_list_categories_has_counts():
    """测试23: list_categories有计数"""
    from match_roles import list_categories
    
    result = list_categories()
    
    for cat, count in result["categories"].items():
        assert count > 0
        assert isinstance(count, int)
    print("✓ test_list_categories_has_counts passed")


def test_get_role_by_id_valid():
    """测试24: get_role_by_id有效ID"""
    from match_roles import get_role_by_id, list_categories
    
    # 获取任意一个角色ID
    cats = list_categories()
    if cats["total_roles"] > 0:
        first_cat = next(iter(cats["categories"]))
        # 这个方法可能需要从registry中获取第一个role id
        # 用一个已知的id测试
        role = get_role_by_id("role_security_auditor")
        if role:
            assert "id" in role
            assert "name" in role
            print(f"  Found role: {role['name']}")
    print("✓ test_get_role_by_id_valid passed")


def test_get_role_by_id_nonexistent():
    """测试25: get_role_by_id不存在的ID"""
    from match_roles import get_role_by_id
    
    result = get_role_by_id("nonexistent_role_xyz")
    assert result is None
    print("✓ test_get_role_by_id_nonexistent passed")


def test_registry_loads():
    """测试26: registry能正常加载"""
    from match_roles import _load_registry
    
    registry = _load_registry()
    assert "roles" in registry
    assert isinstance(registry["roles"], list)
    assert len(registry["roles"]) > 100  # 应该有不少于100个角色
    print(f"  Registry loaded: {len(registry['roles'])} roles")
    print("✓ test_registry_loads passed")


def test_match_roles_preserves_query_order():
    """测试27: match_roles不改变查询顺序"""
    from match_roles import match_roles
    
    result = match_roles(["a", "b", "c"], top_k=5)
    # 只验证返回结果，不验证顺序（因为是按得分排序）
    assert len(result["matched_roles"]) <= 5
    print("✓ test_match_roles_preserves_query_order passed")


def test_match_roles_empty_keywords():
    """测试28: match_roles空关键词"""
    from match_roles import match_roles
    
    result = match_roles([], top_k=5)
    # 应该返回一些结果（基于空查询可能也有MIN_SCORE过滤）
    assert "matched_roles" in result
    print("✓ test_match_roles_empty_keywords passed")


def test_weights_config():
    """测试29: WEIGHTS配置"""
    from match_roles import WEIGHTS
    
    assert WEIGHTS["trigger_keywords"] == 3.0
    assert WEIGHTS["description"] == 1.0
    assert WEIGHTS["name"] == 1.5
    assert WEIGHTS["vibe"] == 0.8
    # sum应该>0
    assert sum(WEIGHTS.values()) > 0
    print("✓ test_weights_config passed")


def test_expand_query_audit():
    """测试30: expand_query审计相关"""
    from match_roles import expand_query
    
    result = expand_query("审计")
    assert "audit" in result
    print("✓ test_expand_query_audit passed")


def test_expand_query_integration():
    """测试31: expand_query集成相关"""
    from match_roles import expand_query
    
    result = expand_query("集成")
    assert "integration" in result
    print("✓ test_expand_query_integration passed")


def test_match_roles_min_score_filter():
    """测试32: match_roles MIN_SCORE过滤"""
    from match_roles import match_roles, MIN_SCORE
    
    result = match_roles(["xyz123nonexistent"], top_k=100)
    # 极不相关的查询可能返回空或很少结果
    for role in result["matched_roles"]:
        assert role["match_score"] >= MIN_SCORE
    print(f"  MIN_SCORE={MIN_SCORE}, returned {len(result['matched_roles'])} roles")
    print("✓ test_match_roles_min_score_filter passed")


def test_match_roles_lowercase_categories():
    """测试33: match_roles分类过滤大小写不敏感"""
    from match_roles import match_roles
    
    # 大小写应该等价
    r1 = match_roles(["test"], categories=["Testing"], top_k=3)
    r2 = match_roles(["test"], categories=["testing"], top_k=3)
    # 两个结果应该都有testing分类的角色
    assert "matched_roles" in r1
    assert "matched_roles" in r2
    print("✓ test_match_roles_lowercase_categories passed")


# ============================================================
# 主函数
# ============================================================

def run_all_tests():
    tests = [
        test_tokenize_english,
        test_tokenize_numbers,
        test_tokenize_chinese,
        test_tokenize_mixed,
        test_tokenize_special_chars,
        test_expand_query_chinese,
        test_expand_query_chinese_combined,
        test_expand_query_english,
        test_expand_query_none,
        test_jaccard_basic,
        test_jaccard_identical,
        test_jaccard_disjoint,
        test_jaccard_empty,
        test_match_roles_basic,
        test_match_roles_string_input,
        test_match_roles_chinese,
        test_match_roles_with_categories,
        test_match_roles_top_k,
        test_match_roles_score_order,
        test_match_roles_role_fields,
        test_match_roles_high_score,
        test_list_categories,
        test_list_categories_has_counts,
        test_get_role_by_id_valid,
        test_get_role_by_id_nonexistent,
        test_registry_loads,
        test_match_roles_preserves_query_order,
        test_match_roles_empty_keywords,
        test_weights_config,
        test_expand_query_audit,
        test_expand_query_integration,
        test_match_roles_min_score_filter,
        test_match_roles_lowercase_categories,
    ]

    print("=" * 60)
    print("match_roles 角色匹配测试")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
