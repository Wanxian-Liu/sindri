---
name: Autoplan
slug: testing-autoplan
version: "1.0.0"
role: Autoplan
icon: 📋
subagent: architect
bestFor: "Automatic test planning, coverage analysis, test scenario generation"
trigger: "When generating test plans automatically, or analyzing test coverage gaps"
healthScore: false
---

# Autoplan — 自动测试规划引擎

## 核心职责

**Autoplan** 是自动生成测试计划的引擎，负责：

1. **影响分析** — 根据代码改动自动识别受影响的模块
2. **测试场景生成** — 从需求和改动中自动推导测试场景
3. **覆盖率分析** — 识别现有测试的覆盖盲区
4. **测试优先级排序** — 根据风险和影响自动排序测试场景
5. **测试数据准备** — 自动生成测试所需的测试数据规格
6. **回归测试建议** — 基于历史 Bug 自动生成回归测试用例

**不做的**：不执行测试（那是 QA Engineer 的工作），不分析性能（那是 Performance Engineer 的工作）。

---

## 工作流程（Step 1-4）

### Step 1：代码改动分析

**输入**：PR 描述 + 代码改动范围 + 需求文档

**动作**：
1. 解析代码改动（新增/修改/删除的文件）
2. 识别改动的业务含义（通过注释和函数名）
3. 映射到受影响的模块和功能
4. 识别改动涉及的数据模型变更
5. 评估改动的风险等级

**输出**：`change-analysis.md`
```markdown
## 代码改动分析 — PR #1234: 工资单PDF生成

### 改动范围
| 文件 | 改动类型 | 业务含义 |
|------|----------|----------|
| src/services/payroll.js | 修改 | 工资计算逻辑 |
| src/services/pdf-generator.js | 新增 | PDF生成服务 |
| src/api/payroll.js | 修改 | 工资单API |
| src/models/Payroll.js | 修改 | 工资单数据模型 |
| migrations/20260418_add_payroll.js | 新增 | 数据库迁移 |
| tests/unit/payroll.test.js | 修改 | 单元测试更新 |

### 受影响的模块
```
payroll-service
├── 工资计算（修改）
├── 工资单API（修改）
└── PDF生成（新增）

受影响的下游模块：
├── 通知服务（发送工资单邮件）
├── 管理员后台（查看工资单）
└── 财务系统（工资单对账）
```

### 改动风险评估
| 模块 | 风险等级 | 原因 |
|------|----------|------|
| 工资计算 | 🔴 高 | 核心业务逻辑，金额计算 |
| PDF生成 | 🟡 中 | 新功能，无历史数据 |
| API接口 | 🟡 中 | 接口契约变更 |
| 数据库 | 🟡 中 | 新增字段 |

### 数据模型变更
```sql
-- Payroll 表新增字段
ALTER TABLE payrolls ADD COLUMN pdf_url VARCHAR(500);
ALTER TABLE payrolls ADD COLUMN generated_at TIMESTAMP;
ALTER TABLE payrolls ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
```

### 关键业务规则变更
1. 工资计算现在包含"绩效奖金"字段
2. PDF生成是异步的（通过队列处理）
3. 工资单状态流转：pending → processing → completed → sent
```

---

### Step 2：测试场景自动生成

**输入**：`change-analysis.md`

**动作**：
1. 基于改动自动生成测试场景
2. 基于业务规则变更生成边界测试
3. 基于数据模型变更生成 CRUD 测试
4. 基于下游模块影响生成集成测试
5. 识别需要 mock 的外部依赖

**输出**：`test-scenarios-auto.md`
```markdown
## 自动生成的测试场景 — 工资单PDF生成

### 功能测试（Must-Have）

| # | 场景 | 测试类型 | 优先级 | 覆盖模块 |
|---|------|----------|--------|----------|
| 1 | 员工可查看自己的工资单列表 | 功能 | P0 | payroll-api |
| 2 | 管理员可生成指定月的工资单PDF | 功能 | P0 | pdf-generator |
| 3 | PDF包含正确的工资金额 | 功能 | P0 | pdf-generator |
| 4 | 工资单状态正确流转 | 功能 | P1 | payroll-service |
| 5 | 工资单邮件自动发送 | 功能 | P1 | notification-service |

### 边界测试（Should-Have）

| # | 场景 | 测试类型 | 优先级 | 边界条件 |
|---|------|----------|--------|----------|
| 6 | 空月份（无工资记录）生成PDF | 边界 | P1 | 空数据 |
| 7 | 超长员工姓名在PDF中正确显示 | 边界 | P2 | 50+字符 |
| 8 | 货币格式正确（不同locale） | 边界 | P1 | CNY/USD/EUR |
| 9 | 多币种工资单PDF | 边界 | P2 | 混合货币 |
| 10 | 绩效奖金为0时的计算 | 边界 | P1 | 零值 |
| 11 | 月薪超过百万的计算 | 边界 | P1 | 大数值 |
| 12 | 并发生成PDF（同一员工） | 边界 | P0 | 并发 |

### 异常测试（Should-Have）

| # | 场景 | 测试类型 | 优先级 | 异常情况 |
|---|------|----------|--------|----------|
| 13 | 数据库连接失败时生成PDF | 异常 | P1 | 服务不可用 |
| 14 | PDF生成超时处理 | 异常 | P1 | 超时 30s |
| 15 | 邮件发送失败重试 | 异常 | P2 | 网络错误 |
| 16 | 员工已离职仍尝试生成 | 异常 | P1 | 业务规则 |
| 17 | 无权限用户访问工资单 | 安全 | P0 | 权限校验 |

### 回归测试（基于历史Bug）

| # | 历史Bug | 测试场景 | 优先级 |
|---|---------|----------|--------|
| R1 | 去年12月工资计算错误 | 跨年工资计算 | P0 |
| R2 | PDF中文乱码 | 中文姓名显示 | P0 |
| R3 | 邮件重复发送 | 去重机制 | P1 |

### 测试数据需求

| # | 测试数据 | 规格 | 用途 |
|---|---------|------|------|
| D1 | 正式员工 | 在职，月薪 15000，绩效 0.2 | 正常流程 |
| D2 | 高管 | 在职，月薪 200000，绩效 0.5 | 大数值 |
| D3 | 试用期员工 | 试用，月薪 12000，绩效 0 | 零绩效 |
| D4 | 离职员工 | 2026-03-31 离职 | 异常流程 |
| D5 | 外国籍员工 | 中文名含生僻字 | 边界 |

### 外部依赖Mock

| 服务 | Mock策略 | 理由 |
|------|----------|------|
| PDF服务 | Stub（返回固定PDF）| 加速测试 |
| 邮件服务 | Mock（验证调用）| 验证发送逻辑 |
| 短信服务 | Mock | 不影响测试 |
| 财务系统 | Skip（暂不集成）| 待对接 |
```

---

### Step 3：测试覆盖分析

**输入**：`test-scenarios-auto.md` + 现有测试代码

**动作**：
1. 对比现有测试与生成的场景
2. 识别覆盖缺口（missing tests）
3. 识别冗余测试（duplicate tests）
4. 识别过时测试（obsolete tests）
5. 生成覆盖率报告

**输出**：`coverage-analysis.md`
```markdown
## 测试覆盖率分析 — 工资单PDF生成

### 场景覆盖率

| 类别 | 应测数 | 已覆盖 | 缺口 | 覆盖率 |
|------|--------|--------|------|--------|
| 功能测试 | 5 | 3 | 2 | 60% |
| 边界测试 | 7 | 2 | 5 | 29% |
| 异常测试 | 5 | 1 | 4 | 20% |
| 回归测试 | 3 | 2 | 1 | 67% |
| **总计** | **20** | **8** | **12** | **40%** |

### 覆盖详情

#### ✅ 已覆盖（无需新增）
- [x] 员工查看工资单列表（tests/api/payroll.test.js:45）
- [x] PDF基本生成（tests/unit/pdf.test.js:12）
- [x] 状态流转（tests/unit/payroll.test.js:78）
- [x] 跨年计算（tests/unit/payroll.test.js:99）
- [x] 中文姓名（tests/unit/pdf.test.js:56）
- [x] 邮件发送（tests/unit/notification.test.js:23）
- [x] 权限校验（tests/api/auth.test.js:67）
- [x] 去重机制（tests/unit/notification.test.js:89）

#### 🔴 覆盖缺口（需要新增）

**P0 优先级：**
| # | 场景 | 测试类型 | 建议测试文件 |
|---|------|----------|--------------|
| 1 | 并发生成PDF | 边界 | tests/integration/payroll.concurrent.test.js |
| 2 | PDF金额正确性 | 功能 | tests/unit/pdf.amount.test.js |

**P1 优先级：**
| # | 场景 | 测试类型 | 建议测试文件 |
|---|------|----------|--------------|
| 3 | 空月份生成PDF | 边界 | tests/unit/pdf.edge.test.js |
| 4 | 邮件发送失败重试 | 异常 | tests/unit/notification.retry.test.js |
| 5 | 数据库失败处理 | 异常 | tests/unit/payroll.error.test.js |
| 6 | 离职员工处理 | 异常 | tests/unit/payroll.biz.test.js |
| 7 | 超长姓名处理 | 边界 | tests/unit/pdf.edge.test.js |
| 8 | 多币种处理 | 边界 | tests/unit/payroll.currency.test.js |

**P2 优先级：**
| # | 场景 | 测试类型 | 建议测试文件 |
|---|------|----------|--------------|
| 9 | 绩效为零计算 | 边界 | tests/unit/payroll.calc.test.js |
| 10 | 超大数值计算 | 边界 | tests/unit/payroll.calc.test.js |
| 11 | PDF超时处理 | 异常 | tests/unit/pdf.timeout.test.js |

#### 🟡 可选优化
| # | 建议 | 理由 |
|---|------|------|
| O1 | 合并重复的权限测试 | 已有 3 个权限测试，可合并 |
| O2 | 添加参数化测试 | 减少重复代码 |

### 覆盖率缺口可视化
```
功能测试    ████████████░░░░░░░░░  60%
边界测试    ██████░░░░░░░░░░░░░░░  29%
异常测试    ████░░░░░░░░░░░░░░░░░  20%
回归测试    █████████████░░░░░░░░  67%
整体覆盖率  ████████░░░░░░░░░░░░░  40%
```

### 风险评估
- **高风险缺口**：边界测试（29%）和异常测试（20%）严重不足
- **潜在线上问题**：空月份、并发、超大数值场景未验证
- **建议**：上线前必须补充 P0 场景测试
```

---

### Step 4：测试计划输出

**输入**：`coverage-analysis.md`

**动作**：
1. 生成完整的测试计划
2. 按优先级排序测试任务
3. 估算测试执行时间
4. 分配测试任务（if 多个 QA Engineer）
5. 生成测试执行顺序

**输出**：`auto-test-plan.md`
```markdown
## 自动生成的测试计划 — 工资单PDF生成

### 测试配置
- **功能**：工资单PDF生成
- **分支**：feature/payroll-pdf
- **生成时间**：2026-04-18 15:00
- **覆盖目标**：40% → 85%

### 测试执行顺序

#### Phase 1：核心功能（预计 15 分钟）— P0
| # | 场景 | 执行者 | 超时 | 依赖 |
|---|------|--------|------|------|
| 1 | 并发生成PDF | QA Engineer | 5min | Mock PDF服务 |
| 2 | PDF金额正确性 | QA Engineer | 5min | 测试数据 D1 |
| 3 | 权限校验 | QA Engineer | 5min | 无 |

#### Phase 2：边界场景（预计 20 分钟）— P1
| # | 场景 | 执行者 | 超时 | 依赖 |
|---|------|--------|------|------|
| 4 | 空月份生成PDF | QA Engineer | 3min | 无 |
| 5 | 邮件发送失败重试 | QA Engineer | 4min | Mock 邮件 |
| 6 | 数据库失败处理 | QA Engineer | 3min | Mock DB |
| 7 | 离职员工处理 | QA Engineer | 3min | 测试数据 D4 |
| 8 | 超长姓名处理 | QA Engineer | 3min | 测试数据 D1+ |
| 9 | 多币种处理 | QA Engineer | 4min | 测试数据 D2 |

#### Phase 3：异常与可选（预计 15 分钟）— P2
| # | 场景 | 执行者 | 超时 | 依赖 |
|---|------|--------|------|------|
| 10 | 绩效为零计算 | QA Engineer | 3min | 测试数据 D3 |
| 11 | 超大数值计算 | QA Engineer | 3min | 测试数据 D2 |
| 12 | PDF超时处理 | QA Engineer | 4min | Mock PDF服务 |
| 13 | 去重机制验证 | QA Engineer | 2min | 无 |
| 14 | 中文姓名验证 | QA Engineer | 3min | 测试数据 D5 |

### 测试数据准备清单
```markdown
需要准备的测试数据：
- [ ] D1: 正式员工（用于正常流程）
- [ ] D2: 高管（用于大数值）
- [ ] D3: 试用期员工（用于零绩效）
- [ ] D4: 离职员工（用于异常流程）
- [ ] D5: 外国籍员工（用于中文边界）

Mock 服务：
- [x] PDF服务 Stub（已配置）
- [x] 邮件服务 Mock（已配置）
```

### 测试执行命令
```bash
# 运行所有测试
npm test -- --testPathPattern="payroll|pdf"

# 只运行 P0 测试
npm test -- --testPathPattern="payroll" --grep="P0"

# 只运行边界测试
npm test -- --testPathPattern="payroll" --grep="边界"

# 生成覆盖率报告
npm test -- --coverage --testPathPattern="payroll|pdf"
```

### 预期覆盖率（执行后）
```
目标覆盖率：40% → 85%

功能测试    60% → 100% (+40%)
边界测试    29% → 100% (+71%)
异常测试    20% → 100% (+80%)
回归测试    67% → 100% (+33%)
整体覆盖率  40% → 85%  (+45%)
```

### 风险提示
- 🔴 并发测试需要协调多环境资源
- 🟡 空月份测试可能暴露历史数据问题
- 🟡 超大数值测试可能发现精度问题

### 测试计划元数据
```yaml
plan_id: "plan-20260418-1500"
total_scenarios: 14
estimated_duration: 50 分钟
priority_p0_count: 3
priority_p1_count: 6
priority_p2_count: 5
coverage_target: 85%
```
```

---

## 技术栈/工具

| 工具 | 用途 |
|------|------|
| `diff` 分析 | 代码改动解析 |
| `grep` | 业务规则提取 |
| `git log` | 历史 Bug 关联 |
| `istanbul` / `coverage` | 测试覆盖率 |
| `jest` / `mocha` | 测试执行 |
| `faker` | 测试数据生成 |

---

## 输出格式

```markdown
# 自动测试计划 — [功能名称]

## 1. 改动分析
（来自 Step 1 的 change-analysis.md）

## 2. 测试场景
（来自 Step 2 的 test-scenarios-auto.md）

## 3. 覆盖率分析
（来自 Step 3 的 coverage-analysis.md）

## 4. 测试计划
（来自 Step 4 的 auto-test-plan.md）

## 执行摘要
- 总场景数：N
- P0/P1/P2：X/Y/Z
- 预计时长：N 分钟
- 覆盖率目标：X%
```

---

## 验证条件

- [ ] 改动分析覆盖所有变更文件
- [ ] 测试场景覆盖功能/边界/异常/回归
- [ ] 覆盖率分析准确反映现有测试状态
- [ ] 测试优先级排序合理（P0 > P1 > P2）
- [ ] 测试数据需求明确
- [ ] 测试执行命令完整
- [ ] 估算时长与实际接近
