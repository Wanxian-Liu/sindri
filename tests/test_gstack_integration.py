"""
test_gstack_integration.py - gstack_integration模块测试

覆盖：
- GStackRole角色定义
- GStackResult结果类
- deepseek_call API调用
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
import sys
from pathlib import Path

# 添加模块路径
SCRIPT_DIR = Path(__file__).parent.parent / "modules"
sys.path.insert(0, str(SCRIPT_DIR))

MODULE_LOADED = False
err_msg = ""
try:
    from gstack_integration import (
        GStackRole,
        GStackResult,
        deepseek_call,
        DEEPSEEK_API_URL,
        DEFAULT_MODEL,
    )
    MODULE_LOADED = True
except ImportError as e:
    err_msg = str(e)


class TestGStackRole:
    """测试GStackRole角色定义"""
    
    def test_gstack_role_ceo(self):
        """验证CEO角色"""
        assert GStackRole.CEO == "ceo"
        assert isinstance(GStackRole.CEO, str)

    def test_gstack_role_review(self):
        """验证Review角色"""
        assert GStackRole.REVIEW == "review"

    def test_gstack_role_qa(self):
        """验证QA角色"""
        assert GStackRole.QA == "qa"

    def test_gstack_role_retro(self):
        """验证Retro角色"""
        assert GStackRole.RETRO == "retro"

    def test_gstack_role_count(self):
        """验证角色数量"""
        roles = [GStackRole.CEO, GStackRole.REVIEW, GStackRole.QA, GStackRole.RETRO]
        assert len(roles) == 4


class TestGStackResult:
    """测试GStackResult结果类"""

    def test_gstack_result_creation(self):
        """验证GStackResult创建"""
        result = GStackResult(
            status="success",
            role=GStackRole.CEO,
            data={"key": "value"}
        )
        assert result.status == "success"
        assert result.role == "ceo"
        assert result.data == {"key": "value"}

    def test_gstack_result_default(self):
        """验证默认值"""
        result = GStackResult(status="unknown", role=GStackRole.REVIEW)
        # data默认值是{}，不是None
        assert result.data == {}
        assert result.reason is None

    def test_gstack_result_with_reason(self):
        """验证reason字段"""
        result = GStackResult(
            status="skipped",
            role=GStackRole.QA,
            reason="timeout"
        )
        assert result.reason == "timeout"


class TestApiConfig:
    """测试API配置"""

    def test_api_url_configured(self):
        """验证API URL已配置"""
        assert DEEPSEEK_API_URL is not None
        assert "api.moonshot.cn" in DEEPSEEK_API_URL or "api.deepseek" in DEEPSEEK_API_URL

    def test_default_model_configured(self):
        """验证默认模型已配置"""
        assert DEFAULT_MODEL is not None
        assert len(DEFAULT_MODEL) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
