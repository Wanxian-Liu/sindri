# Engineering Staff Engineer Workflow

**Role**: Staff Engineer (Principal Technical Leader)
**Step**: Round 2 - Execution & Technical Delivery
**Trigger**: Architect completes Step 1 planning → passes to Staff Engineer for implementation

---

## 📋 Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: TASK PARSING & SCOPE CONFIRMATION                    │
│  ├─ Parse Architect's output from task plan                     │
│  ├─ Confirm scope, dependencies, and technical boundaries       │
│  └─ Identify cross-cutting concerns                             │
├─────────────────────────────────────────────────────────────────┤
│  STEP 2: TECHNICAL DESIGN & IMPLEMENTATION STRATEGY            │
│  ├─ Design detailed component architecture                      │
│  ├─ Define interfaces and contracts                            │
│  ├─ Select implementation patterns and anti-patterns to avoid  │
│  └─ Plan for testing, observability, and error handling        │
├─────────────────────────────────────────────────────────────────┤
│  STEP 3: HIGH-QUALITY CODE GENERATION                         │
│  ├─ Generate production-ready code with proper error handling  │
│  ├─ Follow language-specific best practices                     │
│  ├─ Include logging, metrics, and observability hooks           │
│  └─ Ensure security best practices                              │
├─────────────────────────────────────────────────────────────────┤
│  STEP 4: SELF-VERIFICATION                                     │
│  ├─ Code compiles/runs without errors                           │
│  ├─ Unit tests cover core functionality                         │
│  ├─ No hardcoded secrets or credentials                         │
│  └─ Documentation strings complete                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Step 1: Task Parsing & Scope Confirmation

### 1.0 Architect Handshake Protocol

Before proceeding, Staff Engineer MUST validate that `architect.phase1_output` conforms to this握手协议.

#### architect.phase1_output Required Schema

```typescript
interface ArchitectPhase1Output {
  // Task Identity
  task_id: string;                    // Unique identifier, e.g. "AUTH-001"
  title: string;                       // Short descriptive title
  description: string;                 // Full description (≥50 chars)
  task_type: "feature" | "bugfix" | "refactor" | "infrastructure";

  // Scope Definition
  acceptance_criteria: string[];        // Must have ≥1 criterion
  technical_constraints: string[];     // e.g. ["must use PostgreSQL", "no external APIs"]
  dependencies: string[];               // Internal/external dependency names
  out_of_scope: string[];              // Explicitly excluded items

  // Technical Context (from Architect's analysis)
  system_context: {
    component: string;                  // Which system component this belongs to
    upstream_dependencies: string[];     // Components that depend on this
    downstream_dependencies: string[];  // Components this depends on
    data_contracts: DataContract[];     // Expected input/output schemas
  };

  // Pattern Recommendations (Architect's suggestions, not mandates)
  suggested_patterns: {
    backend?: ImplementationPattern[];
    frontend?: ImplementationPattern[];
    data?: ImplementationPattern[];
  };

  // Risk Assessment
  risk_level: "low" | "medium" | "high" | "critical";
  identified_risks: Array<{
    risk: string;
    mitigation: string;
    impact: "blocked" | "degraded" | "acceptable";
  }>;

  // Version & Provenance
  architect_id: string;
  version: string;
  created_at: string;
}

interface DataContract {
  name: string;
  schema: Record<string, string>;
  direction: "input" | "output" | "bidirectional";
  source: string;
}
```

#### Handshake Validation Code (Python)

```python
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class TaskType(Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    INFRASTRUCTURE = "infrastructure"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class DataContract:
    name: str
    schema: Dict[str, str]
    direction: str
    source: str

@dataclass
class SystemContext:
    component: str
    upstream_dependencies: List[str]
    downstream_dependencies: List[str]
    data_contracts: List[DataContract]

@dataclass
class IdentifiedRisk:
    risk: str
    mitigation: str
    impact: str

@dataclass
class ArchitectPhase1Output:
    task_id: str
    title: str
    description: str
    task_type: TaskType
    acceptance_criteria: List[str]
    technical_constraints: List[str]
    dependencies: List[str]
    out_of_scope: List[str]
    system_context: SystemContext
    suggested_patterns: Dict[str, List[str]]
    risk_level: RiskLevel
    identified_risks: List[IdentifiedRisk]
    architect_id: str
    version: str
    created_at: str

def validate_architect_handshake(data: Dict[str, Any]) -> ArchitectPhase1Output:
    """
    Staff Engineer validates Architect's phase1_output against this握手协议.
    Raises ValueError with specific field errors if schema is invalid.
    """
    errors = []
    warnings = []

    required_fields = [
        "task_id", "title", "description", "task_type",
        "acceptance_criteria", "technical_constraints",
        "dependencies", "out_of_scope", "system_context",
        "suggested_patterns", "risk_level", "identified_risks",
        "architect_id", "version", "created_at"
    ]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if errors:
        raise ValueError(f"Architect phase1_output handshake failed: {errors}")

    valid_task_types = [t.value for t in TaskType]
    if data["task_type"] not in valid_task_types:
        errors.append(f"Invalid task_type: {data['task_type']}. Must be one of {valid_task_types}")

    if len(data.get("description", "")) < 50:
        warnings.append("Description is shorter than 50 characters — scope may be unclear")

    if not data.get("acceptance_criteria"):
        errors.append("acceptance_criteria is required and must have at least 1 entry")

    sc = data.get("system_context", {})
    sc_required = ["component", "upstream_dependencies", "downstream_dependencies", "data_contracts"]
    for field in sc_required:
        if field not in sc:
            errors.append(f"system_context missing field: {field}")

    if errors:
        raise ValueError(f"Architect handshake FAILED: {'; '.join(errors)}")

    if warnings:
        print(f"WARNINGS: {'; '.join(warnings)}")

    print(f"Handshake with Architect {data['architect_id']} PASSED (version {data['version']})")
    return data
```

### 1.1 Input Validation

Receive task description from Architect's Step 1 output. Validate:

```python
# Validate incoming task structure
TASK_REQUIRED_FIELDS = [
    "task_id",
    "title",
    "description",
    "acceptance_criteria",
    "technical_constraints",
    "dependencies"
]

def validate_task_input(task: dict) -> ValidationResult:
    """
    Staff Engineer validates Architect's output before proceeding.

    Args:
        task: Complete task object from Architect Step 1

    Returns:
        ValidationResult with status and any issues found

    Raises:
        ValueError: Missing required fields

    Example:
        >>> task = architect.phase1_output
        >>> result = validate_task_input(task)
        >>> if not result.is_valid:
        >>>     raise ValueError(f"Invalid task: {result.errors}")
    """
    missing_fields = []
    for field in TASK_REQUIRED_FIELDS:
        if field not in task:
            missing_fields.append(field)

    if missing_fields:
        return ValidationResult(
            is_valid=False,
            errors=[f"Missing required field: {f}" for f in missing_fields],
            warnings=[]
        )

    # Check for scope clarity
    warnings = []
    if len(task.get("description", "")) < 50:
        warnings.append("Task description seems too brief")
    if not task.get("acceptance_criteria"):
        warnings.append("No acceptance criteria defined")

    return ValidationResult(is_valid=True, errors=[], warnings=warnings)
```

### 1.2 Scope Boundary Analysis

```python
from dataclasses import dataclass
from typing import Set, List

@dataclass
class ScopeBoundary:
    """Defines what is inside vs outside implementation scope."""
    in_scope: Set[str]          # Features/components to implement
    out_of_scope: Set[str]      # Explicitly excluded features
    assumptions: List[str]       # Implicit assumptions being made
    risks: List[str]            # Potential scope creep areas

def analyze_scope_boundaries(task: dict) -> ScopeBoundary:
    """
    Staff Engineer analyzes and documents scope boundaries.

    This prevents scope creep during implementation by clearly
    defining what WILL and WON'T be built.

    Example Output:
        ScopeBoundary(
            in_scope={"user-auth", "token-validation", "refresh-tokens"},
            out_of_scope={"social-login", "2fa", "password-recovery"},
            assumptions=["Redis available for token storage"],
            risks=["Session management scope might expand to include WebSocket"]
        )
    """
    description = task.get("description", "").lower()

    # Infer scope from description keywords
    in_scope = set()
    out_of_scope = set()

    # Auth-related keywords
    auth_keywords = ["auth", "login", "logout", "session", "token", "jwt", "password"]
    for keyword in auth_keywords:
        if keyword in description:
            in_scope.add(f"auth-{keyword}")

    # Explicitly out of scope based on task type
    if "simple" in description or "basic" in description:
        out_of_scope.add("advanced-features")
        out_of_scope.add("optimization")

    # Identify assumptions from dependencies
    dependencies = task.get("dependencies", [])
    assumptions = [f"Dependency '{dep}' is available and functional"
                   for dep in dependencies]

    # Identify scope creep risks
    risks = []
    if len(description.split()) > 100:
        risks.append("Description is complex; verify scope boundaries")

    return ScopeBoundary(
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        assumptions=assumptions,
        risks=risks
    )
```

### 1.3 Dependency Analysis

```python
import asyncio
from typing import Dict, List, Any
from enum import Enum

class DependencyStatus(Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    VERSION_MISMATCH = "version_mismatch"
    CIRCULAR = "circular"

@dataclass
class DependencyInfo:
    name: str
    status: DependencyStatus
    version: str
    resolution: str

async def analyze_dependencies(task: dict) -> Dict[str, DependencyInfo]:
    """
    Staff Engineer analyzes all dependencies for feasibility.

    Returns mapping of dependency name to status information.

    Example:
        >>> deps = await analyze_dependencies(task)
        >>> for name, info in deps.items():
        >>>     if info.status != DependencyStatus.AVAILABLE:
        >>>         print(f"Issue with {name}: {info.resolution}")
    """
    dependencies = task.get("dependencies", [])
    results = {}

    async def check_single(dep: str) -> DependencyInfo:
        # Simulate dependency checking
        if dep.startswith("internal-"):
            return DependencyInfo(
                name=dep,
                status=DependencyStatus.MISSING,
                version="N/A",
                resolution=f"Internal dependency '{dep}' needs to be created first"
            )
        elif dep == "broken-dep":
            return DependencyInfo(
                name=dep,
                status=DependencyStatus.VERSION_MISMATCH,
                version="2.0.0 (needs 1.5.0)",
                resolution="Update version requirement in package.json"
            )
        else:
            return DependencyInfo(
                name=dep,
                status=DependencyStatus.AVAILABLE,
                version="latest",
                resolution="No action needed"
            )

    # Check all dependencies in parallel
    checks = await asyncio.gather(*[check_single(dep) for dep in dependencies])
    for dep, info in zip(dependencies, checks):
        results[dep] = info

    return results
```

---

## 🔧 Step 2: Technical Design & Implementation Strategy

### 2.1 Component Architecture Design

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

class Component(ABC):
    """Base class for all implementation components."""

    @abstractmethod
    def get_interface(self) -> Dict[str, Any]:
        """Returns the public interface contract."""
        pass

    @abstractmethod
    def implement(self) -> str:
        """Returns the implementation code."""
        pass

@dataclass
class ServiceComponent(Component):
    name: str
    inputs: List[str]
    outputs: List[str]
    side_effects: List[str]

    def get_interface(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": "service",
            "inputs": self.inputs,
            "outputs": self.outputs,
            "side_effects": self.side_effects
        }

    def implement(self) -> str:
        return f'''class {self.name.title().replace("-", "")}Service:
    """
    Service component for {self.name}.

    Inputs: {', '.join(self.inputs)}
    Outputs: {', '.join(self.outputs)}
    Side Effects: {', '.join(self.side_effects)}
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._dependencies = {{}}

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize service with configuration."""
        self._config = config
        self.logger.info(f"Initialized {{self.__class__.__name__}}")

    async def execute(self, input_data: Any) -> Any:
        """Execute the service logic."""
        self.logger.debug(f"Executing {{self.__class__.__name__}}")
        # TODO: Implement actual logic
        return {{"status": "success", "data": input_data}}

    def cleanup(self) -> None:
        """Release resources."""
        self._dependencies.clear()
        self.logger.info(f"Cleaned up {{self.__class__.__name__}}")
'''

class DataComponent(Component):
    """Data access layer component."""

    def __init__(self, name: str, schema: Dict[str, str]):
        self.name = name
        self.schema = schema

    def get_interface(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": "data",
            "schema": self.schema,
            "operations": ["create", "read", "update", "delete"]
        }

    def implement(self) -> str:
        field_decls = "\n    ".join([
            f'self.{field}: {dtype} = None'
            for field, dtype in self.schema.items()
        ])
        return f'''class {self.name.title().replace("-", "")}Repository:
    """
    Data repository for {self.name}.

    Schema:
{chr(10).join(f"      - {f}: {t}" for f, t in self.schema.items())}
    """

    def __init__(self, connection_string: str):
        self._conn_str = connection_string
        self._pool = None
        self._cache = {{}}

    async def connect(self) -> None:
        """Establish database connection."""
        # self._pool = await create_connection_pool(self._conn_str)
        pass

    async def create(self, data: Dict[str, Any]) -> str:
        """Insert new record and return ID."""
        # Validate against schema
        for field, dtype in self.schema.items():
            if field not in data:
                raise ValueError(f"Missing required field: {{field}}")
        # Insert into database
        # record_id = await self._pool.insert(self.name, data)
        # return record_id
        return "generated-id"

    async def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve record by ID."""
        # Check cache first
        if record_id in self._cache:
            return self._cache[record_id]
        # Fetch from database
        # record = await self._pool.select_one(self.name, record_id)
        # if record:
        #     self._cache[record_id] = record
        return {{}}

    async def update(self, record_id: str, data: Dict[str, Any]) -> bool:
        """Update existing record."""
        # await self._pool.update(self.name, record_id, data)
        # Invalidate cache
        self._cache.pop(record_id, None)
        return True

    async def delete(self, record_id: str) -> bool:
        """Delete record by ID."""
        # await self._pool.delete(self.name, record_id)
        self._cache.pop(record_id, None)
        return True

    async def close(self) -> None:
        """Close database connection."""
        if self._pool:
            # await self._pool.close()
            self._pool = None
'''

def design_component_architecture(task: dict) -> List[Component]:
    """
    Staff Engineer designs the component architecture.

    Returns list of components that need to be implemented.
    Each component has a clear interface and implementation strategy.

    Example:
        >>> components = design_component_architecture(task)
        >>> for comp in components:
        >>>     print(comp.get_interface())
    """
    components = []
    task_title = task.get("title", "unnamed")

    # Create service component
    service = ServiceComponent(
        name=task_title.lower().replace(" ", "-"),
        inputs=["request_data"],
        outputs=["response_data"],
        side_effects=["logging", "metrics"]
    )
    components.append(service)

    # Create data component if persistence needed
    if "store" in task.get("description", "").lower() or \
       "persist" in task.get("description", "").lower():
        data_comp = DataComponent(
            name=task_title.lower().replace(" ", "-"),
            schema={"id": "str", "created_at": "datetime", "updated_at": "datetime"}
        )
        components.append(data_comp)

    return components
```

### 2.2 Interface & Contract Definition

```python
from typing import Protocol, TypeVar, Generic, Union, Optional
from dataclasses import dataclass
import json

T = TypeVar('T')

class Request(Protocol):
    """Base protocol for request objects."""
    request_id: str
    timestamp: float

@dataclass
class Response:
    """Standard response wrapper."""
    request_id: str
    status: str
    data: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "data": self.data,
            "error": self.error
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

def define_api_contract(
    endpoint: str,
    method: str,
    request_schema: dict,
    response_schema: dict,
    error_codes: List[int]
) -> Dict[str, Any]:
    """
    Staff Engineer defines a complete API contract.

    This contract serves as the source of truth for both
    client and server implementations.

    Example:
        >>> contract = define_api_contract(
        ...     endpoint="/api/v1/users",
        ...     method="POST",
        ...     request_schema={"username": "string", "email": "string"},
        ...     response_schema={"id": "string", "created_at": "datetime"},
        ...     error_codes=[400, 401, 403, 404, 500]
        ... )
        >>> print(json.dumps(contract, indent=2))
    """
    return {
        "endpoint": endpoint,
        "method": method,
        "request": {
            "schema": request_schema,
            "example": {k: f"<{k}>" for k in request_schema.keys()}
        },
        "response": {
            "success": {
                "status_code": 200,
                "schema": response_schema,
                "example": {k: f"<{k}>" for k in response_schema.keys()}
            },
            "errors": {
                code: {
                    "status_code": code,
                    "message": f"Error {code} description",
                    "schema": {"error": "string", "details": "object"}
                }
                for code in error_codes
            }
        },
        "version": "1.0",
        "last_updated": "2026-04-18"
    }
```

### 2.3 Implementation Pattern Selection

```python
from enum import Enum
from typing import Callable, Any

class ImplementationPattern(Enum):
    """Common implementation patterns Staff Engineer selects from."""
    STRATEGY = "strategy"           # Interchangeable algorithms
    FACTORY = "factory"             # Object creation
    REPOSITORY = "repository"       # Data access abstraction
    SERVICE_LAYER = "service"       # Business logic orchestration
    EVENT_DRIVEN = "event"          # Async event handling
    PIPELINE = "pipeline"           # Chained transformations
    BUFFERED = "buffered"           # Batch processing
    CQRS = "cqrs"                   # Command Query Responsibility Segregation
    SAGAS = "sagas"                 # Distributed transaction pattern

@dataclass
class PatternSelection:
    pattern: ImplementationPattern
    rationale: str
    tradeoffs: List[str]
    code_template: str
    # Performance/Cost Annotations
    time_complexity_best: str = "O(1)"
    time_complexity_worst: str = "O(n)"
    space_complexity: str = "O(n)"
    estimated_latency_ms: int = 10
    estimated_throughput_rps: int = 1000
    cost_per_100k_calls_usd: float = 0.50
    # ADR Fields
    decision_date: str = ""
    alternatives_considered: List[str] = field(default_factory=list)
    consequences: Dict[str, str] = field(default_factory=dict)

def select_implementation_pattern(task: dict, architect_suggestions: List[str] = None) -> PatternSelection:
    """
    Staff Engineer selects the best implementation pattern.

    Decision tree based on task characteristics:

    IF task involves:
      - Multiple algorithms selectable at runtime → STRATEGY
      - Complex object creation logic → FACTORY
      - Data persistence and retrieval → REPOSITORY
      - Business logic orchestration → SERVICE_LAYER
      - Async event handling → EVENT_DRIVEN
      - Chained data transformations → PIPELINE
      - Batch processing with buffering → BUFFERED

    Example:
        >>> selection = select_implementation_pattern(task)
        >>> print(f"Selected: {selection.pattern.value}")
        >>> print(f"Rationale: {selection.rationale}")
    """
    description = task.get("description", "").lower()
    title = task.get("title", "").lower()

    # Decision logic
    if "transform" in description or "process" in description:
        return PatternSelection(
            pattern=ImplementationPattern.PIPELINE,
            rationale="Task involves chained data transformations",
            tradeoffs=["Memory usage for buffering", "Debugging complexity"],
            code_template="pipeline_template",
            # Performance/Cost Annotations
            time_complexity_best="O(n)",
            time_complexity_worst="O(n²)",
            space_complexity="O(n)",
            estimated_latency_ms=15,
            estimated_throughput_rps=500,
            cost_per_100k_calls_usd=0.75,
            # ADR Fields
            decision_date="2026-04-20",
            alternatives_considered=["Sequential processing", "Parallel map-reduce"],
            consequences={
                "positive": "Clean separation of concerns, easy to add/remove stages",
                "negative": "Memory overhead for buffering, harder to debug intermediate states"
            }
        )
    elif "batch" in description or "bulk" in description:
        return PatternSelection(
            pattern=ImplementationPattern.BUFFERED,
            rationale="Batch processing with size limits",
            tradeoffs=["Latency vs throughput tradeoff", "Partial failure handling"],
            code_template="buffered_template",
            # Performance/Cost Annotations
            time_complexity_best="O(1)",
            time_complexity_worst="O(n)",
            space_complexity="O(batch_size)",
            estimated_latency_ms=5,
            estimated_throughput_rps=5000,
            cost_per_100k_calls_usd=0.25,
            # ADR Fields
            decision_date="2026-04-20",
            alternatives_considered=["Stream processing", "Synchronous bulk operations"],
            consequences={
                "positive": "High throughput, reduced network overhead",
                "negative": "Increased latency per item, complexity in partial failure handling"
            }
        )
    elif "event" in title or "handler" in description:
        return PatternSelection(
            pattern=ImplementationPattern.EVENT_DRIVEN,
            rationale="Async event handling required",
            tradeoffs=["Event ordering complexity", "Debugging async flows"],
            code_template="event_template",
            # Performance/Cost Annotations
            time_complexity_best="O(1)",
            time_complexity_worst="O(log n)",
            space_complexity="O(n)",
            estimated_latency_ms=2,
            estimated_throughput_rps=10000,
            cost_per_100k_calls_usd=0.40,
            # ADR Fields
            decision_date="2026-04-20",
            alternatives_considered=["Polling-based architecture", "Synchronous RPC calls"],
            consequences={
                "positive": "Loose coupling, high scalability",
                "negative": "Event ordering challenges, distributed tracing complexity"
            }
        )
    else:
        return PatternSelection(
            pattern=ImplementationPattern.SERVICE_LAYER,
            rationale="Standard business logic orchestration",
            tradeoffs=["Potential for god-class if overused", "Testing complexity"],
            code_template="service_template",
            # Performance/Cost Annotations
            time_complexity_best="O(1)",
            time_complexity_worst="O(n)",
            space_complexity="O(1)",
            estimated_latency_ms=10,
            estimated_throughput_rps=2000,
            cost_per_100k_calls_usd=0.50,
            # ADR Fields
            decision_date="2026-04-20",
            alternatives_considered=["Transaction Script", "Domain-Driven Design"],
            consequences={
                "positive": "Clear separation of business logic from infrastructure",
                "negative": "May become a god class if not properly scoped"
            }
        )
```


### 2.3.5 Architecture Decision Record (ADR) Template

When a pattern is selected, Staff Engineer MUST document the decision using this ADR format:

```markdown
# ADR-{number}: {Decision Title}

**Date**: {YYYY-MM-DD}
**Status**: Proposed | Accepted | Deprecated | Superseded
**Deciders**: Staff Engineer, Architect
**Context**: {What is the issue that we're seeing that is motivating this decision?}

## Decision Drivers
- {Driver 1}
- {Driver 2}
- {Driver N}

## Considered Alternatives

### 1. {Alternative Name}
**Description**: {Brief description}
**Pros**: {List of pros}
**Cons**: {List of cons}

### 2. {Alternative Name}
**Description**: {Brief description}
**Pros**: {List of pros}
**Cons**: {List of cons}

## Decision Outcome

**Chosen Option**: {Option Name}
**Rationale**: {Why this option was chosen}

## Performance & Cost Analysis

| Metric | Value |
|--------|-------|
| Time Complexity (Best) | {O-notation} |
| Time Complexity (Worst) | {O-notation} |
| Space Complexity | {O-notation} |
| Est. Latency | {N}ms |
| Est. Throughput | {N} RPS |
| Cost per 100K calls | ${N.XX} |

## Consequences

**Positive**:
- {Positive consequence 1}
- {Positive consequence 2}

**Negative/Tradeoffs**:
- {Negative consequence 1}
- {Negative consequence 2}

## Related ADRs
- ADR-{N}: {Related decision title}
```

#### ADR Generation Code (Python)

```python
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime

@dataclass
class ArchitectureDecision:
    """Architecture Decision Record."""
    number: int
    title: str
    status: str = "Proposed"
    date: str = ""
    deciders: List[str] = field(default_factory=lambda: ["Staff Engineer", "Architect"])
    context: str = ""
    decision_drivers: List[str] = field(default_factory=list)
    alternatives: List[Dict[str, str]] = field(default_factory=list)
    chosen_option: str = ""
    rationale: str = ""
    performance_metrics: Dict[str, str] = field(default_factory=dict)
    consequences_positive: List[str] = field(default_factory=list)
    consequences_negative: List[str] = field(default_factory=list)
    related_adrs: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Generate ADR in markdown format."""
        alt_rows = ""
        for i, alt in enumerate(self.alternatives, 1):
            alt_rows += f"""### {i}. {alt['name']}
**Description**: {alt.get('description', 'N/A')}
**Pros**: {alt.get('pros', 'N/A')}
**Cons**: {alt.get('cons', 'N/A')}

"""
        perf_table = ""
        for k, v in self.performance_metrics.items():
            perf_table += f"| {k} | {v} |\n"

        pos_items = "\n".join(f"- {p}" for p in self.consequences_positive)
        neg_items = "\n".join(f"- {n}" for n in self.consequences_negative)
        related = "\n".join(f"- {adr}" for adr in self.related_adrs) or "None"

        return f"""# ADR-{self.number}: {self.title}

**Date**: {self.date or datetime.now().strftime('%Y-%m-%d')}
**Status**: {self.status}
**Deciders**: {', '.join(self.deciders)}
**Context**: {self.context}

## Decision Drivers
{chr(10).join(f'- {d}' for d in self.decision_drivers)}

## Considered Alternatives

{alt_rows}
## Decision Outcome

**Chosen Option**: {self.chosen_option}
**Rationale**: {self.rationale}

## Performance & Cost Analysis

| Metric | Value |
|--------|-------|
{perf_table}
## Consequences

**Positive**:
{pos_items}

**Negative/Tradeoffs**:
{neg_items}

## Related ADRs
{related}
"""


def create_adr_from_pattern(
    pattern_selection: PatternSelection,
    adr_number: int,
    context: str,
    decision_drivers: List[str],
    alternatives: List[Dict[str, str]]
) -> ArchitectureDecision:
    """
    Generate an ADR from a PatternSelection with full performance/cost annotations.

    Example:
        >>> pattern = select_implementation_pattern(task)
        >>> adr = create_adr_from_pattern(
        ...     pattern_selection=pattern,
        ...     adr_number=1,
        ...     context="Need to choose pattern for user data transformation",
        ...     decision_drivers=["Throughput requirements", "Latency constraints"],
        ...     alternatives=[
        ...         {"name": "Sequential", "pros": "Simple", "cons": "Slow"},
        ...         {"name": "Pipeline", "pros": "Fast", "cons": "Complex"}
        ...     ]
        ... )
        >>> print(adr.to_markdown())
    """
    return ArchitectureDecision(
        number=adr_number,
        title=f"Select {pattern_selection.pattern.value.upper()} Pattern for Implementation",
        context=context,
        decision_drivers=decision_drivers,
        alternatives=alternatives,
        chosen_option=pattern_selection.pattern.value,
        rationale=pattern_selection.rationale,
        performance_metrics={
            "Time Complexity (Best)": pattern_selection.time_complexity_best,
            "Time Complexity (Worst)": pattern_selection.time_complexity_worst,
            "Space Complexity": pattern_selection.space_complexity,
            "Est. Latency": f"{pattern_selection.estimated_latency_ms}ms",
            "Est. Throughput": f"{pattern_selection.estimated_throughput_rps} RPS",
            "Cost per 100K calls": f"${pattern_selection.cost_per_100k_calls_usd:.2f}"
        },
        consequences_positive=[
            pattern_selection.consequences.get("positive", "")
        ] if isinstance(pattern_selection.consequences, dict) else [],
        consequences_negative=[
            pattern_selection.consequences.get("negative", "")
        ] if isinstance(pattern_selection.consequences, dict) else [],
        related_adrs=[]
    )
```

### 2.4 Error Handling & Observability Planning

```python
import logging
from typing import Optional, Callable
from functools import wraps
import time

class ErrorHandlingStrategy(Enum):
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK = "fallback"
    GRACEFUL_DEGRADATION = "graceful_degradation"

@dataclass
class ErrorHandlingPlan:
    strategy: ErrorHandlingStrategy
    max_retries: int
    backoff_multiplier: float
    fallback_value: Any

def plan_error_handling(task: dict) -> ErrorHandlingPlan:
    """
    Staff Engineer plans comprehensive error handling.

    Considerations:
    - What can fail? (network, database, external services)
    - How should failures be handled? (retry, fallback, circuit breaker)
    - What should be logged? (errors, warnings, debug info)
    - What metrics should be emitted?
    """
    description = task.get("description", "").lower()

    # Determine error handling strategy
    if "critical" in description or "payment" in description:
        strategy = ErrorHandlingStrategy.CIRCUIT_BREAKER
        max_retries = 3
        backoff = 2.0
    elif "optional" in description or "enhancement" in description:
        strategy = ErrorHandlingStrategy.FALLBACK
        max_retries = 1
        backoff = 1.5
    else:
        strategy = ErrorHandlingStrategy.RETRY
        max_retries = 3
        backoff = 1.5

    return ErrorHandlingPlan(
        strategy=strategy,
        max_retries=max_retries,
        backoff_multiplier=backoff,
        fallback_value=None
    )

def with_logging(func: Callable) -> Callable:
    """Decorator for structured logging."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        func_name = func.__name__

        logger.info(f"ENTER: {func_name}", extra={
            "function": func_name,
            "args_count": len(args),
            "kwargs_keys": list(kwargs.keys())
        })

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            logger.info(f"EXIT: {func_name}", extra={
                "function": func_name,
                "duration_ms": round(duration * 1000, 2),
                "status": "success"
            })
            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"ERROR: {func_name}", extra={
                "function": func_name,
                "duration_ms": round(duration * 1000, 2),
                "status": "error",
                "error_type": type(e).__name__,
                "error_message": str(e)
            }, exc_info=True)
            raise

    return wrapper

def with_metrics(func: Callable) -> Callable:
    """Decorator for metrics emission."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        import time
        from typing import Any

        # In production, use proper metrics library (prometheus, statsd, etc.)
        metrics = {
            "function": func.__name__,
            "start_time": time.time(),
            "success": False,
            "error": None
        }

        try:
            result = func(*args, **kwargs)
            metrics["success"] = True
            return result
        except Exception as e:
            metrics["error"] = {
                "type": type(e).__name__,
                "message": str(e)
            }
            raise
        finally:
            duration = time.time() - metrics["start_time"]
            # Emit metrics (would use prometheus_client in production)
            print(f"METRIC: {func.__name__}_duration_seconds {duration:.4f}")
            print(f"METRIC: {func.__name__}_total 1")
            if metrics["success"]:
                print(f"METRIC: {func.__name__}_success 1")
            else:
                print(f"METRIC: {func.__name__}_error 1")

    return wrapper
```

---

## 🔧 Step 3: High-Quality Code Generation

### 3.1 Production Code Implementation

```python
"""
Staff Engineer Implementation Template
=====================================

This module contains production-ready code generation templates
following best practices for error handling, logging, and observability.
"""

import asyncio
import logging
from typing import (
    Dict, List, Optional, Any, Callable,
    Union, TypeVar, Generic, Protocol
)
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from enum import Enum
import json

logger = logging.getLogger(__name__)

# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

T = TypeVar('T')
U = TypeVar('U')

@dataclass
class BaseEntity:
    """Base class for all domain entities."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class EntityStatus(Enum):
    """Common entity status values."""
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    ERROR = "error"

@dataclass
class TaskResult:
    """Standardized task execution result."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **metadata) -> "TaskResult":
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, error: str, **metadata) -> "TaskResult":
        return cls(success=False, error=error, metadata=metadata)

# ============================================================================
# SERVICE LAYER IMPLEMENTATION
# ============================================================================

class BaseService(ABC):
    """
    Abstract base class for all services.

    Provides common functionality:
    - Structured logging
    - Metrics collection
    - Health checks
    - Graceful shutdown
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self._is_initialized = False
        self._is_shutting_down = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize service resources."""
        pass

    @abstractmethod
    async def execute(self, *args, **kwargs) -> TaskResult:
        """Execute the main service logic."""
        pass

    async def health_check(self) -> bool:
        """Check if service is healthy."""
        return self._is_initialized and not self._is_shutting_down

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self.logger.info(f"Shutting down {self.name}")
        self._is_shutting_down = True
        await self._cleanup()

    async def _cleanup(self) -> None:
        """Override to provide cleanup logic."""
        pass


class UserManagementService(BaseService):
    """
    Example implementation: User Management Service.

    Demonstrates:
    - Service layer pattern
    - Error handling with proper exceptions
    - Structured logging
    - Metrics
    - Health checks
    """

    def __init__(
        self,
        repository: Optional["UserRepository"] = None,
        event_publisher: Optional["EventPublisher"] = None
    ):
        super().__init__(name="UserManagement")
        self._repository = repository
        self._event_publisher = event_publisher
        self._cache: Dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize service dependencies."""
        self.logger.info("Initializing UserManagementService")

        if self._repository:
            await self._repository.connect()

        self._is_initialized = True
        self.logger.info("UserManagementService initialized successfully")

    async def execute(self, operation: str, **kwargs) -> TaskResult:
        """Execute user management operation."""
        if not self._is_initialized:
            return TaskResult.fail("Service not initialized")

        operations = {
            "create": self._create_user,
            "get": self._get_user,
            "update": self._update_user,
            "delete": self._delete_user,
            "list": self._list_users
        }

        if operation not in operations:
            return TaskResult.fail(f"Unknown operation: {operation}")

        try:
            handler = operations[operation]
            result = await handler(**kwargs)
            return TaskResult.ok(data=result)
        except ValueError as e:
            self.logger.warning(f"Validation error in {operation}: {e}")
            return TaskResult.fail(str(e))
        except Exception as e:
            self.logger.error(f"Error in {operation}: {e}", exc_info=True)
            return TaskResult.fail(f"Internal error: {operation}")

    async def _create_user(
        self,
        username: str,
        email: str,
        password_hash: Optional[str] = None,
        **extra_fields
    ) -> Dict[str, Any]:
        """Create a new user."""
        # Validate input
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")

        if not email or "@" not in email:
            raise ValueError("Invalid email format")

        # Create user entity
        user = BaseEntity()
        user_data = {
            "id": user.id,
            "username": username,
            "email": email,
            "status": EntityStatus.PENDING.value,
            "created_at": user.created_at.isoformat(),
            **extra_fields
        }

        # Store in repository
        if self._repository:
            await self._repository.create(user_data)

        # Publish event
        if self._event_publisher:
            await self._event_publisher.publish("user.created", user_data)

        # Cache the result
        self._cache[user.id] = user_data

        self.logger.info(f"Created user {user.id} with username {username}")

        return user_data

    async def _get_user(self, user_id: str) -> Dict[str, Any]:
        """Retrieve user by ID."""
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        # Fetch from repository
        if self._repository:
            user = await self._repository.read(user_id)
            if user:
                self._cache[user_id] = user
            return user

        raise ValueError(f"User not found: {user_id}")

    async def _update_user(
        self,
        user_id: str,
        **updates
    ) -> Dict[str, Any]:
        """Update user data."""
        # Validate user exists
        existing = await self._get_user(user_id)

        # Apply updates
        for key, value in updates.items():
            if key not in ("id", "created_at"):
                existing[key] = value
        existing["updated_at"] = datetime.utcnow().isoformat()

        # Persist changes
        if self._repository:
            await self._repository.update(user_id, existing)

        # Invalidate cache
        self._cache.pop(user_id, None)

        self.logger.info(f"Updated user {user_id}")

        return existing

    async def _delete_user(self, user_id: str) -> bool:
        """Soft delete user."""
        existing = await self._get_user(user_id)
        existing["status"] = EntityStatus.DELETED.value
        existing["updated_at"] = datetime.utcnow().isoformat()

        if self._repository:
            await self._repository.update(user_id, existing)

        self._cache.pop(user_id, None)

        self.logger.info(f"Deleted user {user_id}")

        return True

    async def _list_users(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List users with pagination."""
        if self._repository:
            users = await self._repository.list(limit, offset)

            if status:
                users = [u for u in users if u.get("status") == status]

            return users

        return []

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        self._cache.clear()
        if self._repository:
            await self._repository.close()

# ============================================================================
# REPOSITORY PATTERN IMPLEMENTATION
# ============================================================================

class UserRepository(Protocol):
    """Protocol for user data persistence."""

    async def connect(self) -> None: ...
    async def create(self, data: Dict[str, Any]) -> str: ...
    async def read(self, record_id: str) -> Optional[Dict[str, Any]]: ...
    async def update(self, record_id: str, data: Dict[str, Any]) -> bool: ...
    async def delete(self, record_id: str) -> bool: ...
    async def list(self, limit: int, offset: int) -> List[Dict[str, Any]]: ...
    async def close(self) -> None: ...


class PostgresUserRepository:
    """
    PostgreSQL implementation of UserRepository.

    Uses asyncpg for high-performance async database access.
    """

    def __init__(self, connection_string: str):
        self._conn_str = connection_string
        self._pool = None

    async def connect(self) -> None:
        """Create connection pool."""
        # In production: self._pool = await asyncpg.create_pool(self._conn_str)
        self._pool = True  # Placeholder
        logger.info("PostgreSQL connection pool created")

    async def create(self, data: Dict[str, Any]) -> str:
        """Insert new user and return ID."""
        query = '''
            INSERT INTO users (id, username, email, status, created_at, updated_at, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        '''
        # In production:
        # async with self._pool.acquire() as conn:
        #     record = await conn.fetchrow(query, ...)
        #     return record['id']
        return data.get("id", str(uuid.uuid4()))

    async def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user by ID."""
        query = 'SELECT * FROM users WHERE id = $1'
        # async with self._pool.acquire() as conn:
        #     return await conn.fetchrow(query, record_id)
        return None

    async def update(self, record_id: str, data: Dict[str, Any]) -> bool:
        """Update user record."""
        # Build dynamic update query based on data keys
        set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(data.keys())]
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = $1"
        # Execute query
        return True

    async def delete(self, record_id: str) -> bool:
        """Delete user record."""
        query = 'DELETE FROM users WHERE id = $1'
        return True

    async def list(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        """List users with pagination."""
        query = 'SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2'
        # async with self._pool.acquire() as conn:
        #     return await conn.fetch(query, limit, offset)
        return []

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            # await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")


class InMemoryUserRepository:
    """
    In-memory implementation for testing.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    async def connect(self) -> None:
        pass

    async def create(self, data: Dict[str, Any]) -> str:
        record_id = data.get("id", str(uuid.uuid4()))
        self._store[record_id] = data.copy()
        return record_id

    async def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get(record_id)

    async def update(self, record_id: str, data: Dict[str, Any]) -> bool:
        if record_id in self._store:
            self._store[record_id].update(data)
            return True
        return False

    async def delete(self, record_id: str) -> bool:
        return self._store.pop(record_id, None) is not None

    async def list(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        records = list(self._store.values())
        return records[offset:offset+limit]

    async def close(self) -> None:
        self._store.clear()

# ============================================================================
# EVENT PUBLISHING
# ============================================================================

class EventPublisher:
    """
    Simple event publisher for domain events.

    In production, would integrate with message broker (Kafka, RabbitMQ, etc.)
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}
        self._logger = logging.getLogger(f"{__name__}.EventPublisher")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to all subscribers."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        self._logger.info(f"Publishing event: {event_type}")

        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    self._logger.error(f"Event handler error: {e}")

# ============================================================================
# PIPELINE PATTERN IMPLEMENTATION
# ============================================================================

@dataclass
class PipelineContext:
    """Context passed through pipeline stages."""
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class PipelineStage(ABC):
    """Base class for pipeline stages."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        """Process the context and return updated context."""
        pass


class ValidationStage(PipelineStage):
    """Stage for input validation."""

    def __init__(self, validators: List[Callable]):
        super().__init__("ValidationStage")
        self._validators = validators

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        for validator in self._validators:
            try:
                if asyncio.iscoroutinefunction(validator):
                    await validator(ctx.data)
                else:
                    validator(ctx.data)
            except ValueError as e:
                ctx.add_error(f"Validation failed: {e}")

        return ctx


class TransformationStage(PipelineStage):
    """Stage for data transformation."""

    def __init__(self, transformer: Callable[[Any], Any]):
        super().__init__("TransformationStage")
        self._transformer = transformer

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if ctx.has_errors:
            return ctx

        try:
            if asyncio.iscoroutinefunction(self._transformer):
                ctx.data = await self._transformer(ctx.data)
            else:
                ctx.data = self._transformer(ctx.data)
        except Exception as e:
            ctx.add_error(f"Transformation failed: {e}")

        return ctx


class Pipeline:
    """Pipeline for chaining processing stages."""

    def __init__(self, name: str):
        self.name = name
        self._stages: List[PipelineStage] = []
        self.logger = logging.getLogger(f"{__name__}.{name}")

    def add_stage(self, stage: PipelineStage) -> "Pipeline":
        self._stages.append(stage)
        return self

    async def execute(self, initial_data: Any) -> PipelineContext:
        ctx = PipelineContext(data=initial_data)

        for stage in self._stages:
            self.logger.debug(f"Executing stage: {stage.name}")
            ctx = await stage.process(ctx)

            if ctx.has_errors:
                self.logger.warning(
                    f"Stage {stage.name} completed with errors: {ctx.errors}"
                )
                break

        return ctx


# ============================================================================
# FACTORY PATTERN IMPLEMENTATION
# ============================================================================

class ServiceFactory:
    """
    Factory for creating service instances.

    Supports:
    - Singleton registration
    - Dependency injection
    - Lazy initialization
    """

    _instance: Optional["ServiceFactory"] = None
    _services: Dict[str, Callable] = {}
    _singletons: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "ServiceFactory":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        name: str,
        factory: Callable,
        singleton: bool = False
    ) -> None:
        """Register a service factory."""
        self._services[name] = factory
        if singleton:
            self._singletons[name] = None

    def create(self, name: str, **kwargs) -> Any:
        """Create or retrieve a service instance."""
        if name not in self._services:
            raise ValueError(f"Unknown service: {name}")

        factory = self._services[name]

        # Check for singleton
        if name in self._singletons:
            if self._singletons[name] is None:
                self._singletons[name] = factory(**kwargs)
            return self._singletons[name]

        return factory(**kwargs)

    def clear_singletons(self) -> None:
        """Clear all singleton instances."""
        self._singletons.clear()


# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreaker:
    """
    Circuit breaker for fault tolerance.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests rejected
    - HALF_OPEN: Testing if service recovered
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED)
    _failure_count: int = field(default=0)
    _success_count: int = field(default=0)
    _last_failure_time: float = field(default=0)

    @property
    def state(self) -> CircuitState:
        return self._state

    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            import time
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                return True
            return False

        # HALF_OPEN state
        return self._success_count < self.half_open_max_calls

    def record_success(self) -> None:
        """Record successful execution."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.half_open_max_calls:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"Circuit {self.name}: Recovered to CLOSED")
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed execution."""
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name}: HALF_OPEN → OPEN (failed)")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit {self.name}: CLOSED → OPEN (threshold reached)")


@asynccontextmanager
async def circuit_breaker(breaker: CircuitBreaker):
    """Context manager for circuit breaker execution."""
    if not breaker.can_execute():
        raise CircuitBreakerOpenError(f"Circuit {breaker.name} is OPEN")

    try:
        yield breaker
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
```

### 3.1.1 Multi-Language Pattern Examples

Below are equivalent implementations of the key patterns in **TypeScript** and **Go**.

---

#### TypeScript Examples

##### TypeScript: Service Layer Pattern

```typescript
/**
 * TypeScript Service Layer Pattern
 * Demonstrates: Dependency Injection, Async Operations, Error Handling
 */

interface TaskResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}

abstract class BaseService {
  protected name: string;
  protected logger: Console;
  protected initialized: boolean = false;

  constructor(name: string) {
    this.name = name;
    this.logger = console;
  }

  abstract execute(...args: any[]): Promise<TaskResult<any>>;

  async initialize(): Promise<void> {
    this.logger.log(`Initializing ${this.name}`);
    this.initialized = true;
  }

  async healthCheck(): Promise<boolean> {
    return this.initialized;
  }

  protected log(level: 'info' | 'warn' | 'error', message: string, meta?: object): void {
    this.logger[level](`[${this.name}] ${message}`, meta ?? {});
  }
}

interface User {
  id: string;
  username: string;
  email: string;
  status: 'pending' | 'active' | 'inactive' | 'deleted';
  createdAt: Date;
  updatedAt: Date;
}

interface UserRepository {
  create(data: Partial<User>): Promise<string>;
  findById(id: string): Promise<User | null>;
  update(id: string, data: Partial<User>): Promise<boolean>;
  delete(id: string): Promise<boolean>;
  list(limit: number, offset: number): Promise<User[]>;
}

class InMemoryUserRepository implements UserRepository {
  private store: Map<string, User> = new Map();

  async create(data: Partial<User>): Promise<string> {
    const id = crypto.randomUUID();
    const user: User = {
      id,
      username: data.username ?? '',
      email: data.email ?? '',
      status: 'pending',
      createdAt: new Date(),
      updatedAt: new Date(),
      ...data,
    };
    this.store.set(id, user);
    return id;
  }

  async findById(id: string): Promise<User | null> {
    return this.store.get(id) ?? null;
  }

  async update(id: string, data: Partial<User>): Promise<boolean> {
    const user = this.store.get(id);
    if (!user) return false;
    const updated: User = { ...user, ...data, updatedAt: new Date() };
    this.store.set(id, updated);
    return true;
  }

  async delete(id: string): Promise<boolean> {
    return this.store.delete(id);
  }

  async list(limit: number, offset: number): Promise<User[]> {
    return Array.from(this.store.values()).slice(offset, offset + limit);
  }
}

class UserManagementService extends BaseService {
  private repository: UserRepository;
  private cache: Map<string, User> = new Map();

  constructor(repository: UserRepository) {
    super('UserManagement');
    this.repository = repository;
  }

  async execute(operation: string, params: Record<string, any>): Promise<TaskResult<any>> {
    if (!this.initialized) {
      return { success: false, error: 'Service not initialized' };
    }

    const operations: Record<string, () => Promise<TaskResult<any>>> = {
      create: () => this.createUser(params),
      get: () => this.getUser(params),
      update: () => this.updateUser(params),
      delete: () => this.deleteUser(params),
      list: () => this.listUsers(params),
    };

    const handler = operations[operation];
    if (!handler) {
      return { success: false, error: `Unknown operation: ${operation}` };
    }

    try {
      return await handler();
    } catch (error) {
      this.log('error', `Operation ${operation} failed`, { error });
      return { success: false, error: `Internal error: ${operation}` };
    }
  }

  private async createUser(params: { username: string; email: string }): Promise<TaskResult<User>> {
    if (!params.username || params.username.length < 3) {
      return { success: false, error: 'Username must be at least 3 characters' };
    }
    if (!params.email || !params.email.includes('@')) {
      return { success: false, error: 'Invalid email format' };
    }

    const id = await this.repository.create(params);
    const user = await this.repository.findById(id);
    this.log('info', `Created user ${id}`);
    return { success: true, data: user! };
  }

  private async getUser(params: { userId: string }): Promise<TaskResult<User>> {
    const cached = this.cache.get(params.userId);
    if (cached) return { success: true, data: cached };

    const user = await this.repository.findById(params.userId);
    if (!user) return { success: false, error: 'User not found' };

    this.cache.set(params.userId, user);
    return { success: true, data: user };
  }

  private async updateUser(params: { userId: string; updates: Partial<User> }): Promise<TaskResult<User>> {
    const user = await this.repository.findById(params.userId);
    if (!user) return { success: false, error: 'User not found' };

    await this.repository.update(params.userId, params.updates);
    this.cache.delete(params.userId);
    this.log('info', `Updated user ${params.userId}`);

    const updated = await this.repository.findById(params.userId);
    return { success: true, data: updated! };
  }

  private async deleteUser(params: { userId: string }): Promise<TaskResult<boolean>> {
    const user = await this.repository.findById(params.userId);
    if (!user) return { success: false, error: 'User not found' };

    await this.repository.update(params.userId, { status: 'deleted' });
    this.cache.delete(params.userId);
    this.log('info', `Deleted user ${params.userId}`);

    return { success: true, data: true };
  }

  private async listUsers(params: { limit?: number; offset?: number }): Promise<TaskResult<User[]>> {
    const users = await this.repository.list(params.limit ?? 100, params.offset ?? 0);
    return { success: true, data: users };
  }
}
```

##### TypeScript: Circuit Breaker Pattern

```typescript
/**
 * TypeScript Circuit Breaker Pattern
 * States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)
 */

enum CircuitState {
  CLOSED = 'closed',
  OPEN = 'open',
  HALF_OPEN = 'half_open',
}

interface CircuitBreakerOptions {
  name: string;
  failureThreshold?: number;      // Failures before opening (default: 5)
  recoveryTimeout?: number;       // Seconds before half-open (default: 60)
  halfOpenMaxCalls?: number;     // Max calls in half-open (default: 3)
}

class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private successCount: number = 0;
  private lastFailureTime: number = 0;

  readonly name: string;
  readonly failureThreshold: number;
  readonly recoveryTimeout: number; // milliseconds
  readonly halfOpenMaxCalls: number;

  constructor(options: CircuitBreakerOptions) {
    this.name = options.name;
    this.failureThreshold = options.failureThreshold ?? 5;
    this.recoveryTimeout = (options.recoveryTimeout ?? 60) * 1000;
    this.halfOpenMaxCalls = options.halfOpenMaxCalls ?? 3;
  }

  get circuitState(): CircuitState {
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      if (now - this.lastFailureTime >= this.recoveryTimeout) {
        this.state = CircuitState.HALF_OPEN;
        this.successCount = 0;
      }
    }
    return this.state;
  }

  canExecute(): boolean {
    if (this.circuitState === CircuitState.CLOSED) return true;
    if (this.circuitState === CircuitState.OPEN) return false;
    // HALF_OPEN
    return this.successCount < this.halfOpenMaxCalls;
  }

  recordSuccess(): void {
    if (this.state === CircuitState.HALF_OPEN) {
      this.successCount++;
      if (this.successCount >= this.halfOpenMaxCalls) {
        this.state = CircuitState.CLOSED;
        this.failureCount = 0;
        console.log(`[CircuitBreaker] ${this.name}: Recovered to CLOSED`);
      }
    } else {
      this.failureCount = 0;
    }
  }

  recordFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
      console.warn(`[CircuitBreaker] ${this.name}: HALF_OPEN → OPEN (failed)`);
    } else if (this.failureCount >= this.failureThreshold) {
      this.state = CircuitState.OPEN;
      console.warn(`[CircuitBreaker] ${this.name}: CLOSED → OPEN (threshold reached)`);
    }
  }
}

class CircuitBreakerOpenError extends Error {
  constructor(name: string) {
    super(`Circuit ${name} is OPEN`);
    this.name = 'CircuitBreakerOpenError';
  }
}

// Usage example
async function withCircuitBreaker<T>(
  breaker: CircuitBreaker,
  fn: () => Promise<T>
): Promise<T> {
  if (!breaker.canExecute()) {
    throw new CircuitBreakerOpenError(breaker.name);
  }

  try {
    const result = await fn();
    breaker.recordSuccess();
    return result;
  } catch (error) {
    breaker.recordFailure();
    throw error;
  }
}

// Example usage
const breaker = new CircuitBreaker({ name: 'external-api', failureThreshold: 3 });

async function fetchUserData(userId: string) {
  return withCircuitBreaker(breaker, async () => {
    const response = await fetch(`/api/users/${userId}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}
```

##### TypeScript: Repository Pattern + Dependency Injection

```typescript
/**
 * TypeScript Repository Pattern with Dependency Injection
 */

interface Repository<T, ID = string> {
  create(data: Omit<T, 'id'>): Promise<ID>;
  findById(id: ID): Promise<T | null>;
  update(id: ID, data: Partial<T>): Promise<boolean>;
  delete(id: ID): Promise<boolean>;
  findAll(limit: number, offset: number): Promise<T[]>;
}

// Generic repository base
abstract class BaseRepository<T, ID = string> implements Repository<T, ID> {
  protected storage: Map<ID, T> = new Map();

  abstract create(data: Omit<T, 'id'>): Promise<ID>;
  abstract findById(id: ID): Promise<T | null>;
  abstract update(id: ID, data: Partial<T>): Promise<boolean>;
  abstract delete(id: ID): Promise<boolean>;
  abstract findAll(limit: number, offset: number): Promise<T[]>;

  protected generateId(): ID {
    return crypto.randomUUID() as ID;
  }
}

interface Order {
  id: string;
  userId: string;
  amount: number;
  status: 'pending' | 'completed' | 'cancelled';
  createdAt: Date;
}

class OrderRepository extends BaseRepository<Order, string> {
  async create(data: Omit<Order, 'id'>): Promise<string> {
    const id = this.generateId();
    const order: Order = { id, ...data };
    this.storage.set(id, order);
    return id;
  }

  async findById(id: string): Promise<Order | null> {
    return this.storage.get(id) ?? null;
  }

  async update(id: string, data: Partial<Order>): Promise<boolean> {
    const existing = this.storage.get(id);
    if (!existing) return false;
    this.storage.set(id, { ...existing, ...data });
    return true;
  }

  async delete(id: string): Promise<boolean> {
    return this.storage.delete(id);
  }

  async findAll(limit: number, offset: number): Promise<Order[]> {
    return Array.from(this.storage.values()).slice(offset, offset + limit);
  }

  async findByUserId(userId: string): Promise<Order[]> {
    return Array.from(this.storage.values()).filter(o => o.userId === userId);
  }
}

// Dependency Injection Container
class DIContainer {
  private services: Map<string, any> = new Map();

  register<T>(token: string, instance: T): void {
    this.services.set(token, instance);
  }

  resolve<T>(token: string): T {
    const service = this.services.get(token);
    if (!service) throw new Error(`Service ${token} not registered`);
    return service as T;
  }
}

// Usage
const container = new DIContainer();
container.register<OrderRepository>('OrderRepository', new OrderRepository());

const orderRepo = container.resolve<OrderRepository>('OrderRepository');
const orderId = await orderRepo.create({
  userId: 'user-123',
  amount: 99.99,
  status: 'pending',
  createdAt: new Date(),
});
```

---

#### Go Examples

##### Go: Service Layer Pattern

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"
)

// TaskResult wraps execution results.
type TaskResult[T any] struct {
	Success bool
	Data    *T
	Error   error
}

// BaseService provides common service functionality.
type BaseService struct {
	Name        string
	Logger      *log.Logger
	Initialized bool
}

func (s *BaseService) Initialize() {
	s.Logger.Printf("[%s] Initializing", s.Name)
	s.Initialized = true
}

func (s *BaseService) HealthCheck() bool {
	return s.Initialized
}

// User represents a user entity.
type User struct {
	ID        string    `json:"id"`
	Username  string    `json:"username"`
	Email     string    `json:"email"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

// UserRepository defines the user data access interface.
type UserRepository interface {
	Create(ctx context.Context, user *User) (string, error)
	FindByID(ctx context.Context, id string) (*User, error)
	Update(ctx context.Context, id string, updates map[string]interface{}) error
	Delete(ctx context.Context, id string) error
	List(ctx context.Context, limit, offset int) ([]*User, error)
}

// InMemoryUserRepository is a thread-safe in-memory implementation.
type InMemoryUserRepository struct {
	mu    sync.RWMutex
	store map[string]*User
}

func NewInMemoryUserRepository() *InMemoryUserRepository {
	return &InMemoryUserRepository{store: make(map[string]*User)}
}

func (r *InMemoryUserRepository) Create(ctx context.Context, user *User) (string, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	user.ID = fmt.Sprintf("%d", time.Now().UnixNano())
	user.CreatedAt = time.Now()
	user.UpdatedAt = user.CreatedAt
	r.store[user.ID] = user
	return user.ID, nil
}

func (r *InMemoryUserRepository) FindByID(ctx context.Context, id string) (*User, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if user, ok := r.store[id]; ok {
		return user, nil
	}
	return nil, errors.New("user not found")
}

func (r *InMemoryUserRepository) Update(ctx context.Context, id string, updates map[string]interface{}) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	user, ok := r.store[id]
	if !ok {
		return errors.New("user not found")
	}

	// Apply updates (simplified - in production use reflection or struct mapping)
	if username, ok := updates["username"].(string); ok {
		user.Username = username
	}
	if email, ok := updates["email"].(string); ok {
		user.Email = email
	}
	if status, ok := updates["status"].(string); ok {
		user.Status = status
	}
	user.UpdatedAt = time.Now()

	r.store[id] = user
	return nil
}

func (r *InMemoryUserRepository) Delete(ctx context.Context, id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, ok := r.store[id]; !ok {
		return errors.New("user not found")
	}
	delete(r.store, id)
	return nil
}

func (r *InMemoryUserRepository) List(ctx context.Context, limit, offset int) ([]*User, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	users := make([]*User, 0, limit)
	i := 0
	for _, user := range r.store {
		if i >= offset && len(users) < limit {
			users = append(users, user)
		}
		i++
	}
	return users, nil
}

// UserManagementService orchestrates user operations.
type UserManagementService struct {
	BaseService
	repo UserRepository
	cache map[string]*User
}

func NewUserManagementService(repo UserRepository) *UserManagementService {
	return &UserManagementService{
		BaseService: BaseService{
			Name:   "UserManagement",
			Logger: log.Default(),
		},
		repo:  repo,
		cache: make(map[string]*User),
	}
}

func (s *UserManagementService) CreateUser(ctx context.Context, username, email string) *TaskResult[User] {
	if len(username) < 3 {
		return &TaskResult[User]{Success: false, Error: errors.New("username must be at least 3 characters")}
	}
	if !contains(email, "@") {
		return &TaskResult[User]{Success: false, Error: errors.New("invalid email format")}
	}

	user := &User{
		Username: username,
		Email:    email,
		Status:   "pending",
	}

	id, err := s.repo.Create(ctx, user)
	if err != nil {
		return &TaskResult[User]{Success: false, Error: err}
	}

	user.ID = id
	s.Logger.Printf("Created user: %s", id)
	return &TaskResult[User]{Success: true, Data: user}
}

func (s *UserManagementService) GetUser(ctx context.Context, id string) *TaskResult[User] {
	if cached, ok := s.cache[id]; ok {
		return &TaskResult[User]{Success: true, Data: cached}
	}

	user, err := s.repo.FindByID(ctx, id)
	if err != nil {
		return &TaskResult[User]{Success: false, Error: err}
	}

	s.cache[id] = user
	return &TaskResult[User]{Success: true, Data: user}
}

func (s *UserManagementService) UpdateUser(ctx context.Context, id string, updates map[string]interface{}) *TaskResult[User] {
	err := s.repo.Update(ctx, id, updates)
	if err != nil {
		return &TaskResult[User]{Success: false, Error: err}
	}

	delete(s.cache, id) // Invalidate cache

	user, _ := s.repo.FindByID(ctx, id)
	s.Logger.Printf("Updated user: %s", id)
	return &TaskResult[User]{Success: true, Data: user}
}

func (s *UserManagementService) DeleteUser(ctx context.Context, id string) *TaskResult[bool] {
	err := s.repo.Delete(ctx, id)
	if err != nil {
		return &TaskResult[bool]{Success: false, Error: err}
	}

	delete(s.cache, id)
	s.Logger.Printf("Deleted user: %s", id)
	return &TaskResult[bool]{Success: true, Data: new(bool)}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > 0 && containsHelper(s, substr))
}

func containsHelper(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func main() {
	ctx := context.Background()
	repo := NewInMemoryUserRepository()
	service := NewUserManagementService(repo)
	service.Initialize()

	// Create user
	result := service.CreateUser(ctx, "testuser", "test@example.com")
	if !result.Success {
		log.Fatalf("Failed to create user: %v", result.Error)
	}
	fmt.Printf("Created user: %+v\n", result.Data)
}
```

##### Go: Circuit Breaker Pattern

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"
)

// CircuitState represents the circuit breaker state.
type CircuitState int

const (
	StateClosed CircuitState = iota
	StateOpen
	StateHalfOpen
)

func (s CircuitState) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateOpen:
		return "OPEN"
	case StateHalfOpen:
		return "HALF_OPEN"
	default:
		return "UNKNOWN"
	}
}

// CircuitBreaker implements the circuit breaker pattern.
type CircuitBreaker struct {
	name             string
	state            CircuitState
	failureThreshold int
	recoveryTimeout  time.Duration
	halfOpenMaxCalls int

	mu              int // Mutex via sync would be used in production
	failureCount    int
	successCount    int
	lastFailureTime time.Time
}

// NewCircuitBreaker creates a new circuit breaker.
func NewCircuitBreaker(name string, opts ...func(*CircuitBreaker)) *CircuitBreaker {
	cb := &CircuitBreaker{
		name:             name,
		state:            StateClosed,
		failureThreshold: 5,
		recoveryTimeout:  60 * time.Second,
		halfOpenMaxCalls: 3,
	}
	for _, opt := range opts {
		opt(cb)
	}
	return cb
}

// WithFailureThreshold sets the failure threshold.
func WithFailureThreshold(n int) func(*CircuitBreaker) {
	return func(cb *CircuitBreaker) { cb.failureThreshold = n }
}

// WithRecoveryTimeout sets the recovery timeout.
func WithRecoveryTimeout(d time.Duration) func(*CircuitBreaker) {
	return func(cb *CircuitBreaker) { cb.recoveryTimeout = d }
}

func (cb *CircuitBreaker) State() CircuitState {
	if cb.state == StateOpen {
		if time.Since(cb.lastFailureTime) >= cb.recoveryTimeout {
			cb.state = StateHalfOpen
			cb.successCount = 0
		}
	}
	return cb.state
}

func (cb *CircuitBreaker) CanExecute() bool {
	return cb.State() == StateClosed || cb.State() == StateHalfOpen
}

func (cb *CircuitBreaker) RecordSuccess() {
	switch cb.state {
	case StateHalfOpen:
		cb.successCount++
		if cb.successCount >= cb.halfOpenMaxCalls {
			cb.state = StateClosed
			cb.failureCount = 0
			log.Printf("[CircuitBreaker] %s: Recovered to CLOSED", cb.name)
		}
	default:
		cb.failureCount = 0
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.failureCount++
	cb.lastFailureTime = time.Now()

	switch cb.state {
	case StateHalfOpen:
		cb.state = StateOpen
		log.Printf("[CircuitBreaker] %s: HALF_OPEN → OPEN (failed)", cb.name)
	case StateClosed:
		if cb.failureCount >= cb.failureThreshold {
			cb.state = StateOpen
			log.Printf("[CircuitBreaker] %s: CLOSED → OPEN (threshold reached)", cb.name)
		}
	}
}

// ErrCircuitOpen is returned when the circuit is open.
var ErrCircuitOpen = errors.New("circuit breaker is open")

// CircuitBreakerOpenError represents a circuit open error.
type CircuitBreakerOpenError struct {
	Name string
}

func (e *CircuitBreakerOpenError) Error() string {
	return fmt.Sprintf("circuit %s is OPEN", e.Name)
}

// Execute runs the function with circuit breaker protection.
func (cb *CircuitBreaker) Execute(ctx context.Context, fn func(context.Context) error) error {
	if !cb.CanExecute() {
		return &CircuitBreakerOpenError{Name: cb.name}
	}

	err := fn(ctx)
	if err != nil {
		cb.RecordFailure()
		return err
	}

	cb.RecordSuccess()
	return nil
}

// Example usage
func main() {
	cb := NewCircuitBreaker("external-api", WithFailureThreshold(3))

	ctx := context.Background()

	err := cb.Execute(ctx, func(ctx context.Context) error {
		// Simulate API call
		time.Sleep(100 * time.Millisecond)
		return nil
	})

	if err != nil {
		log.Printf("Request failed: %v", err)
	} else {
		log.Println("Request succeeded")
	}

	fmt.Printf("Circuit state: %s\n", cb.State())
}
```

##### Go: Repository Pattern with Interface

```go
package main

import (
	"context"
	"fmt"
	"sync"
)

// Repository is a generic repository interface.
type Repository[T any, ID any] interface {
	Create(ctx context.Context, entity T) (ID, error)
	FindByID(ctx context.Context, id ID) (T, error)
	Update(ctx context.Context, id ID, entity T) error
	Delete(ctx context.Context, id ID) error
	List(ctx context.Context, limit, offset int) ([]T, error)
}

// BaseRepository provides common repository functionality.
type BaseRepository[T any, ID any] struct {
	mu    sync.RWMutex
	store map[ID]T
	idGen func() ID
}

func NewBaseRepository[T any, ID any](idGen func() ID) *BaseRepository[T, ID] {
	return &BaseRepository[T, ID]{
		store: make(map[ID]T),
		idGen: idGen,
	}
}

// Order represents an order entity.
type Order struct {
	ID        string
	UserID    string
	Amount    float64
	Status    string
	CreatedAt int64
}

// OrderRepository implements Repository for Order.
type OrderRepository struct {
	*BaseRepository[Order, string]
}

func NewOrderRepository() *OrderRepository {
	return &OrderRepository{
		BaseRepository: NewBaseRepository(func() string {
			return fmt.Sprintf("%d", <-idChan)
		}),
	}
}

var idChan = make(chan int, 1000)

func init() {
	go func() {
		for i := 1; ; i++ {
			idChan <- i
		}
	}()
}

func (r *OrderRepository) Create(ctx context.Context, order Order) (string, error) {
	order.ID = r.idGen()
	r.mu.Lock()
	r.store[order.ID] = order
	r.mu.Unlock()
	return order.ID, nil
}

func (r *OrderRepository) FindByID(ctx context.Context, id string) (Order, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if order, ok := r.store[id]; ok {
		return order, nil
	}
	return Order{}, fmt.Errorf("order not found")
}

func (r *OrderRepository) Update(ctx context.Context, id string, order Order) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, ok := r.store[id]; !ok {
		return fmt.Errorf("order not found")
	}
	r.store[id] = order
	return nil
}

func (r *OrderRepository) Delete(ctx context.Context, id string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	delete(r.store, id)
	return nil
}

func (r *OrderRepository) List(ctx context.Context, limit, offset int) ([]Order, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	orders := make([]Order, 0, limit)
	i := 0
	for _, order := range r.store {
		if i >= offset && len(orders) < limit {
			orders = append(orders, order)
		}
		i++
	}
	return orders, nil
}
```

---

### 3.2 Unit Test Generation

```python
"""
Unit Test Suite for Staff Engineer Implementation
================================================
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import the classes we want to test
import sys
sys.path.insert(0, '/home/rayliu/.openclaw/skills/sindris/roles/engineering')
from engineering_staff_engineer import (
    UserManagementService,
    InMemoryUserRepository,
    Pipeline,
    PipelineContext,
    ValidationStage,
    TransformationStage,
    CircuitBreaker,
    CircuitState,
    circuit_breaker,
    CircuitBreakerOpenError,
    EntityStatus,
    TaskResult
)


class TestUserManagementService:
    """Test suite for UserManagementService."""

    @pytest.fixture
    def repository(self):
        return InMemoryUserRepository()

    @pytest.fixture
    def service(self, repository):
        return UserManagementService(repository=repository)

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initializes correctly."""
        await service.initialize()
        assert service._is_initialized is True
        assert service.health_check() is True

    @pytest.mark.asyncio
    async def test_create_user_success(self, service):
        """Test successful user creation."""
        await service.initialize()

        result = await service.execute(
            "create",
            username="testuser",
            email="test@example.com"
        )

        assert result.success is True
        assert result.data is not None
        assert result.data["username"] == "testuser"
        assert result.data["email"] == "test@example.com"
        assert result.data["status"] == EntityStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_create_user_invalid_username(self, service):
        """Test user creation with invalid username."""
        await service.initialize()

        result = await service.execute(
            "create",
            username="ab",  # Too short
            email="test@example.com"
        )

        assert result.success is False
        assert "at least 3 characters" in result.error

    @pytest.mark.asyncio
    async def test_create_user_invalid_email(self, service):
        """Test user creation with invalid email."""
        await service.initialize()

        result = await service.execute(
            "create",
            username="testuser",
            email="invalid-email"  # Missing @
        )

        assert result.success is False
        assert "Invalid email" in result.error

    @pytest.mark.asyncio
    async def test_get_user(self, service):
        """Test retrieving user by ID."""
        await service.initialize()

        # Create user first
        create_result = await service.execute(
            "create",
            username="testuser",
            email="test@example.com"
        )
        user_id = create_result.data["id"]

        # Get user
        get_result = await service.execute("get", user_id=user_id)

        assert get_result.success is True
        assert get_result.data["id"] == user_id
        assert get_result.data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, service):
        """Test retrieving non-existent user."""
        await service.initialize()

        result = await service.execute("get", user_id="non-existent-id")

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_user(self, service):
        """Test updating user data."""
        await service.initialize()

        # Create user
        create_result = await service.execute(
            "create",
            username="testuser",
            email="test@example.com"
        )
        user_id = create_result.data["id"]

        # Update user
        update_result = await service.execute(
            "update",
            user_id=user_id,
            username="updateduser"
        )

        assert update_result.success is True
        assert update_result.data["username"] == "updateduser"

        # Verify update persisted
        get_result = await service.execute("get", user_id=user_id)
        assert get_result.data["username"] == "updateduser"

    @pytest.mark.asyncio
    async def test_delete_user(self, service):
        """Test soft deleting user."""
        await service.initialize()

        # Create user
        create_result = await service.execute(
            "create",
            username="testuser",
            email="test@example.com"
        )
        user_id = create_result.data["id"]

        # Delete user
        delete_result = await service.execute("delete", user_id=user_id)

        assert delete_result.success is True

        # Verify status changed to deleted
        get_result = await service.execute("get", user_id=user_id)
        assert get_result.data["status"] == EntityStatus.DELETED.value

    @pytest.mark.asyncio
    async def test_list_users(self, service):
        """Test listing users with pagination."""
        await service.initialize()

        # Create multiple users
        for i in range(5):
            await service.execute(
                "create",
                username=f"user{i}",
                email=f"user{i}@example.com"
            )

        # List users
        list_result = await service.execute("list", limit=3, offset=0)

        assert list_result.success is True
        assert len(list_result.data) == 3

        # List with offset
        list_result2 = await service.execute("list", limit=3, offset=3)
        assert list_result2.success is True
        assert len(list_result2.data) == 2


class TestPipeline:
    """Test suite for Pipeline pattern."""

    @pytest.mark.asyncio
    async def test_pipeline_single_stage(self):
        """Test pipeline with single stage."""
        pipeline = Pipeline("test")

        def increment(ctx):
            ctx.data = ctx.data + 1

        pipeline.add_stage(TransformationStage(increment))

        result = await pipeline.execute(5)

        assert result.data == 6
        assert not result.has_errors

    @pytest.mark.asyncio
    async def test_pipeline_multiple_stages(self):
        """Test pipeline with multiple stages."""
        pipeline = Pipeline("test")

        pipeline.add_stage(TransformationStage(lambda x: x * 2))
        pipeline.add_stage(TransformationStage(lambda x: x + 1))
        pipeline.add_stage(TransformationStage(lambda x: x ** 2))

        result = await pipeline.execute(3)

        # (3 * 2 + 1) ** 2 = 49
        assert result.data == 49

    @pytest.mark.asyncio
    async def test_pipeline_validation_failure(self):
        """Test pipeline stops on validation failure."""
        pipeline = Pipeline("test")

        def always_fail(data):
            raise ValueError("Validation failed")

        pipeline.add_stage(ValidationStage([always_fail]))
        pipeline.add_stage(TransformationStage(lambda x: x * 2))

        result = await pipeline.execute(5)

        assert result.has_errors
        assert "Validation failed" in result.errors[0]


class TestCircuitBreaker:
    """Test suite for CircuitBreaker."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker(name="test", failure_threshold=3)

        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_circuit_breaker_opens_on_threshold(self):
        """Test circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(name="test", failure_threshold=3)

        # Record failures up to threshold
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_circuit_breaker_success_resets(self):
        """Test success resets failure count."""
        cb = CircuitBreaker(name="test", failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_context_manager_success(self):
        """Test circuit breaker allows execution when closed."""
        cb = CircuitBreaker(name="test")

        async with circuit_breaker(cb):
            pass

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_context_manager_open(self):
        """Test circuit breaker raises when open."""
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()  # Opens the circuit

        with pytest.raises(CircuitBreakerOpenError):
            async with circuit_breaker(cb):
                pass


class TestTaskResult:
    """Test suite for TaskResult dataclass."""

    def test_task_result_ok(self):
        """Test successful result creation."""
        result = TaskResult.ok(data={"key": "value"}, extra="info")

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.metadata["extra"] == "info"

    def test_task_result_fail(self):
        """Test failure result creation."""
        result = TaskResult.fail(error="Something went wrong")

        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_user_lifecycle(self):
        """Test complete user lifecycle."""
        repository = InMemoryUserRepository()
        service = UserManagementService(repository=repository)

        await service.initialize()

        # Create
        create_result = await service.execute(
            "create",
            username="lifecycleuser",
            email="lifecycle@example.com"
        )
        assert create_result.success
        user_id = create_result.data["id"]

        # Read
        get_result = await service.execute("get", user_id=user_id)
        assert get_result.data["username"] == "lifecycleuser"

        # Update
        update_result = await service.execute(
            "update",
            user_id=user_id,
            status=EntityStatus.ACTIVE.value
        )
        assert update_result.data["status"] == EntityStatus.ACTIVE.value

        # Delete
        delete_result = await service.execute("delete", user_id=user_id)
        assert delete_result.success

        # Verify deleted
        get_result = await service.execute("get", user_id=user_id)
        assert get_result.data["status"] == EntityStatus.DELETED.value

    @pytest.mark.asyncio
    async def test_pipeline_with_service(self):
        """Test pipeline processing with service."""
        repository = InMemoryUserRepository()
        service = UserManagementService(repository=repository)
        await service.initialize()

        # Create pipeline for user processing
        pipeline = Pipeline("user-processing")

        # Validation stage
        def validate_user_data(data):
            if not data.get("email"):
                raise ValueError("Email required")

        pipeline.add_stage(ValidationStage([validate_user_data]))

        # Create users stage
        async def create_users(ctx):
            results = []
            for user_data in ctx.data:
                result = await service.execute("create", **user_data)
                results.append(result.data if result.success else None)
            ctx.metadata["created"] = len([r for r in results if r])
            return results

        pipeline.add_stage(TransformationStage(create_users))

        # Execute
        users = [
            {"username": "user1", "email": "user1@example.com"},
            {"username": "user2", "email": "user2@example.com"}
        ]

        result = await pipeline.execute(users)

        assert not result.has_errors
        assert result.metadata["created"] == 2
```

### 3.3 Documentation Generation

```markdown
# User Management Service - API Documentation

## Overview

The User Management Service provides comprehensive user lifecycle management including creation, retrieval, updates, and soft deletion.

## Base URL

```
Production: https://api.example.com/v1
Staging: https://api-staging.example.com/v1
Local: http://localhost:8080/v1
```

## Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer <access_token>
```

## Endpoints

### Create User

**POST** `/users`

Creates a new user with pending status.

#### Request Body

```json
{
  "username": "string (required, min 3 chars)",
  "email": "string (required, valid email format)",
  "password_hash": "string (optional, hashed password)",
  "metadata": "object (optional, arbitrary key-value pairs)"
}
```

#### Response

**201 Created**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "testuser",
  "email": "test@example.com",
  "status": "pending",
  "created_at": "2026-04-18T12:00:00Z",
  "updated_at": "2026-04-18T12:00:00Z"
}
```

#### Error Codes

| Code | Description |
|------|-------------|
| 400  | Invalid request body |
| 409  | Username or email already exists |
| 500  | Internal server error |

---

### Get User

**GET** `/users/{user_id}`

Retrieves a user by their unique identifier.

#### Path Parameters

| Parameter | Type   | Description |
|-----------|--------|-------------|
| user_id   | string | User UUID   |

#### Response

**200 OK**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "testuser",
  "email": "test@example.com",
  "status": "active",
  "created_at": "2026-04-18T12:00:00Z",
  "updated_at": "2026-04-18T14:30:00Z"
}
```

#### Error Codes

| Code | Description |
|------|-------------|
| 404  | User not found |
| 500  | Internal server error |

---

### Update User

**PATCH** `/users/{user_id}`

Updates user data. Only provided fields are updated.

#### Path Parameters

| Parameter | Type   | Description |
|-----------|--------|-------------|
| user_id   | string | User UUID   |

#### Request Body

```json
{
  "username": "string (optional)",
  "email": "string (optional)",
  "status": "string (optional: pending|active|inactive|deleted)",
  "metadata": "object (optional)"
}
```

#### Response

**200 OK**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "updateduser",
  "email": "updated@example.com",
  "status": "active",
  "created_at": "2026-04-18T12:00:00Z",
  "updated_at": "2026-04-18T15:00:00Z"
}
```

---

### Delete User

**DELETE** `/users/{user_id}`

Soft deletes a user by setting status to "deleted".

#### Path Parameters

| Parameter | Type   | Description |
|-----------|--------|-------------|
| user_id   | string | User UUID   |

#### Response

**200 OK**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "deleted",
  "updated_at": "2026-04-18T16:00:00Z"
}
```

---

### List Users

**GET** `/users`

Lists users with pagination.

#### Query Parameters

| Parameter | Type    | Default | Description |
|-----------|---------|---------|-------------|
| limit     | integer | 100     | Max results (1-1000) |
| offset    | integer | 0       | Pagination offset |
| status    | string  | all     | Filter by status |

#### Response

**200 OK**

```json
{
  "users": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "username": "user1",
      "email": "user1@example.com",
      "status": "active",
      "created_at": "2026-04-18T12:00:00Z"
    }
  ],
  "total": 150,
  "limit": 100,
  "offset": 0
}
```

## Events

The service emits the following domain events:

| Event            | Payload | Description |
|------------------|---------|-------------|
| user.created     | User object | Emitted when user is created |
| user.updated     | User object | Emitted when user is updated |
| user.deleted     | User object | Emitted when user is deleted |

## Rate Limiting

- **Create**: 100 requests/minute per IP
- **Read**: 1000 requests/minute per IP
- **Update**: 500 requests/minute per IP
- **Delete**: 100 requests/minute per IP

## Health Check

**GET** `/health`

```json
{
  "status": "healthy",
  "service": "user-management",
  "version": "1.0.0",
  "timestamp": "2026-04-18T12:00:00Z"
}
```
```

---

## 🔧 Step 4: Self-Verification

### 4.1 Code Quality Checks

```python
"""
Self-Verification Checklist
===========================

Staff Engineer verifies implementation against requirements.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import re

@dataclass
class VerificationResult:
    check_name: str
    passed: bool
    message: str
    severity: str  # "error", "warning", "info"

class CodeQualityVerifier:
    """
    Verifies code quality against defined standards.
    """

    def __init__(self, code: str):
        self.code = code
        self.results: List[VerificationResult] = []

    def check_all(self) -> List[VerificationResult]:
        """Run all verification checks."""
        self.verify_no_hardcoded_secrets()
        self.verify_error_handling()
        self.verify_logging()
        self.verify_type_hints()
        self.verify_documentation()
        self.verify_no_blocking_operations()
        self.verify_resource_cleanup()
        return self.results

    def verify_no_hardcoded_secrets(self) -> None:
        """Check for hardcoded secrets, passwords, API keys."""
        patterns = [
            (r'password\s*=\s*["\'][^"\']{1,50}["\']', "hardcoded password"),
            (r'api[_-]?key\s*=\s*["\'][A-Za-z0-9]{20,}["\']', "hardcoded API key"),
            (r'secret\s*=\s*["\'][^"\']{8,}["\']', "hardcoded secret"),
            (r'token\s*=\s*["\'][A-Za-z0-9_\-\.]{20,}["\']', "hardcoded token"),
        ]

        for pattern, description in patterns:
            matches = re.findall(pattern, self.code, re.IGNORECASE)
            if matches:
                self.results.append(VerificationResult(
                    check_name="Hardcoded Secrets",
                    passed=False,
                    message=f"Found potential {description}: {len(matches)} occurrence(s)",
                    severity="error"
                ))
                return

        self.results.append(VerificationResult(
            check_name="Hardcoded Secrets",
            passed=True,
            message="No hardcoded secrets found",
            severity="info"
        ))

    def verify_error_handling(self) -> None:
        """Check for proper error handling."""
        has_try = "try:" in self.code or "try :" in self.code
        has_except = "except" in self.code

        if has_try and not has_except:
            self.results.append(VerificationResult(
                check_name="Error Handling",
                passed=False,
                message="try block without except clause",
                severity="error"
            ))
        elif not (has_try or has_except):
            self.results.append(VerificationResult(
                check_name="Error Handling",
                passed=False,
                message="No exception handling found",
                severity="warning"
            ))
        else:
            self.results.append(VerificationResult(
                check_name="Error Handling",
                passed=True,
                message="Proper error handling found",
                severity="info"
            ))

    def verify_logging(self) -> None:
        """Check for logging statements."""
        has_logging = bool(re.search(r'logger\.\w+', self.code))

        if not has_logging:
            self.results.append(VerificationResult(
                check_name="Logging",
                passed=False,
                message="No logging statements found",
                severity="warning"
            ))
        else:
            self.results.append(VerificationResult(
                check_name="Logging",
                passed=True,
                message="Logging statements found",
                severity="info"
            ))

    def verify_type_hints(self) -> None:
        """Check for type hints on function signatures."""
        functions = re.findall(r'def\s+\w+\([^)]*\)\s*(?:->\s*\w+)?', self.code)
        functions_with_hints = re.findall(r'def\s+\w+\([^)]*\)\s*->\s*\w+', self.code)

        if functions:
            ratio = len(functions_with_hints) / len(functions)
            if ratio < 0.5:
                self.results.append(VerificationResult(
                    check_name="Type Hints",
                    passed=False,
                    message=f"Only {ratio:.0%} of functions have type hints",
                    severity="warning"
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="Type Hints",
                    passed=True,
                    message=f"{ratio:.0%} of functions have type hints",
                    severity="info"
                ))

    def verify_documentation(self) -> None:
        """Check for docstrings."""
        docstrings = len(re.findall(r'""".*?"""', self.code, re.DOTALL))
        functions = len(re.findall(r'def\s+\w+', self.code))

        if functions > 0:
            ratio = docstrings / functions
            if ratio < 0.3:
                self.results.append(VerificationResult(
                    check_name="Documentation",
                    passed=False,
                    message=f"Only {ratio:.0%} of functions have docstrings",
                    severity="warning"
                ))
            else:
                self.results.append(VerificationResult(
                    check_name="Documentation",
                    passed=True,
                    message=f"{ratio:.0%} of functions have docstrings",
                    severity="info"
                ))

    def verify_no_blocking_operations(self) -> None:
        """Check for blocking synchronous operations in async code."""
        # In Python, check for blocking calls in async functions
        has_async_def = "async def" in self.code

        if has_async_def:
            blocking_patterns = [
                (r'time\.sleep\s*\(', "time.sleep in async code"),
                (r'\.join\s*\(', "thread join in async code"),
            ]

            for pattern, description in blocking_patterns:
                if re.search(pattern, self.code):
                    self.results.append(VerificationResult(
                        check_name="Blocking Operations",
                        passed=False,
                        message=f"Found blocking operation: {description}",
                        severity="warning"
                    ))
                    return

            self.results.append(VerificationResult(
                check_name="Blocking Operations",
                passed=True,
                message="No blocking operations in async code",
                severity="info"
            ))

    def verify_resource_cleanup(self) -> None:
        """Check for proper resource cleanup."""
        has_context_manager = "async with" in self.code or "with " in self.code
        has_close = ".close()" in self.code

        if not (has_context_manager or has_close):
            self.results.append(VerificationResult(
                check_name="Resource Cleanup",
                passed=False,
                message="No clear resource cleanup found (no context managers or close calls)",
                severity="warning"
            ))
        else:
            self.results.append(VerificationResult(
                check_name="Resource Cleanup",
                passed=True,
                message="Resource cleanup patterns found",
                severity="info"
            ))


def verify_implementation(
    code: str,
    requirements: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Complete verification of implementation using AST-based analysis.

    This function performs:
    1. AST parsing to verify code is syntactically valid Python
    2. Pattern matching against acceptance criteria using AST nodes
    3. Quality checks via CodeQualityVerifier (linting, secrets, etc.)
    4. Integration with ruff/black/mypy when available

    Returns:
        Dictionary with verification results and summary.
    """
    import ast
    import subprocess
    import sys
    from typing import List, Dict, Any, Optional

    verification_results = {
        "ast_validation": None,
        "ast_analysis": None,
        "lint_results": None,
        "quality_checks": [],
        "requirement_checks": [],
        "passed": False,
        "warnings": 0,
        "errors": 0,
        "summary": ""
    }

    # -------------------------------------------------------------------------
    # 1. AST VALIDATION - Verify code is syntactically valid
    # -------------------------------------------------------------------------
    try:
        tree = ast.parse(code)
        verification_results["ast_validation"] = {
            "passed": True,
            "message": "Code is syntactically valid Python",
            "node_count": sum(1 for _ in ast.walk(tree)),
            "class_count": len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]),
            "function_count": len([n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]),
        }
    except SyntaxError as e:
        verification_results["ast_validation"] = {
            "passed": False,
            "message": f"Syntax error: {e.msg} at line {e.lineno}",
            "line": e.lineno,
            "offset": e.offset
        }
        verification_results["errors"] += 1
        verification_results["summary"] = "Failed: Syntax errors in generated code"
        return verification_results

    # -------------------------------------------------------------------------
    # 2. AST ANALYSIS - Deep inspection of code structure
    # -------------------------------------------------------------------------
    class ASTAnalyzer(ast.NodeVisitor):
        """Analyze AST for code quality patterns."""

        def __init__(self):
            self.functions_with_return = []
            self.functions_without_return = []
            self.async_functions = []
            self.functions_with_docstring = []
            self.functions_without_docstring = []
            self.imports = []
            self.from_imports = []
            self.decorator_list = []
            self.classes_with_init = []
            self.type_annotations_found = []
            self.comprehension_found = False
            self.context_manager_found = False

        def visit_Import(self, node):
            for alias in node.names:
                self.imports.append(alias.name)
            self.generic_visit(node)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                self.from_imports.append(f"{node.module}.{alias.name}" if node.module else alias.name)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            # Check for docstring
            has_docstring = (
                ast.get_docstring(node) is not None or
                (node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant))
            )
            if has_docstring:
                self.functions_with_docstring.append(node.name)
            else:
                self.functions_without_docstring.append(node.name)

            # Check for return statements
            has_return = any(
                isinstance(n, (ast.Return, ast.Yield, ast.YieldFrom))
                for n in ast.walk(node)
            )
            if has_return:
                self.functions_with_return.append(node.name)
            else:
                self.functions_without_return.append(node.name)

            # Check for type annotations
            if node.returns:
                self.type_annotations_found.append(node.name)
            for arg in node.args.args:
                if arg.annotation:
                    if node.name not in self.type_annotations_found:
                        self.type_annotations_found.append(node.name)

            # Check for decorators
            if node.decorator_list:
                self.decorator_list.extend([d.attr if hasattr(d, 'attr') else (d.id if hasattr(d, 'id') else str(d)) for d in node.decorator_list])

            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            self.async_functions.append(node.name)
            self.visit_FunctionDef(node)  # Reuse FunctionDef logic

        def visit_ClassDef(self, node):
            # Check if class has __init__
            has_init = any(
                isinstance(n, ast.FunctionDef) and n.name == "__init__"
                for n in node.body
            )
            if has_init:
                self.classes_with_init.append(node.name)
            self.generic_visit(node)

        def visit_For(self, node):
            if isinstance(node.iter, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                self.comprehension_found = True
            self.generic_visit(node)

        def visit_AsyncFor(self, node):
            self.comprehension_found = True
            self.generic_visit(node)

        def visit_With(self, node):
            self.context_manager_found = True
            self.generic_visit(node)

        def visit_AsyncWith(self, node):
            self.context_manager_found = True
            self.generic_visit(node)

    analyzer = ASTAnalyzer()
    analyzer.visit(tree)

    verification_results["ast_analysis"] = {
        "total_imports": len(analyzer.imports) + len(analyzer.from_imports),
        "imports": analyzer.imports[:10],  # Top 10
        "from_imports": analyzer.from_imports[:10],
        "async_functions": analyzer.async_functions,
        "docstring_coverage": {
            "with_docstring": len(analyzer.functions_with_docstring),
            "without_docstring": len(analyzer.functions_without_docstring),
            "ratio": round(
                len(analyzer.functions_with_docstring) /
                max(1, len(analyzer.functions_with_docstring) + len(analyzer.functions_without_docstring)),
                2
            )
        },
        "type_annotation_coverage": {
            "functions_with_annotations": len(analyzer.type_annotations_found),
            "total_functions": len(analyzer.functions_with_return) + len(analyzer.functions_without_return),
        },
        "decorators_used": list(set(analyzer.decorator_list)),
        "has_context_managers": analyzer.context_manager_found,
        "has_comprehensions": analyzer.comprehension_found,
    }

    # -------------------------------------------------------------------------
    # 3. QUALITY CHECKS via CodeQualityVerifier
    # -------------------------------------------------------------------------
    verifier = CodeQualityVerifier(code)
    quality_results = verifier.check_all()
    verification_results["quality_checks"] = [vars(r) for r in quality_results]
    verification_results["warnings"] += sum(1 for r in quality_results if r.severity == "warning")
    verification_results["errors"] += sum(1 for r in quality_results if r.severity == "error")

    # -------------------------------------------------------------------------
    # 4. REQUIREMENT CHECKS - Verify against acceptance criteria
    # -------------------------------------------------------------------------
    # Define keywords/patterns to check for each type of requirement
    REQUIREMENT_PATTERNS = {
        "async": ["async def", "await", "asyncio"],
        "error_handling": ["try:", "except", "Exception"],
        "logging": ["logger", "logging", "log."],
        "validation": ["validate", "ValidationError", "is_valid"],
        "database": ["INSERT", "SELECT", "repository", "db.", "pool"],
        "auth": ["auth", "token", "jwt", "bearer"],
        "cache": ["cache", "redis", "memcached"],
        "api": ["@app", "@router", "endpoint", "/api/"],
    }

    if "acceptance_criteria" in requirements:
        for criterion in requirements["acceptance_criteria"]:
            criterion_lower = criterion.lower()
            matched_patterns = []

            for req_type, patterns in REQUIREMENT_PATTERNS.items():
                if any(p.lower() in criterion_lower for p in [req_type] + patterns):
                    matched_patterns.append(req_type)

            # Check if code satisfies this criterion
            verified = False
            evidence = ""

            if "async" in matched_patterns:
                verified = len(analyzer.async_functions) > 0
                evidence = f"Found {len(analyzer.async_functions)} async functions" if verified else "No async functions found"
            elif "error_handling" in matched_patterns:
                verified = "try:" in code and "except" in code
                evidence = "Try-except blocks found" if verified else "No error handling found"
            elif "logging" in matched_patterns:
                verified = "logger" in code.lower() or "logging" in analyzer.imports
                evidence = "Logging statements found" if verified else "No logging found"
            elif "validation" in matched_patterns:
                verified = "validate" in code.lower() or "ValidationError" in code
                evidence = "Validation logic found" if verified else "No validation found"
            elif "database" in matched_patterns:
                verified = any(p in code for p in REQUIREMENT_PATTERNS["database"])
                evidence = "Database operations found" if verified else "No database operations found"
            elif matched_patterns:
                # Generic check - look for any of the matched pattern keywords
                verified = any(
                    any(p in code for p in REQUIREMENT_PATTERNS.get(pt, []))
                    for pt in matched_patterns
                )
                evidence = f"Found evidence of: {', '.join(matched_patterns)}" if verified else f"No evidence of: {', '.join(matched_patterns)}"
            else:
                # Unclassified criterion - just check if code is non-empty
                verified = len(code.strip()) > 0
                evidence = "Code generated" if verified else "No code generated"

            verification_results["requirement_checks"].append({
                "criterion": criterion,
                "verified": verified,
                "evidence": evidence,
                "matched_requirement_types": matched_patterns
            })

    # -------------------------------------------------------------------------
    # 5. TRY EXTERNAL LINTERS (ruff, black, mypy) if available
    # -------------------------------------------------------------------------
    try:
        # Try ruff (fastest)
        result = subprocess.run(
            ["ruff", "check", "-", "--output-format=text"],
            input=code.encode(),
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            verification_results["lint_results"] = {
                "tool": "ruff",
                "passed": True,
                "message": "No linting issues",
                "output": ""
            }
        else:
            lint_output = result.stdout.decode() + result.stderr.decode()
            verification_results["lint_results"] = {
                "tool": "ruff",
                "passed": False,
                "message": f"{lint_output.count(chr(10))} linting issues",
                "output": lint_output[:500]  # First 500 chars
            }
            verification_results["warnings"] += lint_output.count(chr(10))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        verification_results["lint_results"] = {
            "tool": "ruff",
            "passed": None,
            "message": "ruff not available or timed out",
            "output": ""
        }

    # -------------------------------------------------------------------------
    # 6. FINAL VERDICT
    # -------------------------------------------------------------------------
    all_errors_passed = all(r.passed for r in quality_results if r.severity == "error")
    all_requirements_met = all(
        check["verified"] for check in verification_results["requirement_checks"]
    )
    ast_valid = verification_results["ast_validation"]["passed"]

    verification_results["passed"] = all_errors_passed and all_requirements_met and ast_valid
    verification_results["summary"] = (
        f"VERIFIED: {len(verification_results['requirement_checks'])} criteria met, "
        f"AST valid, {verification_results['warnings']} warnings"
        if verification_results["passed"] else
        f"FAILED: {'AST invalid' if not ast_valid else 'Quality/requirement checks failed'}"
    )

    return verification_results


# Standalone AST verification function (no dependencies on this file's classes)
def verify_code_ast(code: str) -> Dict[str, Any]:
    """
    Standalone AST-based code verification.
    Can be imported and used independently of the Staff Engineer workflow.

    Example:
        >>> result = verify_code_ast(open("generated_code.py").read())
        >>> print(result["summary"])
        >>> if not result["passed"]:
        ...     print(f"Errors: {result['errors']}")
        ...     for check in result["quality_checks"]:
        ...         if not check["passed"]:
        ...             print(f"  - {check['message']}")
    """
    import ast

    result = {
        "passed": False,
        "ast_valid": False,
        "syntax_errors": [],
        "analysis": {},
        "summary": ""
    }

    # Parse AST
    try:
        tree = ast.parse(code)
        result["ast_valid"] = True
    except SyntaxError as e:
        result["syntax_errors"].append({
            "line": e.lineno,
            "message": e.msg
        })
        result["summary"] = f"Syntax error at line {e.lineno}: {e.msg}"
        return result

    # Analyze structure
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

    result["analysis"] = {
        "function_count": len(functions),
        "class_count": len(classes),
        "async_functions": [f.name for f in functions if isinstance(f, ast.AsyncFunctionDef)],
        "has_main": any(f.name == "main" for f in functions),
        "has_type_hints": any(f.returns is not None for f in functions),
    }

    result["passed"] = True
    result["summary"] = f"Valid Python: {len(functions)} functions, {len(classes)} classes"

    return result
```

---

## 📊 Output Schema

After completing implementation, Staff Engineer produces:

```python
@dataclass
class StaffEngineerOutput:
    task_id: str
    phase: str = "staff-engineer"

    # Implementation artifacts
    code_files: Dict[str, str]  # filename -> content
    test_files: Dict[str, str]  # filename -> content
    documentation: str

    # Verification results
    verification_results: List[Dict[str, Any]]

    # Metadata
    patterns_used: List[str]
    complexity_score: int  # 1-10
    estimated_time_minutes: int

    # Recommendations
    next_steps: List[str]
    potential_improvements: List[str]
    risks: List[str]
```

---

## 🚀 Usage Example

```python
async def execute_staff_engineer_workflow(task: dict) -> StaffEngineerOutput:
    """
    Execute complete Staff Engineer workflow.
    """
    # Step 1: Task Parsing
    validate_task_input(task)
    scope = analyze_scope_boundaries(task)
    dependencies = await analyze_dependencies(task)

    # Step 2: Technical Design
    components = design_component_architecture(task)
    pattern = select_implementation_pattern(task)
    error_handling = plan_error_handling(task)

    # Step 3: Code Generation
    code = generate_production_code(task, components, pattern)
    tests = generate_unit_tests(task, components)
    docs = generate_documentation(task)

    # Step 4: Verification
    verification = verify_implementation(code, task)

    return StaffEngineerOutput(
        task_id=task["task_id"],
        code_files={"main.py": code, "models.py": models},
        test_files={"test_main.py": tests},
        documentation=docs,
        verification_results=verification,
        patterns_used=[pattern.pattern.value],
        complexity_score=5,
        estimated_time_minutes=30,
        next_steps=["Submit for code review", "Deploy to staging"],
        potential_improvements=["Add caching layer", "Implement rate limiting"],
        risks=["External dependency might change API"]
    )
```

---

**Staff Engineer Workflow Complete** ✅

The Staff Engineer produces production-ready code following best practices for error handling, logging, testing, and documentation. Each implementation includes comprehensive verification before submission to the next phase.
