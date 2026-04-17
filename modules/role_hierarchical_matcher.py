"""
Sindri角色分层匹配器
基于GStackPro建议：L1任务域 -> L2技能类型 -> L3角色匹配

不简化角色数量，而是优化匹配逻辑。
"""

import json
from typing import List, Dict, Optional

# L1任务域关键词
DOMAIN_KEYWORDS = {
    "engineering": ["api", "backend", "frontend", "server", "database", "架构", "函数", "类", "模块", "代码", "开发"],
    "creative": ["blender", "unity", "3d", "建模", "渲染", "动画", "设计", "创意", "素材", "材质", "灯光", "角色模型", "场景", "godot"],
    "research": ["研究", "分析", "调研", "论文", "学术", "探索", "调查", "学术论文"],
    "product": ["产品", "需求", "feature", "用户", "体验", "优先级", "sprint", "roadmap"],
    "marketing": ["营销", "推广", "内容", "文案", "运营", "增长"],
    "testing": ["测试", "验证", "QA", "验收", "测试用例"],
    "devops": ["部署", "CI/CD", "docker", "k8s", "运维", "监控"],
    "data": ["数据", "分析", "机器学习", "AI", "模型", "训练", "深度学习"],
}

# 角色category到域的映射
CATEGORY_TO_DOMAIN = {
    "blender": "creative",
    "unity": "creative",
    "godot": "creative",
    "academic": "research",
    "testing": "testing",
    "product": "product",
    "marketing": "marketing",
    "engineering": "engineering",
}

# 强排除关键词
DOMAIN_EXCLUDE = {
    "engineering": ["blender", "unity", "3d", "动画", "渲染"],
    "creative": ["api", "backend", "server", "database", "bug"],
}

# L2技能类型（细分）
SKILL_TYPES = {
    "engineering": {
        "backend": ["api", "server", "database", "sql", "nosql", "cache"],
        "frontend": ["ui", "react", "vue", "css", "html", "界面"],
        "fullstack": ["全栈", "fullstack", "前后端"],
        "mobile": ["ios", "android", "app", "flutter", "react native"],
        "embedded": ["嵌入式", "单片机", "iot", "硬件"],
    },
    "creative": {
        "3d": ["blender", "unity", "3d", "建模", "渲染"],
        "2d": ["illustrator", "photoshop", "设计", "平面"],
        "video": ["视频", "剪辑", "premiere", "after effects"],
    },
    "data": {
        "ml": ["机器学习", "ml", "model", "training"],
        "analysis": ["分析", "analytics", "bi", "可视化"],
        "nlp": ["nlp", "text", "language model", "chatbot"],
    },
}


def classify_domain(task: str) -> str:
    """L1: 根据任务描述判断任务域"""
    task_lower = task.lower()
    scores = {}
    
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in task_lower)
        scores[domain] = score
    
    # 排除逻辑：如果触发排除关键词，大幅降低对应域的分数
    for domain, exclude_kws in DOMAIN_EXCLUDE.items():
        if domain in scores:
            for ekw in exclude_kws:
                if ekw.lower() in task_lower:
                    scores[domain] -= 2  # 排除关键词权重更高
    
    if max(scores.values()) <= 0:
        return "general"
    
    return max(scores, key=scores.get)


def classify_skills(task: str, domain: str) -> List[str]:
    """L2: 根据任务和域获取相关技能类型"""
    task_lower = task.lower()
    skills = []
    
    if domain in SKILL_TYPES:
        for skill_type, keywords in SKILL_TYPES[domain].items():
            if any(kw.lower() in task_lower for kw in keywords):
                skills.append(skill_type)
    
    return skills if skills else ["general"]


def calculate_role_score(role: dict, task: str, domain: str, skills: List[str]) -> float:
    """计算角色与任务的匹配分数"""
    score = 0.0
    task_lower = task.lower()
    
    # 1. category匹配（高权重，考虑映射）
    role_category = role.get("category", "")
    mapped_domain = CATEGORY_TO_DOMAIN.get(role_category, role_category)
    if mapped_domain == domain:
        score += 10.0
    
    # 2. trigger_keywords匹配
    keywords = role.get("trigger_keywords", [])
    for kw in keywords:
        if kw.lower() in task_lower:
            score += 1.0
    
    # 3. description关键词匹配
    desc = role.get("description", "").lower()
    for kw in keywords:
        if kw.lower() in desc:
            score += 0.5
    
    # 4. 技能类型匹配
    if skills and skills != ["general"]:
        for skill in skills:
            if skill.lower() in desc:
                score += 2.0
    
    return score


def match_roles(task: str, roles: List[dict], top_k: int = 5, domain: str = None) -> List[dict]:
    """
    分层匹配角色
    
    Args:
        task: 任务描述
        roles: 角色列表
        top_k: 返回前k个最匹配角色
        domain: 可选，指定任务域
    
    Returns:
        匹配的角色列表，按分数降序
    """
    # L1: 判断任务域
    if domain is None:
        domain = classify_domain(task)
    
    # L2: 获取技能类型
    skills = classify_skills(task, domain)
    
    # L3: 计算所有角色分数
    scored_roles = []
    for role in roles:
        score = calculate_role_score(role, task, domain, skills)
        if score > 0:
            scored_roles.append({
                "role": role,
                "score": score,
                "domain": domain,
                "skills": skills
            })
    
    # 排序并返回top_k
    scored_roles.sort(key=lambda x: x["score"], reverse=True)
    return scored_roles[:top_k]


class RoleHierarchicalMatcher:
    """Sindri角色分层匹配器类"""
    
    def __init__(self, registry_path: str = None):
        if registry_path is None:
            import os
            registry_path = os.path.join(
                os.path.dirname(__file__),
                "../scripts/roles_registry.json"
            )
        
        with open(registry_path) as f:
            data = json.load(f)
            self.roles = data.get('roles', [])
    
    def classify(self, task: str) -> dict:
        """完整分类结果"""
        domain = classify_domain(task)
        skills = classify_skills(task, domain)
        matched = match_roles(task, self.roles, top_k=5, domain=domain)
        
        return {
            "task": task,
            "domain": domain,
            "skills": skills,
            "matched_roles": matched
        }
    
    def match(self, task: str, top_k: int = 5) -> List[dict]:
        """直接匹配角色"""
        domain = classify_domain(task)
        skills = classify_skills(task, domain)
        return match_roles(task, self.roles, top_k=top_k, domain=domain)


if __name__ == "__main__":
    # 测试
    matcher = RoleHierarchicalMatcher()
    
    test_tasks = [
        "修复Python代码bug",
        "设计一个Blender动画",
        "做市场调研报告",
        "开发React前端页面",
    ]
    
    for task in test_tasks:
        result = matcher.classify(task)
        print(f"\n任务: {task}")
        print(f"  域: {result['domain']}")
        print(f"  技能: {result['skills']}")
        print(f"  匹配角色:")
        for m in result['matched_roles'][:3]:
            print(f"    - {m['role']['name']} (score: {m['score']:.1f})")
