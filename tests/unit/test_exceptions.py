#!/usr/bin/env python3
"""异常类单元测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from src.exceptions import (
    EncryptionSystemError,
    EncryptionError,
    DecryptionError,
    ConfigurationError,
    KeyGenerationError,
    InvalidMetadataError,
    SchemaValidationError,
)


class TestEncryptionSystemError:
    """基础异常测试"""
    
    def test_basic_creation(self):
        exc = EncryptionSystemError("测试消息", "TEST001")
        assert exc.message == "测试消息"
        assert exc.error_code == "TEST001"
        assert exc.context == {}
    
    def test_with_context(self):
        exc = EncryptionSystemError("测试", "TEST002", {"key": "value"})
        assert exc.context == {"key": "value"}
    
    def test_format_message(self):
        exc = EncryptionSystemError("测试", "TEST003")
        formatted = exc.format_message()
        assert "TEST003" in formatted
        assert "测试" in formatted
    
    def test_to_dict(self):
        exc = EncryptionSystemError("测试", "TEST004", {"a": 1})
        d = exc.to_dict()
        assert d['error_code'] == "TEST004"
        assert d['message'] == "测试"
        assert d['context'] == {"a": 1}
        assert d['type'] == "EncryptionSystemError"


class TestEncryptionError:
    """加密错误测试"""
    
    def test_default_code(self):
        exc = EncryptionError("加密失败")
        assert exc.error_code == "ENC000"
    
    def test_custom_code(self):
        exc = EncryptionError("加密失败", "ENC999")
        assert exc.error_code == "ENC999"


class TestDecryptionError:
    """解密错误测试"""
    
    def test_default_code(self):
        exc = DecryptionError("解密失败")
        assert exc.error_code == "DEC000"


class TestConfigurationError:
    """配置错误测试"""
    
    def test_default_code(self):
        exc = ConfigurationError("配置错误")
        assert exc.error_code == "CFG000"


class TestKeyGenerationError:
    """密钥生成错误测试"""
    
    def test_with_algorithm(self):
        exc = KeyGenerationError("密钥生成失败", algorithm="AES-256")
        assert exc.context['algorithm'] == "AES-256"
        assert exc.error_code == "ENC001"


class TestInvalidMetadataError:
    """无效元数据错误测试"""
    
    def test_with_field(self):
        exc = InvalidMetadataError("元数据无效", metadata_field="key")
        assert exc.context['metadata_field'] == "key"
        assert exc.error_code == "DEC001"


class TestSchemaValidationError:
    """Schema验证错误测试"""
    
    def test_with_errors(self):
        exc = SchemaValidationError(
            "验证失败",
            config_name="test",
            validation_errors=["错误1", "错误2"]
        )
        assert exc.context['config_name'] == "test"
        assert len(exc.context['validation_errors']) == 2
        assert exc.error_code == "CFG001"
