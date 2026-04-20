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
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

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
        self._setup_jsonl_logger()
        self._setup_fastpath_cache()
        self._setup_subagent_state_machine()
    
    def _setup_jsonl_logger(self):
        """初始化JSONL日志记录器"""
        self.jsonl_dir = Path(SCRIPT_DIR) / ".logs"
        self.jsonl_dir.mkdir(exist_ok=True)
        self.jsonl_file = self.jsonl_dir / f"sindris_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.jsonl_file, encoding='utf-8'),
            ]
        )
        self.logger = logging.getLogger("sindris")
    
    def _setup_fastpath_cache(self):
        """初始化FastPath缓存"""
        self.cache_dir = Path(SCRIPT_DIR) / ".cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_ttl_hours = 24  # 缓存24小时有效
    
    def _get_cache_key(self, task: str) -> str:
        """生成缓存key（基于任务文本的hash）"""
        import hashlib
        return hashlib.md5(task.encode()).hexdigest()[:12]
    
    def _check_fastpath_cache(self, task: str) -> Optional[Dict[str, Any]]:
        """检查FastPath缓存"""
        cache_key = self._get_cache_key(task)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        # 检查是否过期
        import time
        cache_age = time.time() - cache_file.stat().st_mtime
        if cache_age > self.cache_ttl_hours * 3600:
            cache_file.unlink()  # 删除过期缓存
            return None
        
        try:
            with open(cache_file) as f:
                cached = json.load(f)
                self._log_jsonl("fastpath_hit", {"task": task[:50], "cache_key": cache_key})
                return cached
        except:
            return None
    
    def _save_fastpath_cache(self, task: str, result: Dict[str, Any]):
        """保存FastPath缓存"""
        cache_key = self._get_cache_key(task)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        with open(cache_file, "w") as f:
            json.dump(result, f)
        
        self._log_jsonl("fastpath_save", {"cache_key": cache_key})
    
    def _setup_subagent_state_machine(self):
        """初始化子代理状态机"""
        # 状态定义
        self.SubagentState = {
            "PENDING": "pending",
            "RUNNING": "running",
            "COMPLETE": "complete",
            "FAILED": "failed",
            "CANCELLED": "cancelled",
            "TIMEOUT": "timeout",
        }
        # 子代理状态存储
        self._subagent_states: Dict[str, Dict] = {}
    
    def _log_jsonl(self, event_type: str, data: Dict[str, Any]):
        """写入JSONL日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            **data
        }
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
    
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
        
        # 记录规划开始
        self._log_jsonl("plan_start", {"task": task[:100]})
        
        # FastPath缓存检查
        cached_result = self._check_fastpath_cache(task)
        if cached_result:
            cached_result["from_cache"] = True
            self._log_jsonl("plan_cached", {"task": task[:50]})
            return cached_result
        
        # 任务分解
        roles = task_decomposer.get_roles(task, [])
        
        # 检查是否使用审计团队
        is_audit_team = any(r.get('team_type') == 'audit' for r in roles) if roles else False
        
        # 如果是审计团队，直接使用AUDIT_TEAM角色
        if is_audit_team:
            # 审计任务：每个角色一个审计子任务
            subtasks = []
            for r in roles:
                role_name = r.get('name', r.get('id', 'Specialist'))
                role_file = self._find_role_file(role_name)
                role_prompt = self.get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
                subtasks.append({
                    "task_id": f"audit_{r.get('id', 'task')}",
                    "role": role_name,
                    "role_file": role_file,
                    "role_prompt": role_prompt,
                    "title": f"审计角色: {role_name}",
                    "tools": ["read", "exec", "write"],
                    "timeout": 300,
                    "phase": "audit",
                    "verify": [f"{role_name}审计完成"],
                })
            result = {
                "success": True,
                "task_id": self.session_id,
                "subtasks": subtasks,
                "plan_summary": f"审计任务分解为{len(subtasks)}个子任务",
                "phase": "planned",
                "roles": roles,
            }
            # 保存缓存并返回
            self._save_fastpath_cache(task, result)
            return result
        
        # 普通任务：使用Round分解
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
        
        result = {
            "success": True,
            "task_id": self.session_id,
            "subtasks": subtasks,
            "plan_summary": f"分解为{len(subtasks)}个子任务：{[s['role'] for s in subtasks]}",
            "phase": "planned",
            "roles": roles,
        }
        
        # 记录规划完成
        self._log_jsonl("plan_complete", {
            "task_id": self.session_id,
            "subtasks_count": len(subtasks),
            "subtasks": [{"id": s["task_id"], "role": s["role"], "phase": s.get("phase")} for s in subtasks]
        })
        
        # 保存FastPath缓存
        self._save_fastpath_cache(task, result)
        
        return result
    
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
        """查找角色文件路径（优先精确匹配）"""
        roles_dir = Path(SCRIPT_DIR) / "roles"
        if not roles_dir.exists():
            return None
        
        # 标准化角色名：去除sindri-前缀，转换空格/下划线
        normalized = role_name.lower().replace(" ", "-").replace("_", "-")
        # 去掉sindri-前缀如果存在
        if normalized.startswith("sindri-"):
            normalized = normalized[7:]
        
        # 收集所有匹配的文件
        exact_matches = []  # 精确匹配 (normalized == stem)
        contains_matches = []  # 包含匹配 (normalized in stem)
        part_matches = []  # 部分匹配 (any part in stem)
        
        for md_file in roles_dir.rglob("*.md"):
            stem = md_file.stem.lower()
            # 去掉sindri-前缀
            if stem.startswith("sindri-"):
                stem = stem[7:]
            
            # 优先级1: 精确匹配
            if normalized == stem:
                exact_matches.append(str(md_file.relative_to(SCRIPT_DIR)))
            # 优先级2: 包含匹配
            elif normalized in stem:
                contains_matches.append(str(md_file.relative_to(SCRIPT_DIR)))
            # 优先级3: 部分匹配（单词匹配）
            elif any(part in stem for part in normalized.split("-")):
                part_matches.append(str(md_file.relative_to(SCRIPT_DIR)))
        
        # 按优先级返回：精确 > 包含 > 部分
        if exact_matches:
            return exact_matches[0]
        if contains_matches:
            return contains_matches[0]
        if part_matches:
            return part_matches[0]
        
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
    
    def log_execution(self, task_id: str, phase: str, status: str, details: Dict[str, Any] = None):
        """
        记录子代理执行结果
        
        主代理在每次spawn/yield后调用此方法记录执行状态。
        
        用法：
            executor.log_execution(
                task_id="task_abc123",
                phase="round2",
                status="complete",
                details={"role": "Senior Developer", "duration": 120}
            )
        """
        self._log_jsonl("execution", {
            "task_id": task_id,
            "phase": phase,
            "status": status,
            "details": details or {}
        })
    
    # ========== 子代理状态机 ==========
    
    def update_subagent_state(self, task_id: str, session_key: str, state: str):
        """
        更新子代理状态
        
        状态流转：
        PENDING → RUNNING → COMPLETE/FAILED/TIMEOUT/CANCELLED
        """
        if task_id not in self._subagent_states:
            self._subagent_states[task_id] = {
                "session_key": session_key,
                "state": state,
                "state_history": [],
                "created_at": datetime.now().isoformat(),
            }
        else:
            old_state = self._subagent_states[task_id]["state"]
            self._subagent_states[task_id]["state"] = state
            self._subagent_states[task_id]["state_history"].append({
                "from": old_state,
                "to": state,
                "at": datetime.now().isoformat(),
            })
        
        self._log_jsonl("subagent_state", {
            "task_id": task_id,
            "state": state,
            "state_history": self._subagent_states[task_id]["state_history"],
        })
    
    def get_subagent_state(self, task_id: str) -> Optional[str]:
        """获取子代理当前状态"""
        return self._subagent_states.get(task_id, {}).get("state")
    
    def is_subagent_terminal(self, task_id: str) -> bool:
        """判断子代理是否处于终态"""
        state = self.get_subagent_state(task_id)
        return state in [self.SubagentState["COMPLETE"], self.SubagentState["FAILED"], 
                         self.SubagentState["CANCELLED"], self.SubagentState["TIMEOUT"]]
    
    def get_all_subagent_states(self) -> Dict[str, Dict]:
        """获取所有子代理状态"""
        return self._subagent_states


# 兼容性别名
Sindris = SindrisExecutor


async def plan_sindris(task: str) -> Dict[str, Any]:
    """便捷函数：规划sindris"""
    executor = SindrisExecutor()
    return await executor.plan(task)
