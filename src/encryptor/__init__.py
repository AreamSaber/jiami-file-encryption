"""
加密器模块

负责文件和文件夹的加密处理，生成定制化的解密器程序。

主要功能：
- 文件/文件夹加密
- 多层混合加密
- 解密器生成
- 密钥注入
"""

from .main import FileEncryptor
from .hybrid_engine import HybridEncryptionEngine
from .key_injector import KeyInjector
from .file_processor import FileProcessor

__all__ = [
    "FileEncryptor",
    "HybridEncryptionEngine", 
    "KeyInjector",
    "FileProcessor"
]
