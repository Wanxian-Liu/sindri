"""
共识投票官 (Consensus Officer)
解析[CONSENSUS: YES/NO]标签，判断是否达成共识
"""

import re
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class VoteResult:
    """投票结果"""
    has_consensus: bool
    vote: str  # "YES" or "NO"
    confidence: float  # 0.0 - 1.0
    raw_match: Optional[str]  # 原始匹配文本

class ConsensusOfficer:
    """
    共识投票官 - 解析CONSENSUS标签
    
    支持的格式:
    - [CONSENSUS: YES]
    - [CONSENSUS: NO]
    - consensus: yes
    - consensus: no
    - **consensus**: YES
    - 共识投票: YES
    """
    
    # 严格格式: [CONSENSUS: YES/NO]
    STRICT_PATTERN = re.compile(
        r'\[\s*CONSENSUS\s*[:：]\s*(YES|NO)\s*\]', 
        re.IGNORECASE
    )
    
    # 宽松格式: consensus: yes
    # 注意: (yes|no) 后面必须跟词边界或行尾，防止"Yesplease"被误判为YES
    VARIANT_PATTERNS = [
        re.compile(r'consensus[:\s]+(yes|no)(?=\s|[^\w]|$)', re.IGNORECASE),
        re.compile(r'\*\*consensus\*\*[:\s]+(yes|no)(?=\s|[^\w]|$)', re.IGNORECASE),
        re.compile(r'CONSENSUS=(YES|NO)(?=\s|[^\w]|$)', re.IGNORECASE),
        re.compile(r'共识投票[:：\s]+(YES|NO)(?=\s|[^\w]|$)', re.IGNORECASE),
        re.compile(r'\[CONSENSUS\][:\s]+(YES|NO)(?=\s|[^\w]|$)', re.IGNORECASE),
    ]
    
    def __init__(self, threshold: float = 0.5):
        """
        初始化共识投票官
        
        Args:
            threshold: 共识阈值 (0.0-1.0)
        """
        self.threshold = threshold
        self.vote_history: List[VoteResult] = []
    
    def parse_consensus(self, content: str) -> VoteResult:
        """
        从内容中解析共识投票结果
        
        Args:
            content: Agent响应内容
            
        Returns:
            VoteResult: 投票结果
        """
        # 1. 严格格式匹配
        strict_matches = list(self.STRICT_PATTERN.finditer(content))
        if strict_matches:
            # 取最后一个匹配
            last_match = strict_matches[-1]
            vote = last_match.group(1).upper()
            return VoteResult(
                has_consensus=(vote == "YES"),
                vote=vote,
                confidence=1.0,  # 严格格式100%置信
                raw_match=last_match.group(0)
            )
        
        # 2. 宽松格式匹配
        for pattern in self.VARIANT_PATTERNS:
            matches = list(pattern.finditer(content))
            if matches:
                last_match = matches[-1]
                vote = last_match.group(1).upper()
                return VoteResult(
                    has_consensus=(vote == "YES"),
                    vote=vote,
                    confidence=0.8,  # 宽松格式80%置信
                    raw_match=last_match.group(0)
                )
        
        # 3. 无匹配 - 默认NO共识
        return VoteResult(
            has_consensus=False,
            vote="NO",
            confidence=0.0,
            raw_match=None
        )
    
    def check_majority(self, votes: List[VoteResult]) -> bool:
        """
        检查多数投票是否达成共识
        
        Args:
            votes: 投票列表
            
        Returns:
            bool: 是否达成共识
        """
        if not votes:
            return False
        
        yes_count = sum(1 for v in votes if v.has_consensus)
        yes_ratio = yes_count / len(votes)
        
        return yes_ratio >= self.threshold
    
    def add_vote(self, content: str) -> VoteResult:
        """
        添加投票并记录历史
        
        Args:
            content: Agent响应内容
            
        Returns:
            VoteResult: 投票结果
        """
        result = self.parse_consensus(content)
        self.vote_history.append(result)
        return result
    
    def get_majority_result(self) -> bool:
        """
        获取多数投票结果
        
        Returns:
            bool: 是否达成共识
        """
        return self.check_majority(self.vote_history)
    
    def get_status(self) -> dict:
        """
        获取投票状态
        
        Returns:
            dict: 状态信息
        """
        if not self.vote_history:
            return {
                "total_votes": 0,
                "yes_votes": 0,
                "no_votes": 0,
                "majority_reached": False
            }
        
        yes_count = sum(1 for v in self.vote_history if v.has_consensus)
        no_count = len(self.vote_history) - yes_count
        
        return {
            "total_votes": len(self.vote_history),
            "yes_votes": yes_count,
            "no_votes": no_count,
            "majority_reached": self.get_majority_result(),
            "last_vote": self.vote_history[-1].vote if self.vote_history else None
        }
    
    def reset(self):
        """重置投票历史"""
        self.vote_history.clear()


# 快捷函数
def parse_consensus(content: str) -> bool:
    """
    快速解析共识
    
    Args:
        content: Agent响应内容
        
    Returns:
        bool: 是否是[CONSENSUS: YES]
    """
    officer = ConsensusOfficer()
    result = officer.parse_consensus(content)
    return result.has_consensus


def has_consensus_marker(content: str) -> bool:
    """
    检查内容是否包含共识标记
    
    Args:
        content: 内容
        
    Returns:
        bool: 是否包含标记
    """
    if ConsensusOfficer.STRICT_PATTERN.search(content):
        return True
    for pattern in ConsensusOfficer.VARIANT_PATTERNS:
        if pattern.search(content):
            return True
    return False


def strip_consensus_tags(content: str) -> str:
    """
    移除内容中的共识标签
    
    Args:
        content: 内容
        
    Returns:
        str: 清理后的内容
    """
    result = content
    result = ConsensusOfficer.STRICT_PATTERN.sub('', result)
    for pattern in ConsensusOfficer.VARIANT_PATTERNS:
        result = pattern.sub('', result)
    return result.strip()
