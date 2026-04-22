#!/usr/bin/env python3
"""
sindris_cli.py - Sindri's CLI 实现

支持命令:
    sindris plan <task>     # 规划任务
    sindris run <task>      # 完整执行Round1-4
    sindris status          # 查看当前状态
    sindris agents list      # 列出可用角色
    sindris doctor           # 环境检查
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 路径设置
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent.parent  # ~/.openclaw/skills/sindris


def cmd_plan(args):
    """规划命令"""
    from sindris_executor import SindrisExecutor

    async def run():
        executor = SindrisExecutor(workspace_root=args.workspace or str(Path.cwd()))
        result = await executor.plan(args.task)

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("success") else 1

    return asyncio.run(run())


def cmd_run(args):
    """运行命令 - 完整执行Round1-4"""
    from sindris_executor import SindrisExecutor

    async def run():
        executor = SindrisExecutor(workspace_root=args.workspace or str(Path.cwd()))
        result = await executor.run(args.task)

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("success") else 1

    return asyncio.run(run())


def cmd_status(args):
    """状态命令"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from omx_integrator import get_integrator

    workspace = args.workspace or str(Path.cwd())
    integrator = get_integrator(workspace)

    summary = integrator.get_session_summary()

    state = {
        "workspace": workspace,
        "omx_root": str(integrator.root),
        "session_id": integrator._session_id,
        "tasks": summary.get("tasks", 0),
        "ledger_entries": summary.get("ledger_entries", 0),
        "pending_reviews": summary.get("pending_reviews", 0),
    }

    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


def cmd_agents_list(args):
    """列出角色命令"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    # from scripts.match_roles import match_roles  # 暂不需要

    # 加载角色注册表
    registry_path = Path.home() / ".openclaw" / "projects" / "agency-agents" / "roles_registry.json"

    if not registry_path.exists():
        print(f"错误: 角色注册表不存在: {registry_path}", file=sys.stderr)
        return 1

    data = json.loads(registry_path.read_text())
    roles = data.get("roles", []) if isinstance(data, dict) else data

    if args.category:
        roles = [r for r in roles if r.get("category") == args.category]

    if args.json:
        print(json.dumps(roles, indent=2, ensure_ascii=False))
    else:
        print(f"共 {len(roles)} 个角色:\n")
        by_category = {}
        for r in roles:
            cat = r.get("category", "unknown")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f"  {r.get('name')} ({r.get('id')})")

        for cat in sorted(by_category.keys()):
            print(f"[{cat}]")
            print("\n".join(by_category[cat]))
            print()

    return 0


def cmd_doctor(args):
    """环境检查命令"""
    checks = []

    # 检查Python版本
    py_version = sys.version_info
    checks.append({
        "name": "Python版本",
        "status": "✅" if py_version >= (3, 8) else "❌",
        "detail": f"{py_version.major}.{py_version.minor}.{py_version.micro}",
    })

    # 检查sindris_executor
    try:
        from sindris_executor import SindrisExecutor
        checks.append({"name": "sindris_executor", "status": "✅", "detail": "可导入"})
    except ImportError as e:
        checks.append({"name": "sindris_executor", "status": "❌", "detail": str(e)})

    # 检查OMX模块
    try:
        from omx_integrator import get_integrator
        checks.append({"name": "omx_integrator", "status": "✅", "detail": "可导入"})
    except ImportError as e:
        checks.append({"name": "omx_integrator", "status": "❌", "detail": str(e)})

    # 检查tmux
    import shutil
    tmux_available = shutil.which("tmux") is not None
    checks.append({
        "name": "tmux",
        "status": "✅" if tmux_available else "⚠️",
        "detail": "可用" if tmux_available else "不可用（降级到mock模式）",
    })

    # 检查角色注册表
    registry_path = Path.home() / ".openclaw" / "projects" / "agency-agents" / "roles_registry.json"
    if registry_path.exists():
        count = len(json.loads(registry_path.read_text()))
        checks.append({
            "name": "角色注册表",
            "status": "✅",
            "detail": f"{count} 个角色",
        })
    else:
        checks.append({
            "name": "角色注册表",
            "status": "❌",
            "detail": "文件不存在",
        })

    # 检查workspace
    workspace = Path.cwd()
    checks.append({
        "name": "Workspace",
        "status": "✅",
        "detail": str(workspace),
    })

    # 打印结果
    print("=" * 50)
    print("Sindri's Doctor")
    print("=" * 50)
    for check in checks:
        print(f"{check['status']} {check['name']}: {check['detail']}")
    print("=" * 50)

    all_passed = all(c["status"] in ("✅", "⚠️") for c in checks)
    return 0 if all_passed else 1


def cmd_jsonl(args):
    """JSONL日志命令"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from omx_integrator import get_integrator

    workspace = args.workspace or str(Path.cwd())
    integrator = get_integrator(workspace)

    ledger_path = integrator.root / "logs" / "ledger.jsonl"
    if not ledger_path.exists():
        print("错误: 日志文件不存在", file=sys.stderr)
        return 1

    if args.tail:
        lines = ledger_path.read_text().strip().split("\n")
        for line in lines[-args.tail:]:
            print(line)
    elif args.count:
        lines = ledger_path.read_text().strip().split("\n")
        print(f"共 {len(lines)} 条记录")
    else:
        print(ledger_path.read_text())

    return 0


def create_parser():
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="sindris",
        description="Sindri's - 织界统一协调系统 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    sindris plan "分析web_fetch失败率高的原因"
    sindris run "修复登录bug"
    sindris status
    sindris agents list
    sindris agents list --category testing
    sindris doctor
    sindris jsonl --tail 20
        """,
    )

    parser.add_argument(
        "--workspace", "-w",
        help="指定workspace目录（默认: 当前目录）",
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # plan命令
    plan_parser = subparsers.add_parser("plan", help="规划任务")
    plan_parser.add_argument("task", help="任务描述")
    plan_parser.set_defaults(func=cmd_plan)

    # run命令
    run_parser = subparsers.add_parser("run", help="完整执行Round1-4")
    run_parser.add_argument("task", help="任务描述")
    run_parser.set_defaults(func=cmd_run)

    # status命令
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.set_defaults(func=cmd_status)

    # agents命令
    agents_parser = subparsers.add_parser("agents", help="角色管理")
    agents_subparsers = agents_parser.add_subparsers(dest="agents_command")

    agents_list = agents_subparsers.add_parser("list", help="列出角色")
    agents_list.add_argument("--category", "-c", help="按分类筛选")
    agents_list.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    agents_list.set_defaults(func=cmd_agents_list)

    # doctor命令
    doctor_parser = subparsers.add_parser("doctor", help="环境检查")
    doctor_parser.set_defaults(func=cmd_doctor)

    # jsonl命令
    jsonl_parser = subparsers.add_parser("jsonl", help="查看JSONL日志")
    jsonl_parser.add_argument("--tail", "-n", type=int, help="显示最后N条")
    jsonl_parser.add_argument("--count", "-c", action="store_true", help="统计记录数")
    jsonl_parser.set_defaults(func=cmd_jsonl)

    return parser


def main():
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
