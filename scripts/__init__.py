"""
sindris scripts包初始化

确保scripts目录下的模块可以相互导入
"""
import sys
import os
from pathlib import Path

# 获取scripts目录的父目录（sindris根目录）
SINDRI_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = Path(__file__).parent.resolve()

# 将SCRIPTS_DIR添加到Python路径（如果还没有）
scripts_path = str(SCRIPTS_DIR)
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

# 将SINDRI_ROOT添加到Python路径（用于导入roles等）
root_path = str(SINDRI_ROOT)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
