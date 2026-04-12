# Sindri's Role Matching Script — Architecture Design

> **脚本路径**: `~/.openclaw/skills/sindris/scripts/match_roles.py`
> **注册表**: `~/.openclaw/projects/agency-agents/roles_registry.json` (178 角色, 22 类别)

---

## 1. Overview

`match_roles.py` provides automated role matching for the Sindri's multi-agent workflow system. Given a set of task keywords and optional category filters, it scores every role in the registry and returns the top-K most relevant matches with a normalized `match_score`.

---

## 2. Scoring Algorithm

### 2.1 Tokenization
All text fields are normalized via `tokenize(text)`:
- Lowercase conversion
- Regex: `[a-z0-9]+` — strips punctuation and whitespace
- Returns a **set** of unique tokens for Jaccard comparison

### 2.2 Weighted Jaccard Scoring

Each role field contributes to the total score with a predefined weight:

| Field             | Weight | Rationale                                    |
|-------------------|--------|----------------------------------------------|
| `trigger_keywords`| **3.0**| Highest signal — explicit task alignment     |
| `name`            | 1.5    | Role name directly encodes intent            |
| `description`     | 1.0    | Rich semantic content                        |
| `vibe`            | 0.8    | Personality/working-style cue (lower weight) |

**Per-field Jaccard:**
```
jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

**Normalized score per role:**
```
score(role) = Σ(weight_field × jaccard(query_tokens, field_tokens)) / Σ(weights)
```
Result is in **[0, 1]** range.

### 2.3 Threshold & Ranking
- Roles with `score < 0.05` are discarded
- Remaining roles sorted **descending** by score
- Top-K returned (default K=10)

---

## 3. API Reference

### `match_roles(task_keywords, categories?, top_k?) → dict`

**Parameters:**
- `task_keywords: list[str]` — keywords describing the task (e.g. `["performance", "optimization"]`)
- `categories: list[str] | None` — filter to specific categories (e.g. `["engineering", "testing"]`)
- `top_k: int` — max results to return (default: 10)

**Returns:**
```json
{
  "matched_roles": [
    {
      "id": "testing_performance_benchmarker",
      "name": "Performance Benchmarker",
      "category": "testing",
      "description": "Expert performance testing and optimization specialist...",
      "vibe": "Measures everything, optimizes what matters...",
      "match_score": 0.2579
    }
  ],
  "total_candidates": 3
}
```

---

### `list_categories() → dict`

Returns all categories with role counts.

```json
{
  "categories": {
    "academic": 5,
    "engineering": 26,
    "testing": 8,
    ...
  },
  "total_roles": 178
}
```

---

### `get_role_by_id(role_id) → dict | None`

Full role record by exact ID match. Includes `emoji` and `trigger_keywords`.

---

## 4. CLI Interface

```bash
# Match roles
python match_roles.py match performance optimization --categories engineering testing --top-k 5

# List all categories
python match_roles.py categories

# Get single role
python match_roles.py get testing_performance_benchmarker
```

---

## 5. Category Map (22 categories)

| Category          | Count |
|-------------------|-------|
| academic          | 5     |
| blender           | 1     |
| coordination      | 2     |
| design            | 8     |
| engineering       | 26    |
| game-development  | 5     |
| godot             | 3     |
| marketing         | 29    |
| paid-media        | 7     |
| playbooks         | 7     |
| product           | 5     |
| project-management| 6     |
| roblox-studio     | 3     |
| runbooks          | 4     |
| sales             | 8     |
| spatial-computing  | 6     |
| specialized       | 28    |
| strategy          | 3     |
| support           | 6     |
| testing           | 8     |
| unity             | 4     |
| unreal-engine     | 4     |

---

## 6. Design Rationale

### Why Jaccard over BM25/TF-IDF?
- **178 roles** is a small corpus — full inverted-index scoring is overkill
- Jaccard on token sets is fast, interpretable, and adequate for keyword→role matching
- For a larger registry (1000+ roles), upgrading to BM25 is trivial

### Why per-field weights?
- `trigger_keywords` has weight 3.0 because it is the most explicit alignment signal
- `vibe` has weight 0.8 because it is stylistic/ambient, not task-critical
- Weighted sum with normalization keeps scores comparable across queries

### Caching
- `_cached_registry` singleton avoids repeated JSON parsing on repeated calls within a session

---

## 7. Extension Points

1. **Upgrade to BM25**: Replace `jaccard()` with `rank_bm25.BM25Okapi` when corpus grows
2. **Semantic search**: Embed descriptions via `sentence-transformers` and use cosine similarity
3. **Multi-keyword boosting**: Add exact multi-token phrase matching as a bonus signal
4. **Adaptive weights**: Learn optimal field weights from outcome feedback (配对 `foundry_track_outcome`)
