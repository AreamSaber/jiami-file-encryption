"""
批处理器

提供批量文件处理功能，支持并行处理和进度显示。
"""

import os
import sys
import time
import fnmatch
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.encryptor.main import FileEncryptor
from src.utils.logger import Logger
from src.utils.file_utils import FileUtils
from src.thread_pool.thread_manager import thread_manager, ThreadPriority


class BatchProcessor:
    """批处理器类"""
    
    def __init__(self, *, resource_policy=None, resource_ledger=None):
        """初始化批处理器"""
        self.logger = Logger("BatchProcessor")
        # A configuration template only; concurrent tasks never use its engine.
        self.encryptor = FileEncryptor(thread_settings=thread_manager.snapshot(),
                                       resource_policy=resource_policy, resource_ledger=resource_ledger)
        self.resource_ledger = self.encryptor.resource_ledger
        self.file_utils = FileUtils()
        self.progress_lock = threading.Lock()
        self.processed_count = 0
        self.total_count = 0
        
    def process_directory(self, input_dir: str, output_dir: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量处理目录中的文件
        
        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            options: 处理选项
            
        Returns:
            处理结果
        """
        try:
            self._validate_parallel(options)
            self.logger.info(f"开始批量处理: {input_dir}")
            
            # 扫描文件
            files_to_process = self._scan_files(input_dir, options)
            
            if not files_to_process:
                return {
                    'success': False,
                    'error': '没有找到匹配的文件',
                    'processed_count': 0
                }
            
            self.total_count = len(files_to_process)
            self.processed_count = 0
            
            print(f"📁 找到 {self.total_count} 个文件待处理")
            
            if options.get('dry_run', False):
                return self._dry_run(files_to_process, output_dir, options)
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 执行批量处理
            start_time = time.time()
            
            if options.get('parallel', 1) > 1:
                result = self._parallel_process(files_to_process, output_dir, options)
            else:
                result = self._sequential_process(files_to_process, output_dir, options)
            
            end_time = time.time()
            
            result['total_time'] = end_time - start_time
            result['processed_count'] = self.processed_count
            
            self.logger.info(f"批量处理完成，处理了 {self.processed_count} 个文件")
            
            return result
            
        except Exception as e:
            self.logger.error(f"批量处理失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'processed_count': self.processed_count
            }
    
    def _scan_files(self, input_dir: str, options: Dict[str, Any]) -> List[str]:
        """扫描目录中的文件"""
        files = []
        pattern = options.get('pattern', '*')
        exclude_patterns = options.get('exclude', [])
        recursive = options.get('recursive', False)
        
        if recursive:
            # 递归扫描
            for root, dirs, filenames in os.walk(input_dir):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    if self._should_include_file(file_path, pattern, exclude_patterns):
                        files.append(file_path)
        else:
            # 只扫描当前目录
            for filename in os.listdir(input_dir):
                file_path = os.path.join(input_dir, filename)
                if os.path.isfile(file_path):
                    if self._should_include_file(file_path, pattern, exclude_patterns):
                        files.append(file_path)
        
        return files
    
    def _should_include_file(self, file_path: str, pattern: str, exclude_patterns: List[str]) -> bool:
        """检查文件是否应该被包含"""
        filename = os.path.basename(file_path)
        
        # 检查包含模式
        if not fnmatch.fnmatch(filename, pattern):
            return False
        
        # 检查排除模式
        for exclude_pattern in exclude_patterns:
            if fnmatch.fnmatch(filename, exclude_pattern):
                return False
        
        return True
    
    def _dry_run(self, files: List[str], output_dir: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """试运行，显示将要处理的文件"""
        print("🔍 试运行模式 - 将要处理的文件:")
        
        total_size = 0
        for i, file_path in enumerate(files, 1):
            file_size = self.file_utils.get_file_size(file_path)
            total_size += file_size
            
            print(f"  {i:3d}. {file_path} ({self.file_utils.format_size(file_size)})")
        
        print(f"\n📊 统计:")
        print(f"  文件数量: {len(files)}")
        print(f"  总大小: {self.file_utils.format_size(total_size)}")
        print(f"  输出目录: {output_dir}")
        print(f"  加密配置: {options.get('profile', 'standard')}")
        
        return {
            'success': True,
            'processed_count': len(files),
            'dry_run': True
        }
    
    def _sequential_process(self, files: List[str], output_dir: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """顺序处理文件"""
        successful = 0
        failed = 0
        errors = []
        
        for file_path in files:
            try:
                self._process_single_file(file_path, output_dir, options)
                successful += 1
            except Exception as e:
                failed += 1
                error_msg = f"{file_path}: {str(e)}"
                errors.append(error_msg)
                self.logger.error(f"处理文件失败: {error_msg}")
            finally:
                self._update_progress()
        
        return {
            'success': failed == 0,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
    
    def _parallel_process(self, files: List[str], output_dir: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """并行处理文件"""
        budget = max(1, self.encryptor.thread_manager.get_max_threads())
        max_workers = min(options.get('parallel', 1), len(files), budget)
        inner_threads = max(1, budget // max_workers)
        successful = 0
        failed = 0
        errors = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_file = {
                executor.submit(self._process_single_file, file_path, output_dir, options, inner_threads): file_path
                for file_path in files
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    future.result()
                    successful += 1
                except Exception as e:
                    failed += 1
                    error_msg = f"{file_path}: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(f"处理文件失败: {error_msg}")
                finally:
                    self._update_progress()
        
        return {
            'success': failed == 0,
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
    
    @staticmethod
    def _validate_parallel(options):
        count = options.get('parallel', 1)
        if type(count) is not int or count < 1:
            raise ValueError('parallel must be a positive integer')

    def _process_single_file(self, file_path: str, output_dir: str, options: Dict[str, Any], inner_threads=None):
        """处理单个文件"""
        profile = options.get('profile', 'standard')
        
        settings = self.encryptor.thread_manager.snapshot()
        if inner_threads is not None:
            settings.set_config(priority=ThreadPriority.GUI_OVERRIDE,
                                source='batch_worker_budget', max_threads=inner_threads)
        encryptor = FileEncryptor(config_dir=self.encryptor.config_dir, thread_settings=settings,
                                  resource_ledger=self.resource_ledger)
        try:
            result = encryptor.encrypt_file(file_path, output_dir, profile)
            if not result['success']:
                raise RuntimeError(result.get('error', '加密失败'))
        finally:
            encryptor.hybrid_engine.shutdown()
    
    def _update_progress(self):
        """Count completed attempts, including failures; outcomes stay separate."""
        with self.progress_lock:
            self.processed_count += 1
            progress = (self.processed_count / self.total_count) * 100
            
            # 简单的进度条
            bar_length = 30
            filled_length = int(bar_length * self.processed_count // self.total_count)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            
            print(f"\r📊 进度: |{bar}| {progress:.1f}% ({self.processed_count}/{self.total_count})", end='', flush=True)
            
            if self.processed_count == self.total_count:
                print()  # 换行
    
    def process_file_list(self, file_list: List[str], output_dir: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理指定的文件列表
        
        Args:
            file_list: 文件列表
            output_dir: 输出目录
            options: 处理选项
            
        Returns:
            处理结果
        """
        try:
            self._validate_parallel(options)
            # 过滤存在的文件
            existing_files = [f for f in file_list if os.path.isfile(f)]
            
            if not existing_files:
                return {
                    'success': False,
                    'error': '没有有效的文件',
                    'processed_count': 0
                }
            
            self.total_count = len(existing_files)
            self.processed_count = 0
            
            print(f"📁 处理 {self.total_count} 个文件")
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 执行处理
            start_time = time.time()
            
            if options.get('parallel', 1) > 1:
                result = self._parallel_process(existing_files, output_dir, options)
            else:
                result = self._sequential_process(existing_files, output_dir, options)
            
            end_time = time.time()
            
            result['total_time'] = end_time - start_time
            result['processed_count'] = self.processed_count
            
            return result
            
        except Exception as e:
            self.logger.error(f"文件列表处理失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'processed_count': self.processed_count
            }
    
    def get_statistics(self, directory: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取目录统计信息
        
        Args:
            directory: 目录路径
            options: 扫描选项
            
        Returns:
            统计信息
        """
        try:
            files = self._scan_files(directory, options)
            
            total_size = 0
            file_types = {}
            
            for file_path in files:
                # 计算大小
                file_size = self.file_utils.get_file_size(file_path)
                total_size += file_size
                
                # 统计文件类型
                ext = self.file_utils.get_file_extension(file_path).lower()
                if not ext:
                    ext = '无扩展名'
                
                if ext in file_types:
                    file_types[ext]['count'] += 1
                    file_types[ext]['size'] += file_size
                else:
                    file_types[ext] = {'count': 1, 'size': file_size}
            
            return {
                'total_files': len(files),
                'total_size': total_size,
                'file_types': file_types,
                'average_size': total_size / len(files) if files else 0
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'file_types': {},
                'average_size': 0,
                'error': str(e)
            }
