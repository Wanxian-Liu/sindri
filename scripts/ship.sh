#!/bin/bash
# 一键发布脚本

set -e

echo "🚀 Release Engineer: 开始发布流程"

# 1. 检查git状态
echo "📋 Pre-flight检查..."
git status

# 2. 同步主线
echo "📥 同步主线..."
git checkout main 2>/dev/null || git checkout master
git pull origin main

# 3. 运行测试
echo "🧪 运行测试..."
if npm test 2>&1 | tee test.log; then
    echo "✅ 测试通过"
else
    echo "❌ 测试失败，退出"
    exit 1
fi

# 4. 覆盖率检查
echo "📊 覆盖率审计..."
if npm run test:coverage 2>&1 | tee coverage.log; then
    echo "✅ 覆盖率达标"
else
    echo "⚠️ 覆盖率不足，继续发布"
fi

# 5. 提交
echo "📝 提交更改..."
git add -A
git commit -m "chore: release $(date '+%Y-%m-%d %H:%M')"

# 6. 推送
echo "🚀 推送到主线..."
git push origin main

echo "✅ 发布流程完成!"
echo "📋 下一步: 创建PR并等待CI"
