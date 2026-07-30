#!/usr/bin/env python3
"""
解密相关异常模块

定义解密过程中可能发生的异常
"""

from typing import Dict, Any, Optional
from .base import EncryptionSystemError


class DecryptionError(EncryptionSystemError):
    """
    解密错误基类
    
    所有解密相关错误的基类
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "DEC000",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, context)


class InvalidMetadataError(DecryptionError):
    """
    无效元数据错误
    
    当加密元数据无效或损坏时抛出
    """
    
    def __init__(
        self,
        message: str,
        metadata_field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if metadata_field:
            ctx['metadata_field'] = metadata_field
        super().__init__(message, "DEC001", ctx)


class CorruptedDataError(DecryptionError):
    """
    数据损坏错误
    
    当加密数据损坏无法解密时抛出
    """
    
    def __init__(
        self,
        message: str,
        expected_size: Optional[int] = None,
        actual_size: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if expected_size is not None:
            ctx['expected_size'] = expected_size
        if actual_size is not None:
            ctx['actual_size'] = actual_size
        super().__init__(message, "DEC002", ctx)


class KeyMismatchError(DecryptionError):
    """
    密钥不匹配错误
    
    当解密密钥与加密密钥不匹配时抛出
    """
    
    def __init__(
        self,
        message: str = "解密密钥与加密密钥不匹配",
        algorithm: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if algorithm:
            ctx['algorithm'] = algorithm
        super().__init__(message, "DEC003", ctx)


class LayerDecryptionError(DecryptionError):
    """
    层解密错误
    
    当特定加密层解密失败时抛出
    """
    
    def __init__(
        self,
        message: str,
        layer_index: Optional[int] = None,
        algorithm: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if layer_index is not None:
            ctx['layer_index'] = layer_index
        if algorithm:
            ctx['algorithm'] = algorithm
        super().__init__(message, "DEC004", ctx)


class FileDecryptionError(DecryptionError):
    """
    文件解密错误
    
    当文件解密过程失败时抛出
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if file_path:
            ctx['file_path'] = file_path
        super().__init__(message, "DEC005", ctx)
