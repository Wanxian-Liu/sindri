"""
task_classifier.py - 任务类型自动识别

参考Oh-My-Codex的TASK_TYPE_PATTERNS设计
根据关键词识别任务类型，决定角色匹配策略
"""

from enum import Enum
from typing import Dict, List, Optional


class TaskType(str, Enum):
    """任务类型"""
    ENGINEERING = "engineering"      # 工程开发类
    DESIGN = "design"                # 设计类
    RESEARCH = "research"            # 研究分析类
    TESTING = "testing"             # 测试验证类
    WRITING = "writing"             # 写作文档类
    UNKNOWN = "unknown"              # 未知


# 任务类型关键词模式
TASK_TYPE_PATTERNS: Dict[TaskType, List[str]] = {
    TaskType.ENGINEERING: [
        # 编程/开发
        "编程", "开发", "代码", "code", "python", "java", "javascript", "typescript",
        "修改", "优化", "修复", "bug", "feature", "重构", "refactor",
        # 自研系统
        "记忆殿堂", "mimir", "sindris", "进化", "agent", "织界",
        # 工程概念
        "模块", "组件", "系统", "架构", "接口", "实现", "自动化", "流程",
        "算法", "数据结构", "性能", "并发", "异步", "同步",
        # 工具类
        "工具", "脚本", "CLI", "API", "SDK", "集成",
    ],
    TaskType.DESIGN: [
        "界面", "UI", "UX", "设计", "布局", "配色", "视觉",
        "交互", "原型", "mockup", "sketch", "figma",
        "用户体验", "交互设计", "视觉设计",
    ],
    TaskType.RESEARCH: [
        "分析", "调研", "研究", "学习", "对比", "评估",
        "research", "analyze", "survey", "study",
        "调查", "考察", "探索", "发现",
    ],
    TaskType.TESTING: [
        "测试", "验证", "检查", "审查", "评审",
        "test", "verify", "validate", "check", "review",
        "质量", "QA", "回归", "单元测试",
    ],
    TaskType.WRITING: [
        "写作", "文档", "撰写", "编辑", "内容",
        "write", "document", "article", "blog",
        "报告", "总结", "说明", "手册",
    ],
}

# 任务类型 → 默认角色策略
TASK_TYPE_STRATEGY: Dict[TaskType, str] = {
    TaskType.ENGINEERING: "fixed_team",    # 使用固定工程团队
    TaskType.DESIGN: "vector_match",        # 向量匹配
    TaskType.RESEARCH: "vector_match",      # 向量匹配
    TaskType.TESTING: "fixed_team",         # 使用固定测试团队
    TaskType.WRITING: "vector_match",       # 向量匹配
    TaskType.UNKNOWN: "vector_match",       # 默认向量匹配
}


class TaskClassifier:
    """
    任务类型分类器
    
    根据任务文本识别任务类型，决定角色匹配策略
    
    使用方法:
        classifier = TaskClassifier()
        task_type = classifier.classify("为记忆殿堂设计一个知识发现的自动化流程")
        strategy = classifier.get_strategy(task_type)
        
        if strategy == "fixed_team":
            return FIXED_TEAM
        else:
            return vector_match(...)
    """
    
    def __init__(self):
        self._type_scores: Dict[TaskType, int] = {}
    
    def classify(self, task: str) -> TaskType:
        """
        识别任务类型
        
        Args:
            task: 任务描述文本
            
        Returns:
            TaskType: 识别的任务类型
        """
        task_lower = task.lower()
        scores: Dict[TaskType, int] = {}
        
        for task_type, keywords in TASK_TYPE_PATTERNS.items():
            score = sum(1 for kw in keywords if kw.lower() in task_lower)
            scores[task_type] = score
        
        if not any(scores.values()):
            return TaskType.UNKNOWN
        
        # 返回得分最高的类型
        return max(scores, key=scores.get)
    
    def classify_with_scores(self, task: str) -> Dict[TaskType, int]:
        """
        获取所有类型的得分
        
        Returns:
            Dict[TaskType, int]: 类型→得分
        """
        task_lower = task.lower()
        scores: Dict[TaskType, int] = {}
        
        for task_type, keywords in TASK_TYPE_PATTERNS.items():
            score = sum(1 for kw in keywords if kw.lower() in task_lower)
            scores[task_type] = score
        
        return scores
    
    def get_strategy(self, task_type: TaskType) -> str:
        """
        获取任务类型对应的角色匹配策略
        
        Returns:
            str: "fixed_team" | "vector_match"
        """
        return TASK_TYPE_STRATEGY.get(task_type, "vector_match")
    
    def should_use_fixed_team(self, task: str) -> bool:
        """
        快速判断是否使用固定团队
        
        Returns:
            bool: True使用固定团队
        """
        task_type = self.classify(task)
        return self.get_strategy(task_type) == "fixed_team"
    
    def explain(self, task: str) -> str:
        """
        获取分类解释
        
        Returns:
            str: 分类理由
        """
        task_type = self.classify(task)
        scores = self.classify_with_scores(task)
        
        lines = [
            f"任务类型: {task_type.value}",
            f"策略: {self.get_strategy(task_type)}",
            "",
            "各类型得分:",
        ]
        
        for t, score in sorted(scores.items(), key=lambda x: -x[1]):
            if score > 0:
                lines.append(f"  {t.value}: {score}")
        
        return "\n".join(lines)


# 全局实例
_classifier: Optional[TaskClassifier] = None


def get_classifier() -> TaskClassifier:
    """获取全局分类器实例"""
    global _classifier
    if _classifier is None:
        _classifier = TaskClassifier()
    return _classifier


def classify_task(task: str) -> TaskType:
    """快捷函数：分类任务"""
    return get_classifier().classify(task)


def should_use_fixed_team(task: str) -> bool:
    """快捷函数：是否使用固定团队"""
    return get_classifier().should_use_fixed_team(task)
