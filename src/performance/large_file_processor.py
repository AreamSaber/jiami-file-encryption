"""
大文件处理器

优化大文件的加密处理，支持分块处理、流式处理和进度跟踪。
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Callable, Optional, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logger import Logger
from src.utils.file_utils import FileUtils
from .memory_manager import MemoryManager
from .progress_tracker import ProgressTracker


class LargeFileProcessor:
    """大文件处理器类"""
    
    def __init__(self, chunk_size: int = 64 * 1024 * 1024):  # 默认64MB块
        """
        初始化大文件处理器
        
        Args:
            chunk_size: 块大小（字节）
        """
        self.logger = Logger("LargeFileProcessor")
        self.file_utils = FileUtils()
        self.memory_manager = MemoryManager()
        self.chunk_size = chunk_size
        self.max_workers = min(4, os.cpu_count() or 1)
        
    def process_large_file(self, 
                          file_path: str, 
                          output_path: str,
                          processor_func: Callable,
                          progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        处理大文件
        
        Args:
            file_path: 输入文件路径
            output_path: 输出文件路径
            processor_func: 处理函数
            progress_callback: 进度回调函数
            
        Returns:
            处理结果
        """
        try:
            start_time = time.time()
            
            # 获取文件信息
            file_size = self.file_utils.get_file_size(file_path)
            
            if file_size == 0:
                return {'success': False, 'error': '文件为空'}
            
            self.logger.info(f"开始处理大文件: {file_path} ({self.file_utils.format_size(file_size)})")
            
            # 创建进度跟踪器
            progress_tracker = ProgressTracker(file_size, progress_callback)
            
            # 选择处理策略
            if file_size <= self.chunk_size:
                # 小文件直接处理
                result = self._process_small_file(file_path, output_path, processor_func, progress_tracker)
            else:
                # 大文件分块处理
                result = self._process_chunked_file(file_path, output_path, processor_func, progress_tracker)
            
            end_time = time.time()
            result['processing_time'] = end_time - start_time
            result['throughput'] = file_size / (end_time - start_time) if end_time > start_time else 0
            
            self.logger.info(f"文件处理完成，耗时: {result['processing_time']:.2f}秒")
            
            return result
            
        except Exception as e:
            self.logger.error(f"大文件处理失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_small_file(self, 
                           file_path: str, 
                           output_path: str,
                           processor_func: Callable,
                           progress_tracker: ProgressTracker) -> Dict[str, Any]:
        """处理小文件"""
        try:
            # 读取整个文件
            with open(file_path, 'rb') as f:
                data = f.read()
            
            progress_tracker.update(len(data) // 2)  # 读取完成50%
            
            # 处理数据
            processed_data = processor_func(data)
            
            progress_tracker.update(len(data) // 2)  # 处理完成50%
            
            # 写入结果
            with open(output_path, 'wb') as f:
                f.write(processed_data)
            
            progress_tracker.complete()
            
            return {
                'success': True,
                'input_size': len(data),
                'output_size': len(processed_data),
                'method': 'direct'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _process_chunked_file(self, 
                             file_path: str, 
                             output_path: str,
                             processor_func: Callable,
                             progress_tracker: ProgressTracker) -> Dict[str, Any]:
        """分块处理大文件"""
        try:
            total_input_size = 0
            total_output_size = 0
            chunk_count = 0
            
            with open(file_path, 'rb') as input_file, open(output_path, 'wb') as output_file:
                
                while True:
                    # 检查内存使用情况
                    if not self.memory_manager.check_memory_available(self.chunk_size):
                        self.logger.warning("内存不足，等待垃圾回收...")
                        self.memory_manager.force_garbage_collection()
                        time.sleep(0.1)
                    
                    # 读取数据块
                    chunk = input_file.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    chunk_count += 1
                    total_input_size += len(chunk)
                    
                    # 处理数据块
                    processed_chunk = processor_func(chunk)
                    total_output_size += len(processed_chunk)
                    
                    # 写入处理后的数据
                    output_file.write(processed_chunk)
                    
                    # 更新进度
                    progress_tracker.update(len(chunk))
                    
                    # 释放内存
                    del chunk, processed_chunk
            
            progress_tracker.complete()
            
            return {
                'success': True,
                'input_size': total_input_size,
                'output_size': total_output_size,
                'chunk_count': chunk_count,
                'method': 'chunked'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def process_parallel_chunks(self, 
                               file_path: str, 
                               output_path: str,
                               processor_func: Callable,
                               progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        并行处理文件块
        
        Args:
            file_path: 输入文件路径
            output_path: 输出文件路径
            processor_func: 处理函数
            progress_callback: 进度回调函数
            
        Returns:
            处理结果
        """
        try:
            start_time = time.time()
            
            # 获取文件信息
            file_size = self.file_utils.get_file_size(file_path)
            
            if file_size <= self.chunk_size:
                # 小文件不需要并行处理
                return self.process_large_file(file_path, output_path, processor_func, progress_callback)
            
            self.logger.info(f"开始并行处理大文件: {file_path}")
            
            # 创建进度跟踪器
            progress_tracker = ProgressTracker(file_size, progress_callback)
            
            # 分割文件为块
            chunks_info = self._split_file_info(file_path, file_size)
            
            # 并行处理块
            processed_chunks = self._process_chunks_parallel(file_path, chunks_info, processor_func, progress_tracker)
            
            # 合并结果
            result = self._merge_processed_chunks(processed_chunks, output_path)
            
            end_time = time.time()
            result['processing_time'] = end_time - start_time
            result['throughput'] = file_size / (end_time - start_time) if end_time > start_time else 0
            result['parallel_workers'] = self.max_workers
            
            progress_tracker.complete()
            
            self.logger.info(f"并行处理完成，耗时: {result['processing_time']:.2f}秒")
            
            return result
            
        except Exception as e:
            self.logger.error(f"并行处理失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _split_file_info(self, file_path: str, file_size: int) -> list:
        """分割文件信息"""
        chunks_info = []
        chunk_count = (file_size + self.chunk_size - 1) // self.chunk_size
        
        for i in range(chunk_count):
            start_pos = i * self.chunk_size
            end_pos = min(start_pos + self.chunk_size, file_size)
            
            chunks_info.append({
                'index': i,
                'start': start_pos,
                'end': end_pos,
                'size': end_pos - start_pos
            })
        
        return chunks_info
    
    def _process_chunks_parallel(self, 
                                file_path: str, 
                                chunks_info: list,
                                processor_func: Callable,
                                progress_tracker: ProgressTracker) -> list:
        """并行处理文件块"""
        processed_chunks = [None] * len(chunks_info)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_chunk = {
                executor.submit(self._process_single_chunk, file_path, chunk_info, processor_func): chunk_info
                for chunk_info in chunks_info
            }
            
            # 收集结果
            for future in as_completed(future_to_chunk):
                chunk_info = future_to_chunk[future]
                try:
                    processed_data = future.result()
                    processed_chunks[chunk_info['index']] = {
                        'index': chunk_info['index'],
                        'data': processed_data,
                        'size': len(processed_data)
                    }
                    
                    # 更新进度
                    progress_tracker.update(chunk_info['size'])
                    
                except Exception as e:
                    self.logger.error(f"处理块 {chunk_info['index']} 失败: {e}")
                    raise
        
        return processed_chunks
    
    def _process_single_chunk(self, file_path: str, chunk_info: Dict, processor_func: Callable) -> bytes:
        """处理单个文件块"""
        with open(file_path, 'rb') as f:
            f.seek(chunk_info['start'])
            chunk_data = f.read(chunk_info['size'])
        
        # 处理数据
        processed_data = processor_func(chunk_data)
        
        return processed_data
    
    def _merge_processed_chunks(self, processed_chunks: list, output_path: str) -> Dict[str, Any]:
        """合并处理后的块"""
        try:
            total_output_size = 0
            
            with open(output_path, 'wb') as output_file:
                for chunk in processed_chunks:
                    if chunk is None:
                        raise Exception("存在未处理的块")
                    
                    output_file.write(chunk['data'])
                    total_output_size += chunk['size']
            
            return {
                'success': True,
                'output_size': total_output_size,
                'chunk_count': len(processed_chunks),
                'method': 'parallel'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stream_process_file(self, 
                           file_path: str, 
                           output_path: str,
                           processor_func: Callable,
                           progress_callback: Optional[Callable] = None) -> Generator[Dict[str, Any], None, None]:
        """
        流式处理文件
        
        Args:
            file_path: 输入文件路径
            output_path: 输出文件路径
            processor_func: 处理函数
            progress_callback: 进度回调函数
            
        Yields:
            处理进度信息
        """
        try:
            file_size = self.file_utils.get_file_size(file_path)
            progress_tracker = ProgressTracker(file_size, progress_callback)
            
            processed_size = 0
            
            with open(file_path, 'rb') as input_file, open(output_path, 'wb') as output_file:
                
                while True:
                    chunk = input_file.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    # 处理数据块
                    processed_chunk = processor_func(chunk)
                    output_file.write(processed_chunk)
                    
                    processed_size += len(chunk)
                    progress_tracker.update(len(chunk))
                    
                    # 生成进度信息
                    yield {
                        'processed_size': processed_size,
                        'total_size': file_size,
                        'progress': (processed_size / file_size) * 100 if file_size > 0 else 100,
                        'chunk_size': len(chunk)
                    }
            
            progress_tracker.complete()
            
            yield {
                'completed': True,
                'total_processed': processed_size
            }
            
        except Exception as e:
            self.logger.error(f"流式处理失败: {e}")
            yield {'error': str(e)}
    
    def set_chunk_size(self, chunk_size: int):
        """设置块大小"""
        if chunk_size <= 0:
            raise ValueError("块大小必须大于0")
        
        self.chunk_size = chunk_size
        self.logger.info(f"块大小设置为: {self.file_utils.format_size(chunk_size)}")
    
    def set_max_workers(self, max_workers: int):
        """设置最大工作线程数"""
        if max_workers <= 0:
            raise ValueError("工作线程数必须大于0")
        
        self.max_workers = min(max_workers, os.cpu_count() or 1)
        self.logger.info(f"最大工作线程数设置为: {self.max_workers}")
    
    def get_optimal_chunk_size(self, file_size: int, available_memory: int) -> int:
        """
        获取最优块大小
        
        Args:
            file_size: 文件大小
            available_memory: 可用内存
            
        Returns:
            最优块大小
        """
        # 基于可用内存和文件大小计算最优块大小
        max_chunk_size = available_memory // 4  # 使用1/4的可用内存
        min_chunk_size = 1024 * 1024  # 最小1MB
        
        if file_size <= max_chunk_size:
            return file_size
        
        # 计算合适的块数量
        optimal_chunks = min(16, self.max_workers * 4)
        optimal_chunk_size = file_size // optimal_chunks
        
        # 限制在合理范围内
        optimal_chunk_size = max(min_chunk_size, min(optimal_chunk_size, max_chunk_size))
        
        return optimal_chunk_size
