# Oh-My-Codex 参考分析
_生成时间: 2026-04-14_
_目的: 为sindris改进提供参考_

---

## Oh-My-Codex 核心架构

### 1. Agent Catalog

oh-my-codex有6个预定义角色：

```typescript
const OMX_AGENT_CATALOG = [
  {
    id: "architect",
    role: "Architecture and tradeoff analysis",
    defaultSkill: "$architect",
    description: "Maps boundaries, interfaces, risks, and sequencing before implementation begins.",
    allowedTools: ["omx_state_*", "omx_explore_*", "omx_note_*", "omx_memory_*"],
    escalationRules: ["Escalate when scope crosses multiple systems or durable data migrations."],
    verifyContract: ["Produces plan slices", "Names verification commands", "Calls out blast radius"],
    runtimeMode: "solo",
  },
  {
    id: "executor", 
    role: "Focused implementation",
    defaultSkill: "$executor",
    description: "Takes a scoped plan slice, builds it, and records verification evidence.",
    allowedTools: ["omx_task_*", "omx_state_*", "omx_note_*", "omx_explore_*", "omx_team_*"],
    escalationRules: ["Escalate when the task is blocked, underspecified, or requires review."],
    verifyContract: ["Owns one slice", "Records commands run", "Hands off to review"],
    runtimeMode: "team",
  },
  {
    id: "reviewer",
    role: "Verification and regression review",
    defaultSkill: "$reviewer",
    description: "Audits changed code, coverage, docs drift, and remaining risk before landing.",
    allowedTools: ["omx_task_*", "omx_state_*", "omx_explore_*", "omx_team_*"],
    escalationRules: ["Escalate when findings are ambiguous or high-risk."],
    verifyContract: ["Lists findings first", "Names missing tests", "States residual risk"],
    runtimeMode: "review",
  },
  {
    id: "operator",
    role: "Durable runtime operator",
    defaultSkill: "$team",
    description: "Runs tmux-backed workers, leases, inbox routing, and review flow for larger work.",
    allowedTools: ["omx_team_*", "omx_task_*", "omx_state_*", "omx_note_*"],
    escalationRules: ["Escalate when tmux or worker health is degraded."],
    verifyContract: ["Keeps queue moving", "Keeps workers healthy", "Keeps inbox actionable"],
    runtimeMode: "team",
  },
  // ...
];
```

**关键字段：**
| 字段 | 说明 |
|------|------|
| `id` | 唯一标识 |
| `role` | 角色描述 |
| `defaultSkill` | 默认绑定的skill |
| `allowedTools` | 允许的工具（通配符） |
| `escalationRules` | 升级条件 |
| `verifyContract` | 验证契约 |
| `runtimeMode` | 运行模式：solo/team/review |

---

## Sindris可以借鉴的设计

### 1. 角色目录结构化

**现状**: sindris用178角色库，向量匹配

**改进**: 添加verifyContract和escalationRules

```python
# sindris/roles/engineering_architect.py
ENGINEERING_ARCHITECT = {
    "id": "engineering_software_architect",
    "name": "Software Architect",
    "category": "engineering",
    "description": "Maps boundaries, interfaces, risks, and sequencing before implementation begins.",
    "allowed_tools": ["read", "exec", "edit", "write", "browser"],
    "escalation_rules": [
        "Escalate when scope crosses multiple systems",
        "Escalate when durable data migrations are needed",
    ],
    "verify_contract": [
        "Produces plan slices",
        "Names verification commands",
        "Calls out blast radius"
    ],
    "runtime_mode": "solo",  # solo, team, review
}
```

### 2. 任务理解 + 角色匹配

**现状**: 任务理解不准确，匹配到UI Designer

**改进**: 添加任务类型识别

```python
# sindris/modules/task_classifier.py
TASK_TYPE_PATTERNS = {
    "engineering": [
        "实现", "开发", "代码", "python", "修复", "优化",
        "模块", "组件", "系统", "架构", "接口",
        "记忆殿堂", "sindris", "mimir", "进化", "融合"
    ],
    "design": [
        "界面", "ui", "ux", "设计", "布局", "配色"
    ],
    "research": [
        "分析", "调研", "研究", "学习", "对比"
    ],
    "testing": [
        "测试", "验证", "检查", "审查"
    ],
}

def classify_task(self, task: str) -> str:
    """根据关键词识别任务类型"""
    task_lower = task.lower()
    scores = {}
    
    for task_type, keywords in TASK_TYPE_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in task_lower)
        scores[task_type] = score
    
    return max(scores, key=scores.get)
```

### 3. 角色 → Engineering优先

**现状**: "记忆殿堂"匹配到UI Designer

**改进**: engineering任务强制使用engineering角色

```python
def match_roles(self, task: str, subtasks: List[Subtask]) -> List[Role]:
    """混合角色匹配"""
    
    # 1. 任务类型识别
    task_type = self.classify_task(task)
    
    # 2. 如果是engineering任务，使用固定团队
    if task_type == "engineering":
        return self._get_fixed_engineering_team()
    
    # 3. 否则用向量相似度
    return self._vector_match(task, subtasks)

def _get_fixed_engineering_team(self) -> List[Role]:
    """工程任务固定团队"""
    return [
        get_role("engineering_software_architect"),
        get_role("engineering_senior_developer"),
        get_role("testing_api_tester"),
        get_role("testing_reality_checker"),
    ]
```

---

## Oh-My-Codex的Runtime机制

### Ledger（任务分类账）

```typescript
interface OmxLedgerEntry {
  id: string;
  kind: "task" | "worker" | "review" | "session";
  action: string;
  detail: string;
  actor?: string;
  taskId?: string;
  workerId?: string;
  metadata: Record<string, unknown>;
  createdAt: string;
}
```

**Ledger vs Sindris OMX:**
- oh-my-codex: 轻量JSON，无阶段
- sindris: 有Round1-4阶段，有状态

**可以借鉴**: 添加taskId和workerId追踪

---

## 关键差异总结

| 维度 | Oh-My-Codex | Sindris |
|------|-------------|---------|
| 角色定义 | 结构化Catalog | 178角色库JSON |
| 工具约束 | 预定义 | 每个角色不同 |
| 验证契约 | verifyContract字段 | 无 |
| 升级规则 | escalationRules | 无 |
| 团队执行 | tmux workers | sessions_spawn |
| 状态持久化 | .omx/ledger | OMX JSON |

---

## Sindris改进优先级

| 优先级 | 改进项 | 借鉴来源 |
|--------|--------|----------|
| P0 | 任务类型识别 | TASK_TYPE_PATTERNS |
| P0 | 固定工程团队 | engineering任务优先 |
| P1 | verifyContract | OMX角色定义 |
| P1 | escalationRules | OMX角色定义 |
| P2 | 自动执行 | team.ts workers |

---

_参考: oh-my-codex/packages/core/src/agents.ts, runtime.ts, team.ts_
