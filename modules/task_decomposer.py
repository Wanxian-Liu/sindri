"""
task_decomposer.py - 任务分解模块

职责：
- 按Round阶段分解任务
- 固定小组角色分配
- 精确slice生成

v3.5修复：
- 配置化ROUND_STAGES
- 错误处理和降级策略
- 无slices时的fallback处理
"""

import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .role_matcher import RoleMatcher, FIXED_TEAM

# 配置化的Round阶段
ROUND_STAGES = {
    "round1": {
        "name": "规划",
        "role_key": "architect",
        "fallback_role_index": 2,  # Software Architect
    },
    "round2": {
        "name": "执行",
        "role_key": "developer",
        "fallback_role_index": 3,  # Senior Developer
    },
    "round3": {
        "name": "审查",
        "role_key": "tester",
        "fallback_role_index": 5,  # API Tester
    },
}

logger = logging.getLogger(__name__)


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
        获取任务角色
        
        优先级：
        1. auto_matched_roles（来自FusionPlanner._decompose_and_match的预匹配结果）
        2. RoleMatcher.match() 的角色（仅当auto_matched_roles为空时）
        3. 默认固定小组
        
        注意：auto_matched_roles不为空时直接使用，不再重复调用RoleMatcher.match()
              以避免FusionPlanner中RoleMatcher被调用两次的性能开销。
        """
        # 优先使用预匹配结果（来自FusionPlanner._decompose_and_match的第一次调用）
        if auto_matched_roles:
            logger.info(f"[TaskDecomposer] 使用预匹配的角色（{len(auto_matched_roles)}个），跳过重复RoleMatcher调用")
            # 检查是否是审计团队或evolution团队
            is_audit = any(r.get('team_type') == 'audit' for r in auto_matched_roles)
            is_evolution = any(r.get('team_type') == 'evolution' for r in auto_matched_roles)
            if is_evolution:
                for r in auto_matched_roles:
                    r['team_type'] = 'evolution'
            elif is_audit:
                for r in auto_matched_roles:
                    r['team_type'] = 'audit'
            return auto_matched_roles
        
        # auto_matched_roles为空时才调用RoleMatcher（降级fallback）
        try:
            matches = self.role_matcher.match(task)
            if matches:
                logger.info(f"[TaskDecomposer] RoleMatcher匹配到{len(matches)}个角色")
                # 检查是否是审计团队
                is_audit = any(getattr(m, 'source', None) == 'audit_team' for m in matches)
                # 检查是否是角色改进分配器（包括audit_evolution的fallback情况）
                is_evolution = any(getattr(m, 'source', None) in ('evolution_distributor', 'audit_evolution') for m in matches)
                roles = [m.role for m in matches]
                # 注意：evolution优先检查，因为role_matcher的fallback可能返回source=audit_team但team_type=evolution
                if is_evolution:
                    for r in roles:
                        r['team_type'] = 'evolution'
                elif is_audit:
                    for r in roles:
                        r['team_type'] = 'audit'
                return roles
        except Exception as e:
            logger.warning(f"[TaskDecomposer] RoleMatcher错误: {e}，使用fallback")
        
        # 默认使用固定小组
        logger.info(f"[TaskDecomposer] 默认使用固定小组")
        return FIXED_TEAM
    
    def decompose_by_round(
        self,
        task: str,
        roles: List[Dict],
    ) -> Dict[str, List[Task]]:
        """
        按Round阶段分解任务
        
        Returns:
            {
                "round1": [Task, ...],
                "round2": [Task, ...],
                "round3": [Task, ...],
            }
        """
        # 生成slices（可能失败，返回空列表）
        slices = self._generate_slices_safe(task)
        
        # Round1: 规划任务
        round1_tasks = self._create_round1_tasks(task, roles, slices)
        
        # Round2: 执行任务
        round2_tasks = self._create_round2_tasks(slices, roles)
        
        # Round3: 审查任务
        round3_tasks = self._create_round3_tasks(slices, roles)
        
        return {
            "round1": round1_tasks,
            "round2": round2_tasks,
            "round3": round3_tasks,
        }
    
    def _generate_slices_safe(self, task: str) -> List[Dict]:
        """生成代码slice（带错误处理）"""
        try:
            slices = self._generate_slices(task)
            logger.info(f"[TaskDecomposer] 生成了{len(slices)}个slices")
            return slices
        except Exception as e:
            logger.error(f"[TaskDecomposer] Slice生成失败: {e}")
            return []
    
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
            logger.warning(f"[TaskDecomposer] SliceGenerator unavailable: {e}")
            return []
    
    def _get_role_from_team(self, roles: List[Dict], key: str, fallback_index: int) -> Dict:
        """从团队中获取角色"""
        # 尝试通过key匹配
        for r in roles:
            role_id = r.get('id', '').lower()
            if key in role_id:
                return r
        
        # fallback到FIXED_TEAM
        if 0 <= fallback_index < len(FIXED_TEAM):
            return FIXED_TEAM[fallback_index]
        
        # 最后的fallback
        return FIXED_TEAM[0]
    
    def _create_round1_tasks(
        self,
        task: str,
        roles: List[Dict],
        slices: List[Dict],
    ) -> List[Task]:
        """创建Round1任务（规划）"""
        tasks = []
        task_lower = task.lower()
        
        # 产品管理任务 → Product Manager
        if '产品' in task or '路线图' in task or 'pm' in task_lower or 'product' in task_lower:
            pm_role = self._get_role_from_team(roles, 'product_manager', 0)
            tasks.append(Task(
                id=self._gen_id("task"),
                title="产品规划与需求分析",
                kind="round1_planning",
                phase="round1",
                priority="high",
                verify=["PRD文档完整", "利益相关者确认"],
                metadata={
                    "role": pm_role,
                    "task_context": task,
                    "stage": "planning",
                }
            ))
            return tasks
        
        # 工程任务 → Software Architect
        engineering_keywords = [
            '编程', '开发', '代码', 'python', 'java', 'javascript', 'typescript',
            '修改', '优化', '修复', 'bug', '重构', 'refactor', 'feature',
            '模块', '组件', '系统', '架构', '接口', '实现',
            'mimir', 'sindris', '进化', '记忆殿堂',
        ]
        if any(kw in task_lower for kw in engineering_keywords):
            architect_role = self._get_role_from_team(roles, 'architect', 2)
            tasks.append(Task(
                id=self._gen_id("task"),
                title="架构分析与任务规划",
                kind="round1_planning",
                phase="round1",
                priority="high",
                verify=["规划文档完整", "技术方案可行"],
                metadata={
                    "role": architect_role,
                    "task_context": task,
                    "slices_count": len(slices),
                    "stage": "planning",
                }
            ))
            return tasks
        
        # 协调/编排任务 → Agents Orchestrator
        orchestrator_role = self._get_role_from_team(roles, 'orchestrator', 1)
        tasks.append(Task(
            id=self._gen_id("task"),
            title="工作流编排与协调",
            kind="round1_planning",
            phase="round1",
            priority="high",
            verify=["编排方案完整", "资源分配合理"],
            metadata={
                "role": orchestrator_role,
                "task_context": task,
                "stage": "planning",
            }
        ))
        
        return tasks
    
    def _create_round2_tasks(self, slices: List[Dict], roles: List[Dict]) -> List[Task]:
        """创建Round2任务（执行）"""
        tasks = []
        developer_role = self._get_role_from_team(roles, 'developer', 3)  # Senior Developer
        
        # 如果有slices且数量合理（<=5），按slice创建任务
        # 数量>5说明SliceGenerator无法精确匹配，使用fallback避免污染
        if slices and len(slices) <= 5:
            for slice_info in slices:
                # 验证slice的test_cmd是否有效
                test_cmd = slice_info.get('test_cmd', '')
                # 如果test_cmd包含pytest且文件存在，则认为有效
                verify = [test_cmd] if test_cmd and 'pytest' in test_cmd else ['代码审查通过']
                
                tasks.append(Task(
                    id=self._gen_id("task"),
                    title=f"{slice_info['file']}::{slice_info['function']}",
                    kind="round2_execution",
                    phase="round2",
                    priority=slice_info.get('priority', 'medium'),
                    verify=verify,
                    metadata={
                        "role": developer_role,
                        "slice": slice_info,
                        "stage": "execution",
                    }
                ))
        else:
            # slice太多（>10）或无slice时使用fallback
            # 这避免了指向上下文不相关文件的问题
            fallback_tasks = [
                ("任务理解与分解", ["任务理解正确", "分解方案合理"]),
                ("代码实现与调试", ["代码实现完成", "调试通过"]),
                ("测试与验证", ["单元测试通过", "集成测试通过"]),
            ]
            for title, verify_list in fallback_tasks:
                tasks.append(Task(
                    id=self._gen_id("task"),
                    title=title,
                    kind="round2_execution",
                    phase="round2",
                    priority="high",
                    verify=verify_list,
                    metadata={
                        "role": developer_role,
                        "stage": "execution",
                        "fallback": True,
                        "slices_count": len(slices) if slices else 0,
                    }
                ))
        
        return tasks
    
    def _create_round3_tasks(self, slices: List[Dict], roles: List[Dict]) -> List[Task]:
        """创建Round3任务（审查）"""
        tasks = []
        tester_role = self._get_role_from_team(roles, 'tester', 5)  # API Tester
        checker_role = self._get_role_from_team(roles, 'checker', 6)  # Reality Checker
        
        # 功能验证任务
        tasks.append(Task(
            id=self._gen_id("task"),
            title="功能验证",
            kind="round3_review",
            phase="round3",
            priority="high",
            verify=["功能测试通过", "边界条件覆盖"],
            metadata={
                "role": tester_role,
                "review_type": "functional",
                "slices_count": len(slices),
                "stage": "review",
            }
        ))
        
        # 质量审查任务
        tasks.append(Task(
            id=self._gen_id("task"),
            title="代码质量审查",
            kind="round3_review",
            phase="round3",
            priority="high",
            verify=["代码质量达标", "无严重问题"],
            metadata={
                "role": checker_role,
                "review_type": "quality",
                "slices_count": len(slices),
                "stage": "review",
            }
        ))
        
        return tasks
    
    def _gen_id(self, prefix: str) -> str:
        """生成唯一ID"""
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
