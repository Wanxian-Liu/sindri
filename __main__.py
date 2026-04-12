#!/usr/bin/env python3
"""
sindris CLI - 织界统一协调系统命令行工具

用法:
    python -m sindris plan "任务描述"     # 规划
    python -m sindris run "任务描述"      # 完整执行
    python -m sindris status             # 查看状态
    python -m sindris agents list        # 列出角色
    python -m sindris doctor             # 环境检查
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sindris_cli import main

if __name__ == "__main__":
    sys.exit(main())
