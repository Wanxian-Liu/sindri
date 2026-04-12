"""
test_omx_tasks_ops.py - omx_tasks.py 操作测试
测试 Task 相关文件操作
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from omx_tasks import (
    Task,
    TaskEvent,
    TaskStatus,
    TaskPriority,
    CreateTaskInput,
    load_tasks,
    save_tasks,
    create_task,
    get_task,
    update_task,
    transition_task,
    delete_task,
    list_tasks,
    get_task_graph,
    create_task_default,
    get_task_default,
    update_task_default,
    transition_task_default,
    list_tasks_default,
    get_task_graph_default,
)
from omx_contract import ensure_omx_layout, set_workspace_root


class TestTaskEventDatatype:
    """测试 TaskEvent 数据类型"""
    
    def test_create_task_event(self):
        """测试创建 TaskEvent"""
        event = TaskEvent(status="pending", at="2026-01-01T00:00:00", by="alice")
        assert event.status == "pending"
        assert event.by == "alice"
    
    def test_task_event_to_dict(self):
        """测试 TaskEvent.to_dict()"""
        event = TaskEvent(status="in_progress", at="2026-01-01T00:00:00", note="Started")
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["status"] == "in_progress"
    
    def test_task_event_from_dict(self):
        """测试 TaskEvent.from_dict()"""
        data = {"status": "completed", "at": "2026-01-01T00:00:00", "by": "bob", "note": "Done"}
        event = TaskEvent.from_dict(data)
        assert event.status == "completed"
        assert event.by == "bob"


class TestTaskDatatype:
    """测试 Task 数据类型"""
    
    def test_create_task_basic(self):
        """测试创建基本 Task"""
        task = Task(
            id="t1",
            title="Test Task",
            kind="general",
            phase="round1",
            status="pending",
            priority="medium"
        )
        assert task.id == "t1"
        assert task.title == "Test Task"
        assert task.status == "pending"
    
    def test_task_default_timestamps(self):
        """测试 Task 默认时间戳"""
        task = Task(
            id="t2", title="T", kind="k", phase="p",
            status="pending", priority="medium"
        )
        assert task.created_at != ""
        assert task.updated_at != ""
    
    def test_task_with_history(self):
        """测试带历史记录的 Task"""
        history = [
            {"status": "pending", "at": "2026-01-01T00:00:00"},
            {"status": "in_progress", "at": "2026-01-02T00:00:00"},
        ]
        task = Task(
            id="t3", title="T", kind="k", phase="p",
            status="in_progress", priority="medium",
            history=history
        )
        assert len(task.history) == 2
    
    def test_task_with_task_events_in_history(self):
        """测试 history 中包含 TaskEvent 对象"""
        event = TaskEvent(status="pending", at="2026-01-01T00:00:00")
        task = Task(
            id="t4", title="T", kind="k", phase="p",
            status="pending", priority="medium",
            history=[event]
        )
        # __post_init__ 应该将其转换为 dict
        assert isinstance(task.history[0], dict)
    
    def test_task_to_dict(self):
        """测试 Task.to_dict()"""
        task = Task(
            id="t5", title="T", kind="k", phase="p",
            status="pending", priority="medium"
        )
        d = task.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "t5"
    
    def test_task_from_dict(self):
        """测试 Task.from_dict()"""
        data = {
            "id": "t6",
            "title": "Test",
            "kind": "general",
            "phase": "round1",
            "status": "pending",
            "priority": "high",
            "owner": None,
            "verify": [],
            "notes": [],
            "metadata": {},
            "dependencies": [],
            "blockers": [],
            "review_status": "none",
            "claimed_at": None,
            "completed_at": None,
            "result": None,
            "history": [],
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
        task = Task.from_dict(data)
        assert task.id == "t6"
        assert task.priority == "high"
    
    def test_task_with_verify(self):
        """测试带验证项的 Task"""
        task = Task(
            id="t7", title="T", kind="k", phase="p",
            status="pending", priority="medium",
            verify=["check_file_exists", "check_output"]
        )
        assert len(task.verify) == 2
    
    def test_task_with_dependencies(self):
        """测试带依赖的 Task"""
        task = Task(
            id="t8", title="T", kind="k", phase="p",
            status="pending", priority="medium",
            dependencies=["task-1", "task-2"]
        )
        assert len(task.dependencies) == 2
    
    def test_task_with_blockers(self):
        """测试带阻塞的 Task"""
        task = Task(
            id="t9", title="T", kind="k", phase="p",
            status="blocked", priority="medium",
            blockers=["Waiting for API"]
        )
        assert len(task.blockers) == 1


class TestCreateTaskInput:
    """测试 CreateTaskInput 数据类型"""
    
    def test_create_input_basic(self):
        """测试基本 CreateTaskInput"""
        inp = CreateTaskInput(title="New task")
        assert inp.title == "New task"
        assert inp.kind == "general"
        assert inp.priority == "medium"
    
    def test_create_input_full(self):
        """测试完整 CreateTaskInput"""
        inp = CreateTaskInput(
            title="Full task",
            kind="sindris_planning",
            phase="round1",
            priority="high",
            verify=["check1", "check2"],
            notes=["Note 1"],
            metadata={"key": "value"},
            dependencies=["dep-1"],
        )
        assert inp.kind == "sindris_planning"
        assert inp.phase == "round1"
        assert inp.priority == "high"
        assert len(inp.verify) == 2
    
    def test_create_input_to_dict(self):
        """测试 CreateTaskInput.to_dict()"""
        inp = CreateTaskInput(title="Test", priority="low")
        d = inp.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "Test"


class TestTaskOperations:
    """测试 Task 文件操作"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_tasks_empty(self):
        """测试加载空任务列表"""
        tasks = load_tasks(self.temp_dir)
        assert tasks == []
    
    def test_save_and_load_tasks(self):
        """测试保存和加载任务"""
        tasks = [
            Task(id="t1", title="Task 1", kind="g", phase="p", status="pending", priority="medium"),
            Task(id="t2", title="Task 2", kind="g", phase="p", status="completed", priority="high"),
        ]
        save_tasks(self.temp_dir, tasks)
        loaded = load_tasks(self.temp_dir)
        assert len(loaded) == 2
        assert loaded[0].title == "Task 1"
    
    def test_create_task(self):
        """测试创建任务"""
        inp = CreateTaskInput(title="New Task", kind="general", priority="high")
        task = create_task(self.temp_dir, inp)
        assert task.id.startswith("task_")
        assert task.title == "New Task"
        assert task.status == "pending"
        assert len(task.history) == 1  # 初始 history 条目
        
        # 验证持久化
        tasks = load_tasks(self.temp_dir)
        assert len(tasks) == 1
    
    def test_create_multiple_tasks(self):
        """测试创建多个任务"""
        for i in range(3):
            create_task(self.temp_dir, CreateTaskInput(title=f"Task {i}"))
        
        tasks = load_tasks(self.temp_dir)
        assert len(tasks) == 3
    
    def test_get_task(self):
        """测试获取任务"""
        created = create_task(self.temp_dir, CreateTaskInput(title="Find me"))
        found = get_task(self.temp_dir, created.id)
        assert found is not None
        assert found.id == created.id
    
    def test_get_task_not_found(self):
        """测试获取不存在的任务"""
        result = get_task(self.temp_dir, "nonexistent")
        assert result is None
    
    def test_update_task_status(self):
        """测试更新任务状态"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Update me"))
        
        updated = update_task(self.temp_dir, task.id, {"status": "in_progress"})
        assert updated is not None
        assert updated.status == "in_progress"
    
    def test_update_task_owner(self):
        """测试更新任务负责人"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Assign me"))
        
        updated = update_task(self.temp_dir, task.id, {"owner": "alice"})
        assert updated.owner == "alice"
    
    def test_update_task_metadata(self):
        """测试更新任务元数据"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Meta me"))
        
        updated = update_task(self.temp_dir, task.id, {"metadata": {"key": "value", "num": 42}})
        assert updated.metadata["key"] == "value"
        assert updated.metadata["num"] == 42
    
    def test_update_task_notes(self):
        """测试更新任务笔记"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Note me"))
        
        updated = update_task(self.temp_dir, task.id, {"notes": ["Note 1", "Note 2"]})
        assert len(updated.notes) == 2
    
    def test_update_task_not_found(self):
        """测试更新不存在的任务"""
        result = update_task(self.temp_dir, "nonexistent", {"status": "in_progress"})
        assert result is None


class TestTransitionTask:
    """测试 transition_task"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_transition_to_in_progress(self):
        """测试转换到 in_progress"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Start me"))
        
        updated = transition_task(self.temp_dir, task.id, "in_progress", by="alice")
        assert updated is not None
        assert updated.status == "in_progress"
        assert updated.claimed_at is not None  # 首次认领设置 claimed_at
        assert len(updated.history) == 2  # 增加了 history 条目
    
    def test_transition_to_completed(self):
        """测试转换到 completed"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Complete me"))
        
        updated = transition_task(self.temp_dir, task.id, "completed", by="bob", note="All done")
        assert updated is not None
        assert updated.status == "completed"
        assert updated.completed_at is not None
    
    def test_transition_to_failed(self):
        """测试转换到 failed"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Fail me"))
        
        updated = transition_task(self.temp_dir, task.id, "failed")
        assert updated.status == "failed"
    
    def test_transition_not_found(self):
        """测试转换不存在的任务"""
        result = transition_task(self.temp_dir, "nonexistent", "in_progress")
        assert result is None
    
    def test_transition_records_ledger(self):
        """测试 transition_task 记录到 ledger"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Ledger test"))
        
        transition_task(self.temp_dir, task.id, "completed")
        
        # 验证 ledger 记录
        from omx_ledger import load_ledger
        ledger = load_ledger(self.temp_dir)
        task_entries = [e for e in ledger if e.task_id == task.id]
        assert len(task_entries) >= 1


class TestDeleteTask:
    """测试 delete_task"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_delete_task(self):
        """测试删除任务"""
        task = create_task(self.temp_dir, CreateTaskInput(title="Delete me"))
        assert len(load_tasks(self.temp_dir)) == 1
        
        result = delete_task(self.temp_dir, task.id)
        assert result is True
        assert len(load_tasks(self.temp_dir)) == 0
    
    def test_delete_task_not_found(self):
        """测试删除不存在的任务"""
        result = delete_task(self.temp_dir, "nonexistent")
        assert result is False


class TestListTasks:
    """测试 list_tasks"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_list_tasks_no_filter(self):
        """测试列出全部任务"""
        for i in range(3):
            create_task(self.temp_dir, CreateTaskInput(title=f"Task {i}"))
        
        tasks = list_tasks(self.temp_dir)
        assert len(tasks) == 3
    
    def test_list_tasks_status_filter(self):
        """测试按状态过滤"""
        t1 = create_task(self.temp_dir, CreateTaskInput(title="Pending"))
        t2 = create_task(self.temp_dir, CreateTaskInput(title="In Progress"))
        transition_task(self.temp_dir, t2.id, "in_progress")
        t3 = create_task(self.temp_dir, CreateTaskInput(title="Completed"))
        transition_task(self.temp_dir, t3.id, "completed")
        
        pending = list_tasks(self.temp_dir, status="pending")
        assert len(pending) == 1
        
        in_progress = list_tasks(self.temp_dir, status="in_progress")
        assert len(in_progress) == 1
        
        completed = list_tasks(self.temp_dir, status="completed")
        assert len(completed) == 1
    
    def test_list_tasks_owner_filter(self):
        """测试按负责人过滤"""
        t1 = create_task(self.temp_dir, CreateTaskInput(title="T1"))
        t2 = create_task(self.temp_dir, CreateTaskInput(title="T2"))
        update_task(self.temp_dir, t1.id, {"owner": "alice"})
        update_task(self.temp_dir, t2.id, {"owner": "bob"})
        
        alice_tasks = list_tasks(self.temp_dir, owner="alice")
        assert len(alice_tasks) == 1
        assert alice_tasks[0].id == t1.id
    
    def test_list_tasks_phase_filter(self):
        """测试按阶段过滤"""
        t1 = create_task(self.temp_dir, CreateTaskInput(title="T1", phase="round1"))
        t2 = create_task(self.temp_dir, CreateTaskInput(title="T2", phase="round2"))
        
        round1_tasks = list_tasks(self.temp_dir, phase="round1")
        assert len(round1_tasks) == 1
    
    def test_list_tasks_multiple_filters(self):
        """测试多条件过滤"""
        t1 = create_task(self.temp_dir, CreateTaskInput(title="T1", phase="round1"))
        t2 = create_task(self.temp_dir, CreateTaskInput(title="T2", phase="round1"))
        update_task(self.temp_dir, t2.id, {"owner": "alice"})
        transition_task(self.temp_dir, t2.id, "completed")
        
        result = list_tasks(self.temp_dir, phase="round1", owner="alice")
        assert len(result) == 1
        assert result[0].id == t2.id


class TestGetTaskGraph:
    """测试 get_task_graph"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_graph_empty(self):
        """测试空任务图的统计"""
        graph = get_task_graph(self.temp_dir)
        assert graph["total"] == 0
        assert graph["by_status"] == {}
        assert graph["by_phase"] == {}
    
    def test_graph_with_tasks(self):
        """测试有任务的任务图统计"""
        t1 = create_task(self.temp_dir, CreateTaskInput(title="T1", phase="round1"))
        t2 = create_task(self.temp_dir, CreateTaskInput(title="T2", phase="round1"))
        transition_task(self.temp_dir, t1.id, "completed")
        
        graph = get_task_graph(self.temp_dir)
        assert graph["total"] == 2
        assert graph["by_status"]["pending"] == 1
        assert graph["by_status"]["completed"] == 1
        assert graph["by_phase"]["round1"] == 2


class TestDefaultWorkspace:
    """测试默认工作区便捷函数"""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        ensure_omx_layout(self.temp_dir)
        set_workspace_root(self.temp_dir)
    
    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_task_default(self):
        """测试 create_task_default"""
        task = create_task_default(title="Default task", priority="high")
        assert task.title == "Default task"
    
    def test_get_task_default(self):
        """测试 get_task_default"""
        created = create_task_default(title="Find me")
        found = get_task_default(created.id)
        assert found is not None
    
    def test_update_task_default(self):
        """测试 update_task_default"""
        task = create_task_default(title="Update me")
        updated = update_task_default(task.id, status="in_progress")
        assert updated.status == "in_progress"
    
    def test_transition_task_default(self):
        """测试 transition_task_default"""
        task = create_task_default(title="Trans me")
        updated = transition_task_default(task.id, "completed")
        assert updated.status == "completed"
    
    def test_list_tasks_default(self):
        """测试 list_tasks_default"""
        create_task_default(title="T1")
        create_task_default(title="T2")
        tasks = list_tasks_default()
        assert len(tasks) == 2
    
    def test_get_task_graph_default(self):
        """测试 get_task_graph_default"""
        graph = get_task_graph_default()
        assert "total" in graph
