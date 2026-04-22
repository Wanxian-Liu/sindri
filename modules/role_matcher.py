"""
role_matcher.py - 角色匹配器（混合方案）

结合：
1. 任务类型识别（TaskClassifier）
2. 固定小组（工程/测试任务）
3. 向量相似度（语义匹配）
4. oh-my-codex claim机制（动态调整）
"""

import os
import json
import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .task_classifier import TaskClassifier, TaskType
from .role_hierarchical_matcher import classify_domain, RoleHierarchicalMatcher


# 固定小组配置（sindri原生团队）
FIXED_TEAM = [
    {
        "id": "product_product_manager",
        "name": "Product Manager",
        "category": "product",
        "description": "sindri Round1角色。接收用户需求/业务目标，输出结构化subtasks给Architect/Developer/QA。负责问题发现、需求定义、优先级排序，不负责技术实现和测试策略。",
        "emoji": "🧭",
        "vibe": "Ships the right thing, not just the next thing — outcome-obsessed, user-grounded, and diplomatically ruthless about focus."
    },
    {
        "id": "coordination_agents_orchestrator",
        "name": "Agents Orchestrator",
        "category": "coordination",
        "description": "Sindri Round2+ execution coordinator — orchestrates parallel engineering subagents with CircuitBreaker protection and ConsensusOfficer voting gates.",
        "emoji": "🎛️",
        "vibe": "The conductor who runs the entire dev pipeline from spec to ship — but only after the architects have planned."
    },
    {
        "id": "engineering_staff_engineer",
        "name": "Staff Engineer",
        "category": "engineering",
        "description": "Principal Technical Leader — drives technical direction, architecture decisions, and cross-team engineering excellence for sindri Round2 execution.",
        "emoji": "⚙️",
        "vibe": "Designs systems that survive contact with reality — and fixes them when they don't."
    },
    {
        "id": "engineering_debugger",
        "name": "Debugger",
        "category": "engineering",
        "description": "Bug Diagnosis & Resolution Specialist — executes Round 2.5 bug fix verification with root cause analysis and systemic solution identification.",
        "emoji": "🔧",
        "vibe": "Finds what others miss, fixes what others fear to touch."
    },
    {
        "id": "engineering_frontend_developer",
        "name": "Frontend Developer",
        "category": "engineering",
        "description": "Expert frontend developer specializing in modern web technologies, React/Vue/Angular frameworks, UI implementation, and performance optimization.",
        "emoji": "🖥️",
        "vibe": "Builds responsive, accessible web apps with pixel-perfect precision."
    },
    {
        "id": "testing_api_tester",
        "name": "API Tester",
        "category": "testing",
        "description": "Expert API testing specialist focused on comprehensive API validation, performance testing, and quality assurance across all systems and third-party integrations.",
        "emoji": "🔌",
        "vibe": "Breaks your API before your users do."
    },
    {
        "id": "sindri_reality_checker",
        "name": "sindri Reality Checker",
        "category": "testing",
        "description": "Stops fantasy approvals, evidence-based certification — Default to 'NEEDS WORK', requires overwhelming proof for production readiness. Round 3 verification specialist.",
        "emoji": "🧐",
        "vibe": "Defaults to 'NEEDS WORK' — requires overwhelming proof for production readiness."
    },
]

FIXED_TEAM_TRIGGERS = [
    # 编程/开发类
    "编程", "开发", "代码", "code",
    "python", "java", "javascript", "typescript",
    "修改", "优化", "修复", "bug", "feature", "重构", "refactor",
    # 自研系统类
    "记忆殿堂", "mimir", "sindris", "进化",
    # 工程类关键词
    "模块", "组件", "系统", "架构", "接口", "实现",
    "自动化", "流程", "设计", "开发",
]

# 审计专业团队 v2.0（方案B：完整团队）
AUDIT_TEAM = [
    {"id": "engineering_code_reviewer", "name": "Code Reviewer", "category": "engineering"},
    {"id": "engineering_security_engineer", "name": "Security Engineer", "category": "engineering"},
    {"id": "engineering_software_architect", "name": "Software Architect", "category": "engineering"},
    {"id": "testing_qa_lead", "name": "QA Lead", "category": "testing"},
    {"id": "testing_reality_checker", "name": "Reality Checker", "category": "testing"},
]

AUDIT_TEAM_TRIGGERS = [
    # 审计/评估类（使用精确词，避免误匹配角色名）
    # 中文
    "审计", "评估", "审查", 
    "代码审计", "安全审计", "系统审计",
    "质量检查", "代码检查", "安全检查", "核查",
    "评分", "评级", "打分", "评价", "评审",
    "代码review", "安全review",
    # 英文
    "audit", "review", "assessment",
    "code review", "security audit", "system audit",
    "quality check", "security check",
]

# 角色改进分配器（Role Evolution Distributor）
# 分配规则：被改进角色category → 改进角色
EVOLUTION_DISTRIBUTOR = {
    "coordination": {
        "improver": "engineering_software_architect",
        "target": "Agents Orchestrator",
        "reason": "架构不匹配需Software Architect重新设计"
    },
    "product": {
        "improver": "engineering_technical_writer",
        "target": "Product Manager",
        "reason": "文档结构/工作流需Technical Writer规范化"
    },
    "engineering": {
        "improver": "engineering_code_reviewer",
        "target": "Staff Engineer/Frontend Developer",
        "reason": "代码质量/接口契约问题"
    },
    "engineering_debugger": {
        "improver": "engineering_security_engineer",
        "target": "Debugger",
        "reason": "安全调试/多语言问题"
    },
    "testing": {
        "improver": "testing_qa_lead",
        "target": "Reality Checker/API Tester",
        "reason": "测试方法论/sindri集成问题"
    },
}

EVOLUTION_TEAM_TRIGGERS = [
    # 改进/优化类
    "改进角色", "优化角色", "升级角色", "完善角色", "修复角色",
    "改进", "改善", "提升", "优化", "upgrade", "improve",
    "角色进化", "角色完善", "角色升级",
    # 完善/优化 + 角色名（需要同时出现"完善/优化"和"角色/role"）
    "完善角色md", "优化角色md", "改进角色md",
    # 完善（单独使用，配合角色名时触发）
    "完善",
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
        self._task_classifier = TaskClassifier()  # 任务类型识别器
        self._hierarchical_matcher = RoleHierarchicalMatcher(self._registry_path)  # 分层匹配器
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
        """判断是否使用固定小组（使用TaskClassifier）"""
        return self._task_classifier.should_use_fixed_team(task)
    
    def should_use_audit_team(self, task: str) -> bool:
        """判断是否使用审计专业团队"""
        task_lower = task.lower()
        return any(trigger in task_lower for trigger in AUDIT_TEAM_TRIGGERS)
    
    def should_use_evolution_team(self, task: str) -> bool:
        """判断是否使用角色改进分配器"""
        task_lower = task.lower()
        return any(trigger in task_lower for trigger in EVOLUTION_TEAM_TRIGGERS)
    
    def get_evolution_improver(self, task: str) -> Optional[Dict]:
        """
        根据任务中的被改进角色，返回最合适的改进角色
        
        Returns:
            改进角色的role dict，如果没有匹配返回None
        """
        task_lower = task.lower()
        
        # 遍历分配矩阵，找匹配项
        for category, config in EVOLUTION_DISTRIBUTOR.items():
            target = config["target"]
            # 支持多个目标（用/分隔），逐个检查
            targets = [t.strip().lower() for t in target.split("/")]
            for t in targets:
                if t in task_lower:
                    # 找到对应的改进角色
                    improver_id = config["improver"]
                    if improver_id in self._role_cache:
                        print(f"[RoleMatcher] 角色改进分配：{config['target']} → {improver_id} ({config['reason']})")
                        return self._role_cache[improver_id]
        
        return None
    
    def classify_task_type(self, task: str) -> TaskType:
        """获取任务类型"""
        return self._task_classifier.classify(task)
    
    def match(self, task: str, top_k: int = 4) -> List[RoleMatch]:
        """
        匹配角色
        
        策略优先级：
        1. 固定小组（通用编程任务，creative和specialized域除外）
        2. 分层域判断 + 向量相似度
        3. claim覆盖
        4. 关键词匹配
        """
        # 0. 分层域判断（优先）
        task_domain = classify_domain(task)
        
        # 1. 角色改进分配器优先（改进角色任务使用分配器）
        # 注意：必须在审计团队之前检查，因为"完善角色"等关键词可能被AUDIT_TEAM错误匹配
        if self.should_use_evolution_team(task):
            improver = self.get_evolution_improver(task)
            if improver:
                print(f"[RoleMatcher] 检测到角色改进任务，使用改进角色: {improver['name']}")
                return [RoleMatch(role=improver, similarity=1.0, source="evolution_distributor")]
            
            # Fallback: 如果evolution触发但找不到improver，检查是否是AUDIT_TEAM角色改进自身
            # 例如："完善Code Reviewer Security Engineer角色md" → 使用AUDIT_TEAM改进自身
            audit_names = [r['name'].lower() for r in AUDIT_TEAM]
            task_lower = task.lower()
            if any(name in task_lower for name in audit_names):
                print(f"[RoleMatcher] 检测到AUDIT_TEAM角色改进任务，使用AUDIT_TEAM")
                return [
                    RoleMatch(role={**r, 'team_type': 'evolution'}, similarity=1.0, source="audit_evolution")
                    for r in AUDIT_TEAM
                ][:top_k]
        
        # 1.5. 审计团队（只有明确是审计任务时才触发）
        if self.should_use_audit_team(task):
            print(f"[RoleMatcher] 检测到审计任务，使用审计专业团队")
            return [
                RoleMatch(role=r, similarity=1.0, source="audit_team")
                for r in AUDIT_TEAM
            ][:top_k]
        
        # 2. 任务类型识别 + 固定小组（creative/specialized域不用固定团队）
        if task_domain not in ["creative", "data", "research"] and self.should_use_fixed_team(task):
            task_type = self.classify_task_type(task)
            print(f"[RoleMatcher] 任务类型: {task_type.value}, 使用固定团队")
            return [
                RoleMatch(role=r, similarity=1.0, source="fixed_team")
                for r in FIXED_TEAM
            ][:top_k]
        
        # 2. 分层域判断 + 向量相似度匹配
        vector_matches = self._match_by_vector(task, top_k, preferred_domain=task_domain)
        
        # 3. 应用claim覆盖
        matches = self._apply_claim_overrides(vector_matches, task)
        
        # 4. 关键词备用
        if not matches:
            matches = self._match_by_keywords(task, top_k)
        
        return matches[:top_k]
    
    def _match_by_vector(self, task: str, top_k: int, preferred_domain: str = None) -> List[RoleMatch]:
        """向量相似度匹配（简化版TF-IDF + 分层域增强）"""
        task_lower = task.lower()
        task_tokens = self._tokenize(task)
        if not task_tokens and not task_lower:
            return []
        
        # 计算task的TF-IDF
        task_tfidf = self._compute_tfidf(task_tokens)
        
        # 分层域映射：角色category -> 任务域
        CATEGORY_TO_DOMAIN = {
            "blender": "creative", "unity": "creative", "godot": "creative",
            "academic": "research", "testing": "testing", "product": "product",
            "marketing": "marketing", "engineering": "engineering",
        }
        
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
            
            # 分层域增强：如果角色category匹配任务域，大幅增强
            if preferred_domain:
                role_domain = CATEGORY_TO_DOMAIN.get(role_category, role_category)
                if role_domain == preferred_domain:
                    keyword_boost += 0.5  # 域匹配加分
            
            # 分类匹配增强
            category_keywords = {
                'engineering': [
                    '开发', '代码', 'python', 'java', '编程', 'code', 'develop', 'software', '架构', 'architect', '系统', 'react', '前端', 'frontend', 'machine learning', 'ai', 'ml',
                    '机器学习', '模型训练', 'ai工程师', '深度学习', '神经网络', '训练', '模型', 'AI', 'ML'
                ],
                'testing': ['测试', '验证', 'test', 'verify', 'qa', '检查'],
                'marketing': ['营销', '增长', '推广', 'marketing', 'growth', '用户'],
                'design': ['设计', 'design', 'ui', 'ux', '界面'],
                'research': ['研究', '分析', 'research', 'analyze'],
                'academic': ['学术', '研究', 'theory', '理论'],
                'creative': ['blender', 'unity', '3d', '建模', '渲染', '动画', '设计'],
            }
            
            for cat, kws in category_keywords.items():
                if cat in role_category.lower() or (preferred_domain and cat == preferred_domain):
                    for kw in kws:
                        if kw in task_lower:
                            keyword_boost += 0.15
            
            # 角色名精确匹配：如果角色名包含任务相关关键词，加分（不cap）
            role_name_lower = role.get('name', '').lower()
            name_boost = 0
            if preferred_domain == 'engineering':
                if 'ai engineer' in role_name_lower and any(kw in task_lower for kw in ['机器学习', 'ai', 'ml', 'machine', '深度学习', '模型训练']):
                    name_boost += 0.8
                elif 'machine learning' in role_name_lower or ' ml ' in f' {role_name_lower} ':
                    if any(kw in task_lower for kw in ['机器学习', '模型训练', 'machine', 'ml']):
                        name_boost += 0.6
            keyword_boost += name_boost
            
            final_score = similarity + keyword_boost  # 不cap，让专业角色分数更高
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
