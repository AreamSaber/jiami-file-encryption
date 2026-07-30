#!/usr/bin/env python3
"""
异常基类模块

定义加密系统的基础异常类
"""

from typing import Dict, Any, Optional


class EncryptionSystemError(Exception):
    """
    加密系统基础异常
    
    所有加密系统异常的基类，提供统一的错误信息格式
    
    Attributes:
        message: 错误消息
        error_code: 错误代码
        context: 错误上下文信息
    """
    
    def __init__(
        self,
        message: str,
        error_code: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码（如 'ENC001', 'DEC002'）
            context: 可选的错误上下文信息
        """
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """格式化错误消息"""
        base_msg = f"[{self.error_code}] {self.message}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base_msg += f" (context: {context_str})"
        return base_msg
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'context': self.context,
            'type': self.__class__.__name__
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(error_code='{self.error_code}', message='{self.message}')"
