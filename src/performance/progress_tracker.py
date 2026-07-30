"""
进度跟踪器

提供详细的进度跟踪和显示功能。
"""

import time
import threading
from typing import Optional, Callable, Dict, Any

from ..utils.logger import Logger


class ProgressTracker:
    """进度跟踪器类"""
    
    def __init__(self, 
                 total_size: int, 
                 callback: Optional[Callable] = None,
                 update_interval: float = 0.1):
        """
        初始化进度跟踪器
        
        Args:
            total_size: 总大小
            callback: 进度回调函数
            update_interval: 更新间隔（秒）
        """
        self.logger = Logger("ProgressTracker")
        self.total_size = total_size
        self.callback = callback
        self.update_interval = update_interval
        
        self.processed_size = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_processed_size = 0
        
        self.lock = threading.Lock()
        self.completed = False
        
        # 统计信息
        self.update_count = 0
        self.speed_history = []
        self.max_speed = 0
        self.min_speed = float('inf')
        
    def update(self, processed_bytes: int):
        """
        更新进度
        
        Args:
            processed_bytes: 已处理的字节数
        """
        with self.lock:
            self.processed_size += processed_bytes
            self.update_count += 1
            
            current_time = time.time()
            
            # 检查是否需要更新
            if current_time - self.last_update_time >= self.update_interval:
                self._do_update(current_time)
                self.last_update_time = current_time
    
    def _do_update(self, current_time: float):
        """执行更新"""
        # 计算进度
        progress_percent = (self.processed_size / self.total_size) * 100 if self.total_size > 0 else 100
        
        # 计算速度
        time_diff = current_time - self.last_update_time
        size_diff = self.processed_size - self.last_processed_size
        
        current_speed = size_diff / time_diff if time_diff > 0 else 0
        
        # 更新速度统计
        if current_speed > 0:
            self.speed_history.append(current_speed)
            if len(self.speed_history) > 10:  # 保留最近10次的速度
                self.speed_history.pop(0)
            
            self.max_speed = max(self.max_speed, current_speed)
            self.min_speed = min(self.min_speed, current_speed)
        
        # 计算平均速度
        avg_speed = sum(self.speed_history) / len(self.speed_history) if self.speed_history else 0
        
        # 计算剩余时间
        remaining_size = self.total_size - self.processed_size
        eta = remaining_size / avg_speed if avg_speed > 0 else 0
        
        # 计算总耗时
        elapsed_time = current_time - self.start_time
        
        # 构建进度信息
        progress_info = {
            'processed_size': self.processed_size,
            'total_size': self.total_size,
            'progress_percent': progress_percent,
            'current_speed': current_speed,
            'average_speed': avg_speed,
            'max_speed': self.max_speed,
            'min_speed': self.min_speed if self.min_speed != float('inf') else 0,
            'elapsed_time': elapsed_time,
            'eta': eta,
            'update_count': self.update_count
        }
        
        # 调用回调函数
        if self.callback:
            try:
                self.callback(progress_info)
            except Exception as e:
                self.logger.error(f"进度回调函数执行失败: {e}")
        
        # 更新上次处理大小
        self.last_processed_size = self.processed_size
    
    def complete(self):
        """标记完成"""
        with self.lock:
            if self.completed:
                return
            
            self.completed = True
            self.processed_size = self.total_size
            
            # 最终更新
            current_time = time.time()
            total_time = current_time - self.start_time
            avg_speed = self.total_size / total_time if total_time > 0 else 0
            
            final_info = {
                'processed_size': self.total_size,
                'total_size': self.total_size,
                'progress_percent': 100.0,
                'current_speed': 0,
                'average_speed': avg_speed,
                'max_speed': self.max_speed,
                'min_speed': self.min_speed if self.min_speed != float('inf') else 0,
                'elapsed_time': total_time,
                'eta': 0,
                'update_count': self.update_count,
                'completed': True
            }
            
            if self.callback:
                try:
                    self.callback(final_info)
                except Exception as e:
                    self.logger.error(f"完成回调函数执行失败: {e}")
    
    def get_progress_info(self) -> Dict[str, Any]:
        """获取当前进度信息"""
        with self.lock:
            current_time = time.time()
            elapsed_time = current_time - self.start_time
            
            progress_percent = (self.processed_size / self.total_size) * 100 if self.total_size > 0 else 100
            avg_speed = self.processed_size / elapsed_time if elapsed_time > 0 else 0
            
            remaining_size = self.total_size - self.processed_size
            eta = remaining_size / avg_speed if avg_speed > 0 else 0
            
            return {
                'processed_size': self.processed_size,
                'total_size': self.total_size,
                'progress_percent': progress_percent,
                'average_speed': avg_speed,
                'max_speed': self.max_speed,
                'min_speed': self.min_speed if self.min_speed != float('inf') else 0,
                'elapsed_time': elapsed_time,
                'eta': eta,
                'update_count': self.update_count,
                'completed': self.completed
            }
    
    def reset(self, new_total_size: Optional[int] = None):
        """
        重置进度跟踪器
        
        Args:
            new_total_size: 新的总大小（可选）
        """
        with self.lock:
            if new_total_size is not None:
                self.total_size = new_total_size
            
            self.processed_size = 0
            self.start_time = time.time()
            self.last_update_time = self.start_time
            self.last_processed_size = 0
            self.completed = False
            
            self.update_count = 0
            self.speed_history.clear()
            self.max_speed = 0
            self.min_speed = float('inf')
    
    def format_progress_bar(self, width: int = 50) -> str:
        """
        格式化进度条
        
        Args:
            width: 进度条宽度
            
        Returns:
            格式化的进度条字符串
        """
        progress_info = self.get_progress_info()
        
        # 计算进度条
        progress_percent = progress_info['progress_percent']
        filled_width = int(width * progress_percent / 100)
        bar = '█' * filled_width + '░' * (width - filled_width)
        
        # 格式化大小
        processed_str = self._format_bytes(progress_info['processed_size'])
        total_str = self._format_bytes(progress_info['total_size'])
        
        # 格式化速度
        speed_str = self._format_bytes(progress_info['average_speed']) + '/s'
        
        # 格式化时间
        elapsed_str = self._format_time(progress_info['elapsed_time'])
        eta_str = self._format_time(progress_info['eta'])
        
        return (f"|{bar}| {progress_percent:.1f}% "
                f"({processed_str}/{total_str}) "
                f"[{speed_str}, {elapsed_str}<{eta_str}]")
    
    def _format_bytes(self, bytes_value: float) -> str:
        """格式化字节数"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f}PB"
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m{secs:02d}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h{minutes:02d}m"


class ConsoleProgressTracker(ProgressTracker):
    """控制台进度跟踪器"""
    
    def __init__(self, total_size: int, description: str = "处理中"):
        """
        初始化控制台进度跟踪器
        
        Args:
            total_size: 总大小
            description: 描述文本
        """
        super().__init__(total_size, self._console_callback)
        self.description = description
        self.last_line_length = 0
    
    def _console_callback(self, progress_info: Dict[str, Any]):
        """控制台回调函数"""
        # 清除上一行
        if self.last_line_length > 0:
            print('\r' + ' ' * self.last_line_length + '\r', end='')
        
        # 构建进度行
        progress_bar = self.format_progress_bar(30)
        line = f"{self.description}: {progress_bar}"
        
        # 输出进度
        print(line, end='', flush=True)
        self.last_line_length = len(line)
        
        # 如果完成，换行
        if progress_info.get('completed', False):
            print()  # 换行
