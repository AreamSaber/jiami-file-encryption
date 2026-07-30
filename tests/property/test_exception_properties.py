#!/usr/bin/env python3
"""
异常信息完整性属性测试

Feature: tech-debt-refactor, Property 5: 异常信息完整性
Validates: Requirements 3.1, 3.2, 3.3
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hypothesis import given, strategies as st, settings
from src.exceptions import (
    EncryptionSystemError,
    EncryptionError,
    DecryptionError,
    ConfigurationError,
    KeyGenerationError,
    InvalidMetadataError,
    SchemaValidationError,
)


# 定义策略
error_messages = st.text(min_size=1, max_size=200)
error_codes = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=3,
    max_size=10
)
context_keys = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=20
)
context_values = st.one_of(
    st.text(max_size=100),
    st.integers(),
    st.booleans(),
)
context_dicts = st.dictionaries(context_keys, context_values, max_size=5)


class TestExceptionCompleteness:
    """
    Property 5: 异常信息完整性
    
    For any 无效输入导致的错误，抛出的异常应该包含error_code和非空的message
    Validates: Requirements 3.1, 3.2, 3.3
    """

    @given(message=error_messages, error_code=error_codes, context=context_dicts)
    @settings(max_examples=100)
    def test_base_exception_has_required_fields(
        self, message: str, error_code: str, context: dict
    ):
        """
        Feature: tech-debt-refactor, Property 5: 异常信息完整性
        Validates: Requirements 3.1, 3.2, 3.3
        
        基础异常应该包含error_code和非空message
        """
        exc = EncryptionSystemError(message, error_code, context)
        
        # 验证必需字段存在
        assert hasattr(exc, 'error_code'), "异常应该有error_code属性"
        assert hasattr(exc, 'message'), "异常应该有message属性"
        assert hasattr(exc, 'context'), "异常应该有context属性"
        
        # 验证字段值
        assert exc.error_code == error_code, "error_code应该与输入一致"
        assert exc.message == message, "message应该与输入一致"
        assert exc.context == context, "context应该与输入一致"
        
        # 验证error_code非空
        assert len(exc.error_code) > 0, "error_code不应为空"
        
        # 验证message非空
        assert len(exc.message) > 0, "message不应为空"

    @given(message=error_messages, context=context_dicts)
    @settings(max_examples=100)
    def test_encryption_error_has_default_code(self, message: str, context: dict):
        """
        Feature: tech-debt-refactor, Property 5: 异常信息完整性
        Validates: Requirements 3.1
        
        加密错误应该有默认的error_code
        """
        exc = EncryptionError(message, context=context)
        
        assert exc.error_code is not None, "应该有默认error_code"
        assert len(exc.error_code) > 0, "error_code不应为空"
        assert exc.message == message, "message应该与输入一致"

    @given(message=error_messages, context=context_dicts)
    @settings(max_examples=100)
    def test_decryption_error_has_default_code(self, message: str, context: dict):
        """
        Feature: tech-debt-refactor, Property 5: 异常信息完整性
        Validates: Requirements 3.2
        
        解密错误应该有默认的error_code
        """
        exc = DecryptionError(message, context=context)
        
        assert exc.error_code is not None, "应该有默认error_code"
        assert len(exc.error_code) > 0, "error_code不应为空"
        assert exc.message == message, "message应该与输入一致"

    @given(message=error_messages, context=context_dicts)
    @settings(max_examples=100)
    def test_config_error_has_default_code(self, message: str, context: dict):
        """
        Feature: tech-debt-refactor, Property 5: 异常信息完整性
        Validates: Requirements 3.3
        
        配置错误应该有默认的error_code
        """
        exc = ConfigurationError(message, context=context)
        
        assert exc.error_code is not None, "应该有默认error_code"
        assert len(exc.error_code) > 0, "error_code不应为空"
        assert exc.message == message, "message应该与输入一致"

    @given(message=error_messages, error_code=error_codes, context=context_dicts)
    @settings(max_examples=100)
    def test_exception_to_dict_completeness(
        self, message: str, error_code: str, context: dict
    ):
        """
        Feature: tech-debt-refactor, Property 5: 异常信息完整性
        Validates: Requirements 3.1, 3.2, 3.3
        
        异常转换为字典时应该包含所有必需字段
        """
        exc = EncryptionSystemError(message, error_code, context)
        exc_dict = exc.to_dict()
        
        # 验证字典包含所有必需字段
        assert 'error_code' in exc_dict, "字典应该包含error_code"
        assert 'message' in exc_dict, "字典应该包含message"
        assert 'context' in exc_dict, "字典应该包含context"
        assert 'type' in exc_dict, "字典应该包含type"
        
        # 验证字段值
        assert exc_dict['error_code'] == error_code
        assert exc_dict['message'] == message
        assert exc_dict['context'] == context
        assert exc_dict['type'] == 'EncryptionSystemError'

    @given(message=error_messages, error_code=error_codes, context=context_dicts)
    @settings(max_examples=100)
    def test_exception_format_message_includes_code(
        self, message: str, error_code: str, context: dict
    ):
        """
        Feature: tech-debt-refactor, Property 5: 异常信息完整性
        Validates: Requirements 3.1, 3.2, 3.3
        
        格式化消息应该包含error_code
        """
        exc = EncryptionSystemError(message, error_code, context)
        formatted = exc.format_message()
        
        # 验证格式化消息包含error_code
        assert error_code in formatted, "格式化消息应该包含error_code"
        assert message in formatted, "格式化消息应该包含原始message"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
