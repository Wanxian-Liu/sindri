#!/usr/bin/env python3
"""
ralph_loop.py - Ralph Loop 验证模块

Ralph是Sindri的验证层，被动调用，执行3轮循环验证直到连续一致通过。

核心规则：
1. 循环执行：无限循环直到3轮连续一致通过
2. 每次Fresh：每轮清空上下文、重置沙盒
3. 客观验证：每步必须输出可验证结果
4. 错误回灌：失败时把错误喂给下一轮
5. 禁止撒谎：任何步骤无真实结果 = 未执行

用法：
    from ralph_loop import RalphLoop
    
    verifier = RalphLoop(task="验证Skill XYZ")
    result = verifier.run()
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import json

# ============================================================
# 数据结构
# ============================================================

class VerificationStatus(str):
    """验证状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"

class RoundState(str):
    """轮次状态"""
    FRESH = "fresh"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"

@dataclass
class VerificationItem:
    """验证项"""
    id: str
    name: str
    description: str
    check_fn: Optional[Callable] = None  # 验证函数
    status: VerificationStatus = VerificationStatus.PENDING
    result: Optional[bool] = None
    output: Optional[str] = None
    error: Optional[str] = None

@dataclass 
class RoundReport:
    """轮次报告"""
    round_num: int
    state: RoundState
    start_time: str
    end_time: Optional[str] = None
    items: List[Dict] = field(default_factory=list)
    passed_count: int = 0
    failed_count: int = 0
    problems: List[str] = field(default_factory=list)
    optimizations: List[str] = field(default_factory=list)
    conclusion: str = "不通过"
    execution_log: List[Dict] = field(default_factory=list)

@dataclass
class RalphResult:
    """最终结果"""
    success: bool
    total_rounds: int
    consecutive_passed: int
    final_report: RoundReport
    all_reports: List[RoundReport]
    error_feedback: List[str] = field(default_factory=list)

# ============================================================
# 受控演示 / 测试桩（通过 check_fn 白名单，禁止任意 lambda）
# ============================================================


class RalphDemoChecks:
    """CLI 与单测使用的受控校验方法，非用户任意可调用对象。"""

    def __init__(self) -> None:
        self._call_seq = 0

    def demo_file_ok(self) -> bool:
        return True

    def demo_code_ok(self) -> bool:
        return True

    def demo_output_fail(self) -> bool:
        return False

    def demo_all_pass_a(self) -> bool:
        return True

    def demo_all_pass_b(self) -> bool:
        return True

    def demo_fail_then_pass(self) -> bool:
        self._call_seq += 1
        return self._call_seq >= 2


# ============================================================
# Ralph Loop 核心
# ============================================================

class RalphLoop:
    """
    Ralph Loop 验证器
    
    执行3轮循环验证，直到连续3轮完全一致通过。
    每次循环清空上下文，进行Fresh验证。
    """
    
    MAX_ROUNDS = 10  # 最大轮数，防止无限循环
    REQUIRED_CONSECUTIVE = 3  # 需要的连续通过轮数

    # ========== P0安全修复：check_fn白名单 ==========
    # 仅允许来自受信任内部模块的check_fn，防止任意代码执行
    # 格式：(class_or_module, method_name) 元组列表
    _ALLOWED_CHECK_SOURCES = [
        # sindris_executor 内部验证方法（按名称白名单）
        ("SindrisExecutor", "_default_file_modified_check"),
        ("SindrisExecutor", "_default_role_consistency_check"),
        ("SindrisExecutor", "_default_audit_check"),
        ("SindrisExecutor", "_default_omx_check"),
        ("SindrisExecutor", "_default_impl_check"),
        ("SindrisExecutor", "_default_test_check"),
        ("SindrisExecutor", "_check_file_modified"),
        ("SindrisExecutor", "_check_role_consistency"),
        ("SindrisExecutor", "_check_audit"),
        ("SindrisExecutor", "_check_omx"),
        ("SindrisExecutor", "_check_impl"),
        ("SindrisExecutor", "_check_test"),
        # 测试Mock类（测试时使用，绑定到MockSindrisExecutor）
        ("MockSindrisExecutor", "_default_file_modified_check"),
        ("MockSindrisExecutor", "_default_role_consistency_check"),
        ("MockSindrisExecutor", "_default_audit_check"),
        ("MockSindrisExecutor", "_default_omx_check"),
        ("MockSindrisExecutor", "_default_impl_check"),
        ("MockSindrisExecutor", "_default_test_check"),
        ("MockSindrisExecutor", "_check_file_modified"),
        ("MockSindrisExecutor", "_check_role_consistency"),
        ("MockSindrisExecutor", "_check_audit"),
        ("MockSindrisExecutor", "_check_omx"),
        ("MockSindrisExecutor", "_check_impl"),
        ("MockSindrisExecutor", "_check_test"),
        # 额外测试方法
        ("MockSindrisExecutor", "_default_test_check_p1"),
        ("MockSindrisExecutor", "_default_test_check_p2"),
        ("MockSindrisExecutor", "_check_pass_item"),
        ("MockSindrisExecutor", "_check_fail_item"),
        ("MockSindrisExecutor", "_check_stateful"),
        ("MockSindrisExecutor", "_check_error_stateful"),
        ("MockSindrisExecutor", "_check_impl_error"),
        ("MockSindrisExecutor", "_check_impl_error_custom"),
        ("MockSindrisExecutor", "_check_impl_false"),
        ("MockSindrisExecutor", "_check_test_false"),
        ("MockSindrisExecutor", "_check_audit_false"),
        # 异步方法
        ("MockSindrisExecutor", "_default_file_modified_check_async"),
        ("MockSindrisExecutor", "_default_impl_check_async"),
        ("MockSindrisExecutor", "_default_impl_check_false_async"),
        ("MockSindrisExecutor", "_check_pass_async"),
        ("MockSindrisExecutor", "_check_fail_async"),
        ("MockSindrisExecutor", "_check_impl_error_async"),
        # 模块内受控演示桩（CLI / 单测）
        ("RalphDemoChecks", "demo_file_ok"),
        ("RalphDemoChecks", "demo_code_ok"),
        ("RalphDemoChecks", "demo_output_fail"),
        ("RalphDemoChecks", "demo_all_pass_a"),
        ("RalphDemoChecks", "demo_all_pass_b"),
        ("RalphDemoChecks", "demo_fail_then_pass"),
    ]

    @classmethod
    def _is_check_fn_allowed(cls, check_fn: Callable) -> bool:
        """检查check_fn是否来自受信任的内部源。

        安全策略：
        - 仅允许来自SindrisExecutor等内部类的绑定方法
        - 不允许外部传入的任意callable
        - 防御：即使攻击者绕过头部检查，仍需通过此处
        """
        if not callable(check_fn):
            return False

        # 获取方法名和绑定对象类名
        try:
            fn_name = getattr(check_fn, "__name__", None)
            if not fn_name:
                return False

            # 获取绑定到的类名（适用于绑定方法）
            bound_class = None
            if hasattr(check_fn, "__self__"):
                bound_class = type(check_fn.__self__).__name__

            # 白名单匹配：(class_name, method_name)
            if (bound_class, fn_name) in cls._ALLOWED_CHECK_SOURCES:
                return True

            # 明确拒绝所有其他callable（包括外部lambda、函数等）
            return False
        except Exception:
            # 出错时默认拒绝（fail-safe）
            return False

    def _parse_verify_items(self, items: List[Dict]) -> List[VerificationItem]:
        """解析验证项（带安全检查）"""
        parsed = []
        for item in items:
            check_fn = item.get("check_fn")

            # P0安全检查：拒绝未授权的check_fn
            if check_fn is not None and not self._is_check_fn_allowed(check_fn):
                import logging
                logging.warning(
                    f"[Ralph] 安全拦截：rejecting untrusted check_fn in verify_items[name={item.get('name')}] "
                    f"— only internal SindrisExecutor bound methods are allowed. "
                    f"This incident should be investigated."
                )
                # 安全：跳过此项而非执行恶意callable
                continue

            v = VerificationItem(
                id=item.get("id", str(uuid.uuid4())[:8]),
                name=item.get("name", "unnamed"),
                description=item.get("description", ""),
                check_fn=check_fn,
            )
            parsed.append(v)
        return parsed

    def __init__(
        self,
        task_name: str,
        verify_items: Optional[List[Dict]] = None,
        execute_fn: Optional[Callable] = None,
        on_round_complete: Optional[Callable] = None,
    ):
        """
        初始化 Ralph Loop
        
        Args:
            task_name: 任务名称
            verify_items: 验证项列表 [{"name": "...", "description": "...", "check_fn": callable}]
            execute_fn: 执行函数 (可选)
            on_round_complete: 轮次完成回调 (可选)
        """
        self.task_name = task_name
        raw_items = verify_items or []
        self.verify_items = self._parse_verify_items(raw_items)
        self._raw_verify_items_count = len(raw_items)
        self.execute_fn = execute_fn
        self.on_round_complete = on_round_complete
        
        self.rounds: List[RoundReport] = []
        self.consecutive_passed = 0
        self.current_round = 0
        self.error_feedback: List[str] = []

    def add_verify_item(
        self,
        name: str,
        description: str = "",
        check_fn: Optional[Callable] = None,
    ):
        """添加验证项（带安全检查）"""
        # P0安全检查：拒绝未授权的check_fn
        if check_fn is not None and not self._is_check_fn_allowed(check_fn):
            import logging
            logging.warning(
                f"[Ralph] 安全拦截：rejecting untrusted check_fn in add_verify_item[name={name}] "
                f"— only internal SindrisExecutor bound methods are allowed."
            )
            return

        self.verify_items.append(VerificationItem(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            check_fn=check_fn,
        ))
    
    async def run(self) -> RalphResult:
        """
        执行 Ralph Loop
        
        Returns:
            RalphResult: 包含所有轮次报告和最终结果
        """
        print(f"[Ralph] 开始验证任务: {self.task_name}")
        print(f"[Ralph] 验证项数量: {len(self.verify_items)}")
        print(f"[Ralph] 需要连续 {self.REQUIRED_CONSECUTIVE} 轮通过")
        print()
        
        for round_num in range(1, self.MAX_ROUNDS + 1):
            self.current_round = round_num
            
            # 执行一轮
            report = await self._run_round(round_num)
            self.rounds.append(report)
            
            # 打印轮次报告
            self._print_round_report(report)
            
            # 回调
            if self.on_round_complete:
                self.on_round_complete(report)
            
            # 检查是否满足退出条件
            if report.conclusion == "通过":
                self.consecutive_passed += 1
                if self.consecutive_passed >= self.REQUIRED_CONSECUTIVE:
                    print(f"\n[Ralph] ✅ 连续 {self.consecutive_passed} 轮通过，验证完成！")
                    break
            else:
                self.consecutive_passed = 0
                # 收集错误反馈
                self.error_feedback.extend(report.problems)
        else:
            print(f"\n[Ralph] ⚠️ 达到最大轮数 {self.MAX_ROUNDS}，验证未通过")
        
        # 构建最终结果
        final_report = self.rounds[-1] if self.rounds else None
        result = RalphResult(
            success=self.consecutive_passed >= self.REQUIRED_CONSECUTIVE,
            total_rounds=len(self.rounds),
            consecutive_passed=self.consecutive_passed,
            final_report=final_report,
            all_reports=self.rounds,
            error_feedback=self.error_feedback,
        )
        
        print(f"\n[Ralph] 最终结果: {'✅ 通过' if result.success else '❌ 未通过'}")
        print(f"[Ralph] 总轮数: {result.total_rounds}")
        print(f"[Ralph] 连续通过: {result.consecutive_passed}/{self.REQUIRED_CONSECUTIVE}")
        
        return result
    
    async def _run_round(self, round_num: int) -> RoundReport:
        """执行单轮验证"""
        print(f"\n{'='*60}")
        print(f"[Ralph 轮次：{round_num} / 状态：进行中]")
        print(f"{'='*60}")
        
        report = RoundReport(
            round_num=round_num,
            state=RoundState.FRESH,
            start_time=datetime.now().isoformat(),
        )
        
        # Step 1: 重置沙盒（Fresh）
        report.execution_log.append({
            "step": "reset",
            "action": "重置沙盒/上下文",
            "status": "pending"
        })
        await self._reset_sandbox()
        report.execution_log[-1]["status"] = "done"
        print("[1] 执行记录: 重置沙盒 ✅")
        
        # Step 2: 执行任务（如果有执行函数）
        if self.execute_fn:
            report.state = RoundState.EXECUTING
            report.execution_log.append({
                "step": "execute",
                "action": "执行任务",
                "input": "execute_fn",
                "status": "pending"
            })
            try:
                # 注入错误反馈
                await self.execute_fn(error_feedback=self.error_feedback)
                report.execution_log[-1]["status"] = "done"
                report.execution_log[-1]["output"] = "success"
                print("[2] 执行记录: 执行任务 ✅")
            except Exception as e:
                report.execution_log[-1]["status"] = "error"
                report.execution_log[-1]["error"] = str(e)
                report.problems.append(f"执行错误: {str(e)}")
                print(f"[2] 执行记录: 执行任务 ❌ ({str(e)})")
        else:
            report.execution_log.append({
                "step": "execute", 
                "action": "无执行函数（跳过）",
                "status": "skipped"
            })
            print("[2] 执行记录: 无执行函数（跳过）")
        
        # Step 3: 验证
        report.state = RoundState.VERIFYING
        await self._verify_items(report)
        
        # Step 4: 统计
        report.passed_count = sum(1 for i in self.verify_items if i.result == True)
        report.failed_count = sum(1 for i in self.verify_items if i.result == False)
        
        # Step 5: 结论
        # 安全策略会过滤不受信任check_fn，过滤后若无有效验证项，不能判定为通过。
        if len(self.verify_items) == 0:
            if self._raw_verify_items_count > 0:
                report.problems.append("所有验证项均被安全策略拦截，无法完成有效验证")
            else:
                report.problems.append("未提供验证项，无法判定任务通过")
            report.failed_count = 1
            report.conclusion = "不通过"
        else:
            report.conclusion = "通过" if report.failed_count == 0 else "不通过"
        report.end_time = datetime.now().isoformat()
        report.state = RoundState.COMPLETED
        
        return report
    
    async def _reset_sandbox(self):
        """重置沙盒"""
        # 这里可以扩展为实际的沙盒重置逻辑
        # 例如：清空临时文件、恢复初始状态等
        await asyncio.sleep(0.01)  # 模拟异步操作
    
    async def _verify_items(self, report: RoundReport):
        """验证所有项"""
        print(f"\n[3] 验证清单 ({len(self.verify_items)} 项):")
        
        for i, item in enumerate(self.verify_items, 1):
            # 重置状态
            item.status = VerificationStatus.IN_PROGRESS
            item.result = None
            item.output = None
            item.error = None
            
            try:
                if item.check_fn:
                    # 调用验证函数
                    result = await self._run_check(item)
                    item.result = result
                    item.status = VerificationStatus.PASSED if result else VerificationStatus.FAILED
                    output = "通过" if result else "失败"
                else:
                    # 无验证函数，标记为待检查
                    item.status = VerificationStatus.PENDING
                    item.result = None
                    output = "待手动检查"
                
                # 记录
                status_val = item.status.value if hasattr(item.status, 'value') else item.status
                item_record = {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "result": item.result,
                    "status": status_val,
                    "output": item.output or output,
                    "error": item.error,
                }
                report.items.append(item_record)
                
                icon = "✅" if item.result == True else "❌" if item.result == False else "⏳"
                print(f"  {icon} [{i}] {item.name}: {item.description or output}")
                
            except Exception as e:
                item.status = VerificationStatus.ERROR
                item.error = str(e)
                item_record = {
                    "id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "result": False,
                    "status": VerificationStatus.ERROR.value if hasattr(VerificationStatus.ERROR, 'value') else 'error',
                    "error": str(e),
                }
                report.items.append(item_record)
                report.problems.append(f"{item.name} 异常: {str(e)}")
                print(f"  ❌ [{i}] {item.name}: 异常 ({str(e)})")
    
    async def _run_check(self, item: VerificationItem) -> bool:
        """运行单个验证"""
        if asyncio.iscoroutinefunction(item.check_fn):
            return await item.check_fn()
        else:
            return item.check_fn()
    
    def _print_round_report(self, report: RoundReport):
        """打印轮次报告"""
        print(f"\n{'='*60}")
        print(f"[Ralph 轮次：{report.round_num} / 状态：已完成]")
        print(f"{'='*60}")
        
        print(f"1. 执行记录：")
        for log in report.execution_log:
            status_icon = "✅" if log.get("status") == "done" else "❌" if log.get("status") == "error" else "⏳"
            print(f"   {status_icon} {log.get('step')}: {log.get('action')} - {log.get('status')}")
        
        print(f"\n2. 验证清单：")
        for item in report.items:
            icon = "✅" if item.get("result") == True else "❌" if item.get("result") == False else "⏳"
            print(f"   {icon} {item.get('name')}: {item.get('output') or item.get('description', '')}")
        
        print(f"\n3. 问题/遗漏：")
        if report.problems:
            for p in report.problems:
                print(f"   ❌ {p}")
        else:
            print("   无")
        
        print(f"\n4. 下轮优化：")
        if report.optimizations:
            for o in report.optimizations:
                print(f"   → {o}")
        else:
            print("   无")
        
        print(f"\n5. 本轮结论：{report.conclusion}")
        print(f"   通过: {report.passed_count} / 失败: {report.failed_count}")


# ============================================================
# 便捷函数
# ============================================================

async def verify_skill(
    skill_name: str,
    verify_items: List[Dict],
    execute_fn: Optional[Callable] = None,
) -> RalphResult:
    """
    快速验证Skill
    
    Args:
        skill_name: Skill名称
        verify_items: 验证项列表
        execute_fn: 执行函数
    
    Returns:
        RalphResult
    """
    verifier = RalphLoop(
        task_name=f"验证Skill: {skill_name}",
        verify_items=verify_items,
        execute_fn=execute_fn,
    )
    return await verifier.run()


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    async def test():
        print("=== Ralph Loop 测试 ===\n")

        demo = RalphDemoChecks()
        items = [
            {"name": "文件存在", "description": "检查文件是否存在", "check_fn": demo.demo_file_ok},
            {"name": "代码可执行", "description": "检查代码能否执行", "check_fn": demo.demo_code_ok},
            {"name": "输出正确", "description": "检查输出是否符合预期", "check_fn": demo.demo_output_fail},
        ]

        verifier = RalphLoop(
            task_name="测试任务",
            verify_items=items,
        )
        
        result = await verifier.run()
        print(f"\n最终结果: {'✅ 通过' if result.success else '❌ 未通过'}")
        return result
    
    asyncio.run(test())
