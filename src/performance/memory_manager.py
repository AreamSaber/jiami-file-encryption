"""
内存管理器

监控和管理内存使用，防止内存溢出。
"""

import gc
import sys
import psutil
import threading
import time
from typing import Dict, Any, Optional

from ..utils.logger import Logger


class MemoryManager:
    """内存管理器类"""
    
    def __init__(self, max_memory_percent: float = 80.0):
        """
        初始化内存管理器
        
        Args:
            max_memory_percent: 最大内存使用百分比
        """
        self.logger = Logger("MemoryManager")
        self.max_memory_percent = max_memory_percent
        self.monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        # 获取系统内存信息
        self.total_memory = psutil.virtual_memory().total
        self.max_memory_bytes = int(self.total_memory * max_memory_percent / 100)
        
        self.logger.info(f"内存管理器初始化，最大使用: {self._format_bytes(self.max_memory_bytes)}")
    
    def get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        try:
            # 系统内存信息
            system_memory = psutil.virtual_memory()
            
            # 当前进程内存信息
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                'system': {
                    'total': system_memory.total,
                    'available': system_memory.available,
                    'used': system_memory.used,
                    'percent': system_memory.percent
                },
                'process': {
                    'rss': process_memory.rss,  # 物理内存
                    'vms': process_memory.vms,  # 虚拟内存
                    'percent': process.memory_percent()
                },
                'python': {
                    'objects': len(gc.get_objects()),
                    'garbage': len(gc.garbage)
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取内存信息失败: {e}")
            return {}
    
    def check_memory_available(self, required_bytes: int) -> bool:
        """
        检查是否有足够的可用内存
        
        Args:
            required_bytes: 需要的内存字节数
            
        Returns:
            是否有足够内存
        """
        try:
            memory_info = self.get_memory_info()
            
            if not memory_info:
                return True  # 如果无法获取信息，假设有足够内存
            
            # 检查系统可用内存
            available_memory = memory_info['system']['available']
            
            # 检查进程内存使用
            process_memory = memory_info['process']['rss']
            
            # 预测使用后的内存
            predicted_memory = process_memory + required_bytes
            
            # 检查是否超过限制
            if predicted_memory > self.max_memory_bytes:
                self.logger.warning(f"内存不足: 需要 {self._format_bytes(required_bytes)}, "
                                  f"当前使用 {self._format_bytes(process_memory)}, "
                                  f"限制 {self._format_bytes(self.max_memory_bytes)}")
                return False
            
            # 检查系统可用内存
            if required_bytes > available_memory * 0.8:  # 保留20%缓冲
                self.logger.warning(f"系统内存不足: 需要 {self._format_bytes(required_bytes)}, "
                                  f"可用 {self._format_bytes(available_memory)}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"检查内存失败: {e}")
            return True  # 出错时假设有足够内存
    
    def force_garbage_collection(self):
        """强制垃圾回收"""
        try:
            before_objects = len(gc.get_objects())
            
            # 执行垃圾回收
            collected = gc.collect()
            
            after_objects = len(gc.get_objects())
            
            self.logger.debug(f"垃圾回收完成: 回收 {collected} 个对象, "
                            f"对象数量从 {before_objects} 减少到 {after_objects}")
            
        except Exception as e:
            self.logger.error(f"垃圾回收失败: {e}")
    
    def start_monitoring(self, interval: float = 5.0):
        """
        开始内存监控
        
        Args:
            interval: 监控间隔（秒）
        """
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_memory,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        
        self.logger.info(f"开始内存监控，间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止内存监控"""
        self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        
        self.logger.info("内存监控已停止")
    
    def _monitor_memory(self, interval: float):
        """内存监控线程"""
        while self.monitoring:
            try:
                memory_info = self.get_memory_info()
                
                if memory_info:
                    # 检查内存使用情况
                    system_percent = memory_info['system']['percent']
                    process_percent = memory_info['process']['percent']
                    
                    # 记录内存使用情况
                    if system_percent > 90:
                        self.logger.warning(f"系统内存使用过高: {system_percent:.1f}%")
                    
                    if process_percent > 50:
                        self.logger.warning(f"进程内存使用过高: {process_percent:.1f}%")
                    
                    # 如果内存使用过高，执行垃圾回收
                    if system_percent > 85 or process_percent > 40:
                        self.force_garbage_collection()
                
                time.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"内存监控错误: {e}")
                time.sleep(interval)
    
    def optimize_memory_usage(self):
        """优化内存使用"""
        try:
            self.logger.info("开始内存优化...")
            
            # 强制垃圾回收
            self.force_garbage_collection()
            
            # 清理Python内部缓存
            if hasattr(sys, 'intern'):
                # 清理字符串缓存（Python 2/3兼容）
                pass
            
            # 设置垃圾回收阈值
            gc.set_threshold(700, 10, 10)
            
            self.logger.info("内存优化完成")
            
        except Exception as e:
            self.logger.error(f"内存优化失败: {e}")
    
    def get_memory_usage_report(self) -> str:
        """获取内存使用报告"""
        try:
            memory_info = self.get_memory_info()
            
            if not memory_info:
                return "无法获取内存信息"
            
            report = []
            report.append("📊 内存使用报告")
            report.append("=" * 40)
            
            # 系统内存
            system = memory_info['system']
            report.append("🖥️  系统内存:")
            report.append(f"  总内存: {self._format_bytes(system['total'])}")
            report.append(f"  已使用: {self._format_bytes(system['used'])} ({system['percent']:.1f}%)")
            report.append(f"  可用: {self._format_bytes(system['available'])}")
            
            # 进程内存
            process = memory_info['process']
            report.append("\n🔧 进程内存:")
            report.append(f"  物理内存: {self._format_bytes(process['rss'])}")
            report.append(f"  虚拟内存: {self._format_bytes(process['vms'])}")
            report.append(f"  使用百分比: {process['percent']:.1f}%")
            
            # Python对象
            python = memory_info['python']
            report.append("\n🐍 Python对象:")
            report.append(f"  对象数量: {python['objects']:,}")
            report.append(f"  垃圾对象: {python['garbage']}")
            
            # 内存限制
            report.append("\n⚙️  内存限制:")
            report.append(f"  最大使用: {self._format_bytes(self.max_memory_bytes)}")
            report.append(f"  使用百分比: {self.max_memory_percent}%")
            
            return "\n".join(report)
            
        except Exception as e:
            return f"生成内存报告失败: {e}"
    
    def set_memory_limit(self, max_memory_percent: float):
        """
        设置内存使用限制
        
        Args:
            max_memory_percent: 最大内存使用百分比
        """
        if max_memory_percent <= 0 or max_memory_percent > 100:
            raise ValueError("内存使用百分比必须在0-100之间")
        
        with self.lock:
            self.max_memory_percent = max_memory_percent
            self.max_memory_bytes = int(self.total_memory * max_memory_percent / 100)
        
        self.logger.info(f"内存限制设置为: {max_memory_percent}% ({self._format_bytes(self.max_memory_bytes)})")
    
    def _format_bytes(self, bytes_value: int) -> str:
        """格式化字节数"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop_monitoring()
        
        # 清理内存
        self.optimize_memory_usage()
