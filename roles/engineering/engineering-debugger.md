# Debugger Workflow

## 核心职责

Debugger 负责系统化地定位、诊断和解决软件缺陷。他们不是简单地"修复bug"，而是建立系统化的调试方法论，将问题从表象追溯到根因，并确保修复具有持久性。

### 核心职责矩阵

| 职责领域 | 具体任务 | 产出物 |
|---------|---------|--------|
| 问题诊断 | 复现问题、收集证据、定位根因 | 诊断报告、根因分析 |
| 修复实施 | 编写修复、验证修复、预防回归 | PR、测试用例 |
| 调试效率 | 优化调试流程、建立工具链 | 调试脚本、工具改进 |
| 知识沉淀 | 记录已知问题、总结调试经验 | Wiki、故障playbook |
| 主动预防 | 识别潜在问题、改进可测试性 | 改进建议、监控规则 |

### 调试 vs 开发：核心差异

```
Developer Mindset:
  ├── 关注: 功能实现
  ├── 方法: 从无到有构建
  ├── 验证: 功能测试
  └── 挑战: 复杂度管理

Debugger Mindset:
  ├── 关注: 问题定位
  ├── 方法: 从现象到根因
  ├── 验证: 复现和消除
  └── 挑战: 不确定性处理
```

## 工作流程（Step 1-4）

### Step 1: 问题复现与信息收集 (15-30分钟)

**目标**: 建立对问题的清晰理解，确认复现条件。

#### 1.1 问题分类

```python
class BugClassifier:
    """Bug分类器"""
    
    SEVERITY_LEVELS = {
        "P0": {
            "name": "Critical",
            "description": "系统不可用或核心功能完全失效",
            "examples": ["服务宕机", "数据丢失", "安全漏洞"]
        },
        "P1": {
            "name": "High",
            "description": "核心功能严重受损但有workaround",
            "examples": ["支付失败", "登录不可用"]
        },
        "P2": {
            "name": "Medium",
            "description": "功能部分受损或性能问题",
            "examples": ["功能慢", "间歇性错误"]
        },
        "P3": {
            "name": "Low",
            "description": "非核心功能问题或UI问题",
            "examples": ["错别字", "样式问题"]
        }
    }
    
    CATEGORIES = {
        "logical": "业务逻辑错误",
        "concurrency": "并发/竞态条件",
        "memory": "内存问题(泄漏/溢出)",
        "performance": "性能问题",
        "security": "安全问题",
        "integration": "集成问题",
        "configuration": "配置错误",
        "data": "数据问题"
    }
    
    def classify(self, bug_report: dict) -> dict:
        """分类Bug"""
        
        severity = self._determine_severity(bug_report)
        category = self._determine_category(bug_report)
        root_cause_domain = self._guess_domain(bug_report)
        
        return {
            "severity": severity,
            "category": category,
            "root_cause_domain": root_cause_domain,
            "estimated_fix_complexity": self._estimate_complexity(
                severity, category
            ),
            "priority_score": self._calculate_priority(
                severity, bug_report.get("impact", 1)
            )
        }
    
    def _determine_severity(self, bug_report: dict) -> str:
        """确定严重程度"""
        
        indicators = {
            "P0": [
                bug_report.get("data_loss"),
                bug_report.get("security_breach"),
                bug_report.get("system_down")
            ],
            "P1": [
                bug_report.get("core_function_broken"),
                not bug_report.get("workaround_available")
            ]
        }
        
        for severity, indicators_list in indicators.items():
            if any(indicators_list):
                return severity
        
        return "P2"  # 默认
    
    def _determine_category(self, bug_report: dict) -> str:
        """确定Bug类别"""
        
        symptoms = bug_report.get("symptoms", [])
        
        category_indicators = {
            "logical": ["wrong_result", "business_rule_violated"],
            "concurrency": ["race_condition", "deadlock", "inconsistent_state"],
            "memory": ["oom", "memory_leak", "crash"],
            "performance": ["slow", "timeout", "high_latency"],
            "security": ["unauthorized_access", "injection", "exposure"],
            "integration": ["external_service_error", "api_mismatch"],
            "configuration": ["wrong_config", "missing_env"],
            "data": ["corrupted_data", "data_loss", "migration_error"]
        }
        
        for category, keywords in category_indicators.items():
            if any(kw in symptoms for kw in keywords):
                return category
        
        return "logical"  # 默认
    
    def _guess_domain(self, bug_report: dict) -> str:
        """推测问题所属领域"""
        return self._determine_domain(bug_report)
    
    def _determine_domain(self, bug_report: dict) -> str:
        """确定问题所属领域"""
        
        domain_indicators = {
            "frontend": ["ui", "render", "click", "input", "display"],
            "backend": ["api", "endpoint", "request", "response", "database"],
            "infrastructure": ["network", "server", "deployment", "docker"],
            "security": ["auth", "permission", "access", "token"],
            "data": ["query", "pipeline", "etl", "migration"]
        }
        
        description = (bug_report.get("description", "") + 
                      " " + 
                      bug_report.get("title", "")).lower()
        
        for domain, keywords in domain_indicators.items():
            if any(kw in description for kw in keywords):
                return domain
        
        return "backend"  # 默认
```

#### 1.2 复现环境准备

```python
class ReproductionEnvironment:
    """复现环境管理器"""
    
    def prepare_environment(self, bug: dict) -> dict:
        """准备复现环境"""
        
        # 1. 确定环境类型
        env_type = self._determine_env_type(bug)
        
        # 2. 准备依赖
        dependencies = self._prepare_dependencies(bug)
        
        # 3. 设置初始状态
        initial_state = self._setup_initial_state(bug)
        
        # 4. 配置日志级别
        logging_config = self._configure_logging(bug)
        
        return {
            "environment": env_type,
            "dependencies": dependencies,
            "initial_state": initial_state,
            "logging": logging_config,
            "reproduction_script": self._create_reproduction_script(bug)
        }
    
    def _determine_env_type(self, bug: dict) -> str:
        """确定环境类型"""
        
        if bug.get("requires_production_data"):
            return "production_clone"
        elif bug.get("requires_external_services"):
            return "staging_with_mocks"
        else:
            return "local_isolated"
    
    def _prepare_dependencies(self, bug: dict) -> dict:
        """准备依赖"""
        dependencies = bug.get("dependencies", [])
        installed = []
        failed = []
        
        for dep in dependencies:
            try:
                result = subprocess.run(
                    ["pip", "install", dep],
                    capture_output=True,
                    timeout=120
                )
                if result.returncode == 0:
                    installed.append(dep)
                else:
                    failed.append({"package": dep, "error": result.stderr.decode()})
            except subprocess.TimeoutExpired:
                failed.append({"package": dep, "error": "Installation timed out"})
            except Exception as e:
                failed.append({"package": dep, "error": str(e)})
        
        return {"installed": installed, "failed": failed}
    
    def _setup_initial_state(self, bug: dict) -> dict:
        """设置初始状态"""
        initial_state = {
            "environment_variables": bug.get("env", {}),
            "files": [],
            "database": None
        }
        
        # Apply environment variables
        for key, value in bug.get("env", {}).items():
            os.environ[key] = str(value)
        
        # Prepare test files if specified
        for file_spec in bug.get("test_files", []):
            try:
                path = file_spec.get("path")
                content = file_spec.get("content", "")
                if path:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w") as f:
                        f.write(content)
                    initial_state["files"].append(path)
            except Exception as e:
                initial_state["files"].append({"error": str(e), "spec": file_spec})
        
        return initial_state
    
    def _configure_logging(self, bug: dict) -> dict:
        """配置日志"""
        log_config = {
            "level": bug.get("log_level", "DEBUG"),
            "handlers": ["console", "file"],
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
        
        # Apply logging configuration
        import logging
        level = getattr(logging, log_config["level"], logging.DEBUG)
        logging.basicConfig(
            level=level,
            format=log_config["format"]
        )
        
        return log_config
    
    def _create_reproduction_script(self, bug: dict) -> str:
        """创建复现脚本"""
        
        bug_id = bug.get('id', 'Unknown')
        bug_title = bug.get('title', 'Unknown')
        bug_severity = bug.get('severity', 'Unknown')
        setup_cmds = bug.get("setup_commands", [])
        repro_steps = bug.get("reproduction_steps", [])
        expected_error = bug.get("expected_error", "")
        
        return f'''
#!/usr/bin/env python3
"""
Bug Reproduction Script
Issue: {bug_title}
Severity: {bug_severity}
"""

import os
import sys
import subprocess
import json
from datetime import datetime

def setup():
    """Setup reproduction environment"""
    print("Setting up reproduction environment...")
    
    # Set debug environment variables
    os.environ["DEBUG"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Initialize test data
    setup_commands = {repr(setup_cmds)}
    
    for cmd in setup_commands:
        print(f"Running: {{cmd}}")
        result = subprocess.run(cmd, shell=True, capture_output=True)
        if result.returncode != 0:
            print(f"Setup failed: {{result.stderr.decode()}}")
            return False
    
    return True

def reproduce():
    """Attempt to reproduce the bug"""
    print("Reproducing bug...")
    
    reproduction_steps = {repr(repro_steps)}
    
    for i, step in enumerate(reproduction_steps, 1):
        print(f"Step {{i}}: {{step}}")
        result = subprocess.run(step, shell=True, capture_output=True)
        
        # Check for expected error
        if "{expected_error}" in result.stderr.decode():
            print(f"✓ Bug reproduced at step {{i}}")
            return True
    
    return False

def collect_recent_logs(lines=1000):
    """Collect recent log entries"""
    log_files = [
        "/var/log/app/app.log",
        "logs/application.log",
        "logs/error.log"
    ]
    
    collected_logs = []
    for log_file in log_files:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                collected_logs.append(
                    f"=== {{log_file}} ===\\n"
                    + "".join(f.readlines()[-lines:])
                )
    
    return "\\n".join(collected_logs)

def collect_evidence():
    """Collect evidence for debugging"""
    print("Collecting evidence...")
    
    evidence = {{
        "timestamp": datetime.now().isoformat(),
        "environment": dict(os.environ),
        "processes": subprocess.run(
            ["ps", "aux"], capture_output=True
        ).stdout.decode(),
        "network": subprocess.run(
            ["netstat", "-tuln"], capture_output=True
        ).stdout.decode(),
        "logs": collect_recent_logs()
    }}
    
    with open("bug_evidence.json", "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    
    print("Evidence saved to bug_evidence.json")
    return evidence

def main():
    print("=" * 60)
    print("Bug Reproduction: {bug_id}")
    print("=" * 60)
    
    if not setup():
        print("Setup failed, cannot reproduce")
        sys.exit(1)
    
    if reproduce():
        print("\\n✓ Bug successfully reproduced")
        collect_evidence()
    else:
        print("\\n✗ Bug could not be reproduced")
        print("This may indicate: ")
        print("  - Missing environment conditions")
        print("  - Timing-dependent issue")
        print("  - Need for production-like load")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    def _collect_recent_logs(self, lines: int = 1000) -> str:
        """收集最近的日志"""
        
        log_files = [
            "/var/log/app/app.log",
            "logs/application.log",
            "logs/error.log"
        ]
        
        collected_logs = []
        for log_file in log_files:
            if os.path.exists(log_file):
                with open(log_file, "r") as f:
                    collected_logs.append(
                        f"=== {{log_file}} ===\\n"
                        + "".join(f.readlines()[-lines:])
                    )
        
        return "\\n".join(collected_logs)
```

#### 1.3 日志收集与分析

```python
class LogAnalyzer:
    """日志分析器"""
    
    def analyze_logs(self, log_paths: list[str], time_range: dict) -> dict:
        """分析日志"""
        
        log_entries = self._parse_log_files(log_paths, time_range)
        
        return {
            "errors": self._extract_errors(log_entries),
            "warnings": self._extract_warnings(log_entries),
            "patterns": self._identify_patterns(log_entries),
            "timeline": self._build_timeline(log_entries),
            "correlations": self._find_correlations(log_entries)
        }
    
    def _parse_log_files(
        self, paths: list[str], time_range: dict
    ) -> list[dict]:
        """解析日志文件"""
        
        entries = []
        for path in paths:
            if not os.path.exists(path):
                continue
            
            with open(path, "r") as f:
                for line in f:
                    entry = self._parse_log_line(line)
                    if self._in_time_range(entry, time_range):
                        entries.append(entry)
        
        return sorted(entries, key=lambda x: x["timestamp"])
    
    def _parse_log_line(self, line: str) -> dict:
        """解析单行日志"""
        
        # 支持多种日志格式
        formats = [
            # JSON格式
            r'\\{{"timestamp":"(?P<timestamp>[^"]+)","level":"(?P<level>[^"]+)","message":"(?P<message>[^"]+)".*\\}}',
            # 标准格式
            r'(?P<timestamp>\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}).*?(?P<level>DEBUG|INFO|WARN|ERROR).*?(?P<message>.*)',
            # Syslog格式
            r'(?P<timestamp>\\w+\\s+\\d+\\s+\\d{2}:\\d{2}:\\d{2}).*?(?P<level>\\w+): (?P<message>.*)'
        ]
        
        for fmt in formats:
            match = re.match(fmt, line)
            if match:
                return match.groupdict()
        
        return {"raw": line, "timestamp": None}
    
    def _identify_patterns(self, entries: list[dict]) -> list[dict]:
        """识别日志模式"""
        
        # 按消息模板聚类
        message_templates = {}
        
        for entry in entries:
            template = self._extract_template(entry.get("message", ""))
            if template not in message_templates:
                message_templates[template] = []
            message_templates[template].append(entry)
        
        patterns = []
        for template, occurrences in message_templates.items():
            if len(occurrences) > 3:  # 至少出现3次
                patterns.append({
                    "template": template,
                    "count": len(occurrences),
                    "first_seen": occurrences[0]["timestamp"],
                    "last_seen": occurrences[-1]["timestamp"],
                    "sample": occurrences[0]["message"]
                })
        
        return sorted(patterns, key=lambda x: -x["count"])
    
    def _extract_template(self, message: str) -> str:
        """提取消息模板（参数化）"""
        
        # 替换数字、UUID、日期等变量
        template = re.sub(r'\\d+', '{n}', message)
        template = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{uuid}',
            template
        )
        template = re.sub(
            r'\\d{4}-\\d{2}-\\d{2}[T\\s]\\d{2}:\\d{2}:\\d{2}',
            '{datetime}',
            template
        )
        
        return template
```

### Step 2: 根因分析 (30-90分钟)

**目标**: 从现象追溯到根本原因。

#### 2.1 调试技术框架

```python
class RootCauseAnalyzer:
    """根因分析器"""
    
    def analyze(self, bug: dict, evidence: dict) -> dict:
        """执行根因分析"""
        
        # 1. 假设生成
        hypotheses = self._generate_hypotheses(bug, evidence)
        
        # 2. 假设验证
        verified_hypotheses = self._verify_hypotheses(hypotheses, evidence)
        
        # 3. 根因确定
        root_cause = self._determine_root_cause(verified_hypotheses)
        
        # 4. 影响分析
        impact = self._analyze_impact(root_cause, bug)
        
        return {
            "root_cause": root_cause,
            "hypotheses_tested": hypotheses,
            "evidence_supporting": self._get_supporting_evidence(
                root_cause, evidence
            ),
            "impact": impact,
            "confidence": self._calculate_confidence(root_cause)
        }
    
    def _generate_hypotheses(self, bug: dict, evidence: dict) -> list[dict]:
        """生成假设"""
        
        hypotheses = []
        
        # 基于症状类型生成假设
        symptom_type = bug.get("category")
        
        hypothesis_templates = {
            "logical": [
                "Incorrect conditional logic",
                "Missing boundary check",
                "Wrong operator used",
                "Off-by-one error",
                "Incorrect data type handling"
            ],
            "concurrency": [
                "Race condition in shared resource access",
                "Deadlock due to lock ordering",
                "Unprotected concurrent modification",
                "Non-thread-safe singleton",
                "Missing memory barrier"
            ],
            "memory": [
                "Memory leak in object lifecycle",
                "Use-after-free",
                "Buffer overflow",
                "Stack overflow (deep recursion)",
                "Double free"
            ],
            "performance": [
                "N+1 query problem",
                "Missing database index",
                "Inefficient algorithm (O(n²) vs O(n))",
                "Unnecessary synchronization",
                "Cache invalidation storm"
            ],
            "integration": [
                "API contract mismatch",
                "Timeout too short for slow external service",
                "Wrong serialization format",
                "Authentication token expired",
                "External service returning unexpected format"
            ]
        }
        
        for template in hypothesis_templates.get(symptom_type, []):
            hypotheses.append({
                "description": template,
                "probability": 0.5,
                "tests": self._design_tests_for_hypothesis(template)
            })
        
        # 基于证据生成特定假设
        evidence_based = self._generate_evidence_based_hypotheses(evidence)
        hypotheses.extend(evidence_based)
        
        return sorted(hypotheses, key=lambda x: -x["probability"])
    
    def _design_tests_for_hypothesis(self, hypothesis: str) -> list[dict]:
        """为假设设计测试"""
        
        test_designs = {
            "Incorrect conditional logic": [
                {
                    "name": "test_all_conditional_branches",
                    "description": "添加日志验证每个分支是否被正确执行"
                }
            ],
            "Race condition in shared resource access": [
                {
                    "name": "test_concurrent_access",
                    "description": "使用多线程并发访问验证"
                }
            ],
            "Memory leak in object lifecycle": [
                {
                    "name": "test_memory_profiling",
                    "description": "使用memory_profiler验证内存增长"
                }
            ]
        }
        
        return test_designs.get(hypothesis, [])
    
    def _determine_root_cause(
        self, verified_hypotheses: list[dict]
    ) -> dict:
        """确定根本原因"""
        
        # 找到被证实的概率最高的假设
        for hypothesis in verified_hypotheses:
            if hypothesis.get("verified") and hypothesis.get("probability", 0) >= 0.8:
                return {
                    "type": hypothesis.get("category", "unknown"),
                    "description": hypothesis.get("description", hypothesis.get("description", "Unknown")),
                    "location": hypothesis.get("location", "Unknown"),
                    "mechanism": hypothesis.get("mechanism", "Detailed mechanism unknown")
                }
        
        # 如果没有高置信度假设，返回最可能的
        if verified_hypotheses:
            top_hypothesis = verified_hypotheses[0]
            return {
                "type": top_hypothesis.get("category", "unknown"),
                "description": top_hypothesis.get("description", "Unknown"),
                "confidence": "low"
            }
        
        return {"error": "Could not determine root cause", "verified_hypotheses": verified_hypotheses}
```

#### 2.2 高级调试技术

```python
class AdvancedDebugging:
    """高级调试技术"""
    
    def debug_concurrency_issue(self, evidence: dict) -> dict:
        """调试并发问题"""
        
        return {
            "analysis": self._analyze_thread_dumps(evidence),
            "lock_graph": self._build_lock_graph(evidence),
            "race_conditions": self._identify_race_conditions(evidence),
            "recommendations": self._generate_fix_recommendations()
        }
    
    def _analyze_thread_dumps(self, evidence: dict) -> dict:
        """分析线程转储"""
        
        thread_dump = evidence.get("thread_dump", "")
        
        # 解析线程状态
        threads = []
        current_thread = None
        
        for line in thread_dump.split("\\n"):
            if '"' in line and 'prio=' in line:
                if current_thread:
                    threads.append(current_thread)
                current_thread = {"name": self._extract_thread_name(line)}
            elif current_thread and "java.lang.Thread.State" in line:
                current_thread["state"] = self._parse_thread_state(line)
            elif current_thread and "locked" in line.lower():
                current_thread.setdefault("locks", []).append(
                    self._extract_lock_info(line)
                )
        
        if current_thread:
            threads.append(current_thread)
        
        # 分析死锁
        deadlocks = self._detect_deadlocks(threads)
        
        return {
            "threads": threads,
            "thread_count": len(threads),
            "blocked_threads": [t for t in threads if t.get("state") == "BLOCKED"],
            "waiting_threads": [t for t in threads if "WAITING" in t.get("state", "")],
            "deadlocks": deadlocks
        }
    
    def _detect_deadlocks(self, threads: list[dict]) -> list[dict]:
        """检测死锁"""
        
        deadlocks = []
        
        # 构建锁依赖图
        lock_graph = {}
        for thread in threads:
            for lock in thread.get("locks", []):
                lock_id = lock["identity_hash"]
                if lock_id not in lock_graph:
                    lock_graph[lock_id] = {"holders": [], "waiters": []}
                lock_graph[lock_id]["holders"].append(thread["name"])
        
        # 检测循环等待
        # (简化版实现)
        
        return deadlocks
    
    def debug_memory_issue(self, evidence: dict) -> dict:
        """调试内存问题"""
        
        heap_dump = evidence.get("heap_dump_analysis", {})
        
        return {
            "memory_usage": self._analyze_memory_usage(heap_dump),
            "leak_suspects": self._identify_leak_suspects(heap_dump),
            "gc_analysis": self._analyze_gc_behavior(evidence),
            "recommendations": self._generate_memory_fix_recommendations()
        }
    
    def _identify_leak_suspects(self, heap_dump: dict) -> list[dict]:
        """识别内存泄漏嫌疑人"""
        
        # 基于支配树分析
        suspects = []
        
        for obj_class, stats in heap_dump.get("by_class", {}).items():
            instance_count = stats.get("instance_count", 0)
            shallow_size = stats.get("shallow_size", 0)
            retained_size = stats.get("retained_size", 0)
            
            # 启发式规则：实例数异常高或保留内存异常大
            if instance_count > 100000 or retained_size > 100 * 1024 * 1024:
                suspects.append({
                    "class": obj_class,
                    "instance_count": instance_count,
                    "retained_size": retained_size,
                    "reason": self._explain_suspicion(
                        instance_count, retained_size
                    )
                })
        
        return sorted(suspects, key=lambda x: -x["retained_size"])[:10]
    
    def debug_performance_issue(self, evidence: dict) -> dict:
        """调试性能问题"""
        
        return {
            "hotspots": self._identify_hotspots(evidence),
            "bottlenecks": self._identify_bottlenecks(evidence),
            "dependency_analysis": self._analyze_dependencies(evidence),
            "optimization_targets": self._suggest_optimizations(evidence)
        }
    
    def _identify_hotspots(self, evidence: dict) -> list[dict]:
        """识别性能热点"""
        
        profiler_data = evidence.get("profiler_data", {})
        
        hotspots = []
        
        for sample in profiler_data.get("samples", []):
            hotspots.append({
                "function": sample["function"],
                "file": sample["file"],
                "line": sample["line"],
                "cpu_time": sample.get("cpu_time", 0),
                "sample_count": sample.get("count", 0),
                "percentage": sample.get("percentage", 0)
            })
        
        return sorted(hotspots, key=lambda x: -x["cpu_time"])[:20]
```

### Step 3: 修复实施与验证 (30-60分钟)

**目标**: 实施修复并确保其有效性。

#### 3.1 修复策略

```python
class FixStrategist:
    """修复策略师"""
    
    def design_fix(
        self, root_cause: dict, bug: dict
    ) -> dict:
        """设计修复方案"""
        
        # 1. 选择修复策略
        strategy = self._select_strategy(root_cause, bug)
        
        # 2. 编写修复代码
        fix_code = self._write_fix(root_cause, strategy)
        
        # 3. 编写测试用例
        test_cases = self._write_test_cases(root_cause, bug)
        
        # 4. 评估风险
        risk_assessment = self._assess_risk(fix_code, strategy)
        
        return {
            "strategy": strategy,
            "fix_code": fix_code,
            "test_cases": test_cases,
            "risk_assessment": risk_assessment,
            "rollback_plan": self._design_rollback_plan(strategy)
        }
    
    def _select_strategy(
        self, root_cause: dict, bug: dict
    ) -> str:
        """选择修复策略"""
        
        strategies = {
            "quick_fix": {
                "applicable": [
                    "configuration_error",
                    "simple_logical_error",
                    "missing_default"
                ],
                "description": "直接修复，单点修改",
                "risk": "low"
            },
            "guard_clause": {
                "applicable": [
                    "boundary_condition",
                    "null_pointer",
                    "invalid_state"
                ],
                "description": "添加防护性检查",
                "risk": "low"
            },
            "refactor_fix": {
                "applicable": [
                    "design_flaw",
                    "complex_logic",
                    "tight_coupling"
                ],
                "description": "重构相关代码",
                "risk": "medium"
            },
            "rollback": {
                "applicable": [
                    "regression",
                    "broken_migration"
                ],
                "description": "回滚变更",
                "risk": "low"
            }
        }
        
        category = root_cause.get("type")
        for strategy_name, strategy_info in strategies.items():
            if category in strategy_info["applicable"]:
                return strategy_name
        
        return "quick_fix"  # 默认
    
    def _write_fix(self, root_cause: dict, strategy: str) -> str:
        """编写修复代码"""
        
        fix_templates = {
            "guard_clause": '''
# 添加防护性检查
def process_data(data):
    # Guard clause: 验证输入
    if data is None:
        logger.warning("Received null data, skipping")
        return None
    
    if not isinstance(data, dict):
        raise TypeError(f"Expected dict, got {type(data).__name__}")
    
    # 原有的处理逻辑
    return do_process(data)
''',
            "quick_fix": '''
# 直接修复错误逻辑
def calculate_discount(price, quantity):
    # 修复: 使用正确的运算符
    if quantity >= 10:
        return price * quantity * 0.9  # 10%折扣
    return price * quantity
''',
            "refactor_fix": '''
# 重构修复
class OrderProcessor:
    """重构后的订单处理器"""
    
    def __init__(self, validator: OrderValidator, repository: OrderRepository):
        self.validator = validator
        self.repository = repository
    
    def process_order(self, order_data: dict) -> Order:
        # 分解为独立的验证和持久化步骤
        validated_order = self.validator.validate(order_data)
        return self.repository.save(validated_order)
'''
        }
        
        return fix_templates.get(strategy, "")
    
    def _write_test_cases(
        self, root_cause: dict, bug: dict
    ) -> list[dict]:
        """编写测试用例"""
        
        test_cases = []
        
        # 1. 复现原始Bug的测试
        test_cases.append({
            "name": f"test_reproduce_{bug.get('id', 'bug')}",
            "description": f"复现原始Bug: {bug.get('title')}",
            "code": f'''
def test_reproduce_{bug.get('id', 'bug')}():
    """复现原始Bug"""
    # Given
    input_data = {bug.get('reproduction_steps', [])}
    
    # When
    result = process(input_data)
    
    # Then
    assert result.status == "error"  # Bug状态下应该报错
''',
            "expected_to_fail": True
        })
        
        # 2. 修复后的验证测试
        test_cases.append({
            "name": f"test_fix_{bug.get('id', 'bug')}",
            "description": f"验证修复: {bug.get('title')}",
            "code": f'''
def test_fix_{bug.get('id', 'bug')}():
    """验证修复"""
    # Given
    input_data = {bug.get('reproduction_steps', [])}
    
    # When
    result = process(input_data)
    
    # Then
    assert result.status == "success"
''',
            "expected_to_pass": True
        })
        
        # 3. 边界情况测试
        test_cases.append({
            "name": "test_edge_cases",
            "description": "边界情况测试",
            "code": '''
@pytest.mark.parametrize("input,expected", [
    (None, None),
    ({}, {}),
    ({"valid": "data"}, {"valid": "data"}),
])
def test_edge_cases(input, expected):
    result = process(input)
    assert result == expected
'''
        })
        
        return test_cases
    
    def _assess_risk(self, fix_code: str, strategy: str) -> dict:
        """评估修复风险"""
        
        risk_indicators = {
            "low": [
                "guard_clause",
                "quick_fix",
                "configuration_change"
            ],
            "medium": [
                "refactor_fix",
                "new_algorithm"
            ],
            "high": [
                "architectural_change",
                "database_migration"
            ]
        }
        
        risk_level = "low"
        for level, strategies in risk_indicators.items():
            if strategy in strategies:
                risk_level = level
                break
        
        return {
            "risk_level": risk_level,
            "affected_components": self._identify_affected_components(fix_code),
            "side_effects": self._potential_side_effects(fix_code),
            "requires_rollback_plan": risk_level in ["medium", "high"]
        }
```

#### 3.2 修复验证框架

```python
class FixVerifier:
    """修复验证器"""
    
    def verify_fix(
        self,
        fix: dict,
        bug: dict,
        original_evidence: dict
    ) -> dict:
        """验证修复"""
        
        results = {
            "original_bug_reproduced": False,
            "bug_fixed": False,
            "no_regression": False,
            "edge_cases_covered": False
        }
        
        # 1. 确认原始Bug可以被复现
        results["original_bug_reproduced"] = self._verify_reproduction(
            bug
        )
        
        # 2. 验证Bug已修复
        results["bug_fixed"] = self._verify_bug_fixed(
            fix, bug, original_evidence
        )
        
        # 3. 确保没有回归
        results["no_regression"] = self._verify_no_regression(
            fix
        )
        
        # 4. 验证边界情况
        results["edge_cases_covered"] = self._verify_edge_cases(fix)
        
        results["overall_verdict"] = all([
            results["bug_fixed"],
            results["no_regression"],
            results["edge_cases_covered"]
        ])
        
        return results
    
    def _verify_bug_fixed(
        self, fix: dict, bug: dict, original_evidence: dict
    ) -> bool:
        """验证Bug已修复"""
        
        # 运行修复后的代码
        # 检查是否还会出现相同的错误
        
        # 1. 单元测试
        test_result = self._run_unit_tests(fix)
        if not test_result["passed"]:
            return False
        
        # 2. 集成测试
        integration_result = self._run_integration_tests(fix)
        if not integration_result["passed"]:
            return False
        
        # 3. 手动验证
        manual_verification = self._manual_verify(fix, bug)
        
        return test_result["passed"] and manual_verification
    
    def _verify_no_regression(self, fix: dict) -> bool:
        """验证没有回归"""
        
        # 运行完整的测试套件
        regression_tests = self._run_regression_tests()
        
        return regression_tests["pass_rate"] >= 0.99  # 99%以上通过
    
    def _run_regression_tests(self) -> dict:
        """运行回归测试"""
        
        return {
            "total": 1000,
            "passed": 995,
            "failed": 5,
            "skipped": 0,
            "pass_rate": 0.995,
            "failures": [
                {
                    "test": "test_legacy_feature_X",
                    "error": "AssertionError",
                    "fix_required": True
                }
            ]
        }
```

### Step 4: 知识沉淀与预防 (15-30分钟)

**目标**: 确保问题不会重现，知识被有效记录。

#### 4.1 调试知识库

```python
class DebugKnowledgeBase:
    """调试知识库"""
    
    def record_debugging_session(
        self, session: dict
    ) -> str:
        """记录调试会话"""
        
        doc = f'''
# Debugging Session Report

## Basic Information
- **Bug ID**: {session.get('bug_id')}
- **Title**: {session.get('title')}
- **Severity**: {session.get('severity')}
- **Date**: {session.get('date')}
- **Duration**: {session.get('duration')}

## Problem Summary
{session.get('problem_summary')}

## Root Cause
**Category**: {session.get('root_cause', {}).get('category')}
**Location**: {session.get('root_cause', {}).get('location')}
**Mechanism**: {session.get('root_cause', {}).get('mechanism')}

## Investigation Process

### Hypotheses Tested
{self._format_hypotheses(session.get('hypotheses', []))}

### Evidence Collected
- Log files: {len(session.get('evidence', {}).get('logs', []))} files
- Thread dumps: {len(session.get('evidence', {}).get('thread_dumps', []))} files
- Heap dumps: {session.get('evidence', {}).get('heap_dump', 'N/A')}

### Key Insights
{self._format_insights(session.get('insights', []))}

## Solution
{session.get('solution')}

## Verification
- Unit tests: {session.get('verification', {}).get('unit_tests')}
- Integration tests: {session.get('verification', {}).get('integration_tests')}
- Regression tests: {session.get('verification', {}).get('regression_tests')}

## Prevention Measures
{self._format_prevention_measures(session.get('prevention', []))}

## Related Issues
{self._format_related_issues(session.get('related_issues', []))}

## Lessons Learned
{self._format_lessons_learned(session.get('lessons', []))}
'''
        
        return doc
    
    def create_playbook(
        self, category: str, solution_template: dict
    ) -> str:
        """创建故障处理手册"""
        
        return f'''
# {category.title()} Troubleshooting Playbook

## Symptoms
{solution_template.get('symptoms', 'TBD')}

## Quick Diagnosis
```
{solution_template.get('quick_diagnosis_commands', 'TBD')}
```

## Investigation Steps

### Step 1: Collect Evidence
```bash
{solution_template.get('evidence_collection_commands', 'TBD')}
```

### Step 2: Analyze Logs
```python
{solution_template.get('log_analysis_script', '# TBD')}
```

### Step 3: Check System State
```bash
{solution_template.get('system_check_commands', 'TBD')}
```

## Known Root Causes

### Cause 1: {solution_template.get('cause_1_title', 'TBD')}
**Symptoms**: {solution_template.get('cause_1_symptoms', 'TBD')}
**Fix**: {solution_template.get('cause_1_fix', 'TBD')}

### Cause 2: {solution_template.get('cause_2_title', 'TBD')}
**Symptoms**: {solution_template.get('cause_2_symptoms', 'TBD')}
**Fix**: {solution_template.get('cause_2_fix', 'TBD')}

## Escalation
{solution_template.get('escalation_path', 'TBD')}

## Prevention
{solution_template.get('prevention_measures', 'TBD')}
'''
```

#### 4.2 预防措施框架

```python
class PreventionFramework:
    """预防措施框架"""
    
    def recommend_preventions(
        self, root_cause: dict, bug: dict
    ) -> list[dict]:
        """推荐预防措施"""
        
        preventions = []
        
        # 1. 测试增强
        if root_cause.get("category") == "logical":
            preventions.append({
                "type": "test_enhancement",
                "action": "添加边界条件和异常场景的测试",
                "priority": "high",
                "effort": "low"
            })
        
        # 2. 监控告警
        if root_cause.get("category") in ["performance", "memory"]:
            preventions.append({
                "type": "monitoring",
                "action": "添加相关指标的监控和告警",
                "priority": "high",
                "effort": "medium"
            })
        
        # 3. 代码审查检查项
        if root_cause.get("category") == "concurrency":
            preventions.append({
                "type": "code_review_checklist",
                "action": "在代码审查清单中添加并发安全检查项",
                "priority": "high",
                "effort": "low"
            })
        
        # 4. 静态分析规则
        preventions.append({
            "type": "static_analysis",
            "action": "添加针对该问题类型的静态分析规则",
            "priority": "medium",
            "effort": "medium"
            })
        
        # 5. 架构改进
        if root_cause.get("category") in ["integration", "data"]:
            preventions.append({
                "type": "architecture",
                "action": "考虑添加契约测试或数据验证层",
                "priority": "medium",
                "effort": "high"
            })
        
        return preventions
    
    def generate_monitoring_rules(
        self, root_cause: dict, bug: dict
    ) -> list[dict]:
        """生成监控规则"""
        
        rules = []
        
        # 基于问题类型生成特定监控
        category = root_cause.get("category")
        
        monitoring_templates = {
            "performance": [
                {
                    "name": f"high_latency_{bug.get('id')}",
                    "metric": "request_latency_p99",
                    "condition": "> 1000",
                    "window": "5m",
                    "severity": "warning"
                }
            ],
            "memory": [
                {
                    "name": f"memory_leak_{bug.get('id')}",
                    "metric": "memory_usage_growth_rate",
                    "condition": "> 10% per hour",
                    "window": "1h",
                    "severity": "critical"
                }
            ],
            "concurrency": [
                {
                    "name": f"deadlock_{bug.get('id')}",
                    "metric": "thread_blocked_count",
                    "condition": "> 10",
                    "window": "1m",
                    "severity": "critical"
                }
            ]
        }
        
        return monitoring_templates.get(category, [])
```

## 技术栈/工具（含代码示例）

### 调试工具链

```yaml
# Debugging Tool Stack

language_tools:
  python:
    - name: pdb/ipdb
      description: 命令行调试器
      usage: |
        import pdb; pdb.set_trace()
        
        # 常用命令:
        # n (next) - 执行下一行
        # s (step) - 进入函数
        # c (continue) - 继续执行
        # p <var> - 打印变量
        # l (list) - 显示代码
        # w (where) - 显示调用栈
    
    - name: breakpoint()
      description: Python 3.7+内置断点
      usage: |
        breakpoint()  # 使用pdb
        # 或设置环境变量使用其他调试器
        # PYTHONBREAKPOINT=ipdb.set_trace breakpoint()
    
    - name: pytest-divert
      description: 测试输出捕获
      usage: |
        def test_debug():
            import divert
            with divert.stdout() as stdout:
                my_function()
            assert "expected" in stdout.getvalue()
    
    - name: memory_profiler
      description: 内存分析
      usage: |
        @memory_profiler.profile
        def my_function():
            # 函数内存分析
            pass
    
    - name: py-spy
      description: 采样分析器
      usage: |
        py-spy record -o profile.svg -- python myscript.py
    
    - name: objgraph
      description: 对象图分析
      usage: |
        import objgraph
        objgraph.show_most_common_types()

  java:
    - name: jdb
      description: Java调试器
    
    - name: VisualVM
      description: 性能分析工具
    
    - name: YourKit
      description: 专业分析器
    
    - name: Arthas
      description: Alibaba诊断工具
      usage: |
        # 热修复示例
        vmtool -c <pid> --action getInstances --className com.example.User
        
  javascript:
    - name: Chrome DevTools
      description: 浏览器调试
      usage: |
        debugger; // 断点
        console.trace(); // 堆栈追踪
    
    - name: Node.js Inspector
      description: Node.js调试
      usage: |
        node --inspect-brk server.js

logging:
  python:
    - name: structlog
      description: 结构化日志
      usage: |
        import structlog
        log = structlog.get_logger()
        log.info("event", user_id=123, action="login")
    
    - name: loguru
      description: 简化日志
      usage: |
        from loguru import logger
        logger.debug("Debug info: {var}", var=value)
  
  infrastructure:
    - name: ELK Stack
      description: 日志聚合分析
    - name: Jaeger
      description: 分布式追踪
    - name: Prometheus + Grafana
      description: 指标监控
```

### 日志分析命令

```bash
# 日志分析命令集

# 实时tail错误日志
tail -f app.log | grep ERROR

# 查找错误模式
grep -E "ERROR|Exception|Traceback" app.log

# 统计错误频率
grep ERROR app.log | awk '{print $NF}' | sort | uniq -c | sort -rn

# 时间范围分析
awk '/2024-01-15 10:00/,/2024-01-15 11:00/' app.log

# 关联请求ID
grep "request_id=abc123" app.log

# JSON日志解析
cat app.log | jq '. | select(.level == "ERROR")'

# 性能日志分析
grep "latency" app.log | awk -F'latency=' '{print $2}' | awk '{print $1}' | sort -n

# 内存dump分析
jmap -dump:format=b,file=heap.bin <pid>
jhat heap.bin
```

### 调试脚本模板

```python
#!/usr/bin/env python3
"""
通用调试脚本模板
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Any

class DebugScript:
    """调试脚本基类"""
    
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Debug Script")
        self.setup_args()
        
    def setup_args(self):
        """设置命令行参数"""
        self.parser.add_argument("--log-file", required=True)
        self.parser.add_argument("--error-pattern", default="ERROR")
        self.parser.add_argument("--output", default="debug_report.json")
        
    def run(self):
        """运行调试流程"""
        args = self.parser.parse_args()
        
        print(f"Starting debug analysis at {datetime.now()}")
        
        # 1. 收集证据
        evidence = self.collect_evidence(args)
        
        # 2. 分析问题
        analysis = self.analyze(evidence)
        
        # 3. 生成报告
        self.generate_report(analysis, args.output)
        
        print(f"Debug report saved to {args.output}")
        
    def collect_evidence(self, args) -> dict:
        """收集证据"""
        return {
            "log_file": args.log_file,
            "error_pattern": args.error_pattern,
            "timestamp": datetime.now().isoformat()
        }
    
    def analyze(self, evidence: dict) -> dict:
        """分析问题"""
        return {"summary": "Analysis pending"}
    
    def generate_report(self, analysis: dict, output: str):
        """生成报告"""
        with open(output, "w") as f:
            json.dump(analysis, f, indent=2, default=str)


if __name__ == "__main__":
    script = DebugScript()
    script.run()
```

## 输出格式

### 调试报告标准格式

```markdown
# Bug Debugging Report

## Bug Information
- **ID**: BUG-XXXX
- **Title**: 
- **Severity**: P0/P1/P2/P3
- **Category**: logical/concurrency/memory/performance/security/...
- **Reporter**: 
- **Date Reported**: 

## Problem Summary
[清楚描述问题现象]

## Environment
- **Environment**: Production/Staging/Local
- **Affected Version**: 
- **Affected Components**: 

## Reproduction
### Steps to Reproduce
1. 
2. 
3. 

### Expected Behavior
[期望的行为]

### Actual Behavior
[实际的行为]

## Evidence Collected
- Logs: [file paths]
- Screenshots: [paths]
- Thread Dumps: [paths]
- Heap Dumps: [paths]

## Root Cause Analysis
### Hypotheses Tested
| Hypothesis | Evidence For | Evidence Against | Status |
|------------|--------------|------------------|--------|
|           |              |                  |        |

### Root Cause
**Type**: 
**Location**: 
**Mechanism**: [详细解释问题如何发生]

### Impact Analysis
[分析问题的影响范围]

## Solution
### Fix Strategy
[选择的修复策略]

### Code Changes
```language
// 修复代码
```

### Test Cases Added
```language
// 新增测试
```

## Verification
- [x] Original bug reproduced
- [x] Bug fixed
- [x] No regression
- [x] Edge cases covered

## Prevention
### Short-term
- 

### Long-term
- 

## Related Documentation
- 

## Lessons Learned
- 
```

## 验证条件

### 修复验证检查清单

```python
class FixVerificationChecklist:
    """修复验证检查清单"""
    
    def verify_fix_complete(self, fix: dict, bug: dict) -> dict:
        """验证修复完整性"""
        
        checks = {
            "code_fix": self._verify_code_fix(fix),
            "tests": self._verify_tests(fix),
            "documentation": self._verify_documentation(fix),
            "monitoring": self._verify_monitoring(fix),
            "rollback_plan": self._verify_rollback_plan(fix)
        }
        
        return {
            "checks": checks,
            "all_passed": all(checks.values()),
            "failed_checks": [k for k, v in checks.items() if not v]
        }
    
    def _verify_code_fix(self, fix: dict) -> bool:
        """验证代码修复"""
        return (
            fix.get("code") is not None and
            len(fix.get("code", "")) > 0
        )
    
    def _verify_tests(self, fix: dict) -> bool:
        """验证测试"""
        return (
            len(fix.get("test_cases", [])) > 0 and
            all(tc.get("implemented") for tc in fix.get("test_cases", []))
        )
    
    def _verify_documentation(self, fix: dict) -> bool:
        """验证文档"""
        return fix.get("debug_report") is not None
    
    def _verify_monitoring(self, fix: dict) -> bool:
        """验证监控"""
        return len(fix.get("monitoring_rules", [])) > 0
    
    def _verify_rollback_plan(self, fix: dict) -> bool:
        """验证回滚计划"""
        return fix.get("rollback_steps") is not None
```

### 回归测试标准

| 测试类型 | 覆盖要求 | 通过标准 |
|---------|---------|----------|
| 单元测试 | 新代码100%，核心模块80% | 100%通过 |
| 集成测试 | 关键路径覆盖 | 100%通过 |
| 系统测试 | 全功能覆盖 | 100%通过 |
| 性能测试 | 响应时间在SLA内 | 100%通过 |
| 安全测试 | 无高危漏洞 | 无高危 |

### 根因分析质量标准

| 维度 | 标准 | 验证方法 |
|------|------|----------|
| 完整性 | 所有假设都被验证或排除 | 检查假设列表 |
| 证据支持 | 每个结论都有证据支撑 | 检查证据链 |
| 置信度 | 高置信度根因有多个独立证据 | 计算置信度 |
| 可重现性 | 根因可以解释所有观察到的现象 | 重现验证 |
