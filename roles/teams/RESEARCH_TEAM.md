---
name: RESEARCH_TEAM
version: 1.0.0
category: teams
description: 调研团队 - 8个研究角色协同进行深度调研
triggers:
  - 组建调研团队
  - 深度调研
  - RESEARCH_TEAM
  - 需要多学科研究
members:
  - academic-historian
  - academic-psychologist
  - academic-narratologist
  - academic-geographer
  - academic-anthropologist
  - product-trend-researcher
  - design-ux-researcher
  - test-results-analyzer
workflow:
  - phase: 议题定义
    description: 确定调研议题和范围
    roles:
      - academic-historian
      - academic-psychologist
  - phase: 各自调研
    description: 各角色按专业进行调研
    parallel: true
    roles:
      - academic-historian
      - academic-psychologist
      - academic-narratologist
      - academic-geographer
      - academic-anthropologist
      - product-trend-researcher
      - design-ux-researcher
      - test-results-analyzer
  - phase: 交叉整合
    description: 整合各角色调研结果
    roles:
      - academic-historian
      - academic-psychologist
  - phase: QA审查
    description: 质量审查
    roles:
      - test-results-analyzer
  - phase: 综合报告
    description: 生成最终调研报告
    roles:
      - academic-narratologist
output: 调研综合报告
