"""
safety_policy.py - 危险操作拦截模块

基于 oh-my-codex safety hook 概念设计
功能: 在执行前检测并拦截危险命令和路径

危险等级:
  - CRITICAL: 直接阻止执行，记录警告
  - HIGH: 警告但允许执行（可配置）
  - MEDIUM: 记录日志

检测类型:
  1. 危险命令: rm -rf, forkbomb, :(){:|:&};:, dd, mkfs等
  2. 危险路径: /system, /etc, /boot, /dev, ~/.ssh等
  3. 危险参数: --no-preserve-root, -P等
"""

import re
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

# ============================================================
# 危险等级定义
# ============================================================

class DangerLevel(Enum):
    CRITICAL = "critical"  # 必须阻止
    HIGH = "high"          # 警告后阻止
    MEDIUM = "medium"      # 记录但允许
    LOW = "low"            # 仅记录

# ============================================================
# 危险模式定义
# ============================================================

@dataclass
class DangerPattern:
    """危险模式"""
    pattern: str
    danger_level: DangerLevel
    description: str
    example: str
    mitigation: str = ""

# 危险命令模式
DANGEROUS_COMMANDS = [
    DangerPattern(
        pattern=r"rm\s+-rf\s+/|rm\s+-rf\s+/\*|rm\s+-rf\s+\.",
        danger_level=DangerLevel.CRITICAL,
        description="递归删除根目录或当前目录",
        example="rm -rf / 或 rm -rf .",
        mitigation="使用 rm -i 进行交互确认"
    ),
    DangerPattern(
        pattern=r":\(\)\s*\{\s*:\|\s*:\s*&\s*\};:",
        danger_level=DangerLevel.CRITICAL,
        description="Fork炸弹 - 耗尽系统资源",
        example=":(){ :|:& };:",
        mitigation="使用ulimit限制进程数"
    ),
    DangerPattern(
        pattern=r"dd\s+if=.*of=/dev/[sh]d[a-z]",
        danger_level=DangerLevel.CRITICAL,
        description="直接写入磁盘设备",
        example="dd if=/dev/zero of=/dev/sda",
        mitigation="先备份，使用镜像文件"
    ),
    DangerPattern(
        pattern=r"mkfs\.|mke2fs\s+",
        danger_level=DangerLevel.CRITICAL,
        description="格式化磁盘",
        example="mkfs.ext4 /dev/sda1",
        mitigation="确认目标设备不是系统盘"
    ),
    DangerPattern(
        pattern=r"parted\s+.*\s+mkpart",
        danger_level=DangerLevel.HIGH,
        description="修改磁盘分区",
        example="parted /dev/sda mkpart",
        mitigation="备份分区表"
    ),
    DangerPattern(
        pattern=r"sfdisk\s+",
        danger_level=DangerLevel.HIGH,
        description="磁盘分区工具",
        example="sfdisk /dev/sda",
        mitigation="确认操作目标"
    ),
    DangerPattern(
        pattern=r">\s*/etc/|>\s*/boot/",
        danger_level=DangerLevel.CRITICAL,
        description="重定向覆盖系统目录",
        example="> /etc/passwd",
        mitigation="使用追加模式 >> "
    ),
    DangerPattern(
        pattern=r"chmod\s+-R\s+777\s+/|chmod\s+-R\s+000\s+/",
        danger_level=DangerLevel.HIGH,
        description="修改系统目录权限",
        example="chmod -R 777 /",
        mitigation="只修改必要目录"
    ),
    DangerPattern(
        pattern=r"chown\s+-R\s+",
        danger_level=DangerLevel.MEDIUM,
        description="修改文件所有权",
        example="chown -R user:group /path",
        mitigation="确认目标路径"
    ),
    DangerPattern(
        pattern=r"mv\s+/dev/null|Mv\s+/dev/null",
        danger_level=DangerLevel.HIGH,
        description="移动/dev/null",
        example="mv /dev/null /tmp/",
        mitigation="不要修改系统设备文件"
    ),
]

# 危险路径模式
DANGEROUS_PATHS = [
    # 系统关键路径
    r"^/system",
    r"^/boot",
    r"^/sys",
    r"^/proc",
    r"^/dev/shm",
    r"^/run",
    
    # 配置目录
    r"^/etc",
    r"^/var/etc",
    
    # 用户敏感目录
    r"^~/.ssh",
    r"^~/.gnupg",
    r"^~/.aws",
    
    # 危险通配
    r"\*\*/\*",        # 递归通配
    r"\.\./\*",        # 父目录通配
]

# 危险参数模式
DANGEROUS_PARAMS = [
    r"--no-preserve-root",
    r"--force",
    r"-f\s+-(?!f)",    # rm -f -rf 这种情况
    r"-P",              # 不跟随符号链接
]

# ============================================================
# SafetyResult
# ============================================================

@dataclass
class SafetyResult:
    """安全检查结果"""
    is_safe: bool
    danger_level: DangerLevel
    reason: str
    matched_pattern: Optional[str] = None
    original_command: str = ""
    timestamp: str = ""
    blocked: bool = False
    warning_message: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.danger_level == DangerLevel.CRITICAL:
            self.blocked = True
            self.is_safe = False

# ============================================================
# SafetyPolicy 主类
# ============================================================

class SafetyPolicy:
    """
    危险操作拦截器
    
    使用方法:
        policy = SafetyPolicy()
        result = policy.check("rm -rf /")
        if not result.is_safe:
            print(f"阻止: {result.reason}")
    """

    def __init__(self, allow_high_risk: bool = False):
        """
        初始化安全策略
        
        Args:
            allow_high_risk: 是否允许高风险操作（默认False）
        """
        self.allow_high_risk = allow_high_risk
        self._command_patterns = [re.compile(p.pattern) for p in DANGEROUS_COMMANDS]
        self._path_patterns = [re.compile(p) for p in DANGEROUS_PATHS]
        self._param_patterns = [re.compile(p) for p in DANGEROUS_PARAMS]
        
        # 统计
        self.blocked_count = 0
        self.allowed_count = 0
        self.log: List[SafetyResult] = []

    def check(self, command: str) -> SafetyResult:
        """
        检查命令是否安全
        
        Args:
            command: 待检查的命令
            
        Returns:
            SafetyResult: 检查结果
        """
        if not command or not command.strip():
            return SafetyResult(
                is_safe=True,
                danger_level=DangerLevel.LOW,
                reason="空命令"
            )
        
        original = command
        command = command.strip()
        
        # 1. 检查危险命令模式
        for i, pattern in enumerate(self._command_patterns):
            if pattern.search(command):
                dp = DANGEROUS_COMMANDS[i]
                result = SafetyResult(
                    is_safe=False,
                    danger_level=dp.danger_level,
                    reason=dp.description,
                    matched_pattern=dp.pattern,
                    original_command=original,
                    warning_message=f"危险命令: {dp.example}\n缓解: {dp.mitigation}"
                )
                self._record(result)
                return result
        
        # 2. 检查危险路径
        for pattern in self._path_patterns:
            if pattern.search(command):
                result = SafetyResult(
                    is_safe=False,
                    danger_level=DangerLevel.CRITICAL,
                    reason="危险路径访问",
                    matched_pattern=pattern.pattern,
                    original_command=original,
                    warning_message="禁止访问系统关键路径"
                )
                self._record(result)
                return result
        
        # 3. 检查危险参数
        for pattern in self._param_patterns:
            if pattern.search(command):
                result = SafetyResult(
                    is_safe=False,
                    danger_level=DangerLevel.HIGH,
                    reason="危险参数",
                    matched_pattern=pattern.pattern,
                    original_command=original
                )
                self._record(result)
                return result
        
        # 4. 检查管道链中的危险命令
        if "|" in command:
            for part in command.split("|"):
                part = part.strip()
                for i, pattern in enumerate(self._command_patterns):
                    if pattern.search(part):
                        dp = DANGEROUS_COMMANDS[i]
                        result = SafetyResult(
                            is_safe=False,
                            danger_level=dp.danger_level,
                            reason=f"管道中的危险命令: {dp.description}",
                            matched_pattern=dp.pattern,
                            original_command=original,
                            warning_message=f"危险命令: {dp.example}"
                        )
                        self._record(result)
                        return result
        
        # 安全
        return SafetyResult(
            is_safe=True,
            danger_level=DangerLevel.LOW,
            reason="命令安全"
        )

    def check_paths(self, paths: List[str]) -> SafetyResult:
        """
        检查多个路径是否安全
        
        Args:
            paths: 路径列表
            
        Returns:
            SafetyResult: 第一个发现的危险路径结果
        """
        for path in paths:
            # 展开~
            path = os.path.expanduser(path)
            
            # 检查危险路径模式
            for pattern in self._path_patterns:
                if pattern.match(path):
                    return SafetyResult(
                        is_safe=False,
                        danger_level=DangerLevel.CRITICAL,
                        reason=f"危险路径: {path}",
                        matched_pattern=pattern.pattern,
                        original_command=path
                    )
        
        return SafetyResult(
            is_safe=True,
            danger_level=DangerLevel.LOW,
            reason="路径安全"
        )

    def _record(self, result: SafetyResult):
        """记录检查结果"""
        self.log.append(result)
        if result.blocked:
            self.blocked_count += 1
        else:
            self.allowed_count += 1

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "blocked": self.blocked_count,
            "allowed": self.allowed_count,
            "total": len(self.log)
        }

    def export_log(self) -> List[Dict[str, Any]]:
        """导出日志为字典列表"""
        return [
            {
                "is_safe": r.is_safe,
                "danger_level": r.danger_level.value,
                "reason": r.reason,
                "timestamp": r.timestamp,
                "blocked": r.blocked
            }
            for r in self.log
        ]


# ============================================================
# 便捷函数
# ============================================================

# 全局默认实例
_default_policy: Optional[SafetyPolicy] = None

def get_default_policy() -> SafetyPolicy:
    """获取默认安全策略实例"""
    global _default_policy
    if _default_policy is None:
        _default_policy = SafetyPolicy()
    return _default_policy

def check_command(command: str) -> SafetyResult:
    """快速检查命令安全性"""
    return get_default_policy().check(command)

def is_safe(command: str) -> bool:
    """快速判断命令是否安全"""
    return get_default_policy().check(command).is_safe

def block_command(command: str) -> bool:
    """检查并阻止危险命令"""
    result = get_default_policy().check(command)
    return result.blocked


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    # 单元测试
    policy = SafetyPolicy()
    
    test_cases = [
        ("rm -rf /", True),           # 危险
        ("rm -rf .", True),           # 危险
        (":(){ :|:& };:", True),      # Fork炸弹
        ("dd if=/dev/zero of=/dev/sda", True),  # 危险
        ("ls /home", False),          # 安全
        ("echo 'hello'", False),      # 安全
        ("cat /etc/passwd", False),   # 中等风险但不阻止
    ]
    
    print("SafetyPolicy 单元测试")
    print("=" * 60)
    
    for cmd, expected_danger in test_cases:
        result = policy.check(cmd)
        status = "❌" if result.is_safe == expected_danger else "✅"
        print(f"{status} {cmd[:40]:<40} safe={result.is_safe} level={result.danger_level.value}")
    
    print("=" * 60)
    print(f"统计: {policy.get_stats()}")
