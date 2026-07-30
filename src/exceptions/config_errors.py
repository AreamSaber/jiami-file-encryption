#!/usr/bin/env python3
"""
配置相关异常模块

定义配置管理过程中可能发生的异常
"""

from typing import Dict, Any, Optional, List
from .base import EncryptionSystemError


class ConfigurationError(EncryptionSystemError):
    """
    配置错误基类
    
    所有配置相关错误的基类
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "CFG000",
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, context)


class SchemaValidationError(ConfigurationError):
    """
    Schema验证错误
    
    当配置不符合JSON Schema时抛出
    """
    
    def __init__(
        self,
        message: str,
        config_name: Optional[str] = None,
        validation_errors: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if config_name:
            ctx['config_name'] = config_name
        if validation_errors:
            ctx['validation_errors'] = validation_errors
        super().__init__(message, "CFG001", ctx)


class ConfigNotFoundError(ConfigurationError):
    """
    配置未找到错误
    
    当请求的配置文件不存在时抛出
    """
    
    def __init__(
        self,
        config_name: str,
        config_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        ctx['config_name'] = config_name
        if config_path:
            ctx['config_path'] = config_path
        message = f"配置文件未找到: {config_name}"
        super().__init__(message, "CFG002", ctx)


class InvalidConfigValueError(ConfigurationError):
    """
    无效配置值错误
    
    当配置值无效时抛出
    """
    
    def __init__(
        self,
        config_key: str,
        invalid_value: Any,
        expected_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        ctx['config_key'] = config_key
        ctx['invalid_value'] = str(invalid_value)
        if expected_type:
            ctx['expected_type'] = expected_type
        message = f"配置项 '{config_key}' 的值无效: {invalid_value}"
        super().__init__(message, "CFG003", ctx)


class ConfigLoadError(ConfigurationError):
    """
    配置加载错误
    
    当配置文件加载失败时抛出
    """
    
    def __init__(
        self,
        message: str,
        config_path: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        if config_path:
            ctx['config_path'] = config_path
        super().__init__(message, "CFG004", ctx)


class ProfileNotFoundError(ConfigurationError):
    """
    配置文件未找到错误
    
    当请求的加密配置文件不存在时抛出
    """
    
    def __init__(
        self,
        profile_name: str,
        available_profiles: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        ctx = context or {}
        ctx['profile_name'] = profile_name
        if available_profiles:
            ctx['available_profiles'] = available_profiles
        message = f"加密配置文件未找到: {profile_name}"
        super().__init__(message, "CFG005", ctx)
