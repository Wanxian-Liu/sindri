"""
path_validator.py - 路径验证器

验证文件/目录路径的有效性：
1. 路径存在性
2. 路径格式正确性
3. 路径可访问性
4. 路径类型（文件/目录）
5. 路径内容验证
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class ValidationLevel(Enum):
    """验证级别"""
    STRICT = "strict"     # 严格：不存在就失败
    WARN = "warn"        # 警告：不存在但记录
    SKIP = "skip"        # 跳过：不验证


@dataclass
class ValidationResult:
    """验证结果"""
    path: str
    passed: bool
    exists: bool = False
    is_file: bool = False
    is_dir: bool = False
    is_readable: bool = False
    is_writable: bool = False
    size: Optional[int] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class PathValidator:
    """
    路径验证器
    
    功能：
    1. 验证单个路径或路径列表
    2. 支持相对路径和绝对路径
    3. 支持通配符匹配
    4. 验证路径属性（存在、类型、权限等）
    5. 生成验证报告
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self._validation_cache: Dict[str, ValidationResult] = {}
    
    def resolve_path(self, path: str) -> str:
        """
        解析路径为绝对路径
        
        Args:
            path: 相对路径或绝对路径
        
        Returns:
            绝对路径
        """
        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace_root, path)
    
    def validate(self, path: str, 
                 check_exists: bool = True,
                 check_type: bool = False,
                 expected_type: str = None,  # "file" or "dir"
                 check_readable: bool = False,
                 check_writable: bool = False,
                 level: ValidationLevel = ValidationLevel.STRICT) -> ValidationResult:
        """
        验证单个路径
        
        Args:
            path: 路径
            check_exists: 是否检查存在
            check_type: 是否检查类型
            expected_type: 期望类型 ("file" or "dir")
            check_readable: 是否检查可读
            check_writable: 是否检查可写
            level: 验证级别
        
        Returns:
            ValidationResult
        """
        # 检查缓存
        cache_key = f"{path}:{check_type}:{expected_type}:{check_readable}:{check_writable}"
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]
        
        full_path = self.resolve_path(path)
        result = ValidationResult(path=path, passed=True)
        warnings = []
        
        try:
            # 检查存在性
            if check_exists:
                exists = os.path.exists(full_path)
                result.exists = exists
                
                if not exists:
                    if level == ValidationLevel.STRICT:
                        result.passed = False
                        result.error = f"Path does not exist: {path}"
                    elif level == ValidationLevel.WARN:
                        warnings.append(f"Path does not exist: {path}")
                    # SKIP: 不验证也不报错
            
            # 如果不存在，后续检查可能无意义
            if not result.exists:
                result.passed = False
                result.warnings = warnings
                self._validation_cache[cache_key] = result
                return result
            
            # 检查类型
            if check_type and expected_type:
                if expected_type == "file":
                    result.is_file = os.path.isfile(full_path)
                    if not result.is_file:
                        result.passed = False
                        result.error = f"Expected file but got: {path}"
                elif expected_type == "dir":
                    result.is_dir = os.path.isdir(full_path)
                    if not result.is_dir:
                        result.passed = False
                        result.error = f"Expected directory but got: {path}"
            
            # 检查读写权限
            if check_readable:
                result.is_readable = os.access(full_path, os.R_OK)
                if not result.is_readable:
                    warnings.append(f"Path not readable: {path}")
            
            if check_writable:
                result.is_writable = os.access(full_path, os.W_OK)
                if not result.is_writable:
                    warnings.append(f"Path not writable: {path}")
            
            # 获取文件大小
            if os.path.isfile(full_path):
                result.size = os.path.getsize(full_path)
            
            result.warnings = warnings
            
        except Exception as e:
            result.passed = False
            result.error = str(e)
        
        self._validation_cache[cache_key] = result
        return result
    
    def validate_batch(self, paths: List[str], 
                       check_exists: bool = True,
                       check_type: bool = False,
                       expected_type: str = None,
                       level: ValidationLevel = ValidationLevel.STRICT) -> Dict[str, ValidationResult]:
        """
        批量验证路径
        
        Returns:
            {path: ValidationResult}
        """
        results = {}
        for path in paths:
            results[path] = self.validate(
                path=path,
                check_exists=check_exists,
                check_type=check_type,
                expected_type=expected_type,
                level=level,
            )
        return results
    
    def validate_wildcard(self, pattern: str, 
                          check_exists: bool = True,
                          check_type: str = None,  # "file" or "dir" or None
                          level: ValidationLevel = ValidationLevel.STRICT) -> List[ValidationResult]:
        """
        验证通配符匹配的路径
        
        Args:
            pattern: 通配符模式，如 "*.py" 或 "src/**/*.js"
            check_type: 期望类型过滤
        
        Returns:
            匹配的验证结果列表
        """
        full_pattern = self.resolve_path(pattern)
        results = []
        
        # 使用Path.glob进行通配符匹配
        try:
            for path_obj in Path(self.workspace_root).glob(pattern):
                path_str = str(path_obj.relative_to(self.workspace_root))
                
                # 类型过滤
                if check_type == "file" and not path_obj.is_file():
                    continue
                if check_type == "dir" and not path_obj.is_dir():
                    continue
                
                result = self.validate(
                    path=path_str,
                    check_exists=check_exists,
                    check_type=False,  # 已经检查过了
                    level=level,
                )
                results.append(result)
        except Exception:
            pass
        
        return results
    
    def validate_contract_paths(self, required_paths: List[str],
                               optional_paths: List[str] = None) -> Dict[str, Any]:
        """
        验证契约路径（必选+可选）
        
        Args:
            required_paths: 必须存在的路径列表
            optional_paths: 可选存在的路径列表
        
        Returns:
            {
                "passed": bool,
                "required_results": {path: ValidationResult},
                "optional_results": {path: ValidationResult},
                "missing_required": [paths],
                "all_valid": bool
            }
        """
        optional_paths = optional_paths or []
        
        # 验证必选路径
        required_results = self.validate_batch(
            required_paths,
            check_exists=True,
            level=ValidationLevel.STRICT,
        )
        
        # 验证可选路径
        optional_results = self.validate_batch(
            optional_paths,
            check_exists=True,
            level=ValidationLevel.WARN,
        )
        
        # 汇总
        missing_required = [p for p, r in required_results.items() if not r.exists]
        failed_required = [p for p, r in required_results.items() if not r.passed]
        
        return {
            "passed": len(missing_required) == 0 and len(failed_required) == 0,
            "required_results": required_results,
            "optional_results": optional_results,
            "missing_required": missing_required,
            "failed_required": failed_required,
            "all_valid": all(r.passed for r in required_results.values()),
        }
    
    def generate_report(self, results: Dict[str, ValidationResult]) -> str:
        """
        生成验证报告
        
        Args:
            results: 验证结果字典
        
        Returns:
            格式化的报告字符串
        """
        lines = ["=" * 60, "Path Validation Report", "=" * 60]
        
        passed_count = 0
        failed_count = 0
        
        for path, result in results.items():
            if result.passed:
                passed_count += 1
                status = "✅"
            else:
                failed_count += 1
                status = "❌"
            
            lines.append(f"\n{status} {path}")
            lines.append(f"   exists: {result.exists}")
            
            if result.is_file:
                lines.append(f"   type: file (size={result.size})")
            elif result.is_dir:
                lines.append(f"   type: directory")
            
            if result.warnings:
                for w in result.warnings:
                    lines.append(f"   ⚠️ {w}")
            
            if result.error:
                lines.append(f"   🔴 {result.error}")
        
        lines.append("\n" + "-" * 60)
        lines.append(f"总计: {len(results)} | ✅ 通过: {passed_count} | ❌ 失败: {failed_count}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def clear_cache(self):
        """清空验证缓存"""
        self._validation_cache.clear()
