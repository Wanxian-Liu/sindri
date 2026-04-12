"""
Worktree隔离官 (Worktree Officer)
管理git worktree，为每个Agent创建独立工作目录
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import shutil

@dataclass
class WorktreeConfig:
    """Worktree配置"""
    base_dir: str = "~/.openclaw/worktrees"
    project_name: str = "default"
    auto_cleanup: bool = True

class WorktreeOfficer:
    """
    Worktree隔离官 - 管理git worktree
    
    功能:
    - 为每个Agent创建独立的worktree目录
    - 隔离Agent的文件操作范围
    - 自动清理worktree
    """
    
    def __init__(self, config: Optional[WorktreeConfig] = None):
        self.config = config or WorktreeConfig()
        self.worktree_map: Dict[str, str] = {}  # agent_name -> worktree_path
        self.project_dir: Optional[str] = None
    
    def _expand_path(self, path: str) -> str:
        """展开~和环境变量"""
        return os.path.expanduser(os.path.expandvars(path))
    
    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """运行git命令"""
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=cwd or self.project_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Git command timeout"
        except Exception as e:
            return -1, "", str(e)
    
    def _validate_agent_name(self, name: str) -> bool:
        """验证Agent名称合法性"""
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))
    
    def setup_project(self, project_dir: str) -> bool:
        """
        初始化项目git仓库
        
        Args:
            project_dir: 项目目录
            
        Returns:
            bool: 是否成功
        """
        self.project_dir = self._expand_path(project_dir)
        
        # 确保目录存在
        Path(self.project_dir).mkdir(parents=True, exist_ok=True)
        
        # 检查是否是git仓库
        code, _, _ = self._run_git(['rev-parse', '--git-dir'])
        if code != 0:
            # 初始化git仓库
            code, _, _ = self._run_git(['init'])
            if code != 0:
                return False
            
            # 配置git用户
            self._run_git(['config', 'user.email', 'council@openclaw'])
            self._run_git(['config', 'user.name', 'Council'])
            
            # 创建初始提交
            code, _, _ = self._run_git(['add', '-A'])
            if code == 0:
                self._run_git(['commit', '-m', 'council: initial'])
        
        return True
    
    def setup_worktree(self, agent_name: str) -> Optional[str]:
        """
        为Agent创建worktree
        
        Args:
            agent_name: Agent名称
            
        Returns:
            str: worktree目录路径，失败返回None
        """
        if not self._validate_agent_name(agent_name):
            raise ValueError(f"Invalid agent name: {agent_name}")
        
        if self.project_dir is None:
            raise ValueError("Project not initialized. Call setup_project() first.")
        
        # 构建worktree路径
        base = self._expand_path(self.config.base_dir)
        wt_dir = os.path.join(base, self.config.project_name, agent_name)
        
        # 如果已存在，先移除
        if os.path.exists(wt_dir):
            self.remove_worktree(agent_name)
        
        # 获取分支名
        branch = f"council/{agent_name}"
        
        # 创建worktree
        code, stdout, stderr = self._run_git(
            ['worktree', 'add', '-b', branch, wt_dir, 'HEAD'],
            cwd=self.project_dir
        )
        
        if code != 0:
            # 可能分支已存在，尝试复用
            code2, _, _ = self._run_git(['worktree', 'list'])
            if agent_name in code2:
                self.worktree_map[agent_name] = wt_dir
                return wt_dir
            return None
        
        # 创建成功，记录映射
        self.worktree_map[agent_name] = wt_dir
        
        # 创建CLAUDE.md约束文件
        self._write_agent_constraints(wt_dir, agent_name)
        
        return wt_dir
    
    def setup_worktrees(self, agent_names: List[str]) -> Dict[str, str]:
        """
        为多个Agent创建worktree
        
        Args:
            agent_names: Agent名称列表
            
        Returns:
            Dict[str, str]: agent_name -> worktree_path
        """
        results = {}
        for name in agent_names:
            wt_dir = self.setup_worktree(name)
            if wt_dir:
                results[name] = wt_dir
        return results
    
    def remove_worktree(self, agent_name: str) -> bool:
        """
        移除Agent的worktree
        
        Args:
            agent_name: Agent名称
            
        Returns:
            bool: 是否成功
        """
        if agent_name not in self.worktree_map:
            # 尝试从git worktree list查找
            code, stdout, _ = self._run_git(['worktree', 'list'])
            if code == 0 and agent_name in stdout:
                # 找到，移除
                wt_dir = None
                for line in stdout.split('\n'):
                    if agent_name in line:
                        wt_dir = line.split()[0]
                        break
                if wt_dir:
                    self._run_git(['worktree', 'remove', '--force', wt_dir])
        
        # 删除本地目录
        if agent_name in self.worktree_map:
            wt_dir = self.worktree_map[agent_name]
            if os.path.exists(wt_dir):
                shutil.rmtree(wt_dir, ignore_errors=True)
            del self.worktree_map[agent_name]
        
        # 删除git分支
        branch = f"council/{agent_name}"
        self._run_git(['branch', '-D', branch])
        
        return True
    
    def cleanup_all(self) -> int:
        """
        清理所有worktree
        
        Returns:
            int: 清理数量
        """
        count = 0
        agent_names = list(self.worktree_map.keys())
        for name in agent_names:
            if self.remove_worktree(name):
                count += 1
        return count
    
    def get_worktree_path(self, agent_name: str) -> Optional[str]:
        """
        获取Agent的worktree路径
        
        Args:
            agent_name: Agent名称
            
        Returns:
            str: worktree路径
        """
        return self.worktree_map.get(agent_name)
    
    def get_status(self) -> dict:
        """
        获取状态
        
        Returns:
            dict: 状态信息
        """
        return {
            "project_dir": self.project_dir,
            "worktree_count": len(self.worktree_map),
            "worktrees": self.worktree_map.copy(),
            "base_dir": self._expand_path(self.config.base_dir)
        }
    
    def _write_agent_constraints(self, wt_dir: str, agent_name: str):
        """写入Agent约束文件"""
        claude_dir = os.path.join(wt_dir, '.claude')
        Path(claude_dir).mkdir(parents=True, exist_ok=True)
        
        content = f"""# {agent_name}

> This file is auto-generated by WorktreeOfficer

## Workspace Boundary

Only operate within: `{wt_dir}`

## Rules

- Do not access paths outside your workspace
- Write all outputs to your worktree directory
- Report completion with [CONSENSUS: YES] or [CONSENSUS: NO]
"""
        
        with open(os.path.join(claude_dir, 'CLAUDE.md'), 'w') as f:
            f.write(content)


# 快捷函数
def create_worktree_officer(
    base_dir: str = "~/.openclaw/worktrees",
    project_name: str = "default"
) -> WorktreeOfficer:
    """创建WorktreeOfficer实例"""
    config = WorktreeConfig(base_dir=base_dir, project_name=project_name)
    return WorktreeOfficer(config)
