"""
文件工具模块

提供文件和目录操作的工具函数。
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Union

from .logger import Logger


class FileUtils:
    """文件工具类"""
    
    def __init__(self):
        """初始化文件工具"""
        self.logger = Logger("FileUtils")
    
    def ensure_dir(self, path: Union[str, Path]) -> bool:
        """
        确保目录存在
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self.logger.error(f"创建目录失败 {path}: {e}")
            return False
    
    def get_file_size(self, file_path: Union[str, Path]) -> int:
        """
        获取文件大小
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件大小（字节）
        """
        try:
            return Path(file_path).stat().st_size
        except Exception as e:
            self.logger.error(f"获取文件大小失败 {file_path}: {e}")
            return 0
    
    def get_dir_size(self, dir_path: Union[str, Path]) -> int:
        """
        获取目录大小
        
        Args:
            dir_path: 目录路径
            
        Returns:
            目录总大小（字节）
        """
        try:
            total_size = 0
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, FileNotFoundError):
                        continue
            return total_size
        except Exception as e:
            self.logger.error(f"获取目录大小失败 {dir_path}: {e}")
            return 0
    
    def copy_file(self, src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """
        复制文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            
        Returns:
            是否成功
        """
        try:
            # 确保目标目录存在
            self.ensure_dir(Path(dst).parent)
            
            shutil.copy2(src, dst)
            self.logger.debug(f"文件复制成功: {src} -> {dst}")
            return True
        except Exception as e:
            self.logger.error(f"文件复制失败: {e}")
            return False
    
    def move_file(self, src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """
        移动文件
        
        Args:
            src: 源文件路径
            dst: 目标文件路径
            
        Returns:
            是否成功
        """
        try:
            # 确保目标目录存在
            self.ensure_dir(Path(dst).parent)
            
            shutil.move(src, dst)
            self.logger.debug(f"文件移动成功: {src} -> {dst}")
            return True
        except Exception as e:
            self.logger.error(f"文件移动失败: {e}")
            return False
    
    def delete_file(self, file_path: Union[str, Path]) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否成功
        """
        try:
            Path(file_path).unlink()
            self.logger.debug(f"文件删除成功: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"文件删除失败: {e}")
            return False
    
    def delete_dir(self, dir_path: Union[str, Path]) -> bool:
        """
        删除目录
        
        Args:
            dir_path: 目录路径
            
        Returns:
            是否成功
        """
        try:
            shutil.rmtree(dir_path)
            self.logger.debug(f"目录删除成功: {dir_path}")
            return True
        except Exception as e:
            self.logger.error(f"目录删除失败: {e}")
            return False
    
    def list_files(self, dir_path: Union[str, Path], pattern: str = "*") -> List[Path]:
        """
        列出目录中的文件
        
        Args:
            dir_path: 目录路径
            pattern: 文件模式
            
        Returns:
            文件路径列表
        """
        try:
            return list(Path(dir_path).glob(pattern))
        except Exception as e:
            self.logger.error(f"列出文件失败: {e}")
            return []
    
    def find_files(self, dir_path: Union[str, Path], pattern: str = "*", recursive: bool = True) -> List[Path]:
        """
        查找文件
        
        Args:
            dir_path: 目录路径
            pattern: 文件模式
            recursive: 是否递归查找
            
        Returns:
            文件路径列表
        """
        try:
            if recursive:
                return list(Path(dir_path).rglob(pattern))
            else:
                return list(Path(dir_path).glob(pattern))
        except Exception as e:
            self.logger.error(f"查找文件失败: {e}")
            return []
    
    def create_temp_file(self, suffix: str = "", prefix: str = "tmp") -> str:
        """
        创建临时文件
        
        Args:
            suffix: 文件后缀
            prefix: 文件前缀
            
        Returns:
            临时文件路径
        """
        try:
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)  # 关闭文件描述符
            return temp_path
        except Exception as e:
            self.logger.error(f"创建临时文件失败: {e}")
            return ""
    
    def create_temp_dir(self, prefix: str = "tmp") -> str:
        """
        创建临时目录
        
        Args:
            prefix: 目录前缀
            
        Returns:
            临时目录路径
        """
        try:
            return tempfile.mkdtemp(prefix=prefix)
        except Exception as e:
            self.logger.error(f"创建临时目录失败: {e}")
            return ""
    
    def is_binary_file(self, file_path: Union[str, Path]) -> bool:
        """
        检查是否为二进制文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否为二进制文件
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' in chunk
        except Exception:
            return True  # 无法读取时假设为二进制
    
    def get_file_extension(self, file_path: Union[str, Path]) -> str:
        """
        获取文件扩展名
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件扩展名（不含点）
        """
        return Path(file_path).suffix.lstrip('.')
    
    def change_extension(self, file_path: Union[str, Path], new_ext: str) -> str:
        """
        更改文件扩展名
        
        Args:
            file_path: 文件路径
            new_ext: 新扩展名
            
        Returns:
            新文件路径
        """
        path = Path(file_path)
        return str(path.with_suffix(f".{new_ext.lstrip('.')}"))
    
    def sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原文件名
            
        Returns:
            清理后的文件名
        """
        # Windows和Unix系统的非法字符
        illegal_chars = '<>:"/\\|?*'
        
        sanitized = filename
        for char in illegal_chars:
            sanitized = sanitized.replace(char, '_')
        
        # 移除前后空格和点
        sanitized = sanitized.strip(' .')
        
        # 确保不为空
        if not sanitized:
            sanitized = "unnamed"
        
        return sanitized
    
    def format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节数
            
        Returns:
            格式化的大小字符串
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    def backup_file(self, file_path: Union[str, Path], backup_suffix: str = ".bak") -> str:
        """
        备份文件
        
        Args:
            file_path: 文件路径
            backup_suffix: 备份后缀
            
        Returns:
            备份文件路径
        """
        try:
            backup_path = str(file_path) + backup_suffix
            shutil.copy2(file_path, backup_path)
            self.logger.debug(f"文件备份成功: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"文件备份失败: {e}")
            return ""
