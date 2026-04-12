#!/usr/bin/env python3
"""
test_memory_manager.py - memory_manager.py 完整测试

测试覆盖:
1. TaskMemory dataclass (init, to_dict, from_dict, __post_init__)
2. SummaryGenerator.generate_from_result()
3. SummaryGenerator.extract_keywords()
4. SummaryGenerator.generate_tags()
5. MemoryManager 初始化
6. MemoryManager.save_task_memory()
7. MemoryManager.save_lesson()
8. MemoryManager.save_decision()
9. MemoryManager.get_recent_memories()
10. MemoryManager.get_memories_by_tag()
11. MemoryManager._write_memory()
12. MemoryManager._update_index()
13. get_default_manager()
"""
import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

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

def assert_in(substr, s, msg=""):
    if substr not in s:
        raise AssertionError(f"{msg}: expected {substr!r} in {s!r}")

def assert_false(condition, msg=""):
    if condition:
        raise AssertionError(f"{msg}: expected falsy, got {condition!r}")


# ============================================================
# fixtures
# ============================================================

@pytest.fixture
def temp_memory_dir():
    tmp = tempfile.mkdtemp(prefix="mem_test_")
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TaskMemory
# ============================================================

def test_task_memory_init():
    """测试 TaskMemory 基本初始化"""
    from memory_manager import TaskMemory, MemoryType
    m = TaskMemory(
        id="mem_001",
        task_id="task_001",
        memory_type=MemoryType.TASK_SUMMARY.value,
        content="Test content",
        tags=["test"],
    )
    assert_eq(m.id, "mem_001")
    assert_eq(m.task_id, "task_001")
    assert_true(m.created_at is not None)

def test_task_memory_to_dict():
    """测试 TaskMemory.to_dict()"""
    from memory_manager import TaskMemory, MemoryType
    m = TaskMemory(
        id="mem_002",
        task_id="task_002",
        memory_type=MemoryType.TASK_SUMMARY.value,
        content="Test content",
        tags=["foo", "bar"],
        importance=4,
    )
    d = m.to_dict()
    assert_eq(d["id"], "mem_002")
    assert_eq(d["tags"], ["foo", "bar"])
    assert_eq(d["importance"], 4)
    # TaskMemory has created_at (not updated_at)
    assert_true("created_at" in d)

def test_task_memory_from_dict():
    """测试 TaskMemory.from_dict()"""
    from memory_manager import TaskMemory, MemoryType
    # TaskMemory only has created_at, not updated_at
    d = {
        "id": "mem_003",
        "task_id": "task_003",
        "memory_type": MemoryType.TASK_SUMMARY.value,
        "content": "From dict",
        "tags": ["test"],
        "importance": 3,
        "created_at": "2024-01-01T00:00:00",
    }
    m = TaskMemory.from_dict(d)
    assert_eq(m.id, "mem_003")
    assert_eq(m.content, "From dict")

def test_task_memory_post_init_sets_timestamps():
    """测试 TaskMemory.__post_init__() 自动设置时间戳"""
    from memory_manager import TaskMemory, MemoryType
    from datetime import datetime
    m = TaskMemory(
        id="mem_ts",
        task_id="task_ts",
        memory_type=MemoryType.TASK_SUMMARY.value,
        content="TS test",
        tags=[],
    )
    assert_true(m.created_at is not None)
    # 应该接近当前时间
    created = datetime.fromisoformat(m.created_at)
    now = datetime.now()
    delta = abs((now - created).total_seconds())
    assert_true(delta < 5)


# ============================================================
# SummaryGenerator
# ============================================================

def test_generate_from_result_success():
    """测试 generate_from_result() 成功情况"""
    from memory_manager import SummaryGenerator
    s = SummaryGenerator.generate_from_result(
        task_title="用户登录功能",
        success=True,
        duration_ms=1500,
        role="developer",
    )
    assert_in("developer", s)
    assert_in("用户登录功能", s)
    assert_in("✅", s)
    assert_in("1.5s", s)

def test_generate_from_result_failure():
    """测试 generate_from_result() 失败情况"""
    from memory_manager import SummaryGenerator
    s = SummaryGenerator.generate_from_result(
        task_title="数据库连接",
        success=False,
        error="Connection refused",
        role="devops",
    )
    assert_in("devops", s)
    assert_in("❌", s)
    assert_in("Connection refused", s)

def test_generate_from_result_ms_under_second():
    """测试 generate_from_result() 毫秒<1秒"""
    from memory_manager import SummaryGenerator
    s = SummaryGenerator.generate_from_result(
        task_title="Quick task",
        success=True,
        duration_ms=500,
    )
    assert_in("500ms", s)

def test_generate_from_result_no_role():
    """测试 generate_from_result() 无角色"""
    from memory_manager import SummaryGenerator
    s = SummaryGenerator.generate_from_result(
        task_title="Anonymous task",
        success=True,
    )
    assert_in("Anonymous task", s)
    assert_true("✅" in s)

def test_generate_from_result_long_title():
    """测试 generate_from_result() 长标题截断"""
    from memory_manager import SummaryGenerator
    long_title = "A" * 200
    s = SummaryGenerator.generate_from_result(
        task_title=long_title,
        success=True,
    )
    assert_true(len(s) < len(long_title) + 50)

def test_extract_keywords_basic():
    """测试 extract_keywords() 基本提取"""
    from memory_manager import SummaryGenerator
    text = "Python programming language development testing deployment"
    kw = SummaryGenerator.extract_keywords(text, max_keywords=3)
    assert_true(len(kw) <= 3)
    # 'the', 'and', 'for' 等停用词应被过滤
    for w in kw:
        assert_true(len(w) > 2)
        assert_true(w not in {'the', 'and', 'for', 'are', 'was'})

def test_extract_keywords_chinese():
    """测试 extract_keywords() 中文提取"""
    from memory_manager import SummaryGenerator
    text = "开发用户认证系统实现注册登录功能"
    kw = SummaryGenerator.extract_keywords(text, max_keywords=5)
    # 应该能提取中文词
    assert_true(len(kw) <= 5)

def test_extract_keywords_empty():
    """测试 extract_keywords() 空文本"""
    from memory_manager import SummaryGenerator
    kw = SummaryGenerator.extract_keywords("", max_keywords=5)
    assert_eq(kw, [])

def test_extract_keywords_stops_words():
    """测试 extract_keywords() 停用词过滤"""
    from memory_manager import SummaryGenerator
    text = "the a an is are was were be been"
    kw = SummaryGenerator.extract_keywords(text, max_keywords=10)
    assert_eq(kw, [])

def test_generate_tags_success():
    """测试 generate_tags() 成功情况"""
    from memory_manager import SummaryGenerator
    tags = SummaryGenerator.generate_tags(
        task_title="用户登录",
        role="developer",
        success=True,
    )
    assert_true("role:developer" in tags)
    assert_true("success" in tags)
    assert_true(len(tags) <= 5)

def test_generate_tags_failure():
    """测试 generate_tags() 失败情况"""
    from memory_manager import SummaryGenerator
    tags = SummaryGenerator.generate_tags(
        task_title="数据库操作",
        role="devops",
        success=False,
        error="Circuit breaker triggered for timeout",
    )
    assert_true("role:devops" in tags)
    assert_true("failure" in tags)
    assert_true("timeout" in tags)
    assert_true("circuit-break" in tags)

def test_generate_tags_max_limit():
    """测试 generate_tags() 最多5个标签"""
    from memory_manager import SummaryGenerator
    tags = SummaryGenerator.generate_tags(
        task_title="Python JavaScript Go Rust TypeScript Kotlin Swift",
        role="developer",
        success=True,
    )
    assert_true(len(tags) <= 5)


# ============================================================
# MemoryManager
# ============================================================

def test_memory_manager_init_default(temp_memory_dir):
    """测试 MemoryManager 默认初始化"""
    from memory_manager import MemoryManager
    # 默认初始化使用 workspace/memory/sindris-tasks
    # 使用自定义目录便于测试
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    assert_true(mgr.memory_dir.exists())
    assert_true(mgr.index_file is not None)

def test_memory_manager_init_creates_dir(temp_memory_dir):
    """测试 MemoryManager 自动创建目录"""
    from memory_manager import MemoryManager
    nested = os.path.join(temp_memory_dir, "a", "b", "c")
    mgr = MemoryManager(memory_dir=nested)
    assert_true(os.path.exists(nested))

def test_save_task_memory_creates_file(temp_memory_dir):
    """测试 save_task_memory() 创建记忆文件"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mem = mgr.save_task_memory(
        task_id="task_mem_001",
        task_title="测试记忆保存",
        success=True,
        duration_ms=2000,
        role="developer",
    )
    assert_true(mem.id.startswith("mem_"))
    assert_eq(mem.task_id, "task_mem_001")
    # 检查索引文件
    assert_true(mgr.index_file.exists())

def test_save_task_memory_with_error_tags(temp_memory_dir):
    """测试 save_task_memory() 失败任务生成正确标签"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mem = mgr.save_task_memory(
        task_id="task_fail_001",
        task_title="失败的任务",
        success=False,
        error="Safety policy blocked: dangerous command",
        role="devops",
    )
    assert_true("failure" in mem.tags)
    assert_true("safety" in mem.tags)

def test_save_lesson_creates_memory(temp_memory_dir):
    """测试 save_lesson() 保存经验"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mem = mgr.save_lesson(
        task_id="task_lesson_001",
        lesson="测试是质量保障的重要手段",
        tags=["testing", "quality"],
    )
    assert_true(mem.id.startswith("lesson_"))
    assert_in("测试是质量保障", mem.content)
    # Note: when tags are provided, they replace the default ["lesson"]
    assert_true("testing" in mem.tags)

def test_save_decision_creates_memory(temp_memory_dir):
    """测试 save_decision() 保存决策"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mem = mgr.save_decision(
        task_id="task_decision_001",
        decision="使用Redis作为缓存层",
        reason="性能要求高，内存访问更快",
        tags=["architecture", "redis"],
    )
    assert_true(mem.id.startswith("decision_"))
    assert_in("使用Redis", mem.content)
    assert_in("性能要求高", mem.content)
    # Note: when tags are provided, they replace the default ["decision"]
    assert_true("architecture" in mem.tags)
    assert_eq(mem.importance, 5)  # 决策重要性最高

def test_get_recent_memories_empty(temp_memory_dir):
    """测试 get_recent_memories() 空目录"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mems = mgr.get_recent_memories()
    assert_eq(mems, [])

def test_get_recent_memories_with_data(temp_memory_dir):
    """测试 get_recent_memories() 返回保存的记忆"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mgr.save_task_memory("t1", "Task 1", True)
    mgr.save_task_memory("t2", "Task 2", True)
    mgr.save_lesson("t1", "Lesson 1")
    mems = mgr.get_recent_memories(limit=5)
    assert_true(len(mems) >= 3)

def test_get_recent_memories_by_type(temp_memory_dir):
    """测试 get_recent_memories() 按类型过滤"""
    from memory_manager import MemoryManager, MemoryType
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mgr.save_task_memory("t1", "Task 1", True)
    mgr.save_lesson("t1", "Lesson 1")
    mems = mgr.get_recent_memories(
        limit=10,
        memory_type=MemoryType.LESSON_LEARNED,
    )
    for m in mems:
        assert_eq(m.memory_type, MemoryType.LESSON_LEARNED.value)

def test_get_memories_by_tag(temp_memory_dir):
    """测试 get_memories_by_tag() 按标签查询"""
    from memory_manager import MemoryManager
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mgr.save_lesson("t1", "Lesson about testing", tags=["testing", "quality"])
    mgr.save_decision("t2", "Decision 1", reason="Because testing matters", tags=["testing"])
    mems = mgr.get_memories_by_tag("testing", limit=10)
    assert_true(len(mems) >= 2)
    for m in mems:
        assert_true("testing" in m.tags)

def test_write_memory_creates_monthly_file(temp_memory_dir):
    """测试 _write_memory() 按月份创建文件"""
    from memory_manager import MemoryManager, TaskMemory, MemoryType
    from datetime import datetime
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mem = TaskMemory(
        id="mem_monthly_001",
        task_id="task_monthly",
        memory_type=MemoryType.TASK_SUMMARY.value,
        content="Monthly test",
        tags=["test"],
    )
    mgr._write_memory(mem)
    month_str = datetime.now().strftime("%Y-%m")
    month_file = mgr.memory_dir / f"{month_str}.md"
    assert_true(month_file.exists())
    # 验证内容
    content = month_file.read_text()
    assert_in("mem_monthly_001", content)
    assert_in("Monthly test", content)

def test_update_index_appends_line(temp_memory_dir):
    """测试 _update_index() 追加索引行"""
    from memory_manager import MemoryManager, TaskMemory, MemoryType
    mgr = MemoryManager(memory_dir=temp_memory_dir)
    mem = TaskMemory(
        id="mem_index_001",
        task_id="task_index",
        memory_type=MemoryType.TASK_SUMMARY.value,
        content="Index test",
        tags=["test"],
    )
    mgr._update_index(mem)
    assert_true(mgr.index_file.exists())
    content = mgr.index_file.read_text()
    assert_in("mem_index_001", content)


# ============================================================
# 便捷函数
# ============================================================

def test_get_default_manager_singleton():
    """测试 get_default_manager() 单例"""
    from memory_manager import get_default_manager, _default_manager
    # 先重置单例
    import memory_manager
    memory_manager._default_manager = None
    mgr1 = get_default_manager()
    mgr2 = get_default_manager()
    assert_true(mgr1 is mgr2)


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
