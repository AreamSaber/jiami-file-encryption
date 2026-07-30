#!/usr/bin/env python3
"""
加密相关异常模块

定义加密过程中可能发生的异常
"""

from typing import Dict, Any, Optional
from .base import EncryptionSystemError


class EncryptionError(EncryptionSystemError):
    """
    加密错误基类
    
    所有加密相关错误的基类
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "ENC000",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, context)


class KeyGenerationError(EncryptionError):
    """
    密钥生成错误
    
    当密钥生成失败时抛出
    """
    
    def __init__(
        self,
        message: str,
        algorithm: Optional[str] = None,
        key_size: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if algorithm:
            ctx['algorithm'] = algorithm
        if key_size:
            ctx['key_size'] = key_size
        super().__init__(message, "ENC001", ctx)


class AlgorithmNotSupportedError(EncryptionError):
    """
    算法不支持错误
    
    当请求的加密算法不被支持时抛出
    """
    
    def __init__(
        self,
        algorithm: str,
        supported_algorithms: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        ctx['algorithm'] = algorithm
        if supported_algorithms:
            ctx['supported'] = supported_algorithms
        message = f"不支持的加密算法: {algorithm}"
        super().__init__(message, "ENC002", ctx)


class DataTooLargeError(EncryptionError):
    """
    数据过大错误
    
    当输入数据超过处理限制时抛出
    """
    
    def __init__(
        self,
        data_size: int,
        max_size: int,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        ctx['data_size'] = data_size
        ctx['max_size'] = max_size
        message = f"数据大小 {data_size} 超过最大限制 {max_size}"
        super().__init__(message, "ENC003", ctx)


class FileEncryptionError(EncryptionError):
    """
    文件加密错误
    
    当文件加密过程失败时抛出
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
        super().__init__(message, "ENC004", ctx)


class GPUEncryptionError(EncryptionError):
    """
    GPU加密错误
    
    当GPU加密过程失败时抛出
    """
    
    def __init__(
        self,
        message: str,
        gpu_device: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if gpu_device:
            ctx['gpu_device'] = gpu_device
        super().__init__(message, "ENC005", ctx)
