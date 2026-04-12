"""
inbox_manager.py - Worker间消息传递系统

功能：
  1. Worker间直接消息传递
  2. 消息持久化积压
  3. 广播功能
  4. 消息标记已读

设计原则：
  - 不阻塞Round流程（异步）
  - 消息只做元信息通知，不参与任务协调
  - 简化subject协议

使用场景：
  - Worker A完成复杂计算 → 发"data_ready"给Worker B
  - 主Agent broadcast"stop"让所有Worker停止
  - Worker在每个Round开始前检查inbox
"""

import json
import uuid
import os
import fcntl
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum
import threading

# ============================================================
# 类型定义
# ============================================================

class MessageKind(Enum):
    """消息类型"""
    INBOX = "inbox"      # 用户消息
    SYSTEM = "system"    # 系统消息
    REVIEW = "review"    # 审查消息

class MessageSubject(Enum):
    """预定义消息主题"""
    TASK_COMPLETE = "task_complete"    # 任务完成
    TASK_FAILED = "task_failed"        # 任务失败
    ERROR = "error"                    # 出错
    DATA_READY = "data_ready"          # 数据就绪
    READY = "ready"                    # 就绪
    STOP = "stop"                     # 停止
    TIMEOUT = "timeout"               # 超时
    REQUEST = "request"               # 请求
    RESPONSE = "response"             # 响应

@dataclass
class InboxMessage:
    """Inbox消息"""
    id: str
    from_worker: str
    to_worker: str  # "*" = 广播
    subject: str
    body: str
    kind: str        # "inbox" | "system" | "review"
    created_at: str
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = f"msg_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> 'InboxMessage':
        return InboxMessage(**d)

    def is_broadcast(self) -> bool:
        return self.to_worker == "*"

# ============================================================
# InboxManager 主类
# ============================================================

class InboxManager:
    """
    Worker间消息管理器
    
    使用方法:
        inbox = InboxManager()
        
        # 发送消息
        inbox.send(from_worker="worker_a", to_worker="worker_b", 
                   subject="data_ready", body="数据已准备好")
        
        # 接收消息
        messages = inbox.get_pending("worker_b")
        
        # 广播
        inbox.broadcast(from_worker="agent", subject="stop", body="停止执行")
    """

    def __init__(self, inbox_dir: Optional[str] = None):
        """
        初始化InboxManager
        
        Args:
            inbox_dir: inbox目录，默认使用.omx/inbox/
        """
        if inbox_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sindris_root = os.path.dirname(script_dir)
            inbox_dir = os.path.join(sindris_root, ".omx", "inbox")
        
        self.inbox_dir = Path(inbox_dir)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        
        # 消息锁（防止并发写入）
        self._lock = threading.Lock()
        
        # 缓存（减少文件IO）
        self._cache: Dict[str, List[InboxMessage]] = {}

    def send(
        self,
        from_worker: str,
        to_worker: str,
        subject: str,
        body: str = "",
        kind: str = "inbox",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InboxMessage:
        """
        发送消息
        
        Args:
            from_worker: 发送者ID
            to_worker: 接收者ID（"*"表示广播）
            subject: 消息主题
            body: 消息内容
            kind: 消息类型
            metadata: 额外元数据
            
        Returns:
            InboxMessage: 创建的消息
        """
        message = InboxMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            from_worker=from_worker,
            to_worker=to_worker,
            subject=subject,
            body=body,
            kind=kind,
            created_at=datetime.now().isoformat(),
            read=False,
            metadata=metadata or {}
        )
        
        self._write_message(message)
        
        # 如果是广播，同时写入每个Worker的inbox
        if message.is_broadcast():
            self._write_broadcast(message)
        
        return message

    def get_pending(
        self,
        worker_id: str,
        unread_only: bool = True,
        limit: int = 100,
    ) -> List[InboxMessage]:
        """
        获取积压消息
        
        Args:
            worker_id: Worker ID
            unread_only: 只返回未读消息
            limit: 返回数量限制
            
        Returns:
            List[InboxMessage]: 消息列表
        """
        messages = self._read_worker_inbox(worker_id)
        
        if unread_only:
            messages = [m for m in messages if not m.read]
        
        return messages[-limit:]

    def mark_read(self, message_id: str) -> bool:
        """
        标记消息为已读
        
        Args:
            message_id: 消息ID
            
        Returns:
            bool: 是否成功
        """
        # 遍历所有Worker的inbox查找消息
        for worker_dir in self.inbox_dir.iterdir():
            if not worker_dir.is_dir():
                continue
            
            for file_path in worker_dir.glob("*.jsonl"):
                messages = self._read_file(file_path)
                for msg in messages:
                    if msg.id == message_id:
                        msg.read = True
                        self._write_messages(file_path, messages)
                        return True
        
        return False

    def mark_read_by_worker(self, worker_id: str) -> int:
        """
        标记Worker的所有消息为已读
        
        Args:
            worker_id: Worker ID
            
        Returns:
            int: 标记的数量
        """
        file_path = self._get_worker_file(worker_id)
        if not file_path.exists():
            return 0
        
        messages = self._read_file(file_path)
        count = 0
        for msg in messages:
            if not msg.read:
                msg.read = True
                count += 1
        
        if count > 0:
            self._write_messages(file_path, messages)
        
        return count

    def broadcast(
        self,
        from_worker: str,
        subject: str,
        body: str = "",
        kind: str = "system",
    ) -> InboxMessage:
        """
        广播消息给所有Worker
        
        Args:
            from_worker: 发送者
            subject: 消息主题
            body: 消息内容
            kind: 消息类型
            
        Returns:
            InboxMessage: 创建的消息
        """
        return self.send(
            from_worker=from_worker,
            to_worker="*",
            subject=subject,
            body=body,
            kind=kind,
        )

    def send_system(
        self,
        from_worker: str,
        to_worker: str,
        subject: str,
        body: str = "",
    ) -> InboxMessage:
        """
        发送系统消息（快捷方法）
        """
        return self.send(
            from_worker=from_worker,
            to_worker=to_worker,
            subject=subject,
            body=body,
            kind="system",
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = 0
        unread = 0
        workers = set()
        
        for worker_dir in self.inbox_dir.iterdir():
            if not worker_dir.is_dir():
                continue
            workers.add(worker_dir.name)
            
            for file_path in worker_dir.glob("*.jsonl"):
                messages = self._read_file(file_path)
                total += len(messages)
                unread += sum(1 for m in messages if not m.read)
        
        return {
            "total_messages": total,
            "unread_messages": unread,
            "workers_with_inbox": len(workers),
        }

    def clear_old_messages(self, days: int = 7) -> int:
        """
        清理旧消息
        
        Args:
            days: 保留最近几天的消息
            
        Returns:
            int: 删除的消息数量
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0
        
        for worker_dir in self.inbox_dir.iterdir():
            if not worker_dir.is_dir():
                continue
            
            for file_path in worker_dir.glob("*.jsonl"):
                messages = self._read_file(file_path)
                original_count = len(messages)
                
                messages = [
                    m for m in messages
                    if datetime.fromisoformat(m.created_at) > cutoff
                ]
                
                deleted += original_count - len(messages)
                
                if messages:
                    self._write_messages(file_path, messages)
                else:
                    file_path.unlink()
        
        return deleted

    # ==================== 私有方法 ====================

    def _get_worker_file(self, worker_id: str) -> Path:
        """获取Worker的inbox文件"""
        worker_dir = self.inbox_dir / worker_id
        worker_dir.mkdir(exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        return worker_dir / f"{date_str}.jsonl"

    def _write_message(self, message: InboxMessage):
        """写入消息"""
        file_path = self._get_worker_file(message.to_worker)
        
        with self._lock:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")
        
        # 清除缓存
        self._cache.pop(message.to_worker, None)

    def _write_broadcast(self, message: InboxMessage):
        """写入广播消息到所有Worker"""
        for worker_dir in self.inbox_dir.iterdir():
            if not worker_dir.is_dir():
                continue
            if worker_dir.name == message.from_worker:
                continue  # 不发给自己
            
            date_str = datetime.now().strftime("%Y-%m-%d")
            file_path = worker_dir / f"{date_str}.jsonl"
            
            with self._lock:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

    def _read_worker_inbox(self, worker_id: str) -> List[InboxMessage]:
        """读取Worker的所有消息"""
        # 检查缓存
        if worker_id in self._cache:
            return self._cache[worker_id]
        
        worker_dir = self.inbox_dir / worker_id
        if not worker_dir.exists():
            return []
        
        all_messages = []
        for file_path in worker_dir.glob("*.jsonl"):
            messages = self._read_file(file_path)
            all_messages.extend(messages)
        
        # 按时间排序
        all_messages.sort(key=lambda m: m.created_at)
        
        # 更新缓存
        self._cache[worker_id] = all_messages
        
        return all_messages

    def _read_file(self, file_path: Path) -> List[InboxMessage]:
        """读取jsonl文件"""
        if not file_path.exists():
            return []
        
        messages = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        messages.append(InboxMessage.from_dict(data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except Exception:
            pass
        
        return messages

    def _write_messages(self, file_path: Path, messages: List[InboxMessage]):
        """写入消息列表到文件"""
        with self._lock:
            with open(file_path, "w", encoding="utf-8") as f:
                for msg in messages:
                    f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + "\n")
        
        # 清除相关缓存
        for key in list(self._cache.keys()):
            if worker_dir_match(key, file_path):
                self._cache.pop(key, None)


def worker_dir_match(worker_id: str, file_path: Path) -> bool:
    """检查worker_id是否匹配file_path"""
    return file_path.name.startswith(worker_id)


# ============================================================
# 便捷函数
# ============================================================

_default_inbox: Optional[InboxManager] = None

def get_default_inbox() -> InboxManager:
    """获取默认InboxManager实例"""
    global _default_inbox
    if _default_inbox is None:
        _default_inbox = InboxManager()
    return _default_inbox


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("InboxManager 单元测试")
    print("=" * 60)
    
    inbox = InboxManager(inbox_dir="/tmp/sindris_inbox_test")
    
    # 测试发送消息
    msg1 = inbox.send(
        from_worker="worker_a",
        to_worker="worker_b",
        subject="data_ready",
        body="数据已准备好",
    )
    print(f"✅ 发送消息: {msg1.id}")
    
    # 测试接收消息
    messages = inbox.get_pending("worker_b")
    print(f"✅ 收到消息数: {len(messages)}")
    
    # 测试广播
    msg2 = inbox.broadcast(
        from_worker="agent",
        subject="stop",
        body="立即停止",
    )
    print(f"✅ 广播消息: {msg2.id}")
    
    # 验证广播（检查worker_c是否收到）
    messages_c = inbox.get_pending("worker_c")
    print(f"✅ worker_c收到广播: {len(messages_c)}")
    
    # 统计
    stats = inbox.get_stats()
    print(f"✅ 统计: {stats}")
    
    # 清理测试数据
    import shutil
    shutil.rmtree("/tmp/sindris_inbox_test", ignore_errors=True)
    
    print("=" * 60)
    print("✅ InboxManager 测试通过")
