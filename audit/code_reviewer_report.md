# Sindris 代码质量审计报告

> [!WARNING]
> **归档状态（2026-04-27）**
> - 本报告是 **2026-04-21** 的历史代码审计快照。
> - 报告中的部分风险项已在后续版本修复（如版本对齐、测试覆盖增强、若干异常处理改进）。
> - 本文仅保留为历史证据，当前代码质量请以最新测试与当前源码为准。

**审计时间**: 2026-04-21 02:38 GMT+8  
**审计范围**: sindris_executor.py + modules/  
**代码总量**: ~3412 行 (modules) + ~600 行 (executor)  
**审计角色**: Code Reviewer

---

## 📊 执行摘要

| 维度 | 评分 | 主要发现 |
|------|------|----------|
| 代码质量 | ⚠️ 6/10 | 版本混乱、裸except过多、类型注解不一致 |
| 模块设计 | ⚠️ 6/10 | 循环依赖隐患、职责边界模糊、单例模式滥用 |
| 错误处理 | ❌ 4/10 | 静默失败、ImportError吞噬、无降级策略 |
| 可维护性 | ⚠️ 5/10 | 无单元测试、魔法数字散落、文档缺失 |

**总体评估**: ⚠️ 需要重构 — 系统功能完整但质量存在系统性风险

---

## 1️⃣ sindris_executor.py 详细审计

### 1.1 版本文档混乱

```python
# 第6行声称 v3.3，但代码中包含 v3.7 v3.8 特性
VERSION = "3.7"  # ← 这才是实际版本

# docstring说 "v3.3: 重构为纯规划器，删除误导的run()方法"
# 但没说明 v3.7 v3.8 改了什么
```

**问题**: 版本号与代码特性不匹配，docstring版本号落后至少4个版本

### 1.2 plan() 方法过于庞大（反单一职责）

`plan()` 方法超过 200 行，承担了 6 个职责：
1. 输入验证
2. 缓存检查
3. 角色匹配
4. 任务分解
5. 验证步骤注入
6. 遥测/OMX记录

**建议**: 拆分为 `plan_input_validation()`, `plan_cached()`, `plan_audit()`, `plan_evolution()`, `plan_dev()` 等方法

### 1.3 裸 except: 吞噬所有异常

```python
# 第 95-98 行
try:
    with open(cache_file) as f:
        cached = json.load(f)
        return cached
except:  # ← 捕获所有异常，包括 KeyboardInterrupt
    return None
```

**风险**: 系统级异常被静默吞噬，调试困难

### 1.4 Async/Sync 混用

```python
async def plan(self, task: str) -> Dict[str, Any]:
    # ...
    if cached_result:
        return cached_result  # ← 同步返回
    # ...
    return await self._plan_fallback(task)  # ← 异步调用

async def _plan_fallback(self, task: str) -> Dict[str, Any]:
    # 这个方法虽然是async，但内部没有任何await
    # 是一个"假异步"方法
```

### 1.5 SafetyPolicy / Telemetry / OMX 导入失败静默

```python
def _setup_safety_policy(self):
    try:
        from scripts.safety_policy import SafetyPolicy
        self.safety_policy = SafetyPolicy()
    except ImportError:
        self.safety_policy = None  # ← 静默失败
        # 后续 check_dangerous_command() 会直接 return safe=True
```

**风险**: 安全功能缺失时没有任何告警，管理员无法感知

---

## 2️⃣ 模块设计审计

### 2.1 循环依赖隐患

```
role_matcher.py 
    ↓ imports
task_decomposer.py
    ↓ imports (line 15)
role_matcher.py  ← 形成循环！
```

**代码证据**:
```python
# task_decomposer.py 第 15 行
from .role_matcher import RoleMatcher, FIXED_TEAM

# role_matcher.py 导入了 task_decomposer 相关的东西
from .task_classifier import TaskClassifier, TaskType
```

虽然目前 Python 能处理这种程度的循环导入，但它是技术债务的标志

### 2.2 FIXED_TEAM 单例被到处复制

```python
# role_matcher.py 定义了
FIXED_TEAM = [...7个角色...]

# task_decomposer.py 又 import 它
from .role_matcher import RoleMatcher, FIXED_TEAM

# 但 task_decomposer.py 内部也用
developer_role = FIXED_TEAM[3]  # ← 硬编码索引

# scheduler.py 也有自己的 FIXED_TEAM？
# gstack_integration.py 也引用了？
```

**问题**: 硬编码索引 `FIXED_TEAM[3]` 是脆弱的，角色顺序变化会导致静默错误

### 2.3 角色文件匹配逻辑过于复杂

```python
# sindris_executor.py _find_role_file() 方法
# 优先级: exact > contains > part
# 内部还做了 normalize: 去"sindri-"前缀、大小写转换
# 复杂度: O(n*m) n=角色文件数 m=匹配次数
```

**建议**: 角色文件应该用注册表（registry）直接映射，而不是动态扫描+优先级匹配

### 2.4 模块大小不一致

| 模块 | 行数 | 职责 |
|------|------|------|
| scheduler.py | 453 | 最大，调度逻辑 |
| role_matcher.py | 469 | 角色匹配核心 |
| gstack_integration.py | 382 | GStack集成 |
| task_decomposer.py | 363 | 任务分解 |
| round_manager.py | 288 | Round流程 |
| role_hierarchical_matcher.py | 223 | 分层匹配 |
| evolution_verifier.py | 211 | 进化验证 |
| task_classifier.py | 190 | 任务分类 |
| evolution_task.py | 190 | 进化任务 |
| report_generator.py | 189 | 报告生成 |
| health_score.py | 155 | 健康分 |
| role_manager.py | 142 | 角色管理 |
| gstack_hook.py | 79 | GStack Hook |
| __init__.py | 78 | 导出 |

**问题**: scheduler.py (453) 和 role_manager.py (142) 差距太大，可能需要拆分

---

## 3️⃣ 错误处理审计

### 3.1 EvolutionVerifier 验证逻辑脆弱

```python
# evolution_verifier.py 第 80-90 行
# 用字符串匹配检查代码是否实现
if role_id in content:
    lines = content.split("\n")
    for line in lines:
        if role_id in line and not line.strip().startswith("#"):
            if "pass" not in line and "NotImplemented" not in line:
                return True  # ← 误判风险高
```

**问题**: 
- `"pass"` 在字符串字面量中也会触发
- 注释中包含 role_id 会误判
- 没有用 AST 解析，只是文本匹配

### 3.2 _run_auto_verification() 吞噬异常

```python
def _run_auto_verification(self, task_type: str) -> Dict:
    try:
        from modules.evolution_verifier import EvolutionVerifier
        # ...
    except Exception as e:
        return {
            "verified": False,
            "task_type": task_type,
            "error": str(e),  # ← 错误被吞了，但没有日志
        }
```

**问题**: 验证器失败时只返回 `verified: False`，主流程会继续执行而不是报错

### 3.3 缺失 fallback 的地方

```python
# sindris_executor.py plan() 中
try:
    from modules import TaskDecomposer, RoleManager
except ImportError:
    return await self._plan_fallback(task)  # ← 有 fallback
```

但 `RoleManager` 的方法很多没有 fallback：

```python
# role_manager.py
def get_allowed_tools(self, role_name: str) -> List[str]:
    # 如果 registry 不存在，会用 ROLE_TOOL_DEFAULTS
    # 但 ROLE_TOOL_DEFAULTS 缺失角色时，返回 "general"
    # 而 general 只有 5 个工具，可能不够用
```

---

## 4️⃣ 可维护性审计

### 4.1 魔法数字

```python
# sindris_executor.py
len(task) < 3      # 最短任务长度
len(task) > 5000   # 最长任务长度
timeout: 60        # 验证超时
timeout: 300        # 审计/完善超时
timeout: 600        # 开发超时

# task_decomposer.py
fallback_role_index: 2  # Software Architect
fallback_role_index: 3  # Senior Developer
fallback_role_index: 5  # API Tester
fallback_role_index: 6  # Reality Checker
cache_ttl_hours = 24    # 缓存TTL
```

**建议**: 全部提取到 `config.py` 或 `constants.py`

### 4.2 无单元测试

```
find . -name "*test*.py" | wc -l
# 只有 scripts/test_*.py，不是模块单元测试
```

**风险**: 重构无保障，改动可能导致未知回归

### 4.3 类型注解不一致

```python
# 有类型注解
async def plan(self, task: str) -> Dict[str, Any]:

# 无类型注解
def _setup_jsonl_logger(self): ...

# 部分注解
def get_allowed_tools(self, role_name: str) -> List[str]:

# 返回类型 Any
def _get_check_fn_for_item(self, item: Dict[str, Any]) -> Optional[callable]:
```

### 4.4 角色注册表 vs 角色目录

```
roles_registry.json  ← 角色元数据
roles/*.md          ← 角色描述文件
```

**问题**: 两份数据需要手动同步，没有自动同步机制

---

## 5️⃣ 关键风险清单

| 风险级别 | 问题 | 影响 |
|----------|------|------|
| 🔴 高 | 裸 `except:` 吞噬异常 | 系统级错误被静默，调试困难 |
| 🔴 高 | SafetyPolicy 导入失败静默 | 安全功能被绕过 |
| 🟠 中 | 版本文档混乱 | 不知道哪个版本有哪些特性 |
| 🟠 中 | 无单元测试 | 重构无保障 |
| 🟠 中 | 循环依赖 | 未来可能触发 ImportError |
| 🟡 低 | 魔法数字散落 | 维护困难 |
| 🟡 低 | 类型注解不一致 | IDE 支持不完整 |

---

## 6️⃣ 改进建议（按优先级）

### P0 - 必须修复

1. **删除裸 except:**
   ```python
   # 改为
   except (json.JSONDecodeError, IOError) as e:
       self.logger.warning(f"Cache read failed: {e}")
       return None
   ```

2. **SafetyPolicy/Telemetry/OMX 导入失败时告警而非静默:**
   ```python
   if self.safety_policy is None:
       self.logger.error("SafetyPolicy not loaded - commands will NOT be checked!")
   ```

3. **EvolutionVerifier 用 AST 而非字符串匹配:**
   ```python
   import ast
   tree = ast.parse(content)
   # 检查 role_id 是否在 AST 中作为实际代码
   ```

### P1 - 应该修复

4. **拆分 plan() 方法** (200+ 行 → 每个子方法 < 50 行)
5. **抽取魔法数字到 constants.py**
6. **添加基础单元测试** (至少覆盖 plan() 的分支路径)
7. **统一版本号** (docstring vs VERSION)

### P2 - 建议优化

8. **用 registry 替代 _find_role_file() 动态扫描**
9. **添加完整的类型注解**
10. **移除 RoleManager 单例，改用依赖注入**
11. **添加集成测试验证 Round1→4 流程**

---

## 7️⃣ 代码亮点

✅ **FastPath 缓存设计** — 避免重复规划相同任务  
✅ **状态机设计** — 子代理状态追踪清晰  
✅ **JSONL 日志** — 便于事后分析  
✅ **Round 分层** — Round1→4 职责分离  
✅ **模块化拆分** — 13 个模块职责较清晰  

---

## 结论

Sindris 是一个**功能完整、架构合理**的协调系统，但**代码质量存在系统性风险**。主要问题是：

1. 异常处理过于粗放（裸 except 到处可见）
2. 安全相关功能的静默失败（SafetyPolicy）
3. 版本管理混乱
4. 缺乏测试保障

建议优先修复 P0 级别的 3 个问题，再逐步解决 P1。

---

*审计完成 | Code Reviewer | 2026-04-21*
