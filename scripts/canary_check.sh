#!/bin/bash
# Canary健康检查脚本
# 用法: ./canary_check.sh [URL] [阈值ms]

TARGET_URL="${1:-http://localhost:8501}"
THRESHOLD_MS="${2:-2000}"

echo "🐦 Canary检查: $TARGET_URL"

# 1. HTTP健康检查
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET_URL" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ HTTP健康: $HTTP_CODE"
else
    echo "❌ HTTP异常: $HTTP_CODE"
fi

# 2. 响应时间检查
RESPONSE_TIME=$(curl -s -o /dev/null -w "%{time_total}" "$TARGET_URL" 2>/dev/null || echo "0")
RESPONSE_TIME_MS=$(echo "$RESPONSE_TIME * 1000" | bc 2>/dev/null || echo "0")

if [ "$RESPONSE_TIME_MS" -lt "$THRESHOLD_MS" ]; then
    echo "✅ 响应时间: ${RESPONSE_TIME_MS}ms (阈值: ${THRESHOLD_MS}ms)"
else
    echo "⚠️ 响应时间: ${RESPONSE_TIME_MS}ms (超过阈值: ${THRESHOLD_MS}ms)"
fi

# 3. 检查应用日志（如果有）
if [ -f "/tmp/app_error.log" ]; then
    ERROR_COUNT=$(tail -100 /tmp/app_error.log 2>/dev/null | grep -ci "error" || echo "0")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo "⚠️ 错误日志: 发现 $ERROR_COUNT 个error"
    else
        echo "✅ 错误日志: 无异常"
    fi
fi

echo "---"
echo "🐦 Canary检查完成"
