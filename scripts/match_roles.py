#!/usr/bin/env python3
"""
Sindri's Role Matching Script - Enhanced Version
==============================================
Improvements over original:
  1. Task-type awareness (code/research/write/coordination)
  2. Role exclusivity rules (mutually exclusive roles)
  3. Structured output with match reasoning

Architecture: TF-IDF inspired scoring for role matching against a 178-role registry.

Scoring Strategy (weight hierarchy):
  1. trigger_keywords   (weight 3.0) - exact/partial match, highest signal
  2. description        (weight 1.0) - semantic content
  3. name              (weight 1.5) - role name carries intent
  4. vibe              (weight 0.8) - personality/working style cue

Algorithm:
  - Tokenize query and role fields (lowercase, alpha only)
  - Compute weighted Jaccard similarity per field
  - Aggregate weighted scores → normalized 0-1 match_score
  - Apply task-type filtering
  - Apply role exclusivity rules
  - Return structured output with reasoning

Usage:
  from match_roles import match_roles, list_categories, get_role_by_id
  result = match_roles(["performance", "optimization"], categories=["engineering"])
  # Returns structured output with match_reasons
"""

import json
import os
import re
import math
from pathlib import Path
from typing import Optional, Literal

# ── Config ─────────────────────────────────────────────────────────────────────

# 本地角色库（独立sindris）
REGISTRY_PATH = Path(__file__).parent / "roles_registry.json"
# 外部角色库（兼容旧路径）
_EXTERNAL_REGISTRY = Path.home() / ".openclaw" / "projects" / "agency-agents" / "roles_registry.json"

WEIGHTS = {
    "trigger_keywords": 3.0,
    "description": 1.0,
    "name": 1.5,
    "vibe": 0.8,
}

DEFAULT_TOP_K = 10
MIN_SCORE = 0.005  # discard roles below this threshold

# ── Task Type Definitions ─────────────────────────────────────────────────────

# Task type keywords for automatic detection
TASK_TYPE_KEYWORDS = {
    "code": [
        "code", "coding", "program", "develop", "implement", "build", "fix", "bug",
        "debug", "refactor", "api", "function", "class", "module", "script",
        "python", "javascript", "java", "rust", "golang", "后端", "前端", "全栈",
        "代码", "开发", "实现", "修复", "重构",
        "设计并实现", "实现方案", "开发系统",
        "系统", "进化", "方案", "v2", "记忆殿堂"
    ],
    "research": [
        "research", "investigate", "analyze", "survey", "study", "find", "search",
        "explore", "evaluate", "compare", "review", "调研", "研究", "分析", "调查",
        "评估", "比较", "审查"
    ],
    "write": [
        "write", "document", "documentation", "draft", "compose", "author", "create",
        "content", "article", "report", "summary", "explain", "写作", "文档", "撰写",
        "编写", "内容", "文章", "报告"
    ],
    "design": [
        "design", "architecture", "plan", "architect", "structure", "schema",
        "blueprint", "架构", "设计", "规划", "结构"
    ],
    "test": [
        "test", "testing", "QA", "quality", "benchmark", "verify", "validate",
        "unit", "integration", "e2e", "测试", "质量", "验证"
    ],
    "operation": [
        "deploy", "deploy", "operation", "operate", "run", "execute", "maintain",
        "monitor", "devops", "CI", "CD", "运维", "部署", "运行", "维护", "监控"
    ],
}

# 任务类型 -> 偏好角色类别（严格匹配）
CATEGORY_PREFERENCE = {
    "code": ["engineering"],  # 只匹配engineering
    "research": ["academic", "strategy"],  
    "write": ["product", "coordination"],
    "design": ["design", "game-development"],
    "test": ["testing"],
    "operation": ["engineering", "runbooks"],
}

# General purpose terms that are too common to be meaningful discriminators
GENERAL_TERMS = {
    # Programming languages
    "python", "javascript", "java", "rust", "golang", "c++", "c#", "ruby", "php",
    "swift", "kotlin", "typescript", "scala", "perl", "r", "matlab",
    # Generic programming
    "code", "coding", "program", "programming", "script", "scripting",
    "function", "class", "method", "object", "variable", "module",
    "api", "library", "framework", "sdk", "tool", "tools",
    # Bug/fix
    "bug", "bugs", "fix", "fixing", "fixed", "debug", "debugging",
    "error", "errors", "issue", "issues", "problem", "problems",
    "repair", "patch", "patching",
    # Generic actions
    "build", "building", "compile", "compiling",
    "run", "running", "execute", "executing", "start", "starting",
    "create", "creating", "make", "making", "generate", "generating",
    "add", "adding", "update", "updating", "change", "changing",
    "read", "reading", "write", "writing", "edit", "editing",
    # Common adjectives
    "new", "old", "good", "bad", "fast", "slow", "big", "small",
    "simple", "complex", "easy", "hard", "basic", "advanced",
    # Generic nouns
    "data", "file", "files", "content", "task", "tasks", "work",
    "project", "value", "result", "results", "example", "test",
    # More generic
    "world", "worlds", "hello", "hi", "goodbye", "thanks", "please",
    "user", "users", "person", "persons", "people", "man", "woman",
    "computer", "laptop", "phone", "mobile", "server", "client",
    # Chinese
    "代码", "程序", "编程", "开发", "修复", "问题", "错误",
    "添加", "更新", "创建", "生成", "运行", "执行",
}

GENERAL_TERMS_PENALTY = 0.15  # heavily penalize roles matched only on general terms

# Role exclusivity rules: groups of roles that cannot be selected together
# Format: {group_name: [role_id_or_pattern, ...]}
ROLE_EXCLUSIVITY = {
    "domain_experts": {
        # Only one domain expert per task
        "patterns": [r"^finance_", r"^marketing_", r"^sales_", r"^engineering_", r"^product_"],
        "max_per_group": 1,
    },
    "testing_types": {
        # Only one type of testing specialist
        "patterns": [r"testing-performance", r"testing-api", r"testing-accessibility"],
        "max_per_group": 1,
    },
}

# ── Chinese to English Keyword Mapping ────────────────────────────────────────

ZH_TO_EN = {
    # Testing related - order matters, more specific first
    "单元测试": "unit test",
    "集成测试": "integration test",
    "性能测试": "performance benchmark",
    "压力测试": "stress load test",
    "端到端测试": "e2e end-to-end test",
    
    # General testing
    "测试": "test testing QA quality assurance",
    "文档": "documentation",
    "质量": "quality assurance QA",
    
    # Engineering related
    "后端": "backend server",
    "前端": "frontend client UI",
    "架构": "architecture design system",
    "插件": "plugin extension",
    "命令行": "CLI command line",
    "用户界面": "UI interface",
    "任务管理": "task management",
    
    # Security related
    "安全": "security",
    "权限": "permission authorization",
    "认证": "authentication JWT",
    "审计": "audit logging",
    "围栏": "fence isolation",
    
    # Integration related
    "集成": "integration",
    "监控": "monitoring health",
    "熔断": "circuit breaker resilience",
    
    # Evolution / Self-improvement
    "进化": "evolution improve",
    "自进化": "self-improvement automation",
    "自我进化": "self-improvement automation testing",
    
    # Design and architecture
    "设计": "design architecture architect system",
    "设计并实现": "architect system engineering implement",
    "架构": "architecture system design",
    "分析": "analysis research evaluate",
    "写文章": "write article documentation author",
    "技术文章": "technical article documentation",
    
    # Research and analysis
    "研究": "research investigate analyze study",
    "分析": "research analyze evaluation evaluation",
    "调研": "research survey investigation analysis",
    "审查": "review evaluate analysis",
}

def expand_query(text: str) -> str:
    """Expand Chinese keywords to English equivalents."""
    if text is None:
        return ""
    result = text.lower()
    for zh, en in ZH_TO_EN.items():
        if zh in text.lower():
            result += " " + en
    return result

# ── Tokenizer ──────────────────────────────────────────────────────────────────

def tokenize(text: str) -> set[str]:
    """Normalize and tokenize a string into a set of word tokens."""
    # English tokens
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    # Chinese character tokens (each character becomes a token for short queries)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
    for chars in chinese_chars:
        # Split Chinese into 2-3 character chunks for better matching
        for i in range(len(chars) - 1):
            tokens.append(chars[i:i+2])
            if i < len(chars) - 2:
                tokens.append(chars[i:i+3])
    return set(tokens)

# ── Scoring ────────────────────────────────────────────────────────────────────

def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two sets."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def score_role(query_tokens: set[str], role: dict, task_type: Optional[str] = None) -> tuple[float, list[str]]:
    """
    Compute weighted aggregate score for a single role.
    General terms are penalized unless combined with domain-specific terms.
    task_type: 如果指定，根据类型偏好角色类别
    """
    total = 0.0
    reasons = []

    # 如果指定了task_type，检查角色类别是否匹配
    if task_type and task_type in CATEGORY_PREFERENCE:
        preferred = CATEGORY_PREFERENCE[task_type]
        role_category = role.get("category", "").lower()
        role_id = role.get("id", "").lower()
        
        # category必须包含至少一个偏好词，或id以前缀形式匹配（如researcher_xxx）
        # 避免"seo_specialist"被误认为匹配"specialist"类型
        category_match = any(p in role_category for p in preferred)
        # id以前缀_分隔匹配：researcher_xxx -> researcher
        id_match = any(role_id.startswith(p + "_") for p in preferred)
        
        matched = category_match or id_match
        
        # 标记category匹配状态
        if matched:
            reasons.append("category_match_bonus")
            # engineering类型额外bonus
            if role.get("category") == "engineering":
                reasons.append("engineering_bonus")
        else:
            reasons.append("category_penalty")

    # Identify general vs specific tokens
    general_matches = query_tokens & GENERAL_TERMS
    specific_tokens = query_tokens - GENERAL_TERMS
    
    # If only general terms, apply STRONG penalty (95% off)
    use_penalty = len(specific_tokens) == 0 and len(general_matches) > 0
    penalty = GENERAL_TERMS_PENALTY if use_penalty else 1.0
    
    # For trigger_keywords: only use general terms if no specific terms exist
    # AND if the match is ONLY through general terms (not domain-specific)
    if specific_tokens:
        trigger_match_tokens = specific_tokens
    else:
        # Only general terms available - still use them but expect low score
        trigger_match_tokens = query_tokens

    # 1. trigger_keywords - ZERO score if only general terms matched
    kw_tokens = set()
    for kw in role.get("trigger_keywords", []):
        kw_tokens.update(tokenize(kw))
    
    kw_score = jaccard(trigger_match_tokens, kw_tokens)
    
    # If only general terms, ZERO out trigger keyword score completely
    if len(specific_tokens) == 0:
        kw_score = 0
        # No partial match bonus either when only general terms
    
    if kw_score > 0:
        reasons.append("trigger_keywords_match")
    total += WEIGHTS["trigger_keywords"] * kw_score

    # 2. description - use specific tokens if available, otherwise all
    desc_match_tokens = specific_tokens if specific_tokens else query_tokens
    desc_tokens = tokenize(role.get("description", ""))
    desc_score = jaccard(desc_match_tokens, desc_tokens)
    
    # Apply penalty if only general terms matched
    if desc_score > 0 and len(specific_tokens) == 0:
        desc_score *= penalty
    
    if desc_score < 0.05 and desc_match_tokens:
        desc_text = role.get("description", "").lower()
        for qt in desc_match_tokens:
            if qt in desc_text:
                desc_score = 0.05 * penalty  # low substring bonus
                reasons.append(f"substring_in_desc:{qt}")
                break
    
    if desc_score > 0:
        reasons.append("description_match")
    total += WEIGHTS["description"] * desc_score

    # 3. name - use specific tokens if available
    name_tokens = tokenize(role.get("name", ""))
    name_match_tokens = specific_tokens if specific_tokens else query_tokens
    name_score = jaccard(name_match_tokens, name_tokens)
    if name_score > 0 and len(specific_tokens) == 0:
        name_score *= penalty
    if name_score > 0:
        reasons.append("name_match")
    total += WEIGHTS["name"] * name_score

    # 4. vibe - use specific tokens if available
    vibe_tokens = tokenize(role.get("vibe", ""))
    vibe_match_tokens = specific_tokens if specific_tokens else query_tokens
    vibe_score = jaccard(vibe_match_tokens, vibe_tokens)
    if vibe_score > 0 and len(specific_tokens) == 0:
        vibe_score *= penalty
    if vibe_score > 0:
        reasons.append("vibe_match")
    total += WEIGHTS["vibe"] * vibe_score

    # 根据reason应用不同的乘数
    bonus_multiplier = 1.0
    if "category_match_bonus" in reasons:
        bonus_multiplier = 1.5
        if "engineering_bonus" in reasons:
            bonus_multiplier = 2.0  # engineering额外bonus
    elif "category_penalty" in reasons:
        bonus_multiplier = 0.2  # category不匹配时0.2倍
    total *= bonus_multiplier
    
    return total, reasons


def detect_task_type(task_keywords: list[str]) -> Optional[Literal["code", "research", "write", "design", "test", "operation"]]:
    """Detect task type from keywords."""
    query_text = " ".join(task_keywords).lower()
    query_tokens = tokenize(query_text)
    
    # 优先检测中文组合词
    code_indicators = ["实现", "开发", "设计并", "系统设计", "方案设计"]
    for indicator in code_indicators:
        if indicator in query_text:
            return "code"
    
    type_scores = {}
    for task_type, type_keywords in TASK_TYPE_KEYWORDS.items():
        type_tokens = set(tokenize(" ".join(type_keywords)))
        score = jaccard(query_tokens, type_tokens)
        if score > 0:
            type_scores[task_type] = score
    
    if type_scores:
        return max(type_scores, key=type_scores.get)
    return None


def apply_exclusivity(matched_roles: list[dict]) -> list[dict]:
    """
    Apply role exclusivity rules to prevent selecting conflicting roles.
    Returns filtered list keeping higher-scoring roles.
    """
    if len(matched_roles) <= 1:
        return matched_roles
    
    result = []
    used_categories = {}  # track categories already represented
    
    for role in matched_roles:
        category = role.get("category", "").lower()
        role_id = role.get("id", "").lower()
        excluded = False
        
        # Domain experts: only one per major category
        if category in ["finance", "marketing", "sales", "engineering", "product"]:
            if used_categories.get(category, 0) >= 1:
                excluded = True
                role["excluded_reason"] = f"exclusivity:{category}"
        
        if not excluded:
            result.append(role)
            if category in ["finance", "marketing", "sales", "engineering", "product"]:
                used_categories[category] = used_categories.get(category, 0) + 1
    
    return result

# ── Core API ───────────────────────────────────────────────────────────────────

def match_roles(
    task_keywords: list[str],
    categories: Optional[list[str]] = None,
    top_k: int = DEFAULT_TOP_K,
    include_reason: bool = True,
) -> dict:
    """
    Match roles from the registry based on task keywords.

    Args:
        task_keywords: List of keywords describing the task. Accepts both list[str] and str.
        categories:    Optional list of categories to filter (e.g. ["engineering", "testing"]). Must be list or None.
        top_k:         Maximum number of roles to return.
        include_reason: If True, include match reasoning in output.

    Returns:
        JSON-serializable dict with matched_roles list and metadata.
    
    Raises:
        TypeError: If categories is not a list or None.
    """
    # Auto-convert string to list for convenience
    if isinstance(task_keywords, str):
        task_keywords = [task_keywords]
    
    # Type check for categories parameter
    if categories is not None and not isinstance(categories, list):
        raise TypeError(f"categories must be a list or None, got {type(categories).__name__}")
    
    registry = _load_registry()
    all_roles = registry["roles"]

    # Filter by category if specified
    if categories:
        categories_lower = [c.lower() for c in categories]
        all_roles = [
            r for r in all_roles
            if r.get("category", "").lower() in categories_lower
        ]

    # Detect task type from keywords
    task_type = detect_task_type(task_keywords)
    
    # Expand Chinese keywords to English and tokenize query once
    query_tokens: set[str] = set()
    for kw in task_keywords:
        expanded = expand_query(kw)
        query_tokens.update(tokenize(expanded))

    # Score every role
    scored = []
    for role in all_roles:
        score, reasons = score_role(query_tokens, role, task_type)
        if score >= MIN_SCORE:
            role_entry = {
                "id":          role["id"],
                "name":        role.get("name", ""),
                "category":    role.get("category", ""),
                "description": role.get("description", ""),
                "vibe":        role.get("vibe", ""),
                "match_score": round(score, 4),
            }
            if include_reason:
                role_entry["match_reasons"] = reasons
            scored.append((score, role_entry))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    # Extract matched roles
    matched = [role for _, role in scored[:top_k]]
    
    # Apply exclusivity rules
    matched = apply_exclusivity(matched)

    return {
        "matched_roles": matched,
        "total_candidates": len(scored),
        "task_type_detected": task_type,
        "query_tokens": list(query_tokens),
        "applied_exclusivity": True,
    }


def list_categories() -> dict:
    """
    List all unique categories in the registry with role counts.

    Returns:
        dict: { "categories": { "name": count, ... }, "total_roles": N }
    """
    registry = _load_registry()
    counts: dict[str, int] = {}
    for role in registry["roles"]:
        cat = role.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return {
        "categories": dict(sorted(counts.items())),
        "total_roles": len(registry["roles"]),
    }


def get_role_by_id(role_id: str) -> Optional[dict]:
    """
    Retrieve a single role by its id.

    Args:
        role_id: The role's unique id string.

    Returns:
        Role dict if found, else None.
    """
    registry = _load_registry()
    for role in registry["roles"]:
        if role["id"] == role_id:
            return {
                "id":               role["id"],
                "name":             role.get("name", ""),
                "category":         role.get("category", ""),
                "description":      role.get("description", ""),
                "vibe":             role.get("vibe", ""),
                "emoji":            role.get("emoji", ""),
                "trigger_keywords": role.get("trigger_keywords", []),
            }
    return None

# ── Internal ───────────────────────────────────────────────────────────────────

_cached_registry: Optional[dict] = None

def _load_registry() -> dict:
    global _cached_registry
    if _cached_registry is not None:
        return _cached_registry
    path = REGISTRY_PATH
    if not path.exists():
        raise FileNotFoundError(f"roles_registry.json not found at {path}")
    with open(path, encoding="utf-8") as f:
        _cached_registry = json.load(f)
    return _cached_registry

# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sindri's Role Matcher - Enhanced")
    sub = parser.add_subparsers(dest="command")

    # match subcommand
    m = sub.add_parser("match", help="Match roles by keywords")
    m.add_argument("keywords", nargs="+", help="Task keywords")
    m.add_argument("--categories", "-c", nargs="*", help="Filter by category")
    m.add_argument("--top-k", "-k", type=int, default=DEFAULT_TOP_K)
    m.add_argument("--no-reason", action="store_true", help="Skip match reasoning")

    # categories subcommand
    sub.add_parser("categories", help="List all categories")

    # get subcommand
    g = sub.add_parser("get", help="Get role by id")
    g.add_argument("role_id", help="Role id to look up")

    # detect-type subcommand
    t = sub.add_parser("detect-type", help="Detect task type from keywords")
    t.add_argument("keywords", nargs="+", help="Task keywords")

    args = parser.parse_args()

    if args.command == "match":
        result = match_roles(
            args.keywords,
            categories=args.categories,
            top_k=args.top_k,
            include_reason=not args.no_reason
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "categories":
        print(json.dumps(list_categories(), indent=2, ensure_ascii=False))
    elif args.command == "get":
        role = get_role_by_id(args.role_id)
        if role:
            print(json.dumps(role, indent=2, ensure_ascii=False))
        else:
            print(f"Role '{args.role_id}' not found.")
    elif args.command == "detect-type":
        task_type = detect_task_type(args.keywords)
        print(json.dumps({"detected_type": task_type, "keywords": args.keywords}, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
