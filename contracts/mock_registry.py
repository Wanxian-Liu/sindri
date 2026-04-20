"""
mock_registry.py - Mock实现追踪器

防止假通过：追踪所有Mock实现，确保验证时不会被骗
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MockSeverity(Enum):
    """Mock严重级别"""
    INFO = "info"           # 信息性Mock
    WARNING = "warning"     # 警告性Mock
    BLOCKING = "blocking"   # 阻塞性Mock（必须修复）


@dataclass
class MockRecord:
    """Mock记录"""
    file_path: str
    line_number: int
    mock_content: str
    mock_type: str  # MOCK/TODO/NotImplemented/placeholder/pass
    severity: MockSeverity
    description: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    task_id: Optional[str] = None  # 关联的任务ID


class MockRegistry:
    """
    Mock注册表
    
    功能：
    1. 扫描文件检测Mock实现
    2. 记录Mock位置和类型
    3. 生成Mock报告
    4. 验证任务是否还有Mock残留
    """
    
    # Mock模式
    MOCK_PATTERNS = {
        "MOCK": (r'\bMOCK\b', MockSeverity.WARNING),
        "TODO": (r'\bTODO\b', MockSeverity.INFO),
        "NotImplemented": (r'NotImplemented(Error)?\b', MockSeverity.WARNING),
        "placeholder": (r'\bplaceholder\b', MockSeverity.INFO),
        "pass_only": (r'^\s*pass\s*$', MockSeverity.INFO),  # 只有pass的函数
        "return_none": (r'^\s*return\s+None\s*$', MockSeverity.INFO),  # 只有return None
    }
    
    # 允许的Mock文件/目录（不检查）
    ALLOWED_PATHS = [
        ".cache",
        ".logs",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
    ]
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self._records: List[MockRecord] = []
        self._file_cache: Dict[str, List[MockRecord]] = {}  # 按文件缓存
    
    def scan_file(self, file_path: str, task_id: Optional[str] = None) -> List[MockRecord]:
        """
        扫描单个文件检测Mock
        
        Args:
            file_path: 文件路径
            task_id: 可选的任务ID关联
        
        Returns:
            检测到的Mock记录列表
        """
        records = []
        
        # 检查是否在允许路径中
        if any(allowed in file_path for allowed in self.ALLOWED_PATHS):
            return records
        
        # 检查文件是否存在且是代码文件
        if not os.path.isfile(file_path):
            return records
        
        if not self._is_code_file(file_path):
            return records
        
        try:
            content = Path(file_path).read_text()
            lines = content.split('\n')
            
            for line_no, line in enumerate(lines, 1):
                for mock_type, (pattern, severity) in self.MOCK_PATTERNS.items():
                    if re.search(pattern, line, re.IGNORECASE):
                        record = MockRecord(
                            file_path=file_path,
                            line_number=line_no,
                            mock_content=line.strip(),
                            mock_type=mock_type,
                            severity=severity,
                            description=f"Found {mock_type} at line {line_no}",
                            task_id=task_id,
                        )
                        records.append(record)
        except Exception:
            pass
        
        return records
    
    def scan_directory(self, dir_path: str, task_id: Optional[str] = None, 
                       recursive: bool = True) -> List[MockRecord]:
        """
        扫描目录检测Mock
        
        Args:
            dir_path: 目录路径
            task_id: 可选的任务ID关联
            recursive: 是否递归
        
        Returns:
            检测到的Mock记录列表
        """
        all_records = []
        
        try:
            if recursive:
                for root, dirs, files in os.walk(dir_path):
                    # 跳过允许的目录
                    dirs[:] = [d for d in dirs if d not in self.ALLOWED_PATHS]
                    for f in files:
                        file_path = os.path.join(root, f)
                        records = self.scan_file(file_path, task_id)
                        all_records.extend(records)
            else:
                for f in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, f)
                    if os.path.isfile(file_path):
                        records = self.scan_file(file_path, task_id)
                        all_records.extend(records)
        except Exception:
            pass
        
        return all_records
    
    def add_record(self, record: MockRecord):
        """添加Mock记录"""
        self._records.append(record)
        self._invalidate_cache(record.file_path)
    
    def add_records(self, records: List[MockRecord]):
        """批量添加Mock记录"""
        for r in records:
            self.add_record(r)
    
    def get_records(self, task_id: Optional[str] = None, 
                    severity: Optional[MockSeverity] = None) -> List[MockRecord]:
        """
        获取Mock记录
        
        Args:
            task_id: 按任务ID过滤
            severity: 按严重级别过滤
        
        Returns:
            过滤后的Mock记录列表
        """
        records = self._records
        
        if task_id is not None:
            records = [r for r in records if r.task_id == task_id]
        
        if severity is not None:
            records = [r for r in records if r.severity == severity]
        
        return records
    
    def get_blocking_mocks(self, task_id: Optional[str] = None) -> List[MockRecord]:
        """获取阻塞性Mock（必须修复的）"""
        return self.get_records(task_id=task_id, severity=MockSeverity.BLOCKING)
    
    def has_blocking_mocks(self, task_id: Optional[str] = None) -> bool:
        """检查是否有阻塞性Mock"""
        return len(self.get_blocking_mocks(task_id)) > 0
    
    def verify_task(self, task_id: str, files: List[str]) -> Dict[str, Any]:
        """
        验证任务是否还有Mock残留
        
        Args:
            task_id: 任务ID
            files: 任务涉及的文件列表
        
        Returns:
            {
                "passed": bool,
                "mock_count": int,
                "blocking_count": int,
                "mocks": [记录列表],
                "recommendation": str
            }
        """
        all_mocks = []
        
        for f in files:
            # 扫描文件
            records = self.scan_file(f, task_id)
            all_mocks.extend(records)
        
        blocking_count = len([r for r in all_mocks if r.severity == MockSeverity.BLOCKING])
        warning_count = len([r for r in all_mocks if r.severity == MockSeverity.WARNING])
        info_count = len([r for r in all_mocks if r.severity == MockSeverity.INFO])
        
        passed = blocking_count == 0
        
        if passed:
            if warning_count > 0:
                recommendation = f"⚠️ 通过但有{warning_count}个警告性Mock，建议修复"
            else:
                recommendation = "✅ 验证通过，无阻塞性Mock"
        else:
            recommendation = f"❌ 验证失败，存在{blocking_count}个阻塞性Mock，必须修复"
        
        return {
            "passed": passed,
            "mock_count": len(all_mocks),
            "blocking_count": blocking_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "mocks": [
                {
                    "file": r.file_path,
                    "line": r.line_number,
                    "type": r.mock_type,
                    "severity": r.severity.value,
                    "content": r.mock_content,
                }
                for r in all_mocks
            ],
            "recommendation": recommendation,
        }
    
    def generate_report(self, task_id: Optional[str] = None) -> str:
        """
        生成Mock报告
        
        Args:
            task_id: 可选的任务ID过滤
        
        Returns:
            格式化的报告字符串
        """
        records = self.get_records(task_id=task_id)
        
        if not records:
            return "✅ 无Mock记录"
        
        # 按文件分组
        by_file: Dict[str, List[MockRecord]] = {}
        for r in records:
            by_file.setdefault(r.file_path, []).append(r)
        
        lines = ["=" * 60, "Mock Registry Report", "=" * 60]
        
        for file_path, file_records in by_file.items():
            lines.append(f"\n📄 {file_path}")
            for r in file_records:
                severity_icon = {
                    MockSeverity.BLOCKING: "🔴",
                    MockSeverity.WARNING: "🟡",
                    MockSeverity.INFO: "🔵",
                }.get(r.severity, "⚪")
                lines.append(f"  {severity_icon} L{r.line_number}: [{r.mock_type}] {r.mock_content[:50]}")
        
        lines.append("\n" + "=" * 60)
        lines.append(f"总计: {len(records)} 个Mock")
        lines.append(f"  🔴 阻塞: {len([r for r in records if r.severity == MockSeverity.BLOCKING])}")
        lines.append(f"  🟡 警告: {len([r for r in records if r.severity == MockSeverity.WARNING])}")
        lines.append(f"  🔵 信息: {len([r for r in records if r.severity == MockSeverity.INFO])}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _is_code_file(self, file_path: str) -> bool:
        """判断是否为代码文件"""
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.go', '.rs'}
        return Path(file_path).suffix.lower() in code_extensions
    
    def _invalidate_cache(self, file_path: str):
        """使文件缓存失效"""
        self._file_cache.pop(file_path, None)
    
    def clear(self):
        """清空所有记录"""
        self._records.clear()
        self._file_cache.clear()


# 全局实例
_global_registry: Optional[MockRegistry] = None


def get_mock_registry(workspace_root: str = None) -> MockRegistry:
    """获取全局MockRegistry实例"""
    global _global_registry
    if _global_registry is None:
        if workspace_root is None:
            workspace_root = str(Path.home() / ".openclaw" / "workspace")
        _global_registry = MockRegistry(workspace_root)
    return _global_registry
