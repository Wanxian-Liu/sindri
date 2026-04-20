"""
contracts/ - OMX路径契约机制

OMXContract: 定义路径契约，验证执行前后路径状态
MockRegistry: 追踪Mock实现，防止假通过
"""

from .omx_contract import OMXContract, OMXContractRegistry, get_contract_registry, create_contract
from .mock_registry import MockRegistry, MockRecord, get_mock_registry

__all__ = [
    "OMXContract",
    "OMXContractRegistry", 
    "MockRegistry",
    "MockRecord",
    "get_contract_registry",
    "create_contract",
    "get_mock_registry",
]
