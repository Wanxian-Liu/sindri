"""
sindris_executor.py - 织界统一协调系统执行引擎 (纯规划器版)

版本历史：
- v3.3: 重构为纯规划器，删除误导的run()方法

核心定位：
- sindri是流程调节器（Orchestrator）
- 主代理调用plan()获取任务配置
- 主代理用sessions_spawn启动子代理执行
- 子代理套用专业角色工作
"""

VERSION = "3.5"

import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

import sys
import os

# 添加模块路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)


class SindrisExecutor:
    """
    Sindris执行器 - 纯规划器
    
    功能：
    1. plan() - 规划任务，返回子任务配置
    2. 主代理用sessions_spawn启动子代理
    3. 子代理按角色配置执行
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or str(Path.home() / ".openclaw" / "workspace")
        self.session_id = f"sindris_{uuid.uuid4().hex[:12]}"
    
    async def plan(self, task: str) -> Dict[str, Any]:
        """
        规划阶段：返回子任务列表
        
        主代理调用此方法获取任务配置，
        然后用sessions_spawn启动子代理执行。
        
        返回结构：
        {
            "success": True,
            "task_id": "xxx",
            "subtasks": [
                {
                    "task_id": "xxx",
                    "role": "Software Architect",
                    "role_file": "engineering/software-architect.md",
                    "title": "[Software Architect] 分析架构问题",
                    "tools": ["read", "glob", "grep", "web_fetch"],
                    "timeout": 600
                }
            ],
            "plan_summary": "..."
        }
        """
        # 导入任务分解器
        try:
            from modules import TaskDecomposer, RoleManager
            task_decomposer = TaskDecomposer(self.workspace_root)
            role_manager = RoleManager(self.workspace_root)
        except ImportError:
            return await self._plan_fallback(task)
        
        # 任务分解
        roles = task_decomposer.get_roles(task, [])
        decomposed = task_decomposer.decompose_by_round(task, roles)
        
        # 合并所有任务
        all_tasks = []
        all_tasks.extend(decomposed.get("round1", []))
        all_tasks.extend(decomposed.get("round2", []))
        all_tasks.extend(decomposed.get("round3", []))
        
        # 构建subtasks
        subtasks = []
        for t in all_tasks:
            role = t.metadata.get("role", {})
            role_name = role.get("name", role.get("id", "Specialist"))
            role_file = self._find_role_file(role_name)
            
            # 获取角色prompt
            role_prompt = self.get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
            
            subtasks.append({
                "task_id": t.id,
                "role": role_name,
                "role_file": role_file,
                "role_prompt": role_prompt,
                "title": t.title,
                "tools": role_manager.get_allowed_tools(role_name) if role_manager else ["read", "exec"],
                "timeout": role_manager.get_timeout(role_name) if role_manager else 600,
                "phase": t.phase,
                "verify": t.verify,  # 验证条件
            })
        
        return {
            "success": True,
            "task_id": self.session_id,
            "subtasks": subtasks,
            "plan_summary": f"分解为{len(subtasks)}个子任务：{[s['role'] for s in subtasks]}",
            "phase": "planned",
            "roles": roles,
        }
    
    async def _plan_fallback(self, task: str) -> Dict[str, Any]:
        """备用规划：使用固定小组"""
        return {
            "success": True,
            "task_id": self.session_id,
            "subtasks": [
                {
                    "task_id": f"fallback_{uuid.uuid4().hex[:8]}",
                    "role": "Specialist",
                    "role_file": None,
                    "title": f"[Specialist] {task}",
                    "tools": ["read", "exec", "edit", "write"],
                    "timeout": 600,
                    "phase": "round2"
                }
            ],
            "plan_summary": "使用默认角色执行",
            "phase": "planned",
            "roles": [{"id": "specialist", "name": "Specialist"}],
        }
    
    def _find_role_file(self, role_name: str) -> Optional[str]:
        """查找角色文件路径"""
        roles_dir = Path(SCRIPT_DIR) / "roles"
        if not roles_dir.exists():
            return None
        
        # 标准化角色名：去除sindri-前缀，转换空格/下划线
        normalized = role_name.lower().replace(" ", "-").replace("_", "-")
        # 去掉sindri-前缀如果存在
        if normalized.startswith("sindri-"):
            normalized = normalized[7:]
        
        for md_file in roles_dir.rglob("*.md"):
            stem = md_file.stem.lower()
            # 去掉sindri-前缀
            if stem.startswith("sindri-"):
                stem = stem[7:]
            # 检查是否匹配（支持部分匹配）
            if (normalized in stem or 
                any(part in stem for part in normalized.split("-"))):
                return str(md_file.relative_to(SCRIPT_DIR))
        
        return None
    
    def get_role_prompt(self, role_name: str) -> str:
        """获取角色Prompt用于子代理"""
        role_file = self._find_role_file(role_name)
        if role_file:
            try:
                with open(Path(SCRIPT_DIR) / role_file, "r") as f:
                    return f.read()
            except:
                pass
        return f"You are {role_name}."


# 兼容性别名
Sindris = SindrisExecutor


async def plan_sindris(task: str) -> Dict[str, Any]:
    """便捷函数：规划sindris"""
    executor = SindrisExecutor()
    return await executor.plan(task)
