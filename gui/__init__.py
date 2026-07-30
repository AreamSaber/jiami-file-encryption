"""
图形用户界面模块

提供用户友好的GUI界面，支持文件加密、解密和配置管理。
"""

try:
    from .main_window import MainWindow
    MAIN_WINDOW_AVAILABLE = True
except ImportError:
    MAIN_WINDOW_AVAILABLE = False

try:
    from .encryption_dialog import EncryptionDialog
    ENCRYPTION_DIALOG_AVAILABLE = True
except ImportError:
    ENCRYPTION_DIALOG_AVAILABLE = False

__all__ = []

if MAIN_WINDOW_AVAILABLE:
    __all__.append("MainWindow")

if ENCRYPTION_DIALOG_AVAILABLE:
    __all__.append("EncryptionDialog")
