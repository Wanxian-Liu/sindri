"""
role_manager.py - 角色管理模块

职责：
- 角色工具约束
- 角色类型推断
- 超时配置
- 角色Markdown加载
"""

import os
import json
from typing import Dict, List, Optional


# 角色工具默认配置
ROLE_TOOL_DEFAULTS = {
    "researcher": ["read", "exec", "grep", "glob", "web_search"],
    "developer": ["read", "exec", "edit", "write", "browser"],
    "verifier": ["read", "exec", "test", "verify"],
    "architect": ["read", "exec", "edit", "write", "browser"],
    "general": ["read", "exec", "edit", "write", "browser"],
}

# 角色超时配置（秒）
ROLE_TIMEOUT_DEFAULTS = {
    "researcher": 600,
    "developer": 1200,
    "verifier": 300,
    "architect": 600,
    "general": 600,
}


class RoleManager:
    """
    角色管理器
    
    职责：
    1. 获取角色允许的工具
    2. 推断角色类型
    3. 配置超时
    4. 加载角色Markdown
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self._role_cache: Dict[str, Dict] = {}
        self._registry_path = os.path.expanduser(
            "~/.openclaw/skills/sindris/scripts/roles_registry.json"
        )
    
    def get_allowed_tools(self, role_name: str) -> List[str]:
        """获取角色允许的工具"""
        role_lower = role_name.lower()
        
        # 先从注册表查找
        registry_tools = self._get_registry_tools(role_name)
        if registry_tools:
            return registry_tools
        
        # 再用关键词匹配
        for role_type, tools in ROLE_TOOL_DEFAULTS.items():
            if role_type in role_lower:
                return tools
        
        # 默认返回通用工具
        return ROLE_TOOL_DEFAULTS["general"]
    
    def _get_registry_tools(self, role_name: str) -> Optional[List[str]]:
        """从角色注册表获取工具"""
        if not os.path.exists(self._registry_path):
            return None
        
        try:
            with open(self._registry_path) as f:
                data = json.load(f)
            
            roles = data.get('roles', data) if isinstance(data, dict) else data
            
            for role in roles:
                role_title = role.get('name', '').lower()
                if role_title in role_name.lower() or role_name.lower() in role_title:
                    return role.get('allowedTools', [])
            
            return None
        except Exception:
            return None
    
    def infer_role_type(self, role: Dict) -> str:
        """推断角色类型"""
        role_lower = role.get('name', '').lower()
        role_id = role.get('id', '').lower()
        
        if 'architect' in role_id or 'architect' in role_lower:
            return 'architect'
        if 'developer' in role_id or 'developer' in role_lower:
            return 'developer'
        if 'tester' in role_id or 'verifier' in role_id or 'tester' in role_lower:
            return 'verifier'
        if 'researcher' in role_id or 'researcher' in role_lower:
            return 'researcher'
        
        # 从分类推断
        category = role.get('category', '').lower()
        if 'engineering' in category or 'development' in category:
            return 'developer'
        if 'testing' in category:
            return 'verifier'
        if 'research' in category or 'analysis' in category:
            return 'researcher'
        
        return 'general'
    
    def get_timeout(self, role_type: str) -> int:
        """获取角色超时时间"""
        return ROLE_TIMEOUT_DEFAULTS.get(role_type, 600)
    
    def load_role_markdown(self, role: Dict) -> str:
        """加载角色Markdown描述"""
        role_name = role.get('name', role.get('id', 'Assistant'))
        role_category = role.get('category', 'general')
        role_desc = role.get('description', '')
        
        # 构建角色Markdown
        markdown = f"""你是一个{role_category}领域的专业{role_name}。

你的专长：
{role_desc}

你的工作方式：
- 使用合适的工具完成分配的任务
- 确保任务高质量完成
- 及时报告问题和进度

可用工具：{', '.join(self.get_allowed_tools(role_name))}
"""
        return markdown
    
    def check_tool_allowed(self, tool: str, allowed_tools: List[str]) -> bool:
        """检查工具是否允许"""
        return tool in allowed_tools or "*" in allowed_tools
