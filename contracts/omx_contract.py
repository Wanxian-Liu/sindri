"""
omx_contract.py - OMX路径契约机制

OMXContract定义执行前后必须满足的路径条件：
- 前置条件：执行前必须存在的路径
- 后置条件：执行后必须存在的路径
- 状态检查：文件类型、大小、内容等
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ContractPhase(Enum):
    """契约阶段"""
    PRE = "pre"      # 执行前检查
    POST = "post"    # 执行后检查
    BOTH = "both"    # 两者都要


class ContractType(Enum):
    """契约类型"""
    PATH_EXISTS = "path_exists"           # 路径存在
    PATH_NOT_EXISTS = "path_not_exists"   # 路径不存在
    FILE_SIZE_GT = "file_size_gt"         # 文件大小大于
    FILE_SIZE_LT = "file_size_lt"         # 文件大小小于
    FILE_CONTENT_MATCH = "file_content_match"  # 文件内容匹配
    FILE_CONTENT_NOT_MATCH = "file_content_not_match"  # 文件内容不匹配
    DIR_EXISTS = "dir_exists"            # 目录存在
    IS_FILE = "is_file"                  # 是文件
    IS_DIR = "is_dir"                    # 是目录
    CUSTOM = "custom"                    # 自定义检查


@dataclass
class ContractCondition:
    """契约条件"""
    contract_type: ContractType
    path: str
    value: Any = None  # 用于比较的值
    description: str = ""
    check_fn: Optional[Callable[[str, Any], bool]] = None  # 自定义检查函数


@dataclass
class OMXContract:
    """
    OMX路径契约
    
    定义一组路径条件，在执行前后进行验证
    """
    name: str
    phase: ContractPhase = ContractPhase.BOTH
    conditions: List[ContractCondition] = field(default_factory=list)
    enabled: bool = True
    strict: bool = True  # 严格模式：失败时阻止执行
    
    def add_condition(self, condition: ContractCondition):
        """添加条件"""
        self.conditions.append(condition)
    
    def add_path_exists(self, path: str, description: str = ""):
        """便捷方法：添加路径存在条件"""
        self.conditions.append(ContractCondition(
            contract_type=ContractType.PATH_EXISTS,
            path=path,
            description=description or f"{path} must exist"
        ))
    
    def add_file_contains(self, path: str, pattern: str, description: str = ""):
        """便捷方法：添加文件包含内容条件"""
        self.conditions.append(ContractCondition(
            contract_type=ContractType.FILE_CONTENT_MATCH,
            path=path,
            value=pattern,
            description=description or f"{path} must contain {pattern}"
        ))
    
    def add_not_mock(self, path: str, description: str = ""):
        """便捷方法：添加非Mock条件"""
        mock_patterns = ["MOCK", "TODO", "placeholder", "NotImplemented"]
        self.conditions.append(ContractCondition(
            contract_type=ContractType.FILE_CONTENT_NOT_MATCH,
            path=path,
            value="|".join(mock_patterns),
            description=description or f"{path} must not contain MOCK/TODO/placeholder"
        ))


class OMXContractRegistry:
    """
    OMX契约注册表
    
    管理所有OMXContract，支持批量验证
    """
    
    def __init__(self):
        self._contracts: Dict[str, OMXContract] = {}
        self._execution_log: List[Dict[str, Any]] = []
    
    def register(self, contract: OMXContract):
        """注册契约"""
        self._contracts[contract.name] = contract
    
    def get(self, name: str) -> Optional[OMXContract]:
        """获取契约"""
        return self._contracts.get(name)
    
    def unregister(self, name: str):
        """注销契约"""
        self._contracts.pop(name, None)
    
    def validate(self, phase: ContractPhase, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        验证所有适用的契约
        
        Args:
            phase: 当前阶段 (PRE/POST)
            context: 执行上下文，包含workspace_root等
        
        Returns:
            {
                "passed": bool,
                "results": [
                    {"contract": "name", "passed": bool, "details": [...]}
                ],
                "failed_contracts": [contract_names],
                "blocked": bool  # 是否应该阻止执行
            }
        """
        context = context or {}
        workspace_root = context.get("workspace_root", str(Path.home()))
        
        results = []
        failed_contracts = []
        blocked = False
        
        for name, contract in self._contracts.items():
            if not contract.enabled:
                continue
            
            # 检查契约是否适用于当前阶段
            if contract.phase not in (ContractPhase.BOTH, phase):
                continue
            
            # 验证所有条件
            contract_result = self._validate_contract(contract, workspace_root)
            results.append({
                "contract": name,
                "passed": contract_result["passed"],
                "conditions": contract_result["conditions"],
            })
            
            if not contract_result["passed"]:
                failed_contracts.append(name)
                if contract.strict:
                    blocked = True
        
        # 记录执行日志
        self._execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase.value,
            "results": results,
            "blocked": blocked,
        })
        
        return {
            "passed": len(failed_contracts) == 0,
            "results": results,
            "failed_contracts": failed_contracts,
            "blocked": blocked,
        }
    
    def _validate_contract(self, contract: OMXContract, workspace_root: str) -> Dict[str, Any]:
        """验证单个契约"""
        condition_results = []
        all_passed = True
        
        for cond in contract.conditions:
            result = self._check_condition(cond, workspace_root)
            condition_results.append({
                "type": cond.contract_type.value,
                "path": cond.path,
                "description": cond.description,
                "passed": result,
            })
            if not result:
                all_passed = False
        
        return {
            "passed": all_passed,
            "conditions": condition_results,
        }
    
    def _check_condition(self, cond: ContractCondition, workspace_root: str) -> bool:
        """检查单个条件"""
        # 解析路径，支持相对路径
        if cond.path.startswith("/"):
            full_path = cond.path
        else:
            full_path = os.path.join(workspace_root, cond.path)
        
        try:
            if cond.contract_type == ContractType.PATH_EXISTS:
                return os.path.exists(full_path)
            
            elif cond.contract_type == ContractType.PATH_NOT_EXISTS:
                return not os.path.exists(full_path)
            
            elif cond.contract_type == ContractType.FILE_SIZE_GT:
                if not os.path.isfile(full_path):
                    return False
                return os.path.getsize(full_path) > cond.value
            
            elif cond.contract_type == ContractType.FILE_SIZE_LT:
                if not os.path.isfile(full_path):
                    return False
                return os.path.getsize(full_path) < cond.value
            
            elif cond.contract_type == ContractType.FILE_CONTENT_MATCH:
                if not os.path.isfile(full_path):
                    return False
                content = Path(full_path).read_text()
                return bool(re.search(str(cond.value), content))
            
            elif cond.contract_type == ContractType.FILE_CONTENT_NOT_MATCH:
                if not os.path.isfile(full_path):
                    return True  # 文件不存在 = 不包含内容 = 通过
                content = Path(full_path).read_text()
                return not bool(re.search(str(cond.value), content))
            
            elif cond.contract_type == ContractType.DIR_EXISTS:
                return os.path.isdir(full_path)
            
            elif cond.contract_type == ContractType.IS_FILE:
                return os.path.isfile(full_path)
            
            elif cond.contract_type == ContractType.IS_DIR:
                return os.path.isdir(full_path)
            
            elif cond.contract_type == ContractType.CUSTOM:
                if cond.check_fn:
                    return cond.check_fn(full_path, cond.value)
                return True
            
            else:
                return True
                
        except Exception:
            return False
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        return self._execution_log
    
    def clear_log(self):
        """清空执行日志"""
        self._execution_log.clear()


# 全局注册表实例
_global_registry = OMXContractRegistry()


def get_contract_registry() -> OMXContractRegistry:
    """获取全局契约注册表"""
    return _global_registry


def create_contract(name: str, phase: ContractPhase = ContractPhase.BOTH) -> OMXContract:
    """创建并注册契约的便捷函数"""
    contract = OMXContract(name=name, phase=phase)
    _global_registry.register(contract)
    return contract
