"""
memory_manager.py - 任务记忆管理模块

功能: 任务完成后自动生成记忆摘要，写入workspace/memory/sindris-tasks/

记忆类型:
  - task_summary: 任务执行摘要
  - lesson_learned: 经验教训
  - decision_record: 关键决策记录
  - pattern_discovery: 发现的模式
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from enum import Enum

# ============================================================
# 类型定义
# ============================================================

class MemoryType(Enum):
    """记忆类型"""
    TASK_SUMMARY = "task_summary"
    LESSON_LEARNED = "lesson_learned"
    DECISION_RECORD = "decision_record"
    PATTERN_DISCOVERY = "pattern_discovery"
    ERROR_PATTERN = "error_pattern"

@dataclass
class TaskMemory:
    """任务记忆"""
    id: str
    task_id: str
    memory_type: str
    content: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    importance: int = 3  # 1-5, 5最重要
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'TaskMemory':
        return TaskMemory(**d)

# ============================================================
# 摘要生成器
# ============================================================

class SummaryGenerator:
    """
    任务摘要生成器
    将执行结果转换为可读的摘要
    """

    @staticmethod
    def generate_from_result(
        task_title: str,
        success: bool,
        duration_ms: Optional[int] = None,
        role: Optional[str] = None,
        error: Optional[str] = None,
    ) -> str:
        """从执行结果生成摘要"""
        parts = []
        
        # 任务描述
        if role:
            parts.append(f"[{role}]")
        parts.append(task_title[:100])
        
        # 结果
        if success:
            parts.append("✅ 完成")
        else:
            parts.append("❌ 失败")
            if error:
                # 简化错误信息
                error_short = error[:100] if len(error) > 100 else error
                parts.append(f"({error_short})")
        
        # 耗时
        if duration_ms:
            if duration_ms < 1000:
                parts.append(f"[{duration_ms}ms]")
            else:
                parts.append(f"[{duration_ms/1000:.1f}s]")
        
        return " ".join(parts)

    @staticmethod
    def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
        """从文本提取关键词"""
        if not text:
            return []
        
        # 简单词频统计
        words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{3,}\b', text.lower())
        
        # 停用词
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 
                     'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 
                     'ought', 'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
                     'from', 'as', 'into', 'through', 'during', 'before', 'after', 
                     'above', 'below', 'between', 'under', 'again', 'further', 'then',
                     'this', 'that', 'these', 'those', '我', '你', '他', '她', '它',
                     '的', '是', '在', '有', '和', '了', '就', '都', '也', '要', '会'}
        
        word_freq = {}
        for w in words:
            if w not in stopwords and len(w) > 2:
                word_freq[w] = word_freq.get(w, 0) + 1
        
        # 排序取前N个
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:max_keywords]]

    @staticmethod
    def generate_tags(
        task_title: str,
        role: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> List[str]:
        """生成记忆标签"""
        tags = []
        
        if role:
            tags.append(f"role:{role}")
        
        if success:
            tags.append("success")
        else:
            tags.append("failure")
            if error:
                # 从错误中提取标签
                error_lower = error.lower()
                if 'timeout' in error_lower:
                    tags.append("timeout")
                if 'circuit' in error_lower:
                    tags.append("circuit-break")
                if 'safety' in error_lower:
                    tags.append("safety")
        
        # 从任务标题提取
        title_keywords = SummaryGenerator.extract_keywords(task_title, max_keywords=2)
        tags.extend(title_keywords)
        
        return tags[:5]  # 最多5个标签


# ============================================================
# MemoryManager 主类
# ============================================================

class MemoryManager:
    """
    任务记忆管理器
    
    使用方法:
        manager = MemoryManager()
        manager.save_task_memory(task_id="task_001", ...)
        memories = manager.get_recent_memories(limit=10)
    """

    def __init__(self, memory_dir: Optional[str] = None):
        """
        初始化MemoryManager
        
        Args:
            memory_dir: 记忆目录，默认使用workspace/memory/sindris-tasks/
        """
        if memory_dir is None:
            # 查找workspace
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sindris_root = os.path.dirname(script_dir)
            workspace = os.path.join(sindris_root, "..", "workspace")
            memory_dir = os.path.join(workspace, "memory", "sindris-tasks")
        
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 索引文件
        self.index_file = self.memory_dir / "index.jsonl"

    def save_task_memory(
        self,
        task_id: str,
        task_title: str,
        success: bool,
        duration_ms: Optional[int] = None,
        role: Optional[str] = None,
        error: Optional[str] = None,
        importance: int = 3,
    ) -> TaskMemory:
        """
        保存任务记忆
        
        Args:
            task_id: 任务ID
            task_title: 任务标题
            success: 是否成功
            duration_ms: 执行耗时
            role: 角色
            error: 错误信息
            importance: 重要性 1-5
            
        Returns:
            TaskMemory: 创建的记忆
        """
        # 生成摘要
        summary = SummaryGenerator.generate_from_result(
            task_title=task_title,
            success=success,
            duration_ms=duration_ms,
            role=role,
            error=error,
        )
        
        # 生成标签
        tags = SummaryGenerator.generate_tags(
            task_title=task_title,
            role=role,
            success=success,
            error=error,
        )
        
        # 创建记忆
        memory = TaskMemory(
            id=f"mem_{task_id}",
            task_id=task_id,
            memory_type=MemoryType.TASK_SUMMARY.value,
            content=summary,
            tags=tags,
            importance=importance,
        )
        
        # 写入文件
        self._write_memory(memory)
        
        # 更新索引
        self._update_index(memory)
        
        return memory

    def save_lesson(
        self,
        task_id: str,
        lesson: str,
        tags: Optional[List[str]] = None,
    ) -> TaskMemory:
        """
        保存经验教训
        
        Args:
            task_id: 关联的任务ID
            lesson: 经验教训内容
            tags: 标签
            
        Returns:
            TaskMemory: 创建的记忆
        """
        memory = TaskMemory(
            id=f"lesson_{task_id}_{datetime.now().strftime('%H%M%S')}",
            task_id=task_id,
            memory_type=MemoryType.LESSON_LEARNED.value,
            content=lesson,
            tags=tags or ["lesson"],
            importance=4,  # 经验教训一般比较重要
        )
        
        self._write_memory(memory)
        self._update_index(memory)
        
        return memory

    def save_decision(
        self,
        task_id: str,
        decision: str,
        reason: str,
        tags: Optional[List[str]] = None,
    ) -> TaskMemory:
        """
        保存决策记录
        
        Args:
            task_id: 关联的任务ID
            decision: 决策内容
            reason: 决策原因
            tags: 标签
            
        Returns:
            TaskMemory: 创建的记忆
        """
        content = f"决策: {decision}\n原因: {reason}"
        
        memory = TaskMemory(
            id=f"decision_{task_id}_{datetime.now().strftime('%H%M%S')}",
            task_id=task_id,
            memory_type=MemoryType.DECISION_RECORD.value,
            content=content,
            tags=tags or ["decision"],
            importance=5,  # 决策一般最重要
        )
        
        self._write_memory(memory)
        self._update_index(memory)
        
        return memory

    def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: Optional[MemoryType] = None,
    ) -> List[TaskMemory]:
        """获取最近的记忆"""
        memories = []
        
        if not self.index_file.exists():
            return memories
        
        with open(self.index_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in reversed(lines[-limit:]):
            try:
                data = json.loads(line.strip())
                if memory_type and data.get("memory_type") != memory_type.value:
                    continue
                memories.append(TaskMemory.from_dict(data))
            except json.JSONDecodeError:
                continue
        
        return memories

    def get_memories_by_tag(self, tag: str, limit: int = 10) -> List[TaskMemory]:
        """按标签获取记忆"""
        all_memories = self.get_recent_memories(limit=1000)
        return [m for m in all_memories if tag in m.tags][:limit]

    def search_keyword(
        self,
        query: str,
        limit: int = 20,
        max_scan: int = 2000,
    ) -> List[TaskMemory]:
        """
        在 index.jsonl 中按关键词检索（MVP：子串匹配 content + tags，从新到旧扫描最多 max_scan 行）。
        """
        q = (query or "").strip().lower()
        if not q or not self.index_file.exists():
            return []
        with open(self.index_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        window = lines[-max_scan:] if len(lines) > max_scan else lines
        matched: List[TaskMemory] = []
        for line in reversed(window):
            line = line.strip()
            if not line:
                continue
            try:
                m = TaskMemory.from_dict(json.loads(line))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
            hay = f"{m.content} {' '.join(m.tags)}".lower()
            if q in hay:
                matched.append(m)
            if len(matched) >= limit:
                break
        return matched

    def _write_memory(self, memory: TaskMemory):
        """写入记忆文件"""
        # 按月份组织: sindris-tasks/YYYY-MM.md
        month_str = datetime.now().strftime("%Y-%m")
        file_path = self.memory_dir / f"{month_str}.md"
        
        # Markdown格式追加
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n## {memory.id}\n")
            f.write(f"**时间**: {memory.created_at}\n")
            f.write(f"**任务**: {memory.task_id}\n")
            f.write(f"**类型**: {memory.memory_type}\n")
            f.write(f"**标签**: {', '.join(memory.tags)}\n")
            f.write(f"\n{memory.content}\n")
            f.write("\n---\n")

    def _update_index(self, memory: TaskMemory):
        """更新索引"""
        with open(self.index_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory.to_dict(), ensure_ascii=False) + "\n")


# ============================================================
# 便捷函数
# ============================================================

_default_manager: Optional[MemoryManager] = None

def get_default_manager() -> MemoryManager:
    """获取默认MemoryManager实例"""
    global _default_manager
    if _default_manager is None:
        _default_manager = MemoryManager()
    return _default_manager


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("MemoryManager 单元测试")
    print("=" * 60)
    
    manager = MemoryManager(memory_dir="/tmp/sindris_memory_test")
    
    # 保存任务记忆
    mem1 = manager.save_task_memory(
        task_id="task_001",
        task_title="开发用户认证系统",
        success=True,
        duration_ms=5000,
        role="developer",
    )
    print(f"✅ 任务记忆: {mem1.id}")
    
    # 保存经验教训
    mem2 = manager.save_lesson(
        task_id="task_001",
        lesson="使用bcrypt代替MD5进行密码哈希",
        tags=["security", "password"],
    )
    print(f"✅ 经验教训: {mem2.id}")
    
    # 保存决策
    mem3 = manager.save_decision(
        task_id="task_001",
        decision="选择JWT作为认证方案",
        reason="无状态、可扩展、支持跨域",
        tags=["architecture", "auth"],
    )
    print(f"✅ 决策记录: {mem3.id}")
    
    # 获取最近记忆
    print("\n最近记忆:")
    for m in manager.get_recent_memories(limit=5):
        print(f"  - [{m.memory_type}] {m.content[:50]}...")
    
    print("=" * 60)
