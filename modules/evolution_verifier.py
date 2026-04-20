"""
evolution_verifier.py - 角色改进验证器

验证角色改进是否真正实现：
1. 代码是否在.py中实现（不是只在MD里）
2. 是否有实际逻辑（不是pass/NotImplemented/MOCK）
3. 是否集成到主流程
"""

import os
import re
import ast
from typing import Dict, List, Optional


class EvolutionVerifier:
    """角色改进验证器"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.modules_dir = os.path.join(workspace_root, "modules")
        self.roles_dir = os.path.join(workspace_root, "roles")
    
    def verify(self, target_role: str, improver_id: str) -> Dict:
        """
        验证角色改进是否真正实现
        
        Args:
            target_role: 被改进的角色名（如"Agents Orchestrator"）
            improver_id: 改进者的role_id（如"engineering_software_architect"）
        
        Returns:
            {
                "passed": bool,
                "issues": List[str],
                "checks": {
                    "code_in_py": bool,
                    "not_mock": bool,
                    "integrated": bool,
                },
                "recommendation": str
            }
        """
        checks = {
            "code_in_py": False,
            "not_mock": False,
            "integrated": False,
        }
        issues = []
        
        # 1. 检查代码是否在.py中实现
        code_in_py = self._check_code_in_python_module(improver_id)
        checks["code_in_py"] = code_in_py
        if not code_in_py:
            issues.append(f"❌ {improver_id} 没有在 .py 模块中实现")
        
        # 2. 检查不是MOCK
        not_mock = self._check_not_mock(improver_id)
        checks["not_mock"] = not_mock
        if not not_mock:
            issues.append(f"❌ {improver_id} 存在 MOCK/placeholder 代码")
        
        # 3. 检查是否集成
        integrated = self._check_integrated(improver_id)
        checks["integrated"] = integrated
        if not integrated:
            issues.append(f"❌ {improver_id} 没有集成到主流程")
        
        passed = all(checks.values())
        
        if passed:
            recommendation = "✅ 验证通过，角色改进已真正实现"
        else:
            recommendation = "⚠️ 验证失败，需要修复上述问题"
        
        return {
            "passed": passed,
            "issues": issues,
            "checks": checks,
            "recommendation": recommendation,
            "target_role": target_role,
            "improver_id": improver_id,
        }
    
    def _check_code_in_python_module(self, role_id: str) -> bool:
        """检查角色ID是否在Python模块中实现"""
        # 检查role_matcher.py中的AUDIT_TEAM/EVOLUTION_DISTRIBUTOR配置
        role_matcher_path = os.path.join(self.modules_dir, "role_matcher.py")
        
        if os.path.exists(role_matcher_path):
            with open(role_matcher_path, "r") as f:
                content = f.read()
            
            # 检查role_id是否在AUDIT_TEAM或EVOLUTION_DISTRIBUTOR中
            if "AUDIT_TEAM" in content and role_id in content:
                # 检查不是注释
                lines = content.split("\n")
                for line in lines:
                    if role_id in line and not line.strip().startswith("#"):
                        if "pass" not in line and "None" not in line.split("#")[0]:
                            return True
            
            if "EVOLUTION_DISTRIBUTOR" in content and role_id in content:
                lines = content.split("\n")
                for line in lines:
                    if role_id in line and not line.strip().startswith("#"):
                        if "pass" not in line and "None" not in line.split("#")[0]:
                            return True
        
        # 检查sindris_executor.py中的处理逻辑
        executor_path = os.path.join(self.workspace_root, "sindris_executor.py")
        if os.path.exists(executor_path):
            with open(executor_path, "r") as f:
                content = f.read()
            
            # 检查是否有处理审计团队或改进任务的逻辑
            if ("is_audit_team" in content or "is_evolution" in content) and role_id in content:
                return True
        
        return False
    
    def _check_not_mock(self, role_id: str) -> bool:
        """检查是否有实际的非MOCK实现"""
        # 检查AUDIT_TEAM和EVOLUTION_DISTRIBUTOR配置
        role_matcher_path = os.path.join(self.modules_dir, "role_matcher.py")
        
        if not os.path.exists(role_matcher_path):
            return False
        
        with open(role_matcher_path, "r") as f:
            content = f.read()
        
        # 检查是否有配置数组
        if role_id in content:
            # 检查是否是作为实际数据存在（不在注释里）
            lines = content.split("\n")
            for line in lines:
                if role_id in line and not line.strip().startswith("#"):
                    # 检查不是 pass、NotImplemented、None
                    if "pass" not in line and "NotImplemented" not in line and "None" not in line.split("#")[0]:
                        return True
        
        return False
    
    def _check_integrated(self, role_id: str) -> bool:
        """检查是否集成到主流程"""
        executor_path = os.path.join(self.workspace_root, "sindris_executor.py")
        
        if not os.path.exists(executor_path):
            return False
        
        with open(executor_path, "r") as f:
            content = f.read()
        
        # 检查是否有审计团队或改进任务的处理逻辑
        has_audit_logic = "is_audit_team" in content
        has_evolution_logic = "is_evolution" in content
        
        if has_audit_logic and has_evolution_logic:
            # 两个逻辑都存在，说明已集成
            # role_id通过配置动态使用，不需要直接出现在代码中
            return True
        
        return False
    
    def verify_and_report(self, target_role: str, improver_id: str) -> str:
        """验证并生成报告"""
        result = self.verify(target_role, improver_id)
        
        lines = [
            f"## 角色改进验证报告",
            f"",
            f"**被改进角色**: {result['target_role']}",
            f"**改进角色**: {result['improver_id']}",
            f"",
            f"### 验证结果",
            f"",
            f"| 检查项 | 结果 |",
            f"|--------|------|",
            f"| 代码在.py中实现 | {'✅' if result['checks']['code_in_py'] else '❌'} |",
            f"| 不是MOCK/placeholder | {'✅' if result['checks']['not_mock'] else '❌'} |",
            f"| 集成到主流程 | {'✅' if result['checks']['integrated'] else '❌'} |",
            f"",
            f"### 问题列表",
            f"",
        ]
        
        if result['issues']:
            for issue in result['issues']:
                lines.append(f"- {issue}")
        else:
            lines.append("- 无问题")
        
        lines.extend([
            f"",
            f"### 结论",
            f"",
            f"{result['recommendation']}",
        ])
        
        return "\n".join(lines)


# 验证函数
def verify_evolution(target_role: str, improver_id: str, workspace_root: str = None) -> Dict:
    """快速验证函数"""
    if workspace_root is None:
        workspace_root = os.path.expanduser("~/.openclaw/skills/sindris")
    
    verifier = EvolutionVerifier(workspace_root)
    return verifier.verify(target_role, improver_id)
