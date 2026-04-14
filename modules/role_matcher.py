"""
role_matcher.py - 角色匹配器（混合方案）

结合：
1. 向量相似度（语义匹配）
2. oh-my-codex claim机制（动态调整）
3. 固定小组（编程任务优先）
"""

import os
import json
import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


# 固定小组配置
FIXED_TEAM = [
    {"id": "engineering_software_architect", "name": "Software Architect", "category": "engineering"},
    {"id": "engineering_senior_developer", "name": "Senior Developer", "category": "engineering"},
    {"id": "testing_api_tester", "name": "API Tester", "category": "testing"},
    {"id": "testing_reality_checker", "name": "Reality Checker", "category": "testing"},
]

FIXED_TEAM_TRIGGERS = [
    "编程", "开发", "进化", "mimir", "sindris", "代码", "code",
    "python", "java", "javascript", "typescript", "修改", "优化",
    "修复", "bug", "feature", "重构", "refactor"
]


@dataclass
class RoleMatch:
    """角色匹配结果"""
    role: Dict
    similarity: float  # 0-1
    source: str  # "vector" | "fixed_team" | "claim" | "keyword"


class RoleMatcher:
    """
    角色匹配器
    
    混合匹配策略：
    1. 固定小组优先（编程任务）
    2. 向量相似度（语义匹配）
    3. oh-my-codex claim（动态调整）
    4. 关键词匹配（备用）
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self._role_cache: Dict[str, Dict] = {}
        self._claim_overrides: Dict[str, str] = {}  # task_id -> role_id
        self._registry_path = os.path.expanduser(
            "~/.openclaw/skills/sindris/scripts/roles_registry.json"
        )
        self._load_roles()
    
    def _load_roles(self) -> None:
        """加载角色注册表"""
        if not os.path.exists(self._registry_path):
            return
        
        try:
            with open(self._registry_path) as f:
                data = json.load(f)
            
            roles = data.get('roles', data) if isinstance(data, dict) else data
            
            for role in roles:
                role_id = role.get('id', '')
                self._role_cache[role_id] = role
                
        except Exception as e:
            print(f"[RoleMatcher] Failed to load roles: {e}")
    
    def should_use_fixed_team(self, task: str) -> bool:
        """判断是否使用固定小组"""
        task_lower = task.lower()
        return any(trigger in task_lower for trigger in FIXED_TEAM_TRIGGERS)
    
    def match(self, task: str, top_k: int = 4) -> List[RoleMatch]:
        """
        匹配角色
        
        策略优先级：
        1. 固定小组（编程任务）
        2. 向量相似度
        3. claim覆盖
        4. 关键词匹配
        """
        # 1. 固定小组优先
        if self.should_use_fixed_team(task):
            return [
                RoleMatch(role=r, similarity=1.0, source="fixed_team")
                for r in FIXED_TEAM
            ][:top_k]
        
        # 2. 向量相似度匹配
        vector_matches = self._match_by_vector(task, top_k)
        
        # 3. 应用claim覆盖
        matches = self._apply_claim_overrides(vector_matches, task)
        
        # 4. 关键词备用
        if not matches:
            matches = self._match_by_keywords(task, top_k)
        
        return matches[:top_k]
    
    def _match_by_vector(self, task: str, top_k: int) -> List[RoleMatch]:
        """向量相似度匹配（简化版TF-IDF + 关键词增强）"""
        task_lower = task.lower()
        task_tokens = self._tokenize(task)
        if not task_tokens and not task_lower:
            return []
        
        # 计算task的TF-IDF
        task_tfidf = self._compute_tfidf(task_tokens)
        
        # 计算每个角色的得分
        scores = []
        for role_id, role in self._role_cache.items():
            role_desc = role.get('description', '')
            role_name = role.get('name', '')
            role_category = role.get('category', '')
            role_lower = (role_desc + ' ' + role_name + ' ' + role_category).lower()
            role_tokens = self._tokenize(role_desc + ' ' + role_name)
            role_tfidf = self._compute_tfidf(role_tokens)
            
            # 计算余弦相似度
            similarity = self._cosine_similarity(task_tfidf, role_tfidf)
            
            # 关键词增强：如果task中有role相关的词，得分更高
            role_keywords = role.get('trigger_keywords', [])
            keyword_boost = 0
            for kw in role_keywords:
                if kw.lower() in task_lower:
                    keyword_boost += 0.2
            
            # 分类匹配增强
            category_keywords = {
                'engineering': ['开发', '代码', 'python', 'java', '编程', 'code', 'develop', 'software', '架构', 'architect', '系统'],
                'testing': ['测试', '验证', 'test', 'verify', 'qa', '检查'],
                'marketing': ['营销', '增长', '推广', 'marketing', 'growth', '用户'],
                'design': ['设计', 'design', 'ui', 'ux', '界面'],
                'research': ['研究', '分析', 'research', 'analyze'],
                'academic': ['学术', '研究', 'theory', '理论'],
            }
            
            for cat, kws in category_keywords.items():
                if cat in role_category.lower():
                    for kw in kws:
                        if kw in task_lower:
                            keyword_boost += 0.15
            
            final_score = min(1.0, similarity + keyword_boost)
            scores.append((role, final_score))
        
        # 排序返回top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [
            RoleMatch(role=r, similarity=s, source="vector")
            for r, s in scores[:top_k] if s > 0
        ]
    
    def _apply_claim_overrides(
        self,
        matches: List[RoleMatch],
        task: str,
    ) -> List[RoleMatch]:
        """应用oh-my-codex claim覆盖"""
        # 生成task key
        task_key = self._task_to_key(task)
        
        if task_key in self._claim_overrides:
            claimed_role_id = self._claim_overrides[task_key]
            
            # 找到被claim的角色
            for role in self._role_cache.values():
                if role.get('id') == claimed_role_id:
                    # 将claim的角色移到第一位
                    new_matches = [RoleMatch(
                        role=role,
                        similarity=1.0,
                        source="claim"
                    )]
                    
                    # 添加其他匹配
                    for m in matches:
                        if m.role.get('id') != claimed_role_id:
                            new_matches.append(m)
                    
                    return new_matches
        
        return matches
    
    def _match_by_keywords(self, task: str, top_k: int) -> List[RoleMatch]:
        """关键词匹配（备用）"""
        task_lower = task.lower()
        scores = []
        
        keywords_map = {
            "architect": ["架构", "设计", "architecture", "design"],
            "developer": ["开发", "实现", "代码", "develop", "code", "implement"],
            "tester": ["测试", "验证", "test", "verify", "validation"],
            "reviewer": ["审查", "review", "检查", "check"],
            "researcher": ["研究", "分析", "research", "analyze"],
        }
        
        for role_id, role in self._role_cache.items():
            score = 0
            role_lower = role_id.lower()
            
            for category, kws in keywords_map.items():
                if category in role_lower:
                    for kw in kws:
                        if kw in task_lower:
                            score += 1
            
            if score > 0:
                scores.append((role, score / 10.0))  # 归一化
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [
            RoleMatch(role=r, similarity=s, source="keyword")
            for r, s in scores[:top_k]
        ]
    
    def claim(self, task: str, role_id: str) -> None:
        """
        oh-my-codex风格：worker claim任务
        
        用法：
            matcher.claim("sindris进化任务", "engineering_senior_developer")
        """
        task_key = self._task_to_key(task)
        self._claim_overrides[task_key] = role_id
        print(f"[RoleMatcher] Task claimed: {task_key} -> {role_id}")
    
    def release(self, task: str) -> None:
        """释放claim"""
        task_key = self._task_to_key(task)
        if task_key in self._claim_overrides:
            del self._claim_overrides[task_key]
    
    def _task_to_key(self, task: str) -> str:
        """将任务转为claim key"""
        return task.lower().strip()[:50]
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词"""
        import re
        tokens = re.findall(r'\w+', text.lower())
        # 去除停用词
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
        return [t for t in tokens if t not in stopwords and len(t) > 2]
    
    def _compute_tfidf(self, tokens: List[str]) -> Dict[str, float]:
        """计算TF-IDF（简化版）"""
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        
        # 归一化
        if tokens:
            for token in tf:
                tf[token] = tf[token] / len(tokens)
        
        return tf
    
    def _cosine_similarity(
        self,
        vec1: Dict[str, float],
        vec2: Dict[str, float],
    ) -> float:
        """计算余弦相似度"""
        # 计算点积
        dot_product = 0
        for token in vec1:
            if token in vec2:
                dot_product += vec1[token] * vec2[token]
        
        # 计算模长
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_fixed_team(self) -> List[Dict]:
        """获取固定小组"""
        return FIXED_TEAM
