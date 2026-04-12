"""
slice_generator.py - 精确Slice生成器

将任务分解为精确到"文件::函数"的子slice，
每个slice包含明确的验证命令。

核心逻辑：
1. 分析任务描述，提取关键实体（模块/类/函数）
2. 根据实体类型生成对应的测试命令
3. 返回结构化的slice列表

使用示例：
    from slice_generator import SliceGenerator
    
    gen = SliceGenerator()
    slices = gen.generate_slices("为用户提供Web服务器")
    # [
    #   {
    #     "file": "server.py",
    #     "function": "create_app",
    #     "test_cmd": "pytest tests/test_server.py::test_create_app -v",
    #     "description": "创建Web应用"
    #   },
    #   ...
    ]
"""

import re
import os
import json
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Slice:
    """一个精确的代码slice"""
    file: str           # 目标文件
    function: str       # 目标函数/类方法
    test_cmd: str       # 验证命令
    description: str    # slice描述
    priority: str = "medium"  # low/medium/high


class SliceGenerator:
    """
    精确Slice生成器
    
    能力：
    1. 从自然语言任务描述中提取代码实体
    2. 生成对应的测试slice
    3. 提供精确的验证命令
    """
    
    # 任务类型到测试文件的映射
    TASK_TYPE_MAPPING = {
        # sindris自进化相关
        "sindris": {
            "test_dir": "scripts",
            "src_files": [
                "scripts/sindris_executor.py",
                "scripts/circuit_breaker.py",
                "scripts/consensus_officer.py",
                "scripts/worktree_officer.py",
                "scripts/omx_integrator.py",
                "scripts/match_roles.py",
                "scripts/ralph_loop.py",
                "scripts/safety_policy.py",
                "scripts/review_logger.py",
                "scripts/telemetry_collector.py",
                "scripts/memory_manager.py",
                "scripts/task_queue.py",
                "scripts/sindris_hud.py",
                "scripts/sindris_tmux_manager.py",
            ],
            "test_pattern": "pytest {file} -v",
        },
        # 测试相关
        "test": {
            "test_dir": "tests",
            "src_files": ["*.py"],
            "test_pattern": "pytest {file} -v",
        },
        # Web服务器
        "server": {
            "test_dir": "tests",
            "src_files": ["server.py", "app.py", "main.py"],
            "test_pattern": "pytest tests/test_server.py -v",
        },
        # API服务
        "api": {
            "test_dir": "tests",
            "src_files": ["api.py", "routes.py", "endpoints.py"],
            "test_pattern": "pytest tests/test_api.py -v",
        },
        # 数据库
        "database": {
            "test_dir": "tests",
            "src_files": ["db.py", "database.py", "models.py"],
            "test_pattern": "pytest tests/test_db.py -v",
        },
        # 缓存
        "cache": {
            "test_dir": "tests",
            "src_files": ["cache.py", "redis_client.py"],
            "test_pattern": "pytest tests/test_cache.py -v",
        },
        # 认证
        "auth": {
            "test_dir": "tests",
            "src_files": ["auth.py", "authenticator.py", "jwt_handler.py"],
            "test_pattern": "pytest tests/test_auth.py -v",
        },
        # 通用Python
        "python": {
            "test_dir": "tests",
            "src_files": ["*.py"],
            "test_pattern": "pytest tests/ -v",
        },
    }
    
    # 分析类任务关键词（高于sindris等具体任务类型）
    ANALYSIS_KEYWORDS = {
        "分析": "analysis",
        "analyze": "analysis",
        "评估": "analysis",
        "evaluate": "analysis",
        "研究": "analysis",
        "research": "analysis",
        "评审": "analysis",
        "review": "analysis",
        "审视": "analysis",
        "检查": "analysis",
        "审查": "analysis",
        "架构": "architecture",
        "architecture": "architecture",
        "设计": "design",
        "规划": "planning",
        "plan": "planning",
    }

    # 分析类任务的高层维度（分析类任务不生成代码级slice）
    ANALYSIS_DIMENSIONS = [
        "架构设计与模块边界",
        "数据流与状态管理",
        "接口定义与协议",
        "性能与扩展性",
        "安全性与权限",
        "可测试性与验证",
        "文档与可维护性",
        "与现有系统的集成",
    ]

    # 关键词到任务类型的映射
    KEYWORD_TO_TYPE = {
        # 分析类任务（最高优先级，在后面根据matched_types排序）
        # sindris相关
        "sindris": "sindris",
        "进化": "sindris",
        "自进化": "sindris",
        "coverage": "sindris",
        "测试覆盖率": "sindris",
        # sindris模块相关
        "circuit": "sindris",
        "breaker": "sindris",
        "circuit_breaker": "sindris",
        "circuit breaker": "sindris",
        "熔断": "sindris",
        "consensus": "sindris",
        "投票": "sindris",
        "worktree": "sindris",
        "omx": "sindris",
        "match_roles": "sindris",
        "ralph": "sindris",
        "telemetry": "sindris",
        "safety": "sindris",
        "review": "sindris",
        # Web相关
        "server": "server",
        "服务器": "server",
        "web": "server",
        "http": "server",
        "rest": "api",
        "api": "api",
        # 数据库
        "database": "database",
        "db": "database",
        "数据库": "database",
        "sql": "database",
        # 缓存
        "cache": "cache",
        "缓存": "cache",
        "redis": "cache",
        # 认证
        "auth": "auth",
        "认证": "auth",
        "login": "auth",
        "jwt": "auth",
        "oauth": "auth",
        # 测试
        "test": "test",
        "测试": "test",
        "pytest": "test",
        "验证": "test",
        # Python
        "python": "python",
        "py": "python",
    }
    
    def __init__(self, workspace_root: Optional[str] = None):
        # 如果没有指定workspace_root，默认指向sindris目录
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/.. = sindris/
        self.workspace_root = workspace_root
        self._cache: Dict[str, List[Slice]] = {}
    
    def generate_slices(self, task: str) -> List[Slice]:
        """
        从任务描述生成精确slice列表
        
        Args:
            task: 任务描述，如"创建用户认证Web服务"
            
        Returns:
            Slice列表，每个slice包含file、function、test_cmd
        """
        # 简单缓存
        cache_key = task[:100]
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        slices = []
        
        # 1. 识别任务类型
        task_type = self._identify_task_type(task)
        
        # 1.5. 分析类任务返回高层维度slice，不返回代码级slice
        if task_type in ("analysis", "architecture", "design", "planning"):
            for dim in self.ANALYSIS_DIMENSIONS:
                slices.append(Slice(
                    file=".",
                    function=dim,
                    test_cmd=f"echo '分析维度: {dim}'",
                    description=f"【{task_type}】{dim}",
                    priority="high"
                ))
            self._cache[cache_key] = slices
            return slices
        
        # 2. 根据任务类型获取配置
        config = self.TASK_TYPE_MAPPING.get(task_type, self.TASK_TYPE_MAPPING["python"])
        
        # 3. 获取源文件和测试命令
        src_files = self._resolve_files(config["src_files"])
        
        for src_file in src_files:
            # 提取函数名
            functions = self._extract_functions(src_file)
            
            for func in functions:
                # 确定测试文件
                test_file = self._get_test_file(src_file)
                
                # 生成测试命令
                if func == "*":
                    # 如果没有指定具体函数，运行整个测试文件
                    test_cmd = f"pytest {test_file} -v"
                else:
                    # 转换函数名为测试名：_calculate_delay -> test_circuit_state_enum（需要查找）
                    # 但实际上测试函数名和源文件函数名不是一一对应的
                    # 所以应该只运行整个测试文件
                    test_cmd = f"pytest {test_file} -v"
                
                slices.append(Slice(
                    file=src_file,
                    function=func,
                    test_cmd=test_cmd,
                    description=f"{src_file}::{func}",
                    priority="high"
                ))
        
        # 如果没有找到任何slice，生成一个默认的
        if not slices:
            slices.append(Slice(
                file=".",
                function="main",
                test_cmd="pytest -v",
                description="默认测试",
                priority="medium"
            ))
        
        self._cache[cache_key] = slices
        return slices
    
    def generate_slices_for_coverage_gaps(self, coverage_gaps: List[Dict]) -> List[Slice]:
        """
        从覆盖率缺口生成精确slice
        
        Args:
            coverage_gaps: 如 [{"file": "scripts/circuit_breaker.py", "missing_lines": [306, 362]}]
            
        Returns:
            Slice列表
        """
        slices = []
        
        for gap in coverage_gaps:
            file = gap.get("file", "")
            missing_lines = gap.get("missing_lines", [])
            
            if not file:
                continue
            
            # 提取函数名
            functions = self._extract_functions_from_lines(file, missing_lines)
            
            for func in functions:
                test_file = self._get_test_file(file)
                test_name = f"test_{func}" if not func.startswith("test_") else func
                
                slices.append(Slice(
                    file=file,
                    function=func,
                    test_cmd=f"pytest {test_file}::{test_name} -v",
                    description=f"未覆盖: {file}::{func} (lines {missing_lines})",
                    priority="high"
                ))
        
        return slices
    
    def _identify_task_type(self, task: str) -> str:
        """从任务描述识别任务类型"""
        task_lower = task.lower()
        
        # 首先检查是否是分析类任务（最高优先级）
        for keyword, task_type in self.ANALYSIS_KEYWORDS.items():
            if keyword in task_lower:
                return task_type  # "analysis", "architecture", "design", "planning"
        
        # 然后检查其他关键词
        matched_types = []
        for keyword, task_type in self.KEYWORD_TO_TYPE.items():
            if keyword in task_lower:
                matched_types.append(task_type)
        
        # 返回最常见的类型
        if matched_types:
            return max(set(matched_types), key=matched_types.count)
        
        return "python"  # 默认
    
    def _resolve_files(self, file_patterns: List[str]) -> List[str]:
        """解析文件模式，返回实际存在的文件"""
        resolved = []
        seen = set()
        
        for pattern in file_patterns:
            if pattern == "*.py":
                # 查找所有Python文件
                root = Path(self.workspace_root)
                for py_file in root.rglob("*.py"):
                    # 排除__pycache__和测试文件
                    if "__pycache__" not in str(py_file) and "test_" not in py_file.name:
                        rel_path = str(py_file.relative_to(root))
                        if rel_path not in seen:
                            seen.add(rel_path)
                            resolved.append(rel_path)
            else:
                if pattern not in seen:
                    seen.add(pattern)
                    resolved.append(pattern)
        
        return resolved[:10]  # 最多10个文件
    
    def _extract_functions(self, file: str) -> List[str]:
        """从源文件提取函数名"""
        if not os.path.exists(file):
            return ["*"]
        
        functions = []
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 提取函数定义
            func_pattern = r'def\s+([a-z_][a-z0-9_]{2,30})\s*\('
            functions = re.findall(func_pattern, content)
        except Exception:
            pass
        
        return functions if functions else ["*"]
    
    def _extract_functions_from_lines(self, file: str, lines: List[int]) -> List[str]:
        """从指定行号范围提取函数名"""
        if not os.path.exists(file) or not lines:
            return ["*"]
        
        try:
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines_content = content.split('\n')
            
            # 找到missing_lines附近的函数定义
            missing_set = set(lines)
            functions = []
            
            # 提取所有函数
            func_pattern = r'def\s+([a-z_][a-z0-9_]{2,30})\s*\('
            all_funcs = {}
            for i, line in enumerate(lines_content):
                match = re.search(func_pattern, line)
                if match:
                    all_funcs[i + 1] = match.group(1)  # 行号从1开始
            
            # 找与missing_lines相关的函数
            for line_no, func_name in all_funcs.items():
                # 检查函数定义行是否在missing_lines附近
                if line_no in missing_set:
                    functions.append(func_name)
            
            # 如果没找到，返回文件中的前几个函数
            if not functions:
                functions = list(all_funcs.values())[:3]
            
            return functions if functions else ["*"]
        except Exception:
            return ["*"]
    
    def _get_test_file(self, src_file: str) -> str:
        """获取源文件对应的测试文件"""
        # 转换规则：
        # scripts/circuit_breaker.py -> tests/test_circuit_breaker.py
        # scripts/sindris_executor.py -> tests/test_sindris.py（特殊处理）
        
        if src_file.startswith("scripts/"):
            base = src_file.replace("scripts/", "")
            name = os.path.splitext(base)[0]
            
            # 特殊处理：移除_executor后缀来匹配测试文件
            # sindris_executor.py -> test_sindris.py
            name = name.replace("_executor", "")
            
            return f"tests/test_{name}.py"
        elif src_file.startswith("src/"):
            base = src_file.replace("src/", "")
            return f"tests/test_{base}"
        else:
            base = os.path.basename(src_file)
            name = os.path.splitext(base)[0]
            return f"tests/test_{name}.py"


class IncrementalSliceGenerator(SliceGenerator):
    """
    增量Slice生成器
    
    在精确slice基础上，添加增量检查：
    1. 只生成需要测试的slice
    2. 跳过已有充分测试的slice
    """
    
    def __init__(self, workspace_root: Optional[str] = None):
        super().__init__(workspace_root)
        self.coverage_baseline: Dict[str, float] = {}
    
    def set_baseline(self, coverage_data: Dict[str, float]):
        """设置覆盖率基准"""
        self.coverage_baseline = coverage_data
    
    def generate_slices(self, task: str, coverage_data: Optional[Dict[str, float]] = None) -> List[Slice]:
        """
        生成增量slice（跳过已有充分测试的）
        
        Args:
            task: 任务描述
            coverage_data: 当前覆盖率数据，如 {"file": 80.5}
        """
        all_slices = super().generate_slices(task)
        
        if coverage_data is None:
            return all_slices
        
        # 过滤掉覆盖率已经很高的slice
        filtered = []
        for slice in all_slices:
            coverage = coverage_data.get(slice.file, 0)
            if coverage < 80:  # 低于80%覆盖率才需要测试
                filtered.append(slice)
        
        return filtered if filtered else all_slices
