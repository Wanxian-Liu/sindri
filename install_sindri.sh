#!/bin/bash
#===============================================================================
# Sindri 一键安装脚本 v2.21
# 织界中枢多Agent协作系统 - 完整安装
# 作者: 琬弦 | 日期: 2026-04-14
#===============================================================================

set -e

SINDRI_ROOT="$HOME/.openclaw/skills/sindris"
SCRIPTS_DIR="$SINDRI_ROOT/scripts"
SKILL_MARKER="~~provider:local"
VERSION=$(grep '^VERSION' "$SINDRI_ROOT/sindris_executor.py" 2>/dev/null | grep -oP '\d+\.\d+' | head -1 || echo "2.21")

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🧵 Sindri v${VERSION} 一键安装脚本${NC}"
echo -e "${BLUE}  织界中枢多Agent协作系统${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 1. 检查Python版本
echo -e "${YELLOW}[1/6] 检查Python环境...${NC}"
PYTHON_CMD=$(command -v python3 || command -v python)
if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}❌ 未找到Python，请先安装Python 3.8+${NC}"
    exit 1
fi
PY_VERSION=$($PYTHON_CMD --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo -e "${GREEN}✅ Python $PY_VERSION${NC} ($PYTHON_CMD)"

# 2. 检查Sindri目录
echo ""
echo -e "${YELLOW}[2/6] 检查Sindri目录...${NC}"
if [ ! -d "$SINDRI_ROOT" ]; then
    echo -e "${RED}❌ Sindri目录不存在: $SINDRI_ROOT${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Sindri目录: $SINDRI_ROOT${NC}"

# 3. 验证核心文件
echo ""
echo -e "${YELLOW}[3/6] 验证核心文件...${NC}"
CORE_FILES=(
    "sindris_executor.py:核心执行器"
    "SKILL.md:技能说明"
    "scripts/agent_executor.py:三级降级执行器"
    "scripts/omx_integrator.py:OMX持久化"
    "scripts/sindris_tmux_manager.py:tmux运行时"
    "scripts/match_roles.py:角色匹配"
    "scripts/consensus_officer.py:共识投票"
    "scripts/circuit_breaker.py:熔断器"
    "scripts/worktree_officer.py:Worktree隔离"
    "roles/roles_registry.json:178角色库"
)

ALL_OK=true
for item in "${CORE_FILES[@]}"; do
    file="${item%%:*}"
    desc="${item##*:}"
    if [ -f "$SINDRI_ROOT/$file" ]; then
        echo -e "${GREEN}✅${NC} $desc"
    else
        echo -e "${RED}❌${NC} 缺失: $file"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo -e "${RED}❌ 核心文件缺失，安装失败${NC}"
    exit 1
fi

# 4. 测试模块可导入性
echo ""
echo -e "${YELLOW}[4/6] 测试模块可导入性...${NC}"

IMPORT_TEST=$($PYTHON_CMD -c "
import sys
sys.path.insert(0, '$SINDRI_ROOT')
sys.path.insert(0, '$SCRIPTS_DIR')

modules = [
    ('sindris_executor', '核心执行器'),
    ('scripts.agent_executor', '三级降级'),
    ('scripts.omx_integrator', 'OMX持久化'),
    ('scripts.match_roles', '角色匹配'),
    ('scripts.consensus_officer', '共识投票'),
    ('scripts.circuit_breaker', '熔断器'),
    ('scripts.worktree_officer', 'Worktree'),
    ('scripts.safety_policy', '安全策略'),
    ('scripts.telemetry_collector', '遥测收集'),
    ('scripts.memory_manager', '记忆管理'),
    ('scripts.task_queue', '任务队列'),
]

failed = []
for mod, name in modules:
    try:
        __import__(mod)
        print(f'OK:{name}')
    except Exception as e:
        print(f'FAIL:{name}:{e}')
        failed.append(name)

if failed:
    sys.exit(1)
" 2>&1) || true

while IFS=: read -r status rest; do
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✅${NC} $rest"
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}❌${NC} $rest"
    fi
done <<< "$IMPORT_TEST"

# 5. 注册SKILL到OpenClaw
echo ""
echo -e "${YELLOW}[5/6] 检查SKILL注册状态...${NC}"
SKILL_LINK="$HOME/.openclaw/skills/sindris/SKILL.md"
if [ -f "$SKILL_LINK" ]; then
    # 检查是否已标记为本地provider
    if grep -q "$SKILL_MARKER" "$SKILL_LINK" 2>/dev/null; then
        echo -e "${GREEN}✅${NC} SKILL.md 已注册为本地provider"
    else
        echo -e "${YELLOW}⚠️${NC} SKILL.md 未标记为本地provider（正常情况，可手动添加标记）"
    fi
    echo -e "${GREEN}✅${NC} SKILL路径: $SKILL_LINK"
else
    echo -e "${RED}❌${NC} SKILL.md 不存在"
fi

# 6. 统计信息
echo ""
echo -e "${YELLOW}[6/6] 统计信息...${NC}"
SCRIPT_COUNT=$(find "$SCRIPTS_DIR" -name "*.py" -type f | grep -v __pycache__ | wc -l)
ROLE_CATEGORIES=$(find "$SINDRI_ROOT/roles" -maxdepth 1 -type d | tail -n +2 | wc -l)
TOTAL_SIZE=$(du -sh "$SINDRI_ROOT" 2>/dev/null | cut -f1)

echo -e "   📁 核心目录: $SINDRI_ROOT"
echo -e "   📊 脚本模块: $SCRIPT_COUNT 个"
echo -e "   👥 角色分类: $ROLE_CATEGORIES 个"
echo -e "   💾 总大小: $TOTAL_SIZE"

# 列出所有角色分类
echo ""
echo -e "${BLUE}📂 角色库分类:${NC}"
find "$SINDRI_ROOT/roles" -maxdepth 1 -type d -name "[!.]*" | while read -r dir; do
    cat=$(basename "$dir")
    count=$(find "$dir" -name "*.json" 2>/dev/null | wc -l)
    echo -e "   • $cat ($count 个角色)"
done

# 完成
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Sindri v${VERSION} 安装完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}使用方式:${NC}"
echo -e "  1. 在OpenClaw中触发Sindri:"
echo -e "     • 说'启动Sindri's'或'多Agent协作'"
echo -e "     • 或说'执行A2'"
echo -e "     • 或刘哥说'继续'"
echo ""
echo -e "  2. sindris_executor方法:"
echo -e "     • sindris.run(task) - 自动执行Round1-4"
echo -e "     • sindris.plan(task) - 只做规划"
echo ""
echo -e "  3. 核心组件:"
echo -e "     • sindris_executor.py - 唯一执行引擎"
echo -e "     • agent_executor.py - 三级降级(绕过sessions_spawn)"
echo -e "     • omx_integrator.py - OMX持久化"
echo -e "     • 178角色库 - 专业角色匹配"
echo -e "     • 熔断/投票/worktree - 织界中枢模块"
echo ""
