#!/usr/bin/env python3
"""
统一异常模块

提供加密系统的统一异常层次结构
"""

from .base import EncryptionSystemError
from .encryption_errors import (
    EncryptionError,
    KeyGenerationError,
    AlgorithmNotSupportedError,
    DataTooLargeError,
)
from .decryption_errors import (
    DecryptionError,
    InvalidMetadataError,
    CorruptedDataError,
    KeyMismatchError,
    IntegrityVerificationError,
)
from .config_errors import (
    ConfigurationError,
    SchemaValidationError,
    ConfigNotFoundError,
    InvalidConfigValueError,
    ConfigLoadError,
)

__all__ = [
    # 基类
    'EncryptionSystemError',
    # 加密错误
    'EncryptionError',
    'KeyGenerationError',
    'AlgorithmNotSupportedError',
    'DataTooLargeError',
    # 解密错误
    'DecryptionError',
    'InvalidMetadataError',
    'CorruptedDataError',
    'KeyMismatchError',
    'IntegrityVerificationError',
    # 配置错误
    'ConfigurationError',
    'SchemaValidationError',
    'ConfigNotFoundError',
    'InvalidConfigValueError',
    'ConfigLoadError',
]
