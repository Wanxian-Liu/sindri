#!/usr/bin/env python3
"""
test_consensus_officer.py - ConsensusOfficer共识投票官完整测试

测试覆盖：
1. 严格格式 [CONSENSUS: YES/NO] 解析
2. 宽松格式 (consensus: yes, **consensus**: YES等) 解析
3. 中文格式 (共识投票: YES)
4. 无匹配时默认NO
5. 多数投票check_majority
6. 投票历史记录
7. 多数投票结果获取
8. 状态查询
9. 重置功能
10. 快捷函数
11. 边界条件
"""

import sys
from pathlib import Path

# 设置路径
SCRIPT_DIR = Path("/home/rayliu/.openclaw/skills/sindris/scripts")
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

def assert_false(condition, msg=""):
    if condition:
        raise AssertionError(f"{msg}: expected falsy, got {condition!r}")


# ============================================================
# 测试类
# ============================================================

def test_strict_format_yes():
    """测试1: 严格格式 [CONSENSUS: YES]"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    # 基本格式
    result = officer.parse_consensus("结果完成 [CONSENSUS: YES] 完毕")
    assert_true(result.has_consensus)
    assert_eq(result.vote, "YES")
    assert_eq(result.confidence, 1.0)
    assert result.raw_match is not None
    print("✓ test_strict_format_yes passed")


def test_strict_format_no():
    """测试2: 严格格式 [CONSENSUS: NO]"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("有问题 [CONSENSUS: NO] 需要修改")
    assert_false(result.has_consensus)
    assert_eq(result.vote, "NO")
    assert_eq(result.confidence, 1.0)
    print("✓ test_strict_format_no passed")


def test_strict_format_case_insensitive():
    """测试3: 严格格式大小写不敏感"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    tests = [
        "[consensus: yes]",
        "[Consensus: YES]",
        "[CONSENSUS: Yes]",
        "共识投票: YES",  # 中文宽松格式
    ]
    
    for test in tests:
        result = officer.parse_consensus(test)
        assert_eq(result.vote, "YES", f"Failed for: {test}")
    print("✓ test_strict_format_case_insensitive passed")


def test_variant_format_consensus_colon():
    """测试4: 宽松格式 consensus: yes"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("consensus: yes")
    assert_true(result.has_consensus)
    assert_eq(result.vote, "YES")
    assert_eq(result.confidence, 0.8)
    print("✓ test_variant_format_consensus_colon passed")


def test_variant_format_double_asterisk():
    """测试5: 宽松格式 **consensus**: YES"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("**consensus**: YES")
    assert_true(result.has_consensus)
    assert_eq(result.vote, "YES")
    assert_eq(result.confidence, 0.8)
    print("✓ test_variant_format_double_asterisk passed")


def test_variant_format_equals():
    """测试6: 宽松格式 CONSENSUS=YES"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("CONSENSUS=YES")
    assert_true(result.has_consensus)
    assert_eq(result.vote, "YES")
    print("✓ test_variant_format_equals passed")


def test_variant_format_chinese():
    """测试7: 宽松格式中文 共识投票: YES"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("共识投票: YES")
    assert_true(result.has_consensus)
    assert_eq(result.vote, "YES")
    print("✓ test_variant_format_chinese passed")


def test_variant_format_no_consensus():
    """测试8: 宽松格式 NO"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("consensus: no")
    assert_false(result.has_consensus)
    assert_eq(result.vote, "NO")
    print("✓ test_variant_format_no_consensus passed")


def test_no_consensus_marker():
    """测试9: 无共识标记"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.parse_consensus("这是一个普通的结果，没有投票")
    assert_false(result.has_consensus)
    assert_eq(result.vote, "NO")
    assert_eq(result.confidence, 0.0)
    assert result.raw_match is None
    print("✓ test_no_consensus_marker passed")


def test_last_match_wins():
    """测试10: 取最后一个匹配"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    # 两个YES，但最后一个是NO
    result = officer.parse_consensus("[CONSENSUS: YES] 然后 [CONSENSUS: NO]")
    assert_false(result.has_consensus)
    assert_eq(result.vote, "NO")
    print("✓ test_last_match_wins passed")


def test_check_majority_empty():
    """测试11: 多数投票空列表"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    result = officer.check_majority([])
    assert_false(result)
    print("✓ test_check_majority_empty passed")


def test_check_majority_all_yes():
    """测试12: 多数投票全是YES"""
    from consensus_officer import ConsensusOfficer, VoteResult
    
    officer = ConsensusOfficer(threshold=0.5)
    
    votes = [
        VoteResult(True, "YES", 1.0, None),
        VoteResult(True, "YES", 1.0, None),
        VoteResult(True, "YES", 1.0, None),
    ]
    
    assert_true(officer.check_majority(votes))
    print("✓ test_check_majority_all_yes passed")


def test_check_majority_all_no():
    """测试13: 多数投票全是NO"""
    from consensus_officer import ConsensusOfficer, VoteResult
    
    officer = ConsensusOfficer(threshold=0.5)
    
    votes = [
        VoteResult(False, "NO", 1.0, None),
        VoteResult(False, "NO", 1.0, None),
    ]
    
    assert_false(officer.check_majority(votes))
    print("✓ test_check_majority_all_no passed")


def test_check_majority_split():
    """测试14: 多数投票平票"""
    from consensus_officer import ConsensusOfficer, VoteResult
    
    officer = ConsensusOfficer(threshold=0.5)
    
    votes = [
        VoteResult(True, "YES", 1.0, None),
        VoteResult(False, "NO", 1.0, None),
    ]
    
    # 50%刚好满足阈值>=0.5，所以返回True
    assert_true(officer.check_majority(votes))
    
    # 降低阈值到0.6，50%不满足
    officer.threshold = 0.6
    assert_false(officer.check_majority(votes))
    print("✓ test_check_majority_split passed")


def test_check_majority_custom_threshold():
    """测试15: 自定义阈值"""
    from consensus_officer import ConsensusOfficer, VoteResult
    
    # 阈值0.6，需要超过60%
    officer = ConsensusOfficer(threshold=0.6)
    
    votes = [
        VoteResult(True, "YES", 1.0, None),
        VoteResult(True, "YES", 1.0, None),
        VoteResult(False, "NO", 1.0, None),
    ]
    
    # 2/3 = 66.7% > 60%
    assert_true(officer.check_majority(votes))
    print("✓ test_check_majority_custom_threshold passed")


def test_add_vote():
    """测试16: 添加投票并记录历史"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    officer.add_vote("[CONSENSUS: YES]")
    officer.add_vote("consensus: no")
    
    assert_eq(len(officer.vote_history), 2)
    assert_eq(officer.vote_history[0].vote, "YES")
    assert_eq(officer.vote_history[1].vote, "NO")
    print("✓ test_add_vote passed")


def test_get_majority_result():
    """测试17: 获取多数投票结果"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    # 2 YES, 1 NO -> majority YES
    officer.add_vote("[CONSENSUS: YES]")
    officer.add_vote("[CONSENSUS: YES]")
    officer.add_vote("[CONSENSUS: NO]")
    
    assert_true(officer.get_majority_result())
    print("✓ test_get_majority_result passed")


def test_get_majority_result_empty():
    """测试18: 空投票历史获取多数结果"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    assert_false(officer.get_majority_result())
    print("✓ test_get_majority_result_empty passed")


def test_get_status_empty():
    """测试19: 空状态查询"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    status = officer.get_status()
    
    assert_eq(status["total_votes"], 0)
    assert_eq(status["yes_votes"], 0)
    assert_eq(status["no_votes"], 0)
    assert_false(status["majority_reached"])
    print("✓ test_get_status_empty passed")


def test_get_status_with_votes():
    """测试20: 有投票的状态查询"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    officer.add_vote("[CONSENSUS: YES]")
    officer.add_vote("[CONSENSUS: YES]")
    officer.add_vote("[CONSENSUS: NO]")
    
    status = officer.get_status()
    
    assert_eq(status["total_votes"], 3)
    assert_eq(status["yes_votes"], 2)
    assert_eq(status["no_votes"], 1)
    assert_true(status["majority_reached"])
    assert_eq(status["last_vote"], "NO")
    print("✓ test_get_status_with_votes passed")


def test_reset():
    """测试21: 重置投票历史"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    officer.add_vote("[CONSENSUS: YES]")
    officer.add_vote("[CONSENSUS: NO]")
    
    assert_eq(len(officer.vote_history), 2)
    
    officer.reset()
    
    assert_eq(len(officer.vote_history), 0)
    assert_false(officer.get_majority_result())
    print("✓ test_reset passed")


def test_parse_consensus_shortcut():
    """测试22: 快捷函数parse_consensus"""
    from consensus_officer import parse_consensus
    
    assert_true(parse_consensus("[CONSENSUS: YES]"))
    assert_false(parse_consensus("[CONSENSUS: NO]"))
    assert_false(parse_consensus("no marker"))
    print("✓ test_parse_consensus_shortcut passed")


def test_has_consensus_marker():
    """测试23: has_consensus_marker函数"""
    from consensus_officer import has_consensus_marker
    
    assert_true(has_consensus_marker("[CONSENSUS: YES]"))
    assert_true(has_consensus_marker("consensus: yes"))
    assert_true(has_consensus_marker("**consensus**: YES"))
    assert_false(has_consensus_marker("普通文本"))
    print("✓ test_has_consensus_marker passed")


def test_strip_consensus_tags():
    """测试24: 移除共识标签"""
    from consensus_officer import strip_consensus_tags
    
    # 严格格式
    result = strip_consensus_tags("结果 [CONSENSUS: YES] 完成")
    assert "CONSENSUS" not in result
    assert "结果" in result
    assert "完成" in result
    
    # 宽松格式
    result = strip_consensus_tags("结果 consensus: YES 完成")
    assert "consensus" not in result.lower() or "consensus:" not in result.lower()
    
    # 无标签
    result = strip_consensus_tags("普通文本")
    assert result == "普通文本"
    print("✓ test_strip_consensus_tags passed")


def test_whitespace_handling():
    """测试25: 空白字符处理"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer()
    
    # 多个空格
    result = officer.parse_consensus("[  CONSENSUS  :  YES  ]")
    assert_true(result.has_consensus)
    assert_eq(result.vote, "YES")
    
    # 换行
    result = officer.parse_consensus("[CONSENSUS:\nYES]")
    assert_true(result.has_consensus)
    print("✓ test_whitespace_handling passed")


def test_threshold_init():
    """测试26: 阈值初始化"""
    from consensus_officer import ConsensusOfficer
    
    officer = ConsensusOfficer(threshold=0.7)
    assert_eq(officer.threshold, 0.7)
    print("✓ test_threshold_init passed")


# ============================================================
# 主函数
# ============================================================

def run_all_tests():
    tests = [
        test_strict_format_yes,
        test_strict_format_no,
        test_strict_format_case_insensitive,
        test_variant_format_consensus_colon,
        test_variant_format_double_asterisk,
        test_variant_format_equals,
        test_variant_format_chinese,
        test_variant_format_no_consensus,
        test_no_consensus_marker,
        test_last_match_wins,
        test_check_majority_empty,
        test_check_majority_all_yes,
        test_check_majority_all_no,
        test_check_majority_split,
        test_check_majority_custom_threshold,
        test_add_vote,
        test_get_majority_result,
        test_get_majority_result_empty,
        test_get_status_empty,
        test_get_status_with_votes,
        test_reset,
        test_parse_consensus_shortcut,
        test_has_consensus_marker,
        test_strip_consensus_tags,
        test_whitespace_handling,
        test_threshold_init,
    ]

    print("=" * 60)
    print("ConsensusOfficer 共识投票官测试")
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
