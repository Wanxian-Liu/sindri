"""
verify_engine.py - 验证引擎（modules层）

职责：
1. Ralph 3轮验证
2. 文件mtime检查
3. Mock注入
4. 集成断言

约束：
- 参考OpenClaw原生能力
- 300秒超时足够
"""

import os
import sys
import asyncio
import hashlib
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# 确保scripts路径可用
_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

class VerifyPhase(str, Enum):
    """验证阶段"""
    PRE = "pre"       # 执行前
    POST = "post"     # 执行后
    INTEGRATION = "integration"  # 集成测试


class MtimeRecord(Dict):
    """文件mtime记录"""
    path: str
    mtime: float
    size: int
    content_hash: Optional[str] = None


@dataclass
class MockInjection:
    """Mock注入项"""
    target_path: str                    # 目标文件路径
    mock_content: str                    # Mock内容
    original_backup: Optional[str] = None  # 原始内容备份
    inject_mode: str = "replace"        # replace/append/prepend
    restore_on_exit: bool = True         # 退出时恢复


@dataclass
class IntegrationAssertion:
    """集成断言"""
    name: str
    check_fn: Callable[[], bool]
    description: str = ""
    required: bool = True
    timeout: float = 10.0               # 超时秒数


@dataclass
class VerifyResult:
    """验证结果"""
    passed: bool
    phase: VerifyPhase
    total_checks: int
    passed_checks: int
    failed_checks: int
    issues: List[str]
    details: Dict[str, Any]
    recommendation: str


@dataclass
class MtimeCheckResult:
    """Mtime检查结果"""
    path: str
    exists: bool
    changed: bool
    old_mtime: Optional[float]
    new_mtime: Optional[float]
    old_size: Optional[int]
    new_size: Optional[int]


# ============================================================
# MtimeTracker - 文件mtime跟踪
# ============================================================

class MtimeTracker:
    """
    文件修改时间追踪器
    
    在执行任务前记录文件状态，执行后对比变化
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self._snapshots: Dict[str, Dict[str, Any]] = {}

    def snapshot(self, paths: List[str]) -> None:
        """
        拍摄文件快照
        
        Args:
            paths: 文件路径列表（支持相对路径）
        """
        for p in paths:
            full_path = self._resolve_path(p)
            if full_path.exists():
                stat = full_path.stat()
                content_hash = None
                if stat.st_size < 1024 * 1024:  # <1MB
                    try:
                        content_hash = hashlib.md5(full_path.read_bytes()).hexdigest()
                    except Exception:
                        pass
                self._snapshots[str(full_path)] = {
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "content_hash": content_hash,
                    "snapshot_time": time.time(),
                }
            else:
                # 文件不存在也记录
                self._snapshots[str(full_path)] = {
                    "mtime": None,
                    "size": None,
                    "content_hash": None,
                    "snapshot_time": time.time(),
                    "existed": False,
                }

    def check(self, paths: List[str]) -> List[MtimeCheckResult]:
        """
        检查文件变化
        
        Args:
            paths: 文件路径列表
        
        Returns:
            MtimeCheckResult列表
        """
        results = []
        for p in paths:
            full_path = self._resolve_path(p)
            result = MtimeCheckResult(
                path=str(full_path),
                exists=full_path.exists(),
                changed=False,
                old_mtime=None,
                new_mtime=None,
                old_size=None,
                new_size=None,
            )
            
            old = self._snapshots.get(str(full_path))
            if old:
                result.old_mtime = old.get("mtime")
                result.old_size = old.get("size")
                
                if full_path.exists():
                    stat = full_path.stat()
                    result.new_mtime = stat.st_mtime
                    result.new_size = stat.st_size
                    result.changed = (
                        result.old_mtime != result.new_mtime or
                        result.old_size != result.new_size
                    )
                else:
                    result.changed = True  # 文件消失了
            else:
                # 没有快照，当前状态
                if full_path.exists():
                    stat = full_path.stat()
                    result.new_mtime = stat.st_mtime
                    result.new_size = stat.st_size
                    result.changed = True  # 没有旧快照 = 视为变化

            results.append(result)
        return results

    def check_and_report(self, paths: List[str]) -> Dict[str, Any]:
        """
        检查并生成报告
        
        Returns:
            {
                "changed": [paths that changed],
                "unchanged": [paths that didn't change],
                "created": [paths that are new],
                "deleted": [paths that disappeared],
                "details": {path: MtimeCheckResult}
            }
        """
        results = self.check(paths)
        report = {
            "changed": [],
            "unchanged": [],
            "created": [],
            "deleted": [],
            "details": {},
        }
        for r in results:
            report["details"][r.path] = r
            if not self._snapshots.get(r.path):
                # 没有旧快照
                if r.exists:
                    report["created"].append(r.path)
                else:
                    report["deleted"].append(r.path)
            else:
                if r.changed:
                    report["changed"].append(r.path)
                else:
                    report["unchanged"].append(r.path)
        return report

    def _resolve_path(self, p: str) -> Path:
        """解析路径"""
        if os.path.isabs(p):
            return Path(p)
        return self.workspace_root / p


# ============================================================
# MockInjector - Mock注入器
# ============================================================

class MockInjector:
    """
    Mock注入器
    
    在测试时替换文件内容，测试后可选恢复
    """

    def __init__(self):
        self._injections: List[MockInjection] = []
        self._active = False

    def inject(self, target_path: str, mock_content: str,
               mode: str = "replace", restore_on_exit: bool = True) -> None:
        """
        注入Mock
        
        Args:
            target_path: 目标文件路径
            mock_content: Mock内容
            mode: replace/append/prepend
            restore_on_exit: 退出时恢复
        """
        path = Path(target_path)
        
        # 备份原始内容
        original_backup = None
        if path.exists():
            original_backup = path.read_text(encoding="utf-8")
        
        injection = MockInjection(
            target_path=str(path),
            mock_content=mock_content,
            original_backup=original_backup,
            inject_mode=mode,
            restore_on_exit=restore_on_exit,
        )
        
        # 执行注入
        self._do_inject(injection)
        self._injections.append(injection)
        self._active = True

    def inject_many(self, items: List[Dict[str, str]]) -> None:
        """
        批量注入Mock
        
        Args:
            items: [{"path": "...", "content": "...", "mode": "replace"}]
        """
        for item in items:
            self.inject(
                target_path=item["path"],
                mock_content=item["content"],
                mode=item.get("mode", "replace"),
                restore_on_exit=item.get("restore_on_exit", True),
            )

    def restore_all(self) -> List[str]:
        """
        恢复所有注入
        
        Returns:
            恢复的文件列表
        """
        restored = []
        for inj in reversed(self._injections):
            if inj.restore_on_exit and inj.original_backup is not None:
                Path(inj.target_path).write_text(inj.original_backup, encoding="utf-8")
                restored.append(inj.target_path)
        self._injections.clear()
        self._active = False
        return restored

    def get_injections(self) -> List[Dict[str, Any]]:
        """获取注入列表"""
        return [
            {
                "path": inj.target_path,
                "mode": inj.inject_mode,
                "content_preview": inj.mock_content[:100],
                "will_restore": inj.restore_on_exit,
            }
            for inj in self._injections
        ]

    @property
    def is_active(self) -> bool:
        """是否活跃（有注入未恢复）"""
        return self._active

    def _do_inject(self, injection: MockInjection) -> None:
        """执行注入"""
        path = Path(injection.target_path)
        
        if injection.inject_mode == "replace":
            path.write_text(injection.mock_content, encoding="utf-8")
        elif injection.inject_mode == "append":
            path.write_text(
                path.read_text(encoding="utf-8") + injection.mock_content,
                encoding="utf-8"
            )
        elif injection.inject_mode == "prepend":
            path.write_text(
                injection.mock_content + path.read_text(encoding="utf-8"),
                encoding="utf-8"
            )


# ============================================================
# IntegrationVerifier - 集成断言验证器
# ============================================================

class IntegrationVerifier:
    """
    集成断言验证器
    
    执行集成测试级别的断言，验证多个组件协作是否正常
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self._assertions: List[IntegrationAssertion] = []

    def add_assertion(
        self,
        name: str,
        check_fn: Callable[[], bool],
        description: str = "",
        required: bool = True,
        timeout: float = 10.0,
    ) -> None:
        """
        添加断言
        
        Args:
            name: 断言名称
            check_fn: 检查函数，返回bool
            description: 描述
            required: 是否必须通过
            timeout: 超时秒数
        """
        self._assertions.append(IntegrationAssertion(
            name=name,
            check_fn=check_fn,
            description=description,
            required=required,
            timeout=timeout,
        ))

    def add_file_assertions(self, file_path: str) -> None:
        """添加文件相关的标准断言"""
        path = self.workspace_root / file_path
        
        self.add_assertion(
            name=f"file_exists:{file_path}",
            check_fn=lambda p=path: p.exists(),
            description=f"{file_path} 必须存在",
        )
        
        self.add_assertion(
            name=f"file_readable:{file_path}",
            check_fn=lambda p=path: p.exists() and os.access(p, os.R_OK),
            description=f"{file_path} 必须可读",
        )
        
        self.add_assertion(
            name=f"file_not_empty:{file_path}",
            check_fn=lambda p=path: p.exists() and p.stat().st_size > 0,
            description=f"{file_path} 不能为空",
        )

    def add_module_import_assertions(self, module_paths: List[str]) -> None:
        """添加模块导入断言"""
        for mp in module_paths:
            module_name = Path(mp).stem
            self.add_assertion(
                name=f"import:{module_name}",
                check_fn=lambda m=module_name: self._try_import(m),
                description=f"模块 {module_name} 必须可导入",
                timeout=30.0,
            )

    async def run(self) -> Dict[str, Any]:
        """
        执行所有断言
        
        Returns:
            {
                "passed": bool,
                "total": int,
                "passed_count": int,
                "failed_count": int,
                "results": [{"name": ..., "passed": bool, "error": ...}],
                "required_failed": [names of failed required assertions],
            }
        """
        results = []
        required_failed = []
        
        for assertion in self._assertions:
            result = {
                "name": assertion.name,
                "description": assertion.description,
                "required": assertion.required,
                "passed": False,
                "error": None,
            }
            
            try:
                if asyncio.iscoroutinefunction(assertion.check_fn):
                    passed = await asyncio.wait_for(
                        assertion.check_fn(),
                        timeout=assertion.timeout
                    )
                else:
                    loop = asyncio.get_running_loop()
                    passed = await asyncio.wait_for(
                        loop.run_in_executor(None, assertion.check_fn),
                        timeout=assertion.timeout
                    )
                result["passed"] = passed
            except asyncio.TimeoutError:
                result["error"] = f"超时 ({assertion.timeout}s)"
            except Exception as e:
                result["error"] = str(e)
            
            if not result["passed"] and assertion.required:
                required_failed.append(assertion.name)
            
            results.append(result)
        
        return {
            "passed": len(required_failed) == 0,
            "total": len(self._assertions),
            "passed_count": sum(1 for r in results if r["passed"]),
            "failed_count": sum(1 for r in results if not r["passed"]),
            "results": results,
            "required_failed": required_failed,
        }

    def clear(self) -> None:
        """清空所有断言"""
        self._assertions.clear()

    def _try_import(self, module_name: str) -> bool:
        """尝试导入模块"""
        try:
            __import__(module_name)
            return True
        except Exception:
            return False


# ============================================================
# VerifyEngine - 主验证引擎
# ============================================================

class VerifyEngine:
    """
    验证引擎（modules层）
    
    整合Ralph 3轮验证、Mtime跟踪、Mock注入、集成断言
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        
        # 初始化子组件
        self.mtime_tracker = MtimeTracker(str(self.workspace_root))
        self.mock_injector = MockInjector()
        self.integration_verifier = IntegrationVerifier(str(self.workspace_root))
        
        # 内部状态
        self._current_phase: Optional[VerifyPhase] = None
        self._ralph_reports: List[Any] = []
        self._injection_log: List[Dict[str, Any]] = []

    # ========== Ralph 3轮验证 ==========

    async def verify_with_ralph(
        self,
        task_name: str,
        verify_items: List[Dict[str, Any]],
        execute_fn: Optional[Callable] = None,
    ) -> VerifyResult:
        """
        使用Ralph进行3轮循环验证
        
        Args:
            task_name: 任务名称
            verify_items: 验证项列表 [{"name": ..., "description": ..., "check_fn": ...}]
            execute_fn: 可选的执行函数
        
        Returns:
            VerifyResult
        """
        from scripts.ralph_loop import RalphLoop

        verifier = RalphLoop(
            task_name=task_name,
            verify_items=verify_items,
            execute_fn=execute_fn,
        )

        ralph_result = await verifier.run()
        self._ralph_reports.append(ralph_result)

        passed = ralph_result.success
        issues = []
        if not passed:
            issues.append(
                f"Ralph验证未通过：连续{ralph_result.consecutive_passed}/3轮"
            )

        return VerifyResult(
            passed=passed,
            phase=VerifyPhase.INTEGRATION,
            total_checks=ralph_result.total_rounds,
            passed_checks=ralph_result.consecutive_passed,
            failed_checks=ralph_result.total_rounds - ralph_result.consecutive_passed,
            issues=issues,
            details={
                "total_rounds": ralph_result.total_rounds,
                "consecutive_passed": ralph_result.consecutive_passed,
                "required_consecutive": 3,
                "final_state": str(ralph_result.final_report.state) if ralph_result.final_report else None,
            },
            recommendation="✅ Ralph验证通过" if passed else "❌ Ralph验证失败",
        )

    # ========== 快速验证流程 ==========

    async def full_verify(
        self,
        task_name: str,
        files: List[str],
        verify_items: List[Dict[str, Any]],
        execute_fn: Optional[Callable] = None,
        pre_assertions: Optional[List[Dict]] = None,
        post_assertions: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        完整验证流程
        
        流程：
        1. Pre-phase: mtime快照 + 前置断言
        2. Execute: 执行任务（含Mock注入）
        3. Post-phase: mtime对比 + 后置断言
        4. Ralph: 3轮验证
        
        Args:
            task_name: 任务名称
            files: 监控的文件列表
            verify_items: Ralph验证项
            execute_fn: 执行函数
            pre_assertions: 前置断言 [{"name": ..., "fn": ...}]
            post_assertions: 后置断言
        
        Returns:
            完整报告
        """
        report = {
            "task_name": task_name,
            "timestamp": datetime.now().isoformat(),
            "phases": {},
            "overall_passed": False,
        }

        # Phase 1: Pre-flight
        self._current_phase = VerifyPhase.PRE
        pre_snapshot = dict(self.mtime_tracker._snapshots)
        self.mtime_tracker.snapshot(files)
        
        pre_result = {"snapshot_taken": True, "files": files}
        if pre_assertions:
            for a in pre_assertions:
                self.integration_verifier.add_assertion(
                    name=a["name"],
                    check_fn=a["fn"],
                    description=a.get("description", ""),
                )
            pre_result["assertions"] = await self.integration_verifier.run()
        
        report["phases"]["pre"] = pre_result

        # Phase 2: Execute
        if execute_fn:
            try:
                await execute_fn()
                report["phases"]["execute"] = {"status": "done"}
            except Exception as e:
                report["phases"]["execute"] = {"status": "error", "error": str(e)}
                report["overall_passed"] = False
                return report

        # Phase 3: Post-flight
        self._current_phase = VerifyPhase.POST
        mtime_report = self.mtime_tracker.check_and_report(files)
        report["phases"]["post"] = {
            "mtime_changes": mtime_report,
        }
        
        if post_assertions:
            for a in post_assertions:
                self.integration_verifier.add_assertion(
                    name=a["name"],
                    check_fn=a["fn"],
                    description=a.get("description", ""),
                )
            post_result = await self.integration_verifier.run()
            report["phases"]["post"]["assertions"] = post_result

        # Phase 4: Ralph验证
        ralph_result = await self.verify_with_ralph(task_name, verify_items, execute_fn)
        report["phases"]["ralph"] = {
            "passed": ralph_result.passed,
            "details": ralph_result.details,
        }

        # 综合结论
        report["overall_passed"] = (
            ralph_result.passed and
            len(mtime_report.get("created", [])) > 0  # 至少有文件变化
        )
        
        return report

    # ========== Mock注入便捷方法 ==========

    def inject_mock(self, file_path: str, content: str) -> None:
        """注入Mock"""
        self.mock_injector.inject(file_path, content)

    def inject_mocks(self, items: List[Dict[str, str]]) -> None:
        """批量注入Mock"""
        self.mock_injector.inject_many(items)

    def restore_mocks(self) -> List[str]:
        """恢复所有Mock"""
        return self.mock_injector.restore_all()

    # ========== Mtime便捷方法 ==========

    def take_snapshot(self, files: List[str]) -> None:
        """拍摄快照"""
        self.mtime_tracker.snapshot(files)

    def check_changes(self, files: List[str]) -> Dict[str, Any]:
        """检查变化"""
        return self.mtime_tracker.check_and_report(files)

    # ========== 集成断言便捷方法 ==========

    def add_file_assertion(self, file_path: str) -> None:
        """添加文件断言"""
        self.integration_verifier.add_file_assertions(file_path)

    def add_import_assertion(self, module_path: str) -> None:
        """添加导入断言"""
        self.integration_verifier.add_module_import_assertions([module_path])

    async def run_assertions(self) -> Dict[str, Any]:
        """运行断言"""
        return await self.integration_verifier.run()

    # ========== 清理 ==========

    def cleanup(self) -> Dict[str, Any]:
        """
        清理所有副作用
        
        Returns:
            清理报告
        """
        report = {
            "mocks_restored": self.mock_injector.restore_all(),
            "assertions_cleared": len(self.integration_verifier._assertions) > 0,
        }
        self.integration_verifier.clear()
        self._ralph_reports.clear()
        return report

    def __enter__(self) -> "VerifyEngine":
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口，自动清理"""
        self.cleanup()


# ============================================================
# 便捷函数
# ============================================================

def create_verify_engine(workspace_root: str) -> VerifyEngine:
    """创建验证引擎"""
    return VerifyEngine(workspace_root)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    import tempfile
    
    async def test():
        print("=== VerifyEngine 测试 ===\n")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VerifyEngine(tmpdir)
            
            # 创建测试文件
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("original")
            
            # 1. Mtime追踪
            print("1. Mtime追踪测试")
            engine.take_snapshot([str(test_file)])
            await asyncio.sleep(0.1)
            test_file.write_text("modified")
            changes = engine.check_changes([str(test_file)])
            print(f"   变化: {changes['changed']}")
            print(f"   ✅" if "test.txt" in changes['changed'] else "   ❌")
            
            # 2. Mock注入
            print("\n2. Mock注入测试")
            mock_file = Path(tmpdir) / "mock_test.py"
            mock_file.write_text("original content")
            engine.inject_mock(str(mock_file), "# MOCKED")
            content = mock_file.read_text()
            print(f"   注入后内容: {content[:20]}")
            print(f"   ✅" if "# MOCKED" in content else "   ❌")
            restored = engine.restore_mocks()
            content = mock_file.read_text()
            print(f"   恢复后内容: {content[:20]}")
            print(f"   ✅" if "original content" in content else "   ❌")
            
            # 3. 集成断言
            print("\n3. 集成断言测试")
            engine.add_file_assertion(str(test_file))
            result = engine.run_assertions()
            print(f"   通过: {result['passed_count']}/{result['total']}")
            print(f"   ✅" if result['passed'] else "   ❌")
            
            # 4. Ralph验证
            print("\n4. Ralph验证测试")
            items = [
                {"name": "文件存在", "check_fn": lambda: test_file.exists()},
                {"name": "内容非空", "check_fn": lambda: len(test_file.read_text()) > 0},
            ]
            ralph_result = await engine.verify_with_ralph("测试任务", items)
            print(f"   通过: {ralph_result.passed}")
            print(f"   ✅" if ralph_result.passed else "   ❌")
            
            engine.cleanup()
            print("\n测试完成 ✅")
    
    asyncio.run(test())
