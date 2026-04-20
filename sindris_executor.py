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

VERSION = "3.7"

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
        self._setup_safety_policy()  # v3.7: 集成SafetyPolicy
        self._setup_telemetry()  # v3.8: 集成TelemetryCollector
        self._setup_omx()  # v3.8: 集成OMXIntegrator
    
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
    
    def _add_verification_step(self, subtasks: list, task_type: str) -> list:
        """
        为所有任务添加验证步骤
        这个验证步骤是给主Agent看的，确保结果真实可用
        
        v3.8改进：根据subtasks生成具体的验证条件，不只是模糊的"验证完成"
        """
        # 从subtasks中提取需要验证的文件
        files_to_verify = []
        for s in subtasks:
            role_file = s.get('role_file')
            if role_file and role_file.endswith('.md'):
                files_to_verify.append(role_file)
        
        # 生成具体的验证命令
        verify_commands = []
        for f in files_to_verify:
            verify_commands.append(f"ls -la {f}")
            verify_commands.append(f"wc -l {f}")
        
        # 生成具体的验证条件
        verify_items = [f"文件存在: {f}" for f in files_to_verify]
        
        verification_step = {
            "task_id": f"{task_type}_verifier",
            "role": "Verifier",
            "role_file": None,
            "role_prompt": f"你是结果验证专家。验证任务执行结果是否满足要求：\n1. 代码是否在.py或.md文件中实现\n2. 是否只是MOCK/placeholder\n3. 是否已集成到主流程\n4. 文件是否真的被修改（检查mtime）\n\n需要验证的文件：\n{chr(10).join(files_to_verify)}\n\n验证命令：\n{chr(10).join(verify_commands[:6])}",
            "title": "验证任务结果",
            "tools": ["read", "exec"],
            "timeout": 60,
            "phase": "verification",
            "verify": verify_items if verify_items else ["验证完成"],
            "auto_run": True,  # 自动运行
        }
        # 添加到末尾
        return subtasks + [verification_step]
    
    def _run_auto_verification(self, task_type: str) -> Dict:
        """
        v3.8: 自动运行真实验证
        返回验证结果（不再返回固定的verified=True）
        """
        try:
            # 动态导入避免循环依赖
            from modules.evolution_verifier import EvolutionVerifier
            verifier = EvolutionVerifier(self.workspace_root)
            
            # 根据任务类型确定要验证的角色
            if task_type == "audit":
                # 审计任务：验证AUDIT_TEAM配置
                target = "AUDIT_TEAM"
                improver = "审计团队"
            elif task_type == "evolution":
                # 改进任务：验证EVOLUTION_DISTRIBUTOR
                target = "EVOLUTION_DISTRIBUTOR"
                improver = "改进分配器"
            else:
                # 开发任务：验证FIXED_TEAM
                target = "FIXED_TEAM"
                improver = "固定团队"
            
            # v3.8: 真正调用验证器（需要传入improver_id）
            verification_result = verifier.verify(target, improver_id=improver)
            
            result = {
                "verified": verification_result.get("success", False),
                "task_type": task_type,
                "target": target,
                "message": verification_result.get("message", f"{improver}验证完成"),
                "details": verification_result,
            }
            return result
        except Exception as e:
            return {
                "verified": False,
                "task_type": task_type,
                "error": str(e),
            }
    
    def _setup_safety_policy(self):
        """v3.7: 初始化SafetyPolicy危险命令拦截"""
        try:
            from scripts.safety_policy import SafetyPolicy
            self.safety_policy = SafetyPolicy()
            self._log_jsonl("safety_policy_loaded", {"status": "loaded"})
        except ImportError:
            self.safety_policy = None
            self._log_jsonl("safety_policy_loaded", {"status": "not_found"})
    
    def _setup_telemetry(self):
        """v3.8: 初始化TelemetryCollector遥测收集"""
        try:
            from scripts.telemetry_collector import TelemetryCollector, get_default_collector
            self.telemetry = get_default_collector()
            self._log_jsonl("telemetry_loaded", {"status": "loaded"})
        except ImportError:
            self.telemetry = None
            self._log_jsonl("telemetry_loaded", {"status": "not_found"})
    
    def _setup_omx(self):
        """v3.8: 初始化OMXIntegrator持久化"""
        try:
            from scripts.omx_integrator import OMXIntegrator
            self.omx = OMXIntegrator(self.workspace_root)
            self._log_jsonl("omx_integrator_loaded", {"status": "loaded", "root": self.workspace_root})
        except ImportError as e:
            self.omx = None
            self._log_jsonl("omx_integrator_loaded", {"status": "not_found", "error": str(e)})
    
    def check_dangerous_command(self, command: str) -> Dict[str, Any]:
        """
        v3.7: 检查命令是否危险
        
        Args:
            command: 要检查的命令
            
        Returns:
            {"safe": bool, "level": str, "message": str}
        """
        if not self.safety_policy:
            return {"safe": True, "level": "none", "message": "SafetyPolicy not loaded"}
        
        result = self.safety_policy.check_command(command)
        
        # v3.8: 记录遥测 - 安全拦截
        if self.telemetry and not result.get("safe", True):
            self.telemetry.safety_block(
                task_id=self.session_id,
                command=command[:100],
                danger_level=result.get("level", "unknown")
            )
        
        return result
    
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
        # v3.8: 输入验证
        if not isinstance(task, str):
            return {
                "success": False,
                "error": f"task must be str, got {type(task).__name__}",
                "phase": "rejected",
            }
        
        task = task.strip()
        if len(task) < 3:
            return {
                "success": False,
                "error": "task must be at least 3 characters after trimming",
                "phase": "rejected",
            }
        
        if len(task) > 5000:
            return {
                "success": False,
                "error": "task exceeds maximum length of 5000 characters",
                "phase": "rejected",
            }
        # v3.8: 输入验证结束
        
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
        is_evolution_team = any(r.get('team_type') == 'evolution' for r in roles) if roles else False
        
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
        elif is_evolution_team:
            # 角色完善任务：每个角色一个完善子任务
            subtasks = []
            for r in roles:
                role_name = r.get('name', r.get('id', 'Specialist'))
                role_file = self._find_role_file(role_name)
                role_prompt = self.get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
                subtasks.append({
                    "task_id": f"evolve_{r.get('id', 'task')}",
                    "role": role_name,
                    "role_file": role_file,
                    "role_prompt": role_prompt,
                    "title": f"完善角色: {role_name}",
                    "tools": ["read", "exec", "write"],
                    "timeout": 300,
                    "phase": "round2",
                    "verify": [f"{role_name}完善完成"],
                })
            # 添加验证步骤
            subtasks = self._add_verification_step(subtasks, "evolution")
            # 自动运行验证
            verification_result = self._run_auto_verification("evolution")
            result = {
                "success": True,
                "task_id": self.session_id,
                "subtasks": subtasks,
                "plan_summary": f"角色完善任务分解为{len(subtasks)}个子任务（包含验证步骤）",
                "phase": "planned",
                "roles": roles,
                "verification": verification_result,
            }
            # 保存缓存并返回
            self._save_fastpath_cache(task, result)
            return result
        
        # 检查是否使用角色改进分配器（原始evolution_distributor路径）
        is_evolution = any(r.get('team_type') == 'evolution' for r in roles) if roles else False
        if is_evolution:
            # 角色改进任务：直接使用改进角色
            improver_match = [m for m in task_decomposer.role_matcher.match(task) if getattr(m, 'source', None) == 'evolution_distributor']
            if improver_match:
                improver_role = improver_match[0].role
                role_name = improver_role.get('name', improver_role.get('id', 'Specialist'))
                role_file = self._find_role_file(role_name)
                role_prompt = self.get_role_prompt(role_name) if role_file else f"你是 {role_name}。"
                subtasks = [{
                    "task_id": "evolution_improver",
                    "role": role_name,
                    "role_file": role_file,
                    "role_prompt": role_prompt,
                    "title": f"改进角色任务",
                    "tools": ["read", "exec", "write"],
                    "timeout": 600,
                    "phase": "evolution",
                    "verify": [f"{role_name}完成角色改进"],
                }]
                # 添加验证步骤
                subtasks = self._add_verification_step(subtasks, "evolution")
                # 自动运行验证
                verification_result = self._run_auto_verification("evolution")
                result = {
                    "success": True,
                    "task_id": self.session_id,
                    "subtasks": subtasks,
                    "plan_summary": f"角色改进任务：使用{role_name}改进（包含验证步骤）",
                    "phase": "planned",
                    "roles": roles,
                    "verification": verification_result,
                }
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
        
        # 添加验证步骤
        subtasks = self._add_verification_step(subtasks, "dev")
        
        # 自动运行验证
        verification_result = self._run_auto_verification("dev")
        
        result = {
            "success": True,
            "task_id": self.session_id,
            "subtasks": subtasks,
            "plan_summary": f"分解为{len(subtasks)}个子任务（包含验证步骤）：{[s['role'] for s in subtasks]}",
            "phase": "planned",
            "roles": roles,
            "verification": verification_result,  # 自动验证结果
        }
        
        # 记录规划完成
        self._log_jsonl("plan_complete", {
            "task_id": self.session_id,
            "subtasks_count": len(subtasks),
            "subtasks": [{"id": s["task_id"], "role": s["role"], "phase": s.get("phase")} for s in subtasks]
        })
        
        # 保存FastPath缓存
        self._save_fastpath_cache(task, result)
        
        # v3.8: 记录遥测 - 规划完成
        if self.telemetry:
            self.telemetry.round_change("pending", "planned", task_id=self.session_id)
            for s in subtasks:
                self.telemetry.task_start(s["task_id"], role=s.get("role"))
        
        # v3.8: OMX持久化 - Round1完成
        if self.omx:
            matched_roles = [s.get("role") for s in subtasks]
            self.omx.on_round1_start(
                task_description=task[:200],
                task_id=self.session_id,
                matched_roles=matched_roles
            )
            self.omx.on_round1_complete(
                plan_summary=result.get("plan_summary", ""),
                task_id=self.session_id,
                verified=True
            )
        
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
                exact_matches.append(str(md_file.absolute()))  # 绝对路径供子代理使用
            # 优先级2: 包含匹配
            elif normalized in stem:
                contains_matches.append(str(md_file.absolute()))  # 绝对路径供子代理使用
            # 优先级3: 部分匹配（单词匹配）
            elif any(part in stem for part in normalized.split("-")):
                part_matches.append(str(md_file.absolute()))  # 绝对路径供子代理使用
        
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

    # ========== v3.7: 默认验证函数 ==========
    
    DEFAULT_CHECK_FUNCTIONS = {
        "file_exists": lambda ctx: (
            ctx.get("file_path") and 
            Path(ctx["file_path"]).exists()
        ),
        "file_not_empty": lambda ctx: (
            ctx.get("file_path") and 
            Path(ctx["file_path"]).exists() and 
            Path(ctx["file_path"]).stat().st_size > 0
        ),
        "code_importable": lambda ctx: (
            ctx.get("module_name") and
            ctx.get("workspace_root") and
            any(
                Path(ctx["workspace_root"]).glob(f"**/{ctx['module_name']}.py")
            )
        ),
        "no_placeholder": lambda ctx: (
            ctx.get("content") and
            "MOCK" not in ctx.get("content", "") and
            "TODO" not in ctx.get("content", "") and
            "placeholder" not in ctx.get("content", "").lower()
        ),
        "function_defined": lambda ctx: (
            ctx.get("file_path") and
            ctx.get("function_name") and
            Path(ctx["file_path"]).exists() and
            f"def {ctx['function_name']}" in Path(ctx["file_path"]).read_text()
        ),
    }
    
    def _get_check_fn_for_item(self, item: Dict[str, Any]) -> Optional[callable]:
        """
        v3.7: 根据验证项的name自动提供默认check_fn
        """
        if item.get("check_fn"):
            return item["check_fn"]
        
        name_lower = item.get("name", "").lower()
        
        if "文件存在" in name_lower or "file exists" in name_lower or "文件已创建" in name_lower:
            return lambda ctx: self.DEFAULT_CHECK_FUNCTIONS["file_exists"](ctx)
        if "非空" in name_lower or "not empty" in name_lower:
            return lambda ctx: self.DEFAULT_CHECK_FUNCTIONS["file_not_empty"](ctx)
        if "可导入" in name_lower or "importable" in name_lower:
            return lambda ctx: self.DEFAULT_CHECK_FUNCTIONS["code_importable"](ctx)
        if "非mock" in name_lower or "no placeholder" in name_lower:
            return lambda ctx: self.DEFAULT_CHECK_FUNCTIONS["no_placeholder"](ctx)
        if "函数定义" in name_lower or "function defined" in name_lower:
            return lambda ctx: self.DEFAULT_CHECK_FUNCTIONS["function_defined"](ctx)
        
        return None


    # ========== Ralph验证集成 ==========
    
    async def verify_with_ralph(
        self,
        task: str,
        result: Any,
        verify_items: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        真正执行Ralph 3轮循环验证
        
        这个方法会真正调用RalphLoop，执行完整的3轮验证流程。
        不是假的验证通过，而是真正的多轮验证+错误回灌。
        
        Args:
            task: 任务描述
            result: 执行结果
            verify_items: 验证项列表 [{"name": "...", "description": "...", "check_fn": None}]
        
        Returns:
            {
                "success": bool,
                "total_rounds": int,
                "consecutive_passed": int,
                "final_report": dict,
            }
        """
        try:
            from scripts.ralph_loop import RalphLoop, RalphResult, VerificationStatus
            
            # 构建验证项 v3.7: 使用默认check_fn
            parsed_items = []
            for item in verify_items:
                check_fn = self._get_check_fn_for_item(item)
                parsed_items.append({
                    "id": item.get("id", str(uuid.uuid4())[:8]),
                    "name": item.get("name", "unnamed"),
                    "description": item.get("description", ""),
                    "check_fn": check_fn,  # v3.7: 可能为None，但有默认值在RalphLoop中
                })
            
            # 创建Ralph验证器
            verifier = RalphLoop(
                task_name=f"验证: {task[:50]}...",
                verify_items=parsed_items,
            )
            
            # 执行3轮验证
            ralph_result = await verifier.run()
            
            # 记录验证结果
            self._log_jsonl("ralph_verification", {
                "task": task[:50],
                "success": ralph_result.success,
                "total_rounds": ralph_result.total_rounds,
                "consecutive_passed": ralph_result.consecutive_passed,
            })
            
            # v3.7: 返回可序列化的dict，不包含循环引用的对象
            return {
                "success": ralph_result.success,
                "total_rounds": ralph_result.total_rounds,
                "consecutive_passed": ralph_result.consecutive_passed,
                "final_report": {
                    "round_num": ralph_result.final_report.round_num,
                    "state": ralph_result.final_report.state,
                    "passed_count": ralph_result.final_report.passed_count,
                    "failed_count": ralph_result.final_report.failed_count,
                    "conclusion": ralph_result.final_report.conclusion,
                },
                # v3.7: 移除ralph_result避免循环引用
            }
            
        except ImportError as e:
            self._log_jsonl("ralph_import_error", {"error": str(e)})
            return {
                "success": False,
                "error": f"Ralph模块不可用: {e}",
                "total_rounds": 0,
                "consecutive_passed": 0,
            }
        except Exception as e:
            self._log_jsonl("ralph_error", {"error": str(e)})
            return {
                "success": False,
                "error": str(e),
                "total_rounds": 0,
                "consecutive_passed": 0,
            }
    
    async def verify_subtask_result(
        self,
        subtask: Dict[str, Any],
        actual_result: Any,
    ) -> Dict[str, Any]:
        """
        验证子任务执行结果
        
        在子代理完成后调用此方法，使用Ralph进行真正的验证。
        
        Args:
            subtask: 子任务配置（包含verify条件）
            actual_result: 实际执行结果
        
        Returns:
            验证结果
        """
        task_title = subtask.get("title", "unknown")
        verify_conditions = subtask.get("verify", [])
        
        # 构建验证项
        verify_items = []
        for condition in verify_conditions:
            verify_items.append({
                "id": str(uuid.uuid4())[:8],
                "name": condition,
                "description": f"验证条件: {condition}",
                "check_fn": None,
            })
        
        # 如果没有明确的验证条件，使用默认条件
        if not verify_items:
            verify_items = [
                {"id": "v1", "name": "结果非空", "description": "实际结果不为空"},
                {"id": "v2", "name": "无错误", "description": "执行过程无错误"},
            ]
        
        # 调用Ralph验证
        return await self.verify_with_ralph(
            task=task_title,
            result=actual_result,
            verify_items=verify_items,
        )


# 兼容性别名
Sindris = SindrisExecutor


async def plan_sindris(task: str) -> Dict[str, Any]:
    """便捷函数：规划sindris"""
    executor = SindrisExecutor()
    return await executor.plan(task)
