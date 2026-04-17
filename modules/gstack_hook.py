"""
Sindri Worker钩子 - 触发GStackPro Paranoid Review

在Sindri Worker完成任务后，自动调用GStackPro进行代码审查
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any

class GStackHook:
    """Sindri Worker钩子：触发GStackPro Review"""
    
    def __init__(self, gstack_url: str = "http://localhost:8000"):
        self.gstack_url = gstack_url
        self.enabled = True
    
    async def on_worker_complete(
        self, 
        task_id: str, 
        output: str,
        worker_role: str
    ) -> Dict[str, Any]:
        """
        Worker完成时自动调用
        触发GStackPro Paranoid Review
        """
        if not self.enabled:
            return {"status": "disabled"}
        
        # 如果是代码相关的角色，触发Review
        code_roles = ["Senior Developer", "Code Reviewer", "Software Architect"]
        if worker_role not in code_roles:
            return {"status": "skipped", "reason": f"{worker_role} not code-related"}
        
        # 调用GStackPro Review API
        try:
            result = await self._call_paranoid_review(output)
            return {
                "status": "reviewed",
                "task_id": task_id,
                "review_result": result
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _call_paranoid_review(self, code: str) -> Dict[str, Any]:
        """调用GStackPro Paranoid Review"""
        import sys
        
        # 优先从sindris_gstack_hybrid导入（因为那里有完整实现）
        hybrid_path = '/home/rayliu/.openclaw/workspace/sindri_gstack_hybrid'
        if hybrid_path not in sys.path:
            sys.path.insert(0, hybrid_path)
        
        try:
            from gstack_integration import call_gstack_role, GStackRole
        except ImportError:
            return {"status": "import_error", "error": "gstack_integration not found"}
        
        result = await call_gstack_role(
            GStackRole.REVIEW,
            f"审查以下代码：\n\n{code[:2000]}",  # 限制长度
            timeout=60
        )
        
        return {
            "status": result.status,
            "data": result.data
        }


# 全局钩子实例
gstack_hook = GStackHook()


async def on_worker_complete(task_id: str, output: str, worker_role: str) -> Dict[str, Any]:
    """便捷函数"""
    return await gstack_hook.on_worker_complete(task_id, output, worker_role)
