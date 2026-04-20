"""
plan_engine.py - 任务规划引擎

职责：
1. 任务分析和分类
2. 角色匹配和分配
3. 子任务分解（按Round）
4. 生成执行计划
"""

import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SubTask:
    """子任务定义"""
    task_id: str
    role: str
    role_file: Optional[str]
    role_prompt: str
    title: str
    tools: List[str]
    timeout: int
    phase: str  # round1/round2/round3
    verify: List[str]
    auto_run: bool = True


@dataclass 
class ExecutionPlan:
    """执行计划"""
    task_id: str
    task: str
    subtasks: List[SubTask]
    plan_summary: str
    phase: str  # planned/audit/evolution
    roles: List[Dict]
    verification_added: bool = False
    verification: Optional[Dict] = None


class PlanEngine:
    """
    任务规划引擎
    
    职责：
    1. 分析任务类型（开发/审计/进化）
    2. 匹配角色（使用RoleMatcher）
    3. 按Round分解任务
    4. 生成SubTask列表
    """
    
    def __init__(self, workspace_root: str, script_dir: str):
        self.workspace_root = workspace_root
        self.script_dir = script_dir
        self._role_matcher = None
        self._role_manager = None
        self._task_decomposer = None
    
    def _get_role_matcher(self):
        """懒加载RoleMatcher"""
        if self._role_matcher is None:
            try:
                from modules.role_matcher import RoleMatcher
                self._role_matcher = RoleMatcher(self.workspace_root)
            except ImportError:
                logger.warning("RoleMatcher not available")
        return self._role_matcher
    
    def _get_role_manager(self):
        """懒加载RoleManager"""
        if self._role_manager is None:
            try:
                from modules.role_manager import RoleManager
                self._role_manager = RoleManager(self.workspace_root)
            except ImportError:
                logger.warning("RoleManager not available")
        return self._role_manager
    
    def _get_task_decomposer(self):
        """懒加载TaskDecomposer"""
        if self._task_decomposer is None:
            try:
                from modules.task_decomposer import TaskDecomposer
                self._task_decomposer = TaskDecomposer(self.workspace_root)
            except ImportError:
                logger.warning("TaskDecomposer not available")
        return self._task_decomposer
    
    def plan(self, task: str) -> ExecutionPlan:
        """
        规划任务
        
        Args:
            task: 任务描述
        
        Returns:
            ExecutionPlan: 完整的执行计划
        """
        session_id = f"sindris_{uuid.uuid4().hex[:12]}"
        
        # 输入验证
        if not isinstance(task, str):
            raise ValueError(f"task must be str, got {type(task).__name__}")
        
        task = task.strip()
        if len(task) < 3:
            raise ValueError("task must be at least 3 characters")
        
        if len(task) > 5000:
            raise ValueError("task exceeds maximum length of 5000")
        
        # 获取组件
        role_matcher = self._get_role_matcher()
        role_manager = self._get_role_manager()
        task_decomposer = self._get_task_decomposer()
        
        # 匹配角色
        if role_matcher:
            matches = role_matcher.match(task)
        else:
            matches = []
        
        # 分析角色类型
        is_audit = any(getattr(m, 'source', None) == 'audit_team' for m in matches) if matches else False
        is_evolution = any(getattr(m, 'source', None) == 'evolution_distributor' for m in matches) if matches else False
        
        if is_audit:
            return self._plan_audit(task, session_id, matches, role_manager)
        elif is_evolution:
            return self._plan_evolution(task, session_id, matches, role_manager)
        else:
            return self._plan_development(task, session_id, matches, role_manager, task_decomposer)
    
    def _plan_audit(self, task: str, session_id: str, matches, role_manager) -> ExecutionPlan:
        """规划审计任务"""
        subtasks = []
        for m in matches:
            role = m.role
            role_name = role.get('name', role.get('id', 'Specialist'))
            role_file = self._find_role_file(role_name)
            role_prompt = self._get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
            
            subtasks.append(SubTask(
                task_id=f"audit_{role.get('id', 'task')}",
                role=role_name,
                role_file=role_file,
                role_prompt=role_prompt,
                title=f"审计角色: {role_name}",
                tools=["read", "exec", "write"],
                timeout=300,
                phase="audit",
                verify=[f"{role_name}审计完成"],
            ))
        
        return ExecutionPlan(
            task_id=session_id,
            task=task,
            subtasks=subtasks,
            plan_summary=f"审计任务分解为{len(subtasks)}个子任务",
            phase="audit",
            roles=[m.role for m in matches],
        )
    
    def _plan_evolution(self, task: str, session_id: str, matches, role_manager) -> ExecutionPlan:
        """规划进化任务"""
        subtasks = []
        for m in matches:
            role = m.role
            role_name = role.get('name', role.get('id', 'Specialist'))
            role_file = self._find_role_file(role_name)
            role_prompt = self._get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
            
            subtasks.append(SubTask(
                task_id=f"evolve_{role.get('id', 'task')}",
                role=role_name,
                role_file=role_file,
                role_prompt=role_prompt,
                title=f"完善角色: {role_name}",
                tools=["read", "exec", "write"],
                timeout=300,
                phase="round2",
                verify=[f"{role_name}完善完成"],
            ))
        
        # 添加验证步骤
        subtasks = self._add_verification_step(subtasks, "evolution")
        
        return ExecutionPlan(
            task_id=session_id,
            task=task,
            subtasks=subtasks,
            plan_summary=f"角色完善任务分解为{len(subtasks)}个子任务（包含验证步骤）",
            phase="evolution",
            roles=[m.role for m in matches],
            verification_added=True,
        )
    
    def _plan_development(self, task: str, session_id: str, matches, role_manager, task_decomposer) -> ExecutionPlan:
        """规划开发任务"""
        if task_decomposer and matches:
            roles = [m.role for m in matches]
            decomposed = task_decomposer.decompose_by_round(task, roles)
            
            # 合并所有任务
            all_tasks = []
            for round_key in ["round1", "round2", "round3"]:
                all_tasks.extend(decomposed.get(round_key, []))
        else:
            all_tasks = []
        
        # 构建subtasks
        subtasks = []
        for t in all_tasks:
            role = t.metadata.get("role", {})
            role_name = role.get("name", role.get("id", "Specialist"))
            role_file = self._find_role_file(role_name)
            role_prompt = self._get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
            
            allowed_tools = role_manager.get_allowed_tools(role_name) if role_manager else ["read", "exec"]
            timeout = role_manager.get_timeout(role_name) if role_manager else 600
            
            subtasks.append(SubTask(
                task_id=t.id,
                role=role_name,
                role_file=role_file,
                role_prompt=role_prompt,
                title=t.title,
                tools=allowed_tools,
                timeout=timeout,
                phase=t.phase,
                verify=t.verify,
            ))
        
        # 添加验证步骤
        subtasks = self._add_verification_step(subtasks, "dev")
        
        return ExecutionPlan(
            task_id=session_id,
            task=task,
            subtasks=subtasks,
            plan_summary=f"分解为{len(subtasks)}个子任务（包含验证步骤）",
            phase="planned",
            roles=[m.role for m in matches] if matches else [],
            verification_added=True,
        )
    
    def _add_verification_step(self, subtasks: List[SubTask], task_type: str) -> List[SubTask]:
        """添加验证步骤"""
        # 从subtasks中提取需要验证的文件
        files_to_verify = []
        for s in subtasks:
            if s.role_file and s.role_file.endswith('.md'):
                files_to_verify.append(s.role_file)
        
        # 生成验证条件
        verify_items = [f"文件存在: {f}" for f in files_to_verify]
        
        verification_step = SubTask(
            task_id=f"{task_type}_verifier",
            role="Verifier",
            role_file=None,
            role_prompt=f"你是结果验证专家。验证任务执行结果是否满足要求：\n1. 代码是否在.py或.md文件中实现\n2. 是否只是MOCK/placeholder\n3. 是否已集成到主流程\n4. 文件是否真的被修改（检查mtime）",
            title="验证任务结果",
            tools=["read", "exec"],
            timeout=60,
            phase="verification",
            verify=verify_items if verify_items else ["验证完成"],
            auto_run=True,
        )
        
        return subtasks + [verification_step]
    
    def _find_role_file(self, role_name: str) -> Optional[str]:
        """查找角色文件"""
        roles_dir = Path(self.script_dir) / "roles"
        if not roles_dir.exists():
            return None
        
        # 标准化角色名
        normalized = role_name.lower().replace(" ", "-").replace("_", "-")
        if normalized.startswith("sindri-"):
            normalized = normalized[7:]
        
        # 搜索匹配
        for md_file in roles_dir.rglob("*.md"):
            stem = md_file.stem.lower()
            if stem.startswith("sindri-"):
                stem = stem[7:]
            
            if normalized == stem or normalized in stem:
                return str(md_file.absolute())
        
        return None
    
    def _get_role_prompt(self, role_name: str) -> str:
        """获取角色Prompt"""
        role_file = self._find_role_file(role_name)
        if role_file:
            try:
                return Path(role_file).read_text()
            except:
                pass
        return f"You are {role_name}."
    
    def to_dict(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """将ExecutionPlan转换为字典"""
        return {
            "success": True,
            "task_id": plan.task_id,
            "subtasks": [
                {
                    "task_id": s.task_id,
                    "role": s.role,
                    "role_file": s.role_file,
                    "role_prompt": s.role_prompt,
                    "title": s.title,
                    "tools": s.tools,
                    "timeout": s.timeout,
                    "phase": s.phase,
                    "verify": s.verify,
                    "auto_run": s.auto_run,
                }
                for s in plan.subtasks
            ],
            "plan_summary": plan.plan_summary,
            "phase": plan.phase,
            "roles": plan.roles,
            "verification_added": plan.verification_added,
        }
