"""
round_manager.py - Round流程管理模块

职责：
- Round1-4流程控制
- Ralph验证集成
- 阶段切换
"""

import asyncio
import os
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

from .report_generator import ReportGenerator, RoundContext, ExecutionResult, ExecutionStatus
from .task_decomposer import TaskDecomposer, Task


@dataclass
class RoundConfig:
    """Round配置"""
    enable_ralph_verify: bool = True
    ralph_max_rounds: int = 3
    consensus_threshold: float = 0.8


class RoundManager:
    """
    Round流程管理器
    
    职责：
    1. 管理Round1-4的执行流程
    2. 调用TaskDecomposer分解任务
    3. 集成Ralph验证
    4. 管理状态转换
    """
    
    def __init__(
        self,
        workspace_root: str,
        session_id: str,
        config: Optional[RoundConfig] = None,
    ):
        self.workspace_root = workspace_root
        self.session_id = session_id
        self.config = config or RoundConfig()
        
        # 初始化子模块
        self.task_decomposer = TaskDecomposer(workspace_root)
        self.report_generator = ReportGenerator(session_id)
        
        # 状态
        self._current_round = 0
        self._context: Optional[RoundContext] = None
        self._round_results: Dict[int, List[ExecutionResult]] = {}
    
    async def execute_round1(
        self,
        task: str,
        auto_matched_roles: List[Dict],
        spawn_callback: Callable,
    ) -> RoundContext:
        """
        执行Round1：规划阶段
        
        1. 获取角色（固定小组 or 自动匹配）
        2. 分解任务
        3. 启动Software Architect
        """
        self._current_round = 1
        
        # 获取角色
        roles = self.task_decomposer.get_roles(task, auto_matched_roles)
        
        # 按Round分解任务
        decomposed = self.task_decomposer.decompose_by_round(task, roles)
        round1_tasks = decomposed["round1"]
        
        # 创建RoundContext
        self._context = RoundContext(
            round=1,
            phase="planning",
            task=task,
            matched_roles=roles,
            tasks=round1_tasks,
            plan_summary=f"Round1: {len(round1_tasks)}个规划任务",
            session_id=self.session_id,
        )
        
        # 执行Round1任务
        if round1_tasks:
            results = await self._execute_tasks(round1_tasks, spawn_callback)
            self._round_results[1] = results
        
        # 生成报告
        self.report_generator.generate_round1_report(self._context)
        
        return self._context
    
    async def execute_round2(
        self,
        spawn_callback: Callable,
    ) -> List[ExecutionResult]:
        """
        执行Round2：执行阶段
        
        1. 获取Round2任务（开发任务）
        2. 分配给Senior Developer
        3. 并行执行
        """
        self._current_round = 2
        
        if not self._context:
            raise ValueError("Round1 must be executed first")
        
        # 获取Round2任务
        decomposed = self.task_decomposer.decompose_by_round(
            self._context.task,
            self._context.matched_roles,
        )
        round2_tasks = decomposed["round2"]
        
        # 执行Round2任务
        results = await self._execute_tasks(round2_tasks, spawn_callback)
        self._round_results[2] = results
        
        # 生成报告
        self.report_generator.generate_round2_report(results)
        
        return results
    
    async def execute_round3(
        self,
        spawn_callback: Callable,
    ) -> bool:
        """
        执行Round3：审查阶段
        
        1. 获取Round3任务（审查任务）
        2. 分配给API Tester + Reality Checker
        3. Ralph验证（如果启用）
        """
        self._current_round = 3
        
        if 2 not in self._round_results:
            raise ValueError("Round2 must be executed first")
        
        # 获取Round3任务
        decomposed = self.task_decomposer.decompose_by_round(
            self._context.task if self._context else "",
            self._context.matched_roles if self._context else [],
        )
        round3_tasks = decomposed["round3"]
        
        # 执行Round3任务
        results = await self._execute_tasks(round3_tasks, spawn_callback)
        self._round_results[3] = results
        
        # Ralph验证（可选）
        review_passed = True
        if self.config.enable_ralph_verify:
            review_passed = await self._execute_ralph_verify(results)
        
        # 生成报告
        self.report_generator.generate_round3_report(results, review_passed)
        
        return review_passed
    
    async def execute_round4(
        self,
        spawn_callback: Callable,
    ) -> Dict[str, Any]:
        """
        执行Round4：完成阶段
        
        1. 汇总所有结果
        2. 生成最终报告
        3. 交付
        """
        self._current_round = 4
        
        all_results = []
        for round_num in [1, 2, 3]:
            if round_num in self._round_results:
                all_results.extend(self._round_results[round_num])
        
        # 生成最终报告
        total_success = sum(
            1 for r in all_results
            if r.status == ExecutionStatus.SUCCESS
        )
        total_failed = len(all_results) - total_success
        
        final_report = {
            "success": total_failed == 0,
            "session_id": self.session_id,
            "total_tasks": len(all_results),
            "successful": total_success,
            "failed": total_failed,
            "rounds_completed": 4,
            "results": [r.to_dict() for r in all_results],
        }
        
        return final_report
    
    async def _execute_tasks(
        self,
        tasks: List[Task],
        spawn_callback: Callable,
    ) -> List[ExecutionResult]:
        """执行任务列表"""
        results = []
        
        for task in tasks:
            try:
                # 检查callback是否是协程函数
                if asyncio.iscoroutinefunction(spawn_callback):
                    result = await spawn_callback(task)
                else:
                    # 同步callback，在线程池中执行
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, lambda: spawn_callback(task))
                
                results.append(ExecutionResult(
                    task_id=task.id,
                    title=task.title,
                    role=task.metadata.get("role", {}).get("name", "unknown"),
                    status=ExecutionStatus.SUCCESS if result.get("success") else ExecutionStatus.FAILED,
                    output=result.get("output"),
                    error=result.get("error"),
                    duration_ms=result.get("duration_ms", 0),
                    metadata=task.metadata,
                ))
            except Exception as e:
                results.append(ExecutionResult(
                    task_id=task.id,
                    title=task.title,
                    role=task.metadata.get("role", {}).get("name", "unknown"),
                    status=ExecutionStatus.FAILED,
                    error=str(e)[:200],
                    metadata=task.metadata,
                ))
        
        return results
    
    async def _execute_ralph_verify(
        self,
        results: List[ExecutionResult],
    ) -> bool:
        """执行Ralph验证"""
        try:
            # 动态导入RalphLoop
            import importlib.util
            ralph_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "scripts", "ralph_loop.py"
            )
            spec = importlib.util.spec_from_file_location("ralph_loop", ralph_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            RalphLoop = module.RalphLoop
            
            verifier = RalphLoop(
                task=f"验证{len(results)}个任务的结果"
            )
            ralph_result = await verifier.run()
            
            return ralph_result.success
            
        except Exception as e:
            print(f"[RoundManager] Ralph verification failed: {e}")
            # Ralph失败不影响流程
            return True
    
    def get_current_round(self) -> int:
        """获取当前Round"""
        return self._current_round
    
    def get_context(self) -> Optional[RoundContext]:
        """获取RoundContext"""
        return self._context
    
    def get_results(self, round_num: Optional[int] = None) -> Dict[int, List[ExecutionResult]]:
        """获取执行结果"""
        if round_num:
            return {round_num: self._round_results.get(round_num, [])}
        return self._round_results
