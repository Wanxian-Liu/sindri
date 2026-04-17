"""
task_decomposer.py - 任务分解模块

职责：
- 按Round阶段分解任务
- 固定小组角色分配
- 精确slice生成
"""

import os
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from .role_matcher import RoleMatcher, FIXED_TEAM


@dataclass
class Task:
    """任务数据结构"""
    id: str
    title: str
    kind: str
    phase: str  # round1/round2/round3
    priority: str
    verify: List[str]
    metadata: Dict[str, Any]


class TaskDecomposer:
    """
    任务分解器
    
    职责：
    1. 分析任务类型
    2. 决定使用固定小组还是自动匹配
    3. 按Round阶段分配任务
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.role_matcher = RoleMatcher(workspace_root)
    
    def get_roles(self, task: str, auto_matched_roles: List[Dict]) -> List[Dict]:
        """
        获取任务角色（使用RoleMatcher混合方案）
        
        优先级：
        1. RoleMatcher.match() 返回的角色（固定小组/向量/claim）
        2. 自动匹配的角色
        3. 默认固定小组
        """
        matches = self.role_matcher.match(task)
        if matches:
            print(f"[TaskDecomposer] RoleMatcher匹配到{len(matches)}个角色")
            return [m.role for m in matches]
        
        if auto_matched_roles:
            print(f"[TaskDecomposer] 使用自动匹配的角色")
            return auto_matched_roles
        
        # 默认使用固定小组
        print(f"[TaskDecomposer] 默认使用固定小组")
        return FIXED_TEAM
    
    def decompose_by_round(
        self,
        task: str,
        roles: List[Dict],
    ) -> Dict[str, List[Task]]:
        """
        按Round阶段分解任务
        
        Round1: 规划 → Software Architect
        Round2: 执行 → Senior Developer
        Round3: 审查 → API Tester + Reality Checker
        
        Returns:
            {
                "round1": [Task, ...],
                "round2": [Task, ...],
                "round3": [Task, ...],
            }
        """
        slices = self._generate_slices(task)
        
        # Round1: 规划任务
        round1_tasks = self._create_round1_tasks(task, roles, slices)
        
        # Round2: 执行任务（分配给Developer）
        round2_tasks = self._create_round2_tasks(slices)
        
        # Round3: 审查任务（分配给Tester）
        round3_tasks = self._create_round3_tasks(slices)
        
        return {
            "round1": round1_tasks,
            "round2": round2_tasks,
            "round3": round3_tasks,
        }
    
    def _generate_slices(self, task: str) -> List[Dict]:
        """生成代码slice"""
        # 动态导入SliceGenerator
        try:
            import importlib.util
            slice_gen_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "scripts", "slice_generator.py"
            )
            spec = importlib.util.spec_from_file_location("slice_generator", slice_gen_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            gen = module.SliceGenerator(workspace_root=self.workspace_root)
            raw_slices = gen.generate_slices(task)
            
            # 转换为dict格式
            slices = []
            for s in raw_slices:
                slices.append({
                    "file": s.file,
                    "function": s.function,
                    "description": s.description,
                    "test_cmd": s.test_cmd,
                    "priority": s.priority,
                })
            return slices
        except Exception as e:
            print(f"[TaskDecomposer] SliceGenerator failed: {e}")
            return []
    
    def _create_round1_tasks(
        self,
        task: str,
        roles: List[Dict],
        slices: List[Dict],
    ) -> List[Task]:
        """创建Round1任务（规划）"""
        tasks = []
        
        # Round1任务：根据任务类型选择
        # 产品管理任务 → Product Manager
        # 协调/编排任务 → Agents Orchestrator
        # 工程任务 → Software Architect
        
        task_lower = task.lower()
        if '产品' in task or '路线图' in task or 'pm' in task_lower or 'product' in task_lower:
            pm_role = next((r for r in roles if 'product_manager' in r.get('id', '').lower()), None)
            if pm_role:
                tasks.append(Task(
                    id=self._gen_id("task"),
                    title="产品规划与需求分析",
                    kind="round1_planning",
                    phase="round1",
                    priority="high",
                    verify=["检查PRD文档是否完整"],
                    metadata={
                        "role": pm_role,
                        "task_context": task,
                    }
                ))
                return tasks
        
        orchestrator_role = next(
            (r for r in roles if 'orchestrator' in r.get('id', '').lower()),
            None
        )
        if orchestrator_role:
            tasks.append(Task(
                id=self._gen_id("task"),
                title="工作流编排与协调",
                kind="round1_planning",
                phase="round1",
                priority="high",
                verify=["检查编排方案是否完整"],
                metadata={
                    "role": orchestrator_role,
                    "task_context": task,
                }
            ))
            return tasks
        
        architect_role = next(
            (r for r in roles if 'architect' in r.get('id', '').lower()),
            roles[0] if roles else FIXED_TEAM[0]
        )
        
        tasks.append(Task(
            id=self._gen_id("task"),
            title="架构分析与任务规划",
            kind="round1_planning",
            phase="round1",
            priority="high",
            verify=["检查规划文档是否完整"],
            metadata={
                "role": architect_role,
                "task_context": task,
                "slices_count": len(slices),
            }
        ))
        
        return tasks
    
    def _create_round2_tasks(self, slices: List[Dict]) -> List[Task]:
        """创建Round2任务（执行）"""
        tasks = []
        
        developer_role = FIXED_TEAM[1]  # Senior Developer
        
        for i, slice in enumerate(slices[:20]):  # 限制最多20个
            tasks.append(Task(
                id=self._gen_id("task"),
                title=f"{slice['file']}::{slice['function']}",
                kind="round2_execution",
                phase="round2",
                priority=slice.get('priority', 'medium'),
                verify=[slice.get('test_cmd', '')],
                metadata={
                    "role": developer_role,
                    "slice": slice,
                }
            ))
        
        return tasks
    
    def _create_round3_tasks(self, slices: List[Dict]) -> List[Task]:
        """创建Round3任务（审查）"""
        tasks = []
        
        # API Tester
        tester_role = FIXED_TEAM[2]  # API Tester
        checker_role = FIXED_TEAM[3]  # Reality Checker
        
        # 功能验证任务
        tasks.append(Task(
            id=self._gen_id("task"),
            title="功能验证",
            kind="round3_review",
            phase="round3",
            priority="high",
            verify=["pytest tests/ -v"],
            metadata={
                "role": tester_role,
                "review_type": "functional",
                "slices_count": len(slices),
            }
        ))
        
        # 质量审查任务
        tasks.append(Task(
            id=self._gen_id("task"),
            title="代码质量审查",
            kind="round3_review",
            phase="round3",
            priority="high",
            verify=["代码质量检查通过"],
            metadata={
                "role": checker_role,
                "review_type": "quality",
                "slices_count": len(slices),
            }
        ))
        
        return tasks
    
    def _gen_id(self, prefix: str) -> str:
        """生成唯一ID"""
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
