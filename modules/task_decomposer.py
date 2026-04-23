"""
task_decomposer.py - 任务分解模块

职责：
- 按Round阶段分解任务
- 固定小组角色分配
- 精确slice生成

v3.5修复：
- 配置化ROUND_STAGES
- 错误处理和降级策略
- 无slices时的fallback处理
"""

import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .role_matcher import RoleMatcher, FIXED_TEAM

# 配置化的Round阶段
ROUND_STAGES = {
    "round1": {
        "name": "规划",
        "role_key": "architect",
        "fallback_role_index": 2,  # Software Architect
    },
    "round2": {
        "name": "执行",
        "role_key": "developer",
        "fallback_role_index": 3,  # Senior Developer
    },
    "round3": {
        "name": "审查",
        "role_key": "tester",
        "fallback_role_index": 5,  # API Tester
    },
}

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """任务数据结构"""
    id: str
    title: str
    kind: str
    phase: str  # round1/round2/round3
    priority: str
    verify: List[str]
    metadata: Dict[str, Any]


class TaskDecomposer:
    """
    任务分解器
    
    职责：
    1. 分析任务类型
    2. 决定使用固定小组还是自动匹配
    3. 按Round阶段分配任务
    """
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.role_matcher = RoleMatcher(workspace_root)
    
    def get_roles(self, task: str, auto_matched_roles: List[Dict]) -> List[Dict]:
        """
        获取任务角色
        
        优先级：
        1. auto_matched_roles（来自FusionPlanner._decompose_and_match的预匹配结果）
        2. RoleMatcher.match() 的角色（仅当auto_matched_roles为空时）
        3. 默认固定小组
        
        注意：auto_matched_roles不为空时直接使用，不再重复调用RoleMatcher.match()
              以避免FusionPlanner中RoleMatcher被调用两次的性能开销。
        """
        # 优先使用预匹配结果（来自FusionPlanner._decompose_and_match的第一次调用）
        if auto_matched_roles:
            logger.info(f"[TaskDecomposer] 使用预匹配的角色（{len(auto_matched_roles)}个），跳过重复RoleMatcher调用")
            # 检查是否是审计团队或evolution团队
            is_audit = any(r.get('team_type') == 'audit' for r in auto_matched_roles)
            is_evolution = any(r.get('team_type') == 'evolution' for r in auto_matched_roles)
            is_skill_develop = any(r.get('team_type') == 'skill_develop' for r in auto_matched_roles)
            is_research = any(r.get('team_type') == 'research' for r in auto_matched_roles)
            # 也检查source='role_evolution_team'的情况
            has_role_evolution_source = any(r.get('source') == 'role_evolution_team' for r in auto_matched_roles)
            has_skill_develop_source = any(r.get('source') == 'skill_develop_team' for r in auto_matched_roles)
            has_research_source = any(r.get('source') == 'research_team' for r in auto_matched_roles)
            has_audit_source = any(r.get('source') == 'audit_team' for r in auto_matched_roles)
            
            if is_skill_develop or has_skill_develop_source:
                for r in auto_matched_roles:
                    r['team_type'] = 'skill_develop'
            elif is_evolution or has_role_evolution_source:
                for r in auto_matched_roles:
                    r['team_type'] = 'evolution'
            elif is_audit or has_audit_source:
                for r in auto_matched_roles:
                    r['team_type'] = 'audit'
            elif is_research or has_research_source:
                for r in auto_matched_roles:
                    r['team_type'] = 'research'
            return auto_matched_roles
        
        # auto_matched_roles为空时才调用RoleMatcher（降级fallback）
        try:
            matches = self.role_matcher.match(task)
            if matches:
                logger.info(f"[TaskDecomposer] RoleMatcher匹配到{len(matches)}个角色")
                # 检查是否是审计团队
                is_audit = any(getattr(m, 'source', None) == 'audit_team' for m in matches)
                # 检查是否是角色改进分配器（包括audit_evolution的fallback情况）
                is_evolution = any(getattr(m, 'source', None) in ('evolution_distributor', 'audit_evolution', 'role_evolution_team') for m in matches)
                # 检查是否是技能开发团队
                is_skill_develop = any(getattr(m, 'source', None) == 'skill_develop_team' for m in matches)
                # 检查是否是调研团队
                is_research = any(getattr(m, 'source', None) == 'research_team' for m in matches)
                roles = [m.role for m in matches]
                # 注意：优先级 skill_develop > evolution > audit > research
                if is_skill_develop:
                    for r in roles:
                        r['team_type'] = 'skill_develop'
                elif is_evolution:
                    for r in roles:
                        r['team_type'] = 'evolution'
                elif is_audit:
                    for r in roles:
                        r['team_type'] = 'audit'
                elif is_research:
                    for r in roles:
                        r['team_type'] = 'research'
                return roles
        except Exception as e:
            logger.warning(f"[TaskDecomposer] RoleMatcher错误: {e}，使用fallback")
        
        # 默认使用固定小组
        logger.info(f"[TaskDecomposer] 默认使用固定小组")
        return FIXED_TEAM
    
    def decompose_by_round(
        self,
        task: str,
        roles: List[Dict],
    ) -> Dict[str, List[Task]]:
        """
        按Round阶段分解任务
        
        Returns:
            {
                "round1": [Task, ...],
                "round2": [Task, ...],
                "round3": [Task, ...],
            }
        """
        # 生成slices（可能失败，返回空列表）
        slices = self._generate_slices_safe(task)
        
        # Round1: 规划任务
        round1_tasks = self._create_round1_tasks(task, roles, slices)
        
        # Round2: 执行任务
        round2_tasks = self._create_round2_tasks(slices, roles)
        
        # Round3: 审查任务
        round3_tasks = self._create_round3_tasks(slices, roles)
        
        return {
            "round1": round1_tasks,
            "round2": round2_tasks,
            "round3": round3_tasks,
        }
    
    def _generate_slices_safe(self, task: str) -> List[Dict]:
        """生成代码slice（带错误处理）"""
        try:
            slices = self._generate_slices(task)
            logger.info(f"[TaskDecomposer] 生成了{len(slices)}个slices")
            return slices
        except Exception as e:
            logger.error(f"[TaskDecomposer] Slice生成失败: {e}")
            return []
    
    def _generate_slices(self, task: str) -> List[Dict]:
        """生成代码slice"""
        # 动态导入SliceGenerator
        try:
            import importlib.util
            slice_gen_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "scripts", "slice_generator.py"
            )
            spec = importlib.util.spec_from_file_location("slice_generator", slice_gen_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            gen = module.SliceGenerator(workspace_root=self.workspace_root)
            raw_slices = gen.generate_slices(task)
            
            # 转换为dict格式
            slices = []
            for s in raw_slices:
                slices.append({
                    "file": s.file,
                    "function": s.function,
                    "description": s.description,
                    "test_cmd": s.test_cmd,
                    "priority": s.priority,
                })
            return slices
        except Exception as e:
            logger.warning(f"[TaskDecomposer] SliceGenerator unavailable: {e}")
            return []
    
    def _get_role_from_team(self, roles: List[Dict], key: str, fallback_index: int) -> Dict:
        """从团队中获取角色"""
        # 尝试通过key匹配（检查id、name和domain）
        for r in roles:
            role_id = r.get('id', '').lower()
            role_name = r.get('name', '').lower()
            role_domain = r.get('domain', '').lower()
            # 同时匹配id、name和domain（RESEARCH_TEAM使用domain字段）
            if key in role_id or key in role_name or key in role_domain:
                return r
        
        # 检查是否是特殊团队（包括audit和research）
        is_special_team = any(r.get('team_type') in ('evolution', 'skill_develop', 'research', 'audit') for r in roles)
        
        # 如果是特殊团队（evolution/skill_develop/research/audit），fallback到roles自身（不使用FIXED_TEAM）
        if is_special_team:
            if 0 <= fallback_index < len(roles):
                return roles[fallback_index]
            # 最后的fallback：返回roles中的第一个
            return roles[0] if roles else {"id": "researcher", "name": "Researcher"}
        
        # 如果有有效的roles参数，也使用roles而非FIXED_TEAM
        if roles and 0 <= fallback_index < len(roles):
            return roles[fallback_index]
        
        # 最后才fallback到FIXED_TEAM
        if 0 <= fallback_index < len(FIXED_TEAM):
            return FIXED_TEAM[fallback_index]
        
        # 最后的fallback
        return FIXED_TEAM[0]
    
    def _create_round1_tasks(
        self,
        task: str,
        roles: List[Dict],
        slices: List[Dict],
    ) -> List[Task]:
        """创建Round1任务（规划）"""
        tasks = []
        task_lower = task.lower()
        
        # 产品管理任务 → Product Manager
        if '产品' in task or '路线图' in task or 'pm' in task_lower or 'product' in task_lower:
            pm_role = self._get_role_from_team(roles, 'product_manager', 0)
            tasks.append(Task(
                id=self._gen_id("task"),
                title="产品规划与需求分析",
                kind="round1_planning",
                phase="round1",
                priority="high",
                verify=["PRD文档完整", "利益相关者确认"],
                metadata={
                    "role": pm_role,
                    "task_context": task,
                    "stage": "planning",
                }
            ))
            return tasks
        
        # 调研任务 → Academic角色（但如果team_type是audit或audit关键词，跳过）
        is_audit_team = any(r.get('team_type') == 'audit' or r.get('source') == 'audit_team' for r in roles)
        if not is_audit_team and any(kw in task_lower for kw in ['调研', '调研报告', '研究报告', '研究分析', '调查', '考察', '分析趋势', '深度调研']):
            researcher_role = self._get_role_from_team(roles, 'academic', 0) or roles[0] if roles else {}
            tasks.append(Task(
                id=self._gen_id("task"),
                title="调研任务规划与设计",
                kind="round1_planning",
                phase="round1",
                priority="high",
                verify=["调研计划完整", "研究方法可行"],
                metadata={
                    "role": researcher_role,
                    "task_context": task,
                    "stage": "research_planning",
                }
            ))
            return tasks
        
        # 审计任务 → AUDIT_TEAM 5个角色全部参与
        is_audit_team = any(r.get('team_type') == 'audit' or r.get('source') == 'audit_team' for r in roles)
        if is_audit_team and any(kw in task_lower for kw in ['审计', 'audit', '审查', '检查问题', '代码审查', '安全审计', '评估', '评价']):
            # AUDIT_TEAM 5个角色，每个都有独立的审计任务
            audit_roles = [
                {'name': 'Code Reviewer', 'title': '代码审计与问题识别', 'verify': ['审计范围明确', '检查清单完整', '代码逻辑无误']},
                {'name': 'Security Engineer', 'title': '安全审计与风险识别', 'verify': ['安全漏洞识别', '风险评估完成', '修复建议可行']},
                {'name': 'Software Architect', 'title': '架构审查与设计评估', 'verify': ['架构设计合理', '模块划分清晰', '扩展性评估']},
                {'name': 'QA Lead', 'title': '质量审查与测试覆盖', 'verify': ['质量标准明确', '测试覆盖充分', '验收条件清晰']},
                {'name': 'Reality Checker', 'title': '现实检查与可行性验证', 'verify': ['假设验证', '约束检查', '可行性确认']},
            ]
            
            for audit_info in audit_roles:
                # 从AUDIT_TEAM roles中找到匹配的角色
                matched_role = None
                for r in roles:
                    role_name = r.get('name', '').lower()
                    if audit_info['name'].lower() in role_name or role_name in audit_info['name'].lower():
                        matched_role = r
                        break
                
                if not matched_role:
                    # fallback: 尝试通过ID匹配
                    for r in roles:
                        role_id = r.get('id', '').lower()
                        if audit_info['name'].lower().replace(' ', '_') in role_id:
                            matched_role = r
                            break
                
                if matched_role:
                    tasks.append(Task(
                        id=self._gen_id("task"),
                        title=audit_info['title'],
                        kind="round1_planning",
                        phase="round1",
                        priority="high",
                        verify=audit_info['verify'],
                        metadata={
                            "role": matched_role,
                            "task_context": task,
                            "stage": "audit_planning",
                            "audit_dimension": audit_info['name'],
                        }
                    ))
            
            # AUDIT_TEAM所有角色都参与审计，不返回，继续让其他流程处理后续任务
            if tasks:
                return tasks
        
        # 工程任务 → Software Architect
        engineering_keywords = [
            '编程', '开发', '代码', 'python', 'java', 'javascript', 'typescript',
            '修改', '优化', '改进', '完善', '修复', 'bug', '重构', 'refactor', 'feature',
            '模块', '组件', '系统', '架构', '接口', '实现',
            'mimir', 'sindris', '进化', '记忆殿堂',
            '角色', 'role', 'workflow', '工作流',
        ]
        if any(kw in task_lower for kw in engineering_keywords):
            architect_role = self._get_role_from_team(roles, 'architect', 2)
            tasks.append(Task(
                id=self._gen_id("task"),
                title="架构分析与任务规划",
                kind="round1_planning",
                phase="round1",
                priority="high",
                verify=["规划文档完整", "技术方案可行"],
                metadata={
                    "role": architect_role,
                    "task_context": task,
                    "slices_count": len(slices),
                    "stage": "planning",
                }
            ))
            return tasks
        
        # 协调/编排任务 → Agents Orchestrator
        orchestrator_role = self._get_role_from_team(roles, 'orchestrator', 1)
        tasks.append(Task(
            id=self._gen_id("task"),
            title="工作流编排与协调",
            kind="round1_planning",
            phase="round1",
            priority="high",
            verify=["编排方案完整", "资源分配合理"],
            metadata={
                "role": orchestrator_role,
                "task_context": task,
                "stage": "planning",
            }
        ))
        
        return tasks
    
    def _create_round2_tasks(self, slices: List[Dict], roles: List[Dict]) -> List[Task]:
        """创建Round2任务（执行）"""
        tasks = []
        # 优先使用researcher角色，其次使用developer角色
        researcher_role = self._get_role_from_team(roles, 'researcher', 0)
        developer_role = researcher_role or self._get_role_from_team(roles, 'developer', 3)
        if not developer_role and roles:
            developer_role = roles[0]  # fallback到第一个角色
        
        # 如果有slices且数量合理（<=5），按slice创建任务
        # 数量>5说明SliceGenerator无法精确匹配，使用fallback避免污染
        if slices and len(slices) <= 5:
            for slice_info in slices:
                # 验证slice的test_cmd是否有效
                test_cmd = slice_info.get('test_cmd', '')
                # 如果test_cmd包含pytest且文件存在，则认为有效
                verify = [test_cmd] if test_cmd and 'pytest' in test_cmd else ['代码审查通过']
                
                tasks.append(Task(
                    id=self._gen_id("task"),
                    title=f"{slice_info['file']}::{slice_info['function']}",
                    kind="round2_execution",
                    phase="round2",
                    priority=slice_info.get('priority', 'medium'),
                    verify=verify,
                    metadata={
                        "role": developer_role,
                        "slice": slice_info,
                        "stage": "execution",
                    }
                ))
        else:
            # slice太多（>10）或无slice时使用fallback
            # 这避免了指向上下文不相关文件的问题
            fallback_tasks = [
                ("任务理解与分解", ["任务理解正确", "分解方案合理"]),
                ("代码实现与调试", ["代码实现完成", "调试通过"]),
                ("测试与验证", ["单元测试通过", "集成测试通过"]),
            ]
            for title, verify_list in fallback_tasks:
                tasks.append(Task(
                    id=self._gen_id("task"),
                    title=title,
                    kind="round2_execution",
                    phase="round2",
                    priority="high",
                    verify=verify_list,
                    metadata={
                        "role": developer_role,
                        "stage": "execution",
                        "fallback": True,
                        "slices_count": len(slices) if slices else 0,
                    }
                ))
        
        return tasks
    
    def _create_round3_tasks(self, slices: List[Dict], roles: List[Dict]) -> List[Task]:
        """创建Round3任务（审查）"""
        tasks = []
        tester_role = self._get_role_from_team(roles, 'tester', 5)  # API Tester
        checker_role = self._get_role_from_team(roles, 'checker', 6)  # Reality Checker
        
        # 功能验证任务
        tasks.append(Task(
            id=self._gen_id("task"),
            title="功能验证",
            kind="round3_review",
            phase="round3",
            priority="high",
            verify=["功能测试通过", "边界条件覆盖"],
            metadata={
                "role": tester_role,
                "review_type": "functional",
                "slices_count": len(slices),
                "stage": "review",
            }
        ))
        
        # 质量审查任务
        tasks.append(Task(
            id=self._gen_id("task"),
            title="代码质量审查",
            kind="round3_review",
            phase="round3",
            priority="high",
            verify=["代码质量达标", "无严重问题"],
            metadata={
                "role": checker_role,
                "review_type": "quality",
                "slices_count": len(slices),
                "stage": "review",
            }
        ))
        
        return tasks
    
    def _gen_id(self, prefix: str) -> str:
        """生成唯一ID"""
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
