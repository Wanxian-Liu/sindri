"""
sindris_introspector.py - sindris自省模块

功能：
1. 读取sindris的模块结构
2. 检测模块可导入性
3. 收集状态信息
4. 为sindris提供自省上下文

使用示例：
    introspector = SindrisIntrospector('/path/to/sindris')
    report = introspector.generate_self_report()
    # 生成的报告可以传给sindris让它分析
"""

import os
import sys
import json
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ModuleInfo:
    """模块信息"""
    name: str
    path: str
    size_bytes: int
    can_import: bool
    import_error: Optional[str] = None


@dataclass
class GitInfo:
    """Git状态"""
    branch: str = "unknown"
    commit: str = "unknown"
    commits_ahead: int = 0
    modified_files: List[str] = None
    
    def __post_init__(self):
        if self.modified_files is None:
            self.modified_files = []


@dataclass
class SelfCheckReport:
    """sindris自检报告"""
    timestamp: str
    root_path: str
    module_count: int
    importable_count: int
    failed_count: int
    git_info: Dict
    role_count: int
    file_structure: Dict
    issues: List[str]
    recommendations: List[str]


class SindrisIntrospector:
    """
    sindris自省器
    
    能够：
    1. 扫描sindris的模块结构
    2. 检测每个模块的可导入性
    3. 收集Git状态
    4. 统计角色库
    5. 生成结构化报告
    """
    
    def __init__(self, sindris_root: Optional[str] = None):
        if sindris_root is None:
            # 默认指向sindris技能目录
            sindris_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # sindris/scripts/../ = sindris/
        self.root = Path(sindris_root).resolve()
        self.scripts_dir = self.root / "scripts"
        self.roles_dir = self.root / "roles"
        
    def scan_modules(self) -> List[ModuleInfo]:
        """扫描所有Python模块"""
        modules = []
        
        if not self.scripts_dir.exists():
            return modules
            
        for py_file in sorted(self.scripts_dir.glob("*.py")):
            if py_file.name.startswith("__"):
                continue
                
            mod_info = self._check_module(py_file)
            modules.append(mod_info)
            
        return modules
    
    def _check_module(self, py_file: Path) -> ModuleInfo:
        """检查单个模块"""
        name = py_file.stem
        
        try:
            # 确保路径在sys.path中
            scripts_path = str(self.scripts_dir)
            if scripts_path not in sys.path:
                sys.path.insert(0, scripts_path)
            
            # 使用importlib直接导入
            import importlib
            module = importlib.import_module(name)
            
            return ModuleInfo(
                name=name,
                path=str(py_file),
                size_bytes=py_file.stat().st_size,
                can_import=True,
                import_error=None
            )
        except Exception as e:
            return ModuleInfo(
                name=name,
                path=str(py_file),
                size_bytes=py_file.stat().st_size,
                can_import=False,
                import_error=str(e)[:100]
            )
    
    def get_git_info(self) -> GitInfo:
        """获取Git状态"""
        import subprocess
        
        git_info = GitInfo()
        
        try:
            # 当前分支
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info.branch = result.stdout.strip()
            
            # 最新commit
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                git_info.commit = result.stdout.strip()
            
            # 修改的文件
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                git_info.modified_files = [l.strip() for l in lines if l.strip()]
                
        except Exception as e:
            git_info.modified_files = [f"Error: {e}"]
            
        return git_info
    
    def count_roles(self) -> int:
        """统计角色数量"""
        registry_path = self.roles_dir / "roles_registry.json"
        if registry_path.exists():
            try:
                with open(registry_path) as f:
                    registry = json.load(f)
                return len(registry.get('roles', []))
            except Exception:
                pass
        return 0
    
    def get_file_structure(self) -> Dict:
        """获取文件结构概览"""
        structure = {
            "scripts": {},
            "roles": {},
            "tests": {}
        }
        
        # Scripts
        if self.scripts_dir.exists():
            for f in sorted(self.scripts_dir.glob("*.py")):
                if not f.name.startswith("__"):
                    structure["scripts"][f.stem] = f.stat().st_size
        
        # Tests
        tests_dir = self.root / "tests"
        if tests_dir.exists():
            for f in sorted(tests_dir.glob("test_*.py")):
                structure["tests"][f.stem] = f.stat().st_size
        
        # Roles目录
        if self.roles_dir.exists():
            structure["roles"]["count"] = len(list(self.roles_dir.iterdir()))
        
        return structure
    
    def generate_self_report(self) -> SelfCheckReport:
        """生成sindris自检报告"""
        modules = self.scan_modules()
        git_info = self.get_git_info()
        role_count = self.count_roles()
        file_structure = self.get_file_structure()
        
        # 统计
        importable = [m for m in modules if m.can_import]
        failed = [m for m in modules if not m.can_import]
        
        # 问题识别
        issues = []
        if failed:
            issues.append(f"{len(failed)}个模块无法导入")
        if git_info.modified_files:
            issues.append(f"{len(git_info.modified_files)}个文件有未提交修改")
        
        # 建议
        recommendations = []
        if failed:
            failed_names = [m.name for m in failed[:5]]
            recommendations.append(f"修复导入失败的模块: {failed_names}")
        if role_count < 100:
            recommendations.append(f"角色库只有{role_count}个角色，考虑扩展")
        if not git_info.modified_files and git_info.commit == "unknown":
            recommendations.append("Git状态未知，检查仓库初始化")
        
        return SelfCheckReport(
            timestamp=datetime.now().isoformat(),
            root_path=str(self.root),
            module_count=len(modules),
            importable_count=len(importable),
            failed_count=len(failed),
            git_info=asdict(git_info),
            role_count=role_count,
            file_structure=file_structure,
            issues=issues,
            recommendations=recommendations
        )
    
    def format_report_for_sindris(self, report: SelfCheckReport) -> str:
        """将报告格式化为sindris可读的格式"""
        lines = [
            "# sindris自我检查报告",
            "",
            f"## 基本信息",
            f"- 时间: {report.timestamp}",
            f"- 路径: {report.root_path}",
            f"- 总模块数: {report.module_count}",
            f"- 可导入模块: {report.importable_count}",
            f"- 导入失败: {report.failed_count}",
            f"- 角色库: {report.role_count}个角色",
            "",
            f"## Git状态",
            f"- 分支: {report.git_info.get('branch', 'unknown')}",
            f"- Commit: {report.git_info.get('commit', 'unknown')}",
            f"- 未提交文件: {len(report.git_info.get('modified_files', []))}",
            "",
            "## 文件结构",
        ]
        
        # Scripts
        fs = report.file_structure
        if fs.get("scripts"):
            lines.append("### Scripts")
            for name, size in fs["scripts"].items():
                lines.append(f"- {name}.py: {size} bytes")
        
        # 失败模块
        if report.failed_count > 0:
            lines.append("")
            lines.append("## 导入失败的模块")
            modules = self.scan_modules()
            for m in modules:
                if not m.can_import:
                    lines.append(f"- {m.name}: {m.import_error}")
        
        # 问题和建议
        if report.issues:
            lines.extend(["", "## 发现的问题"])
            for issue in report.issues:
                lines.append(f"- {issue}")
        
        if report.recommendations:
            lines.extend(["", "## 改进建议"])
            for rec in report.recommendations:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)


# 全局实例
_global_introspector: Optional['SindrisIntrospector'] = None


def get_introspector(sindris_root: Optional[str] = None) -> SindrisIntrospector:
    """获取全局自省器实例"""
    global _global_introspector
    if _global_introspector is None or sindris_root is not None:
        _global_introspector = SindrisIntrospector(sindris_root)
    return _global_introspector


if __name__ == "__main__":
    # 测试自省器
    introspector = SindrisIntrospector()
    report = introspector.generate_self_report()
    
    print("=== sindris自检报告 ===")
    print(f"模块数: {report.module_count}")
    print(f"可导入: {report.importable_count}")
    print(f"导入失败: {report.failed_count}")
    print(f"角色数: {report.role_count}")
    print(f"Git分支: {report.git_info.get('branch')}")
    print(f"Git commit: {report.git_info.get('commit')}")
    print()
    print("问题:", report.issues if report.issues else "无")
    print("建议:", report.recommendations if report.recommendations else "无")
