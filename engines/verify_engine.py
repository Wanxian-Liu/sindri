"""
verify_engine.py - 验证引擎

职责：
1. OMXContract路径契约验证
2. MockRegistry Mock检测
3. PathValidator路径验证
4. Ralph 3轮循环验证
5. EvolutionVerifier角色改进验证
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts import OMXContractRegistry, MockRegistry, get_mock_registry
from validators import PathValidator

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """验证结果"""
    passed: bool
    task_type: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    issues: List[str]
    details: Dict[str, Any]
    recommendation: str


class VerifyEngine:
    """
    验证引擎
    
    职责：
    1. 执行前验证（Pre-flight checks）
    2. 执行后验证（Post-flight checks）
    3. OMXContract路径契约验证
    4. MockRegistry Mock检测
    5. 集成Ralph验证
    """
    
    def __init__(self, workspace_root: str, script_dir: str):
        self.workspace_root = workspace_root
        self.script_dir = script_dir
        
        # 初始化组件
        self._omx_registry = OMXContractRegistry()
        self._mock_registry: Optional[MockRegistry] = None
        self._path_validator: Optional[PathValidator] = None
    
    @property
    def omx_registry(self) -> OMXContractRegistry:
        """获取OMX契约注册表"""
        return self._omx_registry
    
    @property
    def mock_registry(self) -> MockRegistry:
        """获取MockRegistry（懒加载）"""
        if self._mock_registry is None:
            self._mock_registry = get_mock_registry(self.workspace_root)
        return self._mock_registry
    
    @property
    def path_validator(self) -> PathValidator:
        """获取PathValidator（懒加载）"""
        if self._path_validator is None:
            self._path_validator = PathValidator(self.workspace_root)
        return self._path_validator
    
    # ========== Pre-flight验证 ==========
    
    def preflight_check(self, task_type: str, files: List[str] = None) -> VerificationResult:
        """
        执行前验证
        
        检查：
        1. 必要路径是否存在
        2. 是否有阻塞性Mock
        
        Args:
            task_type: 任务类型
            files: 任务涉及的文件列表
        
        Returns:
            VerificationResult
        """
        issues = []
        details = {}
        
        # 1. OMX契约验证（PRE阶段）
        omx_result = self._omx_registry.validate(
            phase="pre",
            context={"workspace_root": self.workspace_root}
        )
        details["omx_pre"] = omx_result
        
        if omx_result.get("blocked"):
            issues.append("OMX契约验证失败，执行被阻止")
        
        # 2. Mock检测
        if files:
            mock_result = self.mock_registry.verify_task(
                task_id=f"preflight_{task_type}",
                files=files
            )
            details["mock_check"] = mock_result
            
            if not mock_result.get("passed"):
                issues.append(f"存在{mock_result.get('blocking_count', 0)}个阻塞性Mock")
        
        passed = len(issues) == 0
        
        return VerificationResult(
            passed=passed,
            task_type=task_type,
            total_checks=len(files or []) + 1,
            passed_checks=(len(files or []) + 1) if passed else 0,
            failed_checks=0 if passed else len(issues),
            issues=issues,
            details=details,
            recommendation="✅ 执行前验证通过" if passed else f"❌ {issues[0]}",
        )
    
    # ========== Post-flight验证 ==========
    
    def postflight_check(self, task_type: str, files: List[str] = None) -> VerificationResult:
        """
        执行后验证
        
        检查：
        1. OMX契约后置条件
        2. Mock残留检测
        3. 路径有效性
        
        Args:
            task_type: 任务类型
            files: 任务涉及的文件列表
        
        Returns:
            VerificationResult
        """
        issues = []
        details = {}
        
        # 1. OMX契约验证（POST阶段）
        omx_result = self._omx_registry.validate(
            phase="post",
            context={"workspace_root": self.workspace_root}
        )
        details["omx_post"] = omx_result
        
        if omx_result.get("blocked"):
            issues.append("OMX契约后置验证失败")
        
        # 2. Mock残留检测
        if files:
            mock_result = self.mock_registry.verify_task(
                task_id=f"postflight_{task_type}",
                files=files
            )
            details["mock_check"] = mock_result
            
            if not mock_result.get("passed"):
                blocking = mock_result.get("blocking_count", 0)
                if blocking > 0:
                    issues.append(f"存在{blocking}个阻塞性Mock未修复")
        
        # 3. 路径有效性检查
        if files:
            validation_results = self.path_validator.validate_batch(
                files,
                check_exists=True,
                check_type=True,
                level="warn"
            )
            details["path_validation"] = {
                path: {"passed": r.passed, "exists": r.exists}
                for path, r in validation_results.items()
            }
        
        passed = len(issues) == 0
        
        return VerificationResult(
            passed=passed,
            task_type=task_type,
            total_checks=len(files or []) + 1,
            passed_checks=(len(files or []) + 1) if passed else 0,
            failed_checks=0 if passed else len(issues),
            issues=issues,
            details=details,
            recommendation="✅ 执行后验证通过" if passed else f"❌ {issues[0]}",
        )
    
    # ========== 角色改进验证 ==========
    
    def verify_evolution(self, target_role: str, improver_id: str) -> VerificationResult:
        """
        验证角色改进
        
        使用EvolutionVerifier进行验证
        
        Args:
            target_role: 被改进的角色名
            improver_id: 改进者的role_id
        
        Returns:
            VerificationResult
        """
        try:
            from modules.evolution_verifier import EvolutionVerifier
            
            verifier = EvolutionVerifier(self.workspace_root)
            result = verifier.verify(target_role, improver_id)
            
            passed = result.get("passed", False)
            issues = result.get("issues", [])
            
            return VerificationResult(
                passed=passed,
                task_type="evolution",
                total_checks=3,
                passed_checks=3 if passed else sum(1 for c in result.get("checks", {}).values() if c),
                failed_checks=0 if passed else len(issues),
                issues=issues,
                details={"evolution_verifier": result},
                recommendation=result.get("recommendation", ""),
            )
        except ImportError as e:
            logger.warning(f"EvolutionVerifier not available: {e}")
            return VerificationResult(
                passed=False,
                task_type="evolution",
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                issues=["EvolutionVerifier模块不可用"],
                details={"error": str(e)},
                recommendation="⚠️ 无法验证：EvolutionVerifier不可用",
            )
    
    # ========== Ralph 3轮循环验证 ==========
    
    async def verify_with_ralph(self, task: str, result: Any, 
                                 verify_items: List[Dict[str, Any]]) -> VerificationResult:
        """
        使用Ralph进行3轮循环验证
        
        Args:
            task: 任务描述
            result: 执行结果
            verify_items: 验证项列表
        
        Returns:
            VerificationResult
        """
        try:
            from scripts.ralph_loop import RalphLoop
            
            verifier = RalphLoop(
                task_name=f"验证: {task[:50]}...",
                verify_items=verify_items,
            )
            
            ralph_result = await verifier.run()
            
            passed = ralph_result.success
            issues = []
            if not passed:
                issues.append(f"Ralph验证失败：连续{ralph_result.consecutive_passed}轮通过")

            return VerificationResult(
                passed=passed,
                task_type="ralph",
                total_checks=ralph_result.total_rounds,
                passed_checks=ralph_result.consecutive_passed,
                failed_checks=ralph_result.total_rounds - ralph_result.consecutive_passed,
                issues=issues,
                details={
                    "total_rounds": ralph_result.total_rounds,
                    "consecutive_passed": ralph_result.consecutive_passed,
                    "final_state": ralph_result.final_report.state,
                },
                recommendation="✅ Ralph验证通过" if passed else "❌ Ralph验证失败",
            )
        except ImportError as e:
            logger.warning(f"RalphLoop not available: {e}")
            return VerificationResult(
                passed=False,
                task_type="ralph",
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                issues=["RalphLoop模块不可用"],
                details={"error": str(e)},
                recommendation="⚠️ 无法验证：RalphLoop不可用",
            )
    
    # ========== 便捷方法 ==========
    
    def create_contract_for_task(self, task_id: str, 
                                  required_paths: List[str],
                                  verify_content: bool = True) -> str:
        """
        为任务创建OMX契约
        
        Args:
            task_id: 任务ID
            required_paths: 必须存在的路径列表
            verify_content: 是否验证内容
        
        Returns:
            contract_name
        """
        from ..contracts import OMXContract, ContractPhase
        
        contract_name = f"task_contract_{task_id}"
        
        contract = OMXContract(
            name=contract_name,
            phase=ContractPhase.BOTH,
        )
        
        for path in required_paths:
            contract.add_path_exists(path)
            if verify_content:
                contract.add_not_mock(path)
        
        self._omx_registry.register(contract)
        
        return contract_name
    
    def scan_mocks_in_files(self, files: List[str], task_id: str = None) -> Dict[str, Any]:
        """
        扫描文件中的Mock
        
        Args:
            files: 文件列表
            task_id: 可选的任务ID
        
        Returns:
            Mock扫描结果
        """
        all_records = []
        
        for f in files:
            records = self.mock_registry.scan_file(f, task_id)
            all_records.extend(records)
        
        blocking = [r for r in all_records if r.severity.value == "blocking"]
        
        return {
            "passed": len(blocking) == 0,
            "total_mocks": len(all_records),
            "blocking_count": len(blocking),
            "mocks": [
                {
                    "file": r.file_path,
                    "line": r.line_number,
                    "type": r.mock_type,
                    "content": r.mock_content,
                }
                for r in all_records
            ],
        }
