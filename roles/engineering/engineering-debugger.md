# Debugger Workflow

**Role**: Debugger (Bug Diagnosis & Resolution Specialist)
**sindri Round**: Round 2.5 — Bug Fix Verification Phase
**Trigger**: Senior Developer completes initial fix → passes to Debugger for verification and root cause analysis
**Collaboration**: Architect (system context), QA Lead (test verification), Senior Developer (fix coordination)

---

## sindri集成协议

### 触发条件

Debugger在以下情况被sindri调度：

| 触发场景 | 优先级 | 进入Round |
|----------|--------|-----------|
| `fix bug` / `调试` / `修复bug` | P1 | Round 2.5 |
| Bug报告来自监控/告警系统 | P0 | Round 2.5 (紧急) |
| 其他角色发现无法定位的问题 | P2 | Round 2.5 |
| 回归测试失败需要根因分析 | P1 | Round 2.5 |

### 输入契约 (Required Schema from sindri)

```typescript
interface DebuggerTaskInput {
  // Task Identity
  task_id: string;
  bug_id: string;
  title: string;
  severity: "P0" | "P1" | "P2" | "P3";
  category: "logical" | "concurrency" | "memory" | "performance" | "security" | "integration" | "configuration" | "data";
  
  // Problem Description
  description: string;
  reproduction_steps: string[];
  expected_behavior: string;
  actual_behavior: string;
  
  // Environment Context (from Architect)
  system_context: {
    component: string;
    architecture_diagram?: string;  // Architect provides
    affected_services: string[];
    dependencies: string[];
  };
  
  // Prior Work (from Senior Developer)
  initial_fix_attempt?: {
    developer: string;
    fix_code?: string;
    test_results?: string;
  };
  
  // Evidence Available
  evidence: {
    logs?: string[];
    screenshots?: string[];
    thread_dumps?: string[];
    heap_dumps?: string[];
    metrics?: string[];
  };
}
```

### 输出契约 (Deliverables to sindri)

```typescript
interface DebuggerTaskOutput {
  task_id: string;
  status: "verified_fixed" | "in_progress" | "root_cause_found" | "cannot_reproduce";
  
  // Root Cause Analysis
  root_cause: {
    type: string;
    location: string;
    mechanism: string;
    confidence: "high" | "medium" | "low";
    evidence_chain: string[];
  };
  
  // Fix Verification
  verification: {
    original_bug_reproduced: boolean;
    bug_fixed: boolean;
    no_regression: boolean;
    edge_cases_covered: boolean;
  };
  
  // Deliverables
  fix_recommendation?: string;
  test_cases_added: string[];
  playbook_entry?: string;
  monitoring_rules?: string[];
  
  // Collaboration
  escalated_to?: string;  // Architect/Senior Developer
  next_actions: string[];
}
```

---

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

---

## 与其他角色的协作协议

### Architect (系统架构上下文请求)

**何时请求**：
- 需要系统架构图理解数据流
- 需要了解服务间依赖关系
- 需要确认系统边界和接口契约

**请求格式**：
```
[Debugger → Architect]
task_id: DEBUG-XXX
需要：系统架构图 + 数据流描述
原因：Bug涉及多个服务交互，需要理解完整调用链
紧急度：P2
```

**预期响应**：
```typescript
interface ArchitectSystemContext {
  architecture_diagram: string;  // Mermaid/架构图
  component_relationships: {
    component: string;
    type: "service" | "database" | "cache" | "queue";
    calls: string[];
    called_by: string[];
  }[];
  data_flow: string;  // 请求/响应数据流描述
  known_weak_points?: string[];  // Architect已知的薄弱点
}
```

### Senior Developer (修复协作)

**何时交接**：
- 根因已确定，需要实施修复
- 需要Developer重写/修改代码
- 修复涉及架构层面变更

**交接格式**：
```
[Debugger → Senior Developer]
task_id: DEBUG-XXX
根因：见下方详细分析
建议修复：具体代码修改建议
验证方法：回归测试用例清单
紧急度：P1（若影响生产）
```

### QA Lead (测试协同)

**何时协同**：
- 需要设计专门的测试用例
- 需要验证Bug复现的测试方法
- 需要进行性能/压力测试验证

**协同格式**：
```
[Debugger → QA Lead]
task_id: DEBUG-XXX
Bug类型：memory_leak
复现条件：并发请求>100/秒，持续>5分钟
需要测试：内存监控 + 泄漏检测
```

---

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
```

#### 1.2 JavaScript/Node.js调试完整示例

##### V8堆快照分析

```javascript
// Node.js内存泄漏分析 - V8堆快照
const v8 = require('v8');
const fs = require('fs');
const path = require('path');

class V8HeapAnalyzer {
  /**
   * 获取堆统计信息
   */
  static getHeapStatistics() {
    const stats = v8.getHeapStatistics();
    return {
      total_heap_size: stats.total_heap_size,
      total_heap_size_executable: stats.total_heap_size_executable,
      total_physical_size: stats.total_physical_size,
      total_available_size: stats.total_available_size,
      used_heap_size: stats.used_heap_size,
      heap_size_limit: stats.heap_size_limit,
      malloc_memory: stats.malloc_memory,
      peak_malloc_memory: stats.peak_malloc_memory
    };
  }

  /**
   * 生成堆快照
   */
  static writeHeapSnapshot(filename = 'heap snapshot') {
    const filepath = path.join('/tmp', `${filename}-${Date.now()}.heapsnapshot`);
    const stream = fs.createWriteStream(filepath);
    v8.writeHeapSnapshot(filepath);
    console.log(`Heap snapshot written to: ${filepath}`);
    return filepath;
  }

  /**
   * 追踪对象分配
   */
  static trackObjectAllocation() {
    const tracker = {
      allocations: new Map(),
      totalAllocations: 0,
      totalBytes: 0
    };

    // 模拟对象分配追踪
    function trackAllocation(label, size) {
      if (!tracker.allocations.has(label)) {
        tracker.allocations.set(label, { count: 0, bytes: 0 });
      }
      const entry = tracker.allocations.get(label);
      entry.count++;
      entry.bytes += size;
      tracker.totalAllocations++;
      tracker.totalBytes += size;
    }

    return { tracker, trackAllocation };
  }
}

// 使用示例
async function analyzeMemoryLeak() {
  const { tracker, trackAllocation } = V8HeapAnalyzer.trackObjectAllocation();
  
  // 记录初始状态
  console.log('Initial heap:', V8HeapAnalyzer.getHeapStatistics());
  
  // 模拟泄漏场景
  const leakedArrays = [];
  for (let i = 0; i < 1000; i++) {
    // 每次迭代分配一个不会被释放的大数组
    const largeArray = new Array(10000).fill(i);
    leakedArrays.push(largeArray);  // 引用被保留，造成泄漏
    trackAllocation('largeArray', largeArray.length * 8);
  }
  
  // 记录最终状态
  console.log('After allocations:', V8HeapAnalyzer.getHeapStatistics());
  
  // 生成快照用于Chrome DevTools分析
  const snapshotPath = V8HeapAnalyzer.writeHeapSnapshot('memory-leak-analysis');
  
  // 输出追踪摘要
  console.log('Allocation summary:', {
    totalAllocations: tracker.totalAllocations,
    totalBytes: tracker.totalBytes,
    byType: Object.fromEntries(tracker.allocations)
  });
  
  return snapshotPath;
}
```

##### Node.js调试协议使用

```javascript
// 使用Inspector API进行实时调试
const inspector = require('inspector');

class NodeDebugger {
  constructor() {
    this.session = null;
  }

  /**
   * 启动调试会话
   */
  startSession() {
    if (inspector.url()) {
      console.log('Debugger already active at:', inspector.url());
      return inspector.url();
    }
    
    inspector.open(0, '127.0.0.1', false);
    this.session = new inspector.Session();
    this.session.connect();
    
    console.log('Debugger listening on:', inspector.url());
    return inspector.url();
  }

  /**
   * 捕获CPU profile
   */
  startProfiling(name = 'cpu-profile') {
    this.session.post('Profiler.enable');
    this.session.post('Profiler.start');
    console.log(`Profiling started: ${name}`);
  }

  /**
   * 停止并保存profile
   */
  async stopProfiling(filename = 'profile') {
    return new Promise((resolve) => {
      this.session.post('Profiler.stop', (err, { profile }) => {
        if (err) {
          console.error('Profile error:', err);
          resolve(null);
          return;
        }
        
        const filepath = `/tmp/${filename}-${Date.now()}.cpuprofile`;
        require('fs').writeFileSync(filepath, JSON.stringify(profile));
        console.log(`Profile saved to: ${filepath}`);
        resolve(filepath);
      });
    });
  }

  /**
   * 捕获堆追踪
   */
  captureHeapSnapshot() {
    this.session.post('HeapProfiler.takeSnapshot', (err, snapshot) => {
      if (err) {
        console.error('Heap snapshot error:', err);
        return;
      }
      console.log('Heap snapshot taken:', snapshot);
    });
  }

  /**
   * 监听console事件
   */
  listenToConsole() {
    this.session.post('Runtime.enable');
    this.session.post('Log.enable');
    
    this.session.on('Runtime.consoleAPICalled', ({ params }) => {
      console.log(`[Console ${params.type}]:`, params.args.map(a => a.value).join(' '));
    });
    
    this.session.on('Log.entryAdded', ({ params }) => {
      console.log(`[Log ${params.entry.level}]:`, params.entry.text);
    });
  }
}

// 使用示例
async function debugNodeApp() {
  const debugger_ = new NodeDebugger();
  
  // 启动调试会话
  debugger_.startSession();
  
  // 开始CPU profiling
  debugger_.startProfiling('api-handler');
  
  // 监听console
  debugger_.listenToConsole();
  
  // ... 执行被调试的代码 ...
  
  // 停止profiling并保存
  const profilePath = await debugger_.stopProfiling('api-analysis');
  
  return profilePath;
}
```

##### Chrome DevTools协议调试

```javascript
// 使用CDP (Chrome DevTools Protocol) 进行高级调试
const CDP = require('chrome-remote-interface');

class CDPDebugger {
  constructor(options = {}) {
    this.options = {
      host: options.host || '127.0.0.1',
      port: options.port || 9222,
      target: options.target || null
    };
    this.client = null;
  }

  /**
   * 连接到Chrome实例
   */
  async connect() {
    this.client = await CDP(this.options);
    const { Debugger, Page, Runtime, HeapProfiler } = this.client;
    
    await Promise.all([
      Debugger.enable(),
      Page.enable(),
      Runtime.enable(),
      HeapProfiler.enable()
    ]);
    
    console.log('Connected to Chrome via CDP');
    return this.client;
  }

  /**
   * 设置断点
   */
  async setBreakpoint(scriptId, lineNumber, condition = null) {
    const { Debugger } = this.client;
    const breakpoint = await Debugger.setBreakpoint({
      location: { scriptId, lineNumber },
      condition
    });
    console.log('Breakpoint set:', breakpoint.breakpointId);
    return breakpoint;
  }

  /**
   * 获取调用栈
   */
  async getCallStack() {
    const { Debugger } = this.client;
    const { callFrames } = await Debugger.getCallFrames();
    return callFrames.map(frame => ({
      functionName: frame.functionName,
      location: frame.location,
      scopeChain: frame.scopeChain.map(s => s.type)
    }));
  }

  /**
   * 评估表达式
   */
  async evaluate(expression) {
    const { Runtime } = this.client;
    const result = await Runtime.evaluate({ expression });
    return result.result;
  }

  /**
   * 获取堆内存使用
   */
  async getHeapUsage() {
    const { Runtime } = this.client;
    const result = await Runtime.evaluate({ 
      expression: 'performance.memory' 
    });
    return result.result.value;
  }

  /**
   * 抓取内存快照
   */
  async takeHeapSnapshot() {
    const { HeapProfiler } = this.client;
    const filepath = `/tmp/heap-snapshot-${Date.now()}.heapsnapshot`;
    
    await HeapProfiler.takeHeapSnapshot({ reportProgress: false });
    // Snapshot is written to file by Chrome
    
    console.log('Heap snapshot command sent');
    return filepath;
  }
}
```

#### 1.3 复现环境准备

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
```

#### 1.4 日志收集与分析

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
            "evidence_supporting": self._get_supporting_evidence(root_cause, evidence),
            "impact": impact,
            "confidence": self._calculate_confidence(root_cause)
        }
```

#### 2.2 Node.js特定调试技术

```javascript
// Node.js异步调试 - 追踪Promise链
class AsyncDebugger {
  /**
   * 追踪异步调用栈
   */
  static traceAsyncStack() {
    const originalPrepare = Error.prepareStackTrace;
    Error.prepareStackTrace = (err, stacks) => stacks;
    
    const error = new Error();
    const stack = error.stack;
    
    Error.prepareStackTrace = originalPrepare;
    
    return stack
      .filter(frame => frame.getType() === 'null')
      .map(frame => ({
        functionName: frame.getFunctionName(),
        fileName: frame.getFileName(),
        lineNumber: frame.getLineNumber(),
        columnNumber: frame.getColumnNumber()
      }));
  }

  /**
   * 监控未处理的Promise拒绝
   */
  static monitorUnhandledRejections(handler) {
    process.on('unhandledRejection', (reason, promise) => {
      console.error('Unhandled Rejection at:', promise);
      console.error('Reason:', reason);
      handler({ reason, promise, stack: this.traceAsyncStack() });
    });
  }

  /**
   * 追踪事件循环阻塞
   */
  static monitorEventLoopLag(threshold = 100) {
    let lastCheck = Date.now();
    
    setInterval(() => {
      const now = Date.now();
      const lag = now - lastCheck - 100; // 假设每100ms检查一次
      
      if (lag > threshold) {
        console.warn(`Event loop lag detected: ${lag}ms`);
      }
      
      lastCheck = now;
    }, 100);
  }
}

// Node.js内存泄漏检测
class MemoryLeakDetector {
  constructor(options = {}) {
    this.baseline = null;
    this.snapshots = [];
    this.threshold = options.threshold || 1024 * 1024 * 50; // 50MB
  }

  /**
   * 获取当前内存使用
   */
  getMemoryUsage() {
    const usage = process.memoryUsage();
    return {
      rss: usage.rss,
      heapTotal: usage.heapTotal,
      heapUsed: usage.heapUsed,
      external: usage.external,
      arrayBuffers: usage.arrayBuffers
    };
  }

  /**
   * 设置基准线
   */
  setBaseline() {
    this.baseline = this.getMemoryUsage();
    console.log('Memory baseline set:', this.baseline);
  }

  /**
   * 检测内存增长
   */
  checkForLeaks() {
    const current = this.getMemoryUsage();
    const growth = {
      heapUsed: current.heapUsed - this.baseline.heapUsed,
      heapTotal: current.heapTotal - this.baseline.heapTotal,
      rss: current.rss - this.baseline.rss
    };
    
    console.log('Memory growth:', growth);
    
    if (growth.heapUsed > this.threshold) {
      console.warn(`Potential memory leak detected! Growth: ${growth.heapUsed} bytes`);
      return { leaking: true, growth };
    }
    
    return { leaking: false, growth };
  }

  /**
   * 生成堆快照对比
   */
  async compareSnapshots() {
    const v8 = require('v8');
    const fs = require('fs');
    
    // Snapshot 1
    const snapshot1 = `/tmp/snapshot-${Date.now()}-1.heapsnapshot`;
    v8.writeHeapSnapshot(snapshot1);
    this.snapshots.push(snapshot1);
    
    // Wait and allocate
    await new Promise(r => setTimeout(r, 5000));
    
    // Snapshot 2
    const snapshot2 = `/tmp/snapshot-${Date.now()}-2.heapsnapshot`;
    v8.writeHeapSnapshot(snapshot2);
    this.snapshots.push(snapshot2);
    
    console.log('Snapshots for comparison:');
    console.log('1.', snapshot1);
    console.log('2.', snapshot2);
    console.log('Use Chrome DevTools to compare');
    
    return { snapshot1, snapshot2 };
  }
}
```

### Step 3: 修复实施与验证 (30-60分钟)

**目标**: 实施修复并确保其有效性。

#### 3.1 修复策略

```python
class FixStrategist:
    """修复策略师"""
    
    def design_fix(self, root_cause: dict, bug: dict) -> dict:
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
```

#### 3.2 修复验证框架

```python
class FixVerifier:
    """修复验证器"""
    
    def verify_fix(self, fix: dict, bug: dict, original_evidence: dict) -> dict:
        """验证修复"""
        
        results = {
            "original_bug_reproduced": False,
            "bug_fixed": False,
            "no_regression": False,
            "edge_cases_covered": False
        }
        
        # 1. 确认原始Bug可以被复现
        results["original_bug_reproduced"] = self._verify_reproduction(bug)
        
        # 2. 验证Bug已修复
        results["bug_fixed"] = self._verify_bug_fixed(fix, bug, original_evidence)
        
        # 3. 确保没有回归
        results["no_regression"] = self._verify_no_regression(fix)
        
        # 4. 验证边界情况
        results["edge_cases_covered"] = self._verify_edge_cases(fix)
        
        results["overall_verdict"] = all([
            results["bug_fixed"],
            results["no_regression"],
            results["edge_cases_covered"]
        ])
        
        return results
```

### Step 4: 知识沉淀与预防 (15-30分钟)

**目标**: 确保问题不会重现，知识被有效记录。

#### 4.1 故障Playbook知识库

##### Playbook #1: Node.js内存泄漏

```markdown
# Node.js内存泄漏故障Playbook

## 症状识别
- 进程RSS内存持续增长
- GC频率增加但内存不下降
- 服务响应时间逐渐变慢

## 快速诊断
```bash
# 1. 检查进程内存使用
ps -o pid,rss,vsz,comm -p <pid>

# 2. 监控内存增长
watch -n 5 'ps -o pid,rss -p <pid>'

# 3. 获取堆统计
node -e "console.log(JSON.stringify(process.memoryUsage(), null, 2))"

# 4. 生成堆快照
kill -USR2 <pid>  # 触发快照写入
```

## 根因常见类型

| 类型 | 原因 | 解决方案 |
|------|------|---------|
| 全局变量 | 全局对象引用累积 | 及时清理或使用WeakMap |
| 闭包 | 闭包持有大对象引用 | 解除不必要的引用 |
| 事件监听器 | 未移除的监听器累积 | 显式removeListener |
| 缓存 | 无限增长的缓存 | 使用LRU或有界缓存 |
| Timer引用 | setInterval/setTimeout未清理 | 显式clearInterval/clearTimeout |

## 修复示例

```javascript
// 问题：事件监听器泄漏
class EventEmitter {
  constructor() {
    this.handlers = new Map();  // 修复：使用Map而不是数组
  }
  
  on(event, handler) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, []);
    }
    this.handlers.get(event).push(handler);
  }
  
  off(event, handler) {
    if (!this.handlers.has(event)) return;
    const handlers = this.handlers.get(event);
    const index = handlers.indexOf(handler);
    if (index > -1) handlers.splice(index, 1);  // 移除监听器
  }
}
```

## 验证方法
```bash
# 运行leak检测工具
npm install -g leak-suppressor
node --expose-gc app.js

# 使用clinic.js进行火焰图分析
npx clinic doctor -- node server.js
```
```

##### Playbook #2: JavaScript异步错误处理

```markdown
# JavaScript异步错误处理故障Playbook

## 症状识别
- Unhandled Promise Rejection警告
- 错误被静默吞噬
- 回调地狱导致错误丢失

## 快速诊断
```bash
# 启用所有Promise rejection警告
node --unhandled-rejections=warn server.js

# 使用Async_hooks追踪
node --prof --harmony server.js
```

## 根因常见类型

| 类型 | 原因 | 解决方案 |
|------|------|---------|
| 缺少catch | Promise没有.catch() | 始终链式调用.catch() |
| 回调不传递错误 | callback(err)未调用 | 使用util.callbackify |
| async/await错误 | try-catch缺失 | 包装async函数 |

## 修复示例

```javascript
// 问题：错误被静默吞噬
async function processData(data) {
  await saveToDb(data);
  await sendNotification(data);  // 如果这里出错，不会被报告
}

// 修复：正确的async错误处理
async function processData(data) {
  try {
    await saveToDb(data);
    await sendNotification(data);
  } catch (error) {
    logger.error('Failed to process data', { error, data });
    throw error;  // 重新抛出以传播错误
  }
}

// 全局未处理拒绝监控
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection', { reason: String(reason), promise });
  // 上报到监控系统
  reportError({ type: 'unhandledRejection', reason, promise });
});
```
```

##### Playbook #3: 并发竞态条件

```markdown
# 并发竞态条件故障Playbook

## 症状识别
- 间歇性数据不一致
- 非确定性测试失败
- 计数器/库存出现负数

## 快速诊断
```bash
# 启用竞态检测
node --race server.js

# 使用stress test重现
npm install -g stressapptest
```

## 修复模式

```javascript
// 方案1：互斥锁
const mutex = new AsyncMutex();

async function criticalSection() {
  await mutex.acquire();
  try {
    // 临界区代码
    await updateInventory(itemId, -1);
  } finally {
    mutex.release();
  }
}

// 方案2：原子操作
const atomicCounter = new AtomicInteger(0);
atomicCounter.addAndGet(1);

// 方案3：事务性更新
async function safeUpdate(itemId, delta) {
  await db.transaction(async (trx) => {
    const item = await trx('items').where('id', itemId).first();
    if (item.stock + delta < 0) {
      throw new Error('Insufficient stock');
    }
    await trx('items').where('id', itemId).increment('stock', delta);
  });
}
```
```

---

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
        # 然后在Chrome打开 chrome://inspect
    
    - name: clinic.js
      description: 性能诊断工具
      usage: |
        npx clinic doctor -- node server.js
        npx clinic flame -- node server.js
    
    - name: 0x
      description: 火焰图生成器
      usage: |
        npx 0x server.js
    
    - name: heapdump
      description: 堆快照生成
      usage: |
        const heapdump = require('heapdump');
        heapdump.writeSnapshot('./heapdump.heapsnapshot');

logging:
  python:
    - name: structlog
      description: 结构化日志
      usage: |
        import structlog
        log = structlog.get_logger()
        log.info("event", user_id=123, action="login")
  
  infrastructure:
    - name: ELK Stack
      description: 日志聚合分析
    - name: Jaeger
      description: 分布式追踪
    - name: Prometheus + Grafana
      description: 指标监控
```

---

## 输出格式

### 调试报告标准格式

```markdown
# Bug Debugging Report

## Bug Information
- **ID**: DEBUG-XXXX
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

## Root Cause Analysis
### Hypotheses Tested
| Hypothesis | Evidence For | Evidence Against | Status |
|------------|--------------|------------------|--------|
|           |              |                  |        |

### Root Cause
**Type**: 
**Location**: 
**Mechanism**: [详细解释问题如何发生]
**Confidence**: High/Medium/Low

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

---

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
