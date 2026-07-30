"""
文件处理器

负责文件和文件夹的读取、处理和保存操作。
"""

import os
import json
import zipfile
import pickle
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..utils.logger import Logger
from ..utils.file_utils import FileUtils


class FileProcessor:
    """文件处理器"""
    
    def __init__(self):
        """初始化文件处理器"""
        self.logger = Logger("FileProcessor")
        self.file_utils = FileUtils()
        
        self.logger.info("文件处理器初始化完成")
    
    def read_file(self, file_path: str) -> bytes:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容字节
        """
        try:
            self.logger.debug(f"读取文件: {file_path}")
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            self.logger.debug(f"文件读取完成，大小: {len(data)} 字节")
            return data
            
        except Exception as e:
            self.logger.error(f"读取文件失败: {e}")
            raise
    
    def process_folder(self, folder_path: str, exclude_patterns: Optional[List[str]] = None) -> bytes:
        """
        处理文件夹，将其打包成字节数据
        
        Args:
            folder_path: 文件夹路径
            exclude_patterns: 排除的文件模式
            
        Returns:
            打包后的字节数据
        """
        try:
            self.logger.info(f"处理文件夹: {folder_path}")
            
            # 扫描文件夹
            file_list = self._scan_folder(folder_path, exclude_patterns or [])
            
            # 创建文件夹包
            folder_package = self._create_folder_package(folder_path, file_list)
            
            # 序列化
            package_data = pickle.dumps(folder_package)
            
            self.logger.info(f"文件夹处理完成，包含 {len(file_list)} 个文件，大小: {len(package_data)} 字节")
            return package_data
            
        except Exception as e:
            self.logger.error(f"处理文件夹失败: {e}")
            raise
    
    def _scan_folder(self, folder_path: str, exclude_patterns: List[str]) -> List[Dict]:
        """扫描文件夹，获取文件列表"""
        file_list = []
        folder_path = Path(folder_path)
        
        for root, dirs, files in os.walk(folder_path):
            root_path = Path(root)
            
            # 处理文件
            for file in files:
                file_path = root_path / file
                relative_path = file_path.relative_to(folder_path)
                
                # 检查是否需要排除
                if self._should_exclude(str(relative_path), exclude_patterns):
                    continue
                
                try:
                    # 获取文件信息
                    stat = file_path.stat()
                    
                    file_info = {
                        'path': str(file_path),
                        'relative_path': str(relative_path),
                        'size': stat.st_size,
                        'modified_time': stat.st_mtime,
                        'is_file': True
                    }
                    
                    file_list.append(file_info)
                    
                except Exception as e:
                    self.logger.warning(f"无法访问文件 {file_path}: {e}")
            
            # 处理空目录
            for dir_name in dirs:
                dir_path = root_path / dir_name
                relative_path = dir_path.relative_to(folder_path)
                
                if self._should_exclude(str(relative_path), exclude_patterns):
                    continue
                
                # 检查是否为空目录
                if not any(dir_path.iterdir()):
                    file_info = {
                        'path': str(dir_path),
                        'relative_path': str(relative_path),
                        'size': 0,
                        'modified_time': dir_path.stat().st_mtime,
                        'is_file': False
                    }
                    file_list.append(file_info)
        
        return file_list
    
    def _should_exclude(self, path: str, exclude_patterns: List[str]) -> bool:
        """检查文件是否应该被排除"""
        import fnmatch
        
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        
        return False
    
    def _create_folder_package(self, folder_path: str, file_list: List[Dict]) -> Dict:
        """创建文件夹包"""
        package = {
            'type': 'folder',
            'name': Path(folder_path).name,
            'original_path': folder_path,
            'file_count': len([f for f in file_list if f['is_file']]),
            'dir_count': len([f for f in file_list if not f['is_file']]),
            'total_size': sum(f['size'] for f in file_list),
            'files': []
        }
        
        # 读取文件内容
        for file_info in file_list:
            if file_info['is_file']:
                try:
                    with open(file_info['path'], 'rb') as f:
                        content = f.read()
                    
                    file_data = {
                        'relative_path': file_info['relative_path'],
                        'size': file_info['size'],
                        'modified_time': file_info['modified_time'],
                        'content': content,
                        'is_file': True
                    }
                    
                    package['files'].append(file_data)
                    
                except Exception as e:
                    self.logger.warning(f"读取文件失败 {file_info['path']}: {e}")
            else:
                # 目录信息
                dir_data = {
                    'relative_path': file_info['relative_path'],
                    'modified_time': file_info['modified_time'],
                    'is_file': False
                }
                package['files'].append(dir_data)
        
        return package
    
    def save_encrypted_data(self, encryption_result: Dict, output_path: str, 
                            original_size: int = None) -> bool:
        """
        保存加密数据
        
        Args:
            encryption_result: 加密结果
            output_path: 输出路径
            original_size: 原始数据大小（可选，用于解密时截断）
            
        Returns:
            是否保存成功
        """
        try:
            self.logger.info(f"保存加密数据: {output_path}")
            
            # 创建输出目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 创建加密包（清理不可序列化的对象）
            cleaned_metadata = self._clean_metadata_for_pickle(encryption_result['metadata'])
            
            # 确保original_size在metadata中
            if original_size is not None:
                cleaned_metadata['original_size'] = original_size
            
            encrypted_package = {
                'version': '1.0',
                'encrypted_data': encryption_result['encrypted_data'],
                'metadata': cleaned_metadata,
                'original_size': original_size,  # 同时保存在顶层
                'created_time': time.time()
            }

            # 保存到文件
            with open(output_path, 'wb') as f:
                pickle.dump(encrypted_package, f)
            
            self.logger.info(f"加密数据保存成功: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存加密数据失败: {e}")
            return False
    
    def load_encrypted_data(self, file_path: str) -> Dict:
        """
        加载加密数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            加密数据包
        """
        try:
            self.logger.info(f"加载加密数据: {file_path}")
            
            with open(file_path, 'rb') as f:
                encrypted_package = pickle.load(f)
            
            self.logger.info("加密数据加载成功")
            return encrypted_package
            
        except Exception as e:
            self.logger.error(f"加载加密数据失败: {e}")
            raise
    
    def restore_folder(self, folder_package: Dict, output_path: str) -> bool:
        """
        恢复文件夹
        
        Args:
            folder_package: 文件夹包
            output_path: 输出路径
            
        Returns:
            是否恢复成功
        """
        try:
            self.logger.info(f"恢复文件夹到: {output_path}")
            
            # 创建根目录
            root_dir = Path(output_path) / folder_package['name']
            root_dir.mkdir(parents=True, exist_ok=True)
            
            # 恢复文件和目录
            for file_data in folder_package['files']:
                target_path = root_dir / file_data['relative_path']
                
                if file_data['is_file']:
                    # 创建父目录
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # 写入文件内容
                    with open(target_path, 'wb') as f:
                        f.write(file_data['content'])
                    
                    # 恢复修改时间
                    os.utime(target_path, (file_data['modified_time'], file_data['modified_time']))
                else:
                    # 创建目录
                    target_path.mkdir(parents=True, exist_ok=True)
                    os.utime(target_path, (file_data['modified_time'], file_data['modified_time']))
            
            self.logger.info(f"文件夹恢复完成: {root_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"恢复文件夹失败: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Dict:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        try:
            path = Path(file_path)
            stat = path.stat()
            
            info = {
                'name': path.name,
                'size': stat.st_size,
                'modified_time': stat.st_mtime,
                'is_file': path.is_file(),
                'is_dir': path.is_dir(),
                'extension': path.suffix,
                'absolute_path': str(path.absolute())
            }
            
            return info
            
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {e}")
            return {}

    def _clean_metadata_for_pickle(self, metadata):
        """清理元数据中不可pickle的对象"""
        if isinstance(metadata, dict):
            cleaned = {}
            for key, value in metadata.items():
                # 跳过RSA私钥对象，因为它们已经在解密器中处理
                if key == 'private_key' and hasattr(value, 'private_bytes'):
                    # RSA私钥对象不需要保存到pickle文件中
                    # 它们已经在解密器中序列化了
                    continue
                elif key == 'public_key' and hasattr(value, 'public_bytes'):
                    # RSA公钥对象也不需要保存
                    continue
                else:
                    cleaned[key] = self._clean_metadata_for_pickle(value)
            return cleaned
        elif isinstance(metadata, list):
            return [self._clean_metadata_for_pickle(item) for item in metadata]
        else:
            return metadata
