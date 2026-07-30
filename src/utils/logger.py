"""
日志记录工具

提供统一的日志记录功能，支持文件和控制台输出。
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    """日志记录器类"""
    
    def __init__(self, name: str, log_dir: Optional[str] = None, level: int = logging.INFO):
        """
        初始化日志记录器
        
        Args:
            name: 日志记录器名称
            log_dir: 日志文件目录
            level: 日志级别
        """
        self.name = name
        self.log_dir = log_dir or self._get_default_log_dir()
        self.level = level
        
        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 设置日志记录器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _get_default_log_dir(self) -> str:
        """获取默认日志目录"""
        return str(Path.home() / ".fileencryption" / "logs")
    
    def _setup_handlers(self):
        """设置日志处理器"""
        # 文件处理器
        log_file = os.path.join(
            self.log_dir, 
            f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(self.level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level)
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """记录信息"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """记录严重错误"""
        self.logger.critical(message)
    
    def exception(self, message: str):
        """记录异常信息"""
        self.logger.exception(message)


# 创建默认日志记录器
default_logger = Logger("FileEncryption")

# 便捷函数
def debug(message: str):
    default_logger.debug(message)

def info(message: str):
    default_logger.info(message)

def warning(message: str):
    default_logger.warning(message)

def error(message: str):
    default_logger.error(message)

def critical(message: str):
    default_logger.critical(message)

def exception(message: str):
    default_logger.exception(message)
