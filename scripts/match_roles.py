#!/usr/bin/env python3
"""
Sindri's Role Matching Script
==============================
Architecture: TF-IDF inspired scoring for role matching against a 178-role registry.

Scoring Strategy (weight hierarchy):
  1. trigger_keywords   (weight 3.0) - exact/partial match, highest signal
  2. description        (weight 1.0) - semantic content
  3. name               (weight 1.5) - role name carries intent
  4. vibe               (weight 0.8) - personality/working style cue

Algorithm:
  - Tokenize query and role fields (lowercase, alpha only)
  - Compute weighted Jaccard similarity per field
  - Aggregate weighted scores → normalized 0-1 match_score

Usage:
  from match_roles import match_roles, list_categories, get_role_by_id
  result = match_roles(["performance", "optimization"], categories=["engineering"])
"""

import json
import os
import re
import math
from pathlib import Path
from typing import Optional

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
MIN_SCORE = 0.020  # discard roles below this threshold (lowered from 0.035 for better recall with short/rare queries)

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
    "进化": "evolution improve growth",
    "自进化": "self-improvement automation",
    "自我进化": "self-improvement automation testing",
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

def score_role(query_tokens: set[str], role: dict) -> float:
    """Compute weighted aggregate score for a single role."""
    total = 0.0

    # 1. trigger_keywords — exact token overlap (highest weight)
    kw_tokens = set()
    for kw in role.get("trigger_keywords", []):
        kw_tokens.update(tokenize(kw))
    kw_score = jaccard(query_tokens, kw_tokens)
    
    # Bonus: substring/subtoken match for trigger_keywords (catches "bugfix" matching "fix")
    if kw_score == 0.0 and query_tokens:
        for qt in query_tokens:
            for kw in role.get("trigger_keywords", []):
                kw_lower = kw.lower()
                if qt in kw_lower or kw_lower in qt:
                    kw_score = 0.05  # small partial match bonus
                    break
            if kw_score > 0:
                break
    
    total += WEIGHTS["trigger_keywords"] * kw_score

    # 2. description — token overlap with full description
    desc_tokens = tokenize(role.get("description", ""))
    desc_score = jaccard(query_tokens, desc_tokens)
    
    # Bonus: substring match for description (catches "fix" in descriptions)
    # Apply when jaccard is small (< 0.05) AND query token is found as substring
    # Set to 0.15 which gives normalized contribution of ~0.024 (passes MIN_SCORE=0.02)
    if desc_score < 0.05 and query_tokens:
        desc_text = role.get("description", "").lower()
        for qt in query_tokens:
            if qt in desc_text:
                desc_score = 0.15  # substantial boost when substring matches
                break
    
    total += WEIGHTS["description"] * desc_score

    # 3. name — token overlap with role name
    name_tokens = tokenize(role.get("name", ""))
    total += WEIGHTS["name"] * jaccard(query_tokens, name_tokens)

    # 4. vibe — token overlap with vibe phrase
    vibe_tokens = tokenize(role.get("vibe", ""))
    total += WEIGHTS["vibe"] * jaccard(query_tokens, vibe_tokens)

    # Normalize by sum of weights to get 0-1 range
    weight_sum = sum(WEIGHTS.values())
    return total / weight_sum

# ── Core API ───────────────────────────────────────────────────────────────────

def match_roles(
    task_keywords: list[str],
    categories: Optional[list[str]] = None,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    """
    Match roles from the registry based on task keywords.

    Args:
        task_keywords: List of keywords describing the task. Accepts both list[str] and str.
        categories:    Optional list of categories to filter (e.g. ["engineering", "testing"]). Must be list or None.
        top_k:         Maximum number of roles to return.

    Returns:
        JSON-serializable dict with matched_roles list.
    
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

    # Expand Chinese keywords to English and tokenize query once
    query_tokens: set[str] = set()
    for kw in task_keywords:
        expanded = expand_query(kw)
        query_tokens.update(tokenize(expanded))

    # Score every role
    scored = []
    for role in all_roles:
        score = score_role(query_tokens, role)
        if score >= MIN_SCORE:
            scored.append((score, role))

    # Sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)

    matched = []
    for score, role in scored[:top_k]:
        matched.append({
            "id":          role["id"],
            "name":        role.get("name", ""),
            "category":    role.get("category", ""),
            "description": role.get("description", ""),
            "vibe":        role.get("vibe", ""),
            "match_score": round(score, 4),
        })

    return {"matched_roles": matched, "total_candidates": len(scored)}


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

    parser = argparse.ArgumentParser(description="Sindri's Role Matcher")
    sub = parser.add_subparsers(dest="command")

    # match subcommand
    m = sub.add_parser("match", help="Match roles by keywords")
    m.add_argument("keywords", nargs="+", help="Task keywords")
    m.add_argument("--categories", "-c", nargs="*", help="Filter by category")
    m.add_argument("--top-k", "-k", type=int, default=DEFAULT_TOP_K)

    # categories subcommand
    sub.add_parser("categories", help="List all categories")

    # get subcommand
    g = sub.add_parser("get", help="Get role by id")
    g.add_argument("role_id", help="Role id to look up")

    args = parser.parse_args()

    if args.command == "match":
        result = match_roles(args.keywords, categories=args.categories, top_k=args.top_k)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "categories":
        print(json.dumps(list_categories(), indent=2, ensure_ascii=False))
    elif args.command == "get":
        role = get_role_by_id(args.role_id)
        if role:
            print(json.dumps(role, indent=2, ensure_ascii=False))
        else:
            print(f"Role '{args.role_id}' not found.")
    else:
        parser.print_help()
