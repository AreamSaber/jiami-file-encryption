"""
文件加密系统 - 核心模块

这是一个企业级文件加密系统，支持多层混合加密，
提供强大的数据保护和安全分发功能。

主要特性：
- 双程序分离架构（加密器 + 解密器）
- 多层混合加密算法
- 密钥分离和注入技术
- 显式文件完整性校验
- 隐写术数据隐藏
- 图形化用户界面

版本：1.0.0
作者：FileEncryption Team
"""

__version__ = "1.0.0"
__author__ = "FileEncryption Team"
__email__ = "team@fileencryption.com"
__license__ = "MIT"

# 导入核心模块
try:
    from .encryptor.main import FileEncryptor
except ImportError:
    FileEncryptor = None

try:
    from .decryptor import FileDecryptor
except ImportError:
    FileDecryptor = None

try:
    from .crypto import AESEncryption, ChaCha20Encryption, RSAEncryption
except ImportError:
    AESEncryption = ChaCha20Encryption = RSAEncryption = None

try:
    from .security.anti_reverse import AntiReverse
except ImportError:
    AntiReverse = None

try:
    from .utils import FileUtils, CryptoUtils, Logger
except ImportError:
    FileUtils = CryptoUtils = Logger = None

# 导出主要类
__all__ = [
    "FileEncryptor",
    "FileDecryptor",
    "AESEncryption",
    "ChaCha20Encryption",
    "RSAEncryption",
    "AntiReverse",
    "FileUtils",
    "CryptoUtils",
    "Logger"
]

# 版本信息
VERSION_INFO = {
    "major": 1,
    "minor": 0,
    "patch": 0,
    "release": "stable"
}

def get_version():
    """获取版本信息"""
    return f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch']}"

def get_full_version():
    """获取完整版本信息"""
    return f"{get_version()}-{VERSION_INFO['release']}"
