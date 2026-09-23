#!/usr/bin/env python3
"""
全局线程管理器

统一管理jiami项目中所有的多线程配置，确保GUI设置优先级最高
"""

import multiprocessing
from typing import Optional, Dict, Any
from enum import Enum

from ..utils.logger import Logger


class ThreadPriority(Enum):
    """线程配置优先级"""
    SYSTEM_DEFAULT = 1      # 系统默认
    CONFIG_FILE = 2         # 配置文件
    ALGORITHM_RECOMMEND = 3 # 算法推荐
    USER_SETTING = 4        # 用户设置
    GUI_OVERRIDE = 5        # GUI强制覆盖


class GlobalThreadManager:
    """全局线程管理器"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.logger = Logger("ThreadManager")

        # 系统信息
        self.cpu_count = multiprocessing.cpu_count()

        # 配置存储（按优先级）
        self.thread_configs = {}

        # 当前生效的配置
        self.active_config = {
            'max_threads': self.cpu_count,
            'enable_threading': True,
            'parallel_threshold': 512 * 1024,  # 512KB
            'chunk_size_base': 1024 * 1024,    # 1MB
            'priority': ThreadPriority.SYSTEM_DEFAULT,
            'source': 'system_default'
        }

        self._initialized = True
        self.logger.info(f"全局线程管理器初始化 - CPU核心数: {self.cpu_count}")

    def set_config(self,
                   priority: ThreadPriority,
                   source: str,
                   max_threads: Optional[int] = None,
                   enable_threading: Optional[bool] = None,
                   parallel_threshold: Optional[int] = None,
                   chunk_size_base: Optional[int] = None) -> None:
        """
        设置线程配置

        Args:
            priority: 配置优先级
            source: 配置来源
            max_threads: 最大线程数
            enable_threading: 是否启用多线程
            parallel_threshold: 并行阈值（字节）
            chunk_size_base: 基础块大小（字节）
        """
        config = {
            'priority': priority,
            'source': source
        }

        if max_threads is not None:
            config['max_threads'] = min(max_threads, self.cpu_count * 2)

        if enable_threading is not None:
            config['enable_threading'] = enable_threading

        if parallel_threshold is not None:
            config['parallel_threshold'] = parallel_threshold

        if chunk_size_base is not None:
            config['chunk_size_base'] = chunk_size_base

        # 存储配置
        self.thread_configs[priority] = config

        # 更新生效配置
        self._update_active_config()

        self.logger.info(f"线程配置更新 - 来源: {source}, 优先级: {priority.name}, 线程数: {max_threads}")

    def _update_active_config(self) -> None:
        """更新当前生效的配置"""
        # 按优先级从高到低合并配置
        new_config = self.active_config.copy()

        for priority in sorted(ThreadPriority, key=lambda x: x.value, reverse=True):
            if priority in self.thread_configs:
                config = self.thread_configs[priority]
                for key, value in config.items():
                    if key != 'priority' and value is not None:
                        new_config[key] = value

                # 更新优先级和来源
                new_config['priority'] = priority
                new_config['source'] = config['source']
                break

        self.active_config = new_config

        self.logger.debug(f"生效配置更新 - 来源: {new_config['source']}, "
                         f"线程数: {new_config.get('max_threads')}, "
                         f"启用: {new_config.get('enable_threading')}")

    def get_config(self) -> Dict[str, Any]:
        """获取当前生效的配置"""
        return self.active_config.copy()

    def snapshot(self):
        """Independent settings for a task; never registers another singleton.

        Take the snapshot before starting concurrent tasks. Later configuration
        changes on either instance do not affect the other instance.
        """
        settings = object.__new__(type(self))
        settings.logger = self.logger
        settings.cpu_count = self.cpu_count
        settings.thread_configs = {p: dict(c) for p, c in self.thread_configs.items()}
        settings.active_config = dict(self.active_config)
        settings._initialized = True
        return settings

    def get_max_threads(self) -> int:
        """获取最大线程数"""
        return self.active_config.get('max_threads', self.cpu_count)

    def is_threading_enabled(self) -> bool:
        """是否启用多线程"""
        return self.active_config.get('enable_threading', True)

    def get_parallel_threshold(self) -> int:
        """获取并行阈值"""
        return self.active_config.get('parallel_threshold', 512 * 1024)

    def get_chunk_size_base(self) -> int:
        """获取基础块大小"""
        return self.active_config.get('chunk_size_base', 1024 * 1024)

    def get_optimal_thread_count(self, data_size: int, algorithm: str = "aes256") -> int:
        """
        获取最优线程数（考虑全局配置）

        Args:
            data_size: 数据大小
            algorithm: 算法名称

        Returns:
            最优线程数
        """
        if not self.is_threading_enabled() or data_size < self.get_parallel_threshold():
            return 1

        max_threads = self.get_max_threads()

        # 算法特性因子
        algorithm_factors = {
            'aes256': 1.0,
            'chacha20': 0.8,
            'salsa20': 0.8,
            'blowfish': 1.0,
            'twofish': 1.0,
            'rsa': 0.5,
            'custom': 0.6,
            'steganography': 0.4
        }

        factor = algorithm_factors.get(algorithm, 0.8)

        # 根据数据大小计算线程数
        if data_size < 1024 * 1024:  # < 1MB
            optimal_threads = min(4, max_threads)
        elif data_size < 10 * 1024 * 1024:  # < 10MB
            optimal_threads = min(8, max_threads)
        elif data_size < 100 * 1024 * 1024:  # < 100MB
            optimal_threads = min(12, max_threads)
        else:  # >= 100MB
            optimal_threads = max_threads

        result = max(1, int(optimal_threads * factor))

        # 但是不能超过全局设置的最大线程数
        return min(result, max_threads)

    def set_gui_config(self,
                       max_threads: Optional[int] = None,
                       enable_threading: Optional[bool] = None,
                       parallel_threshold_mb: Optional[float] = None) -> None:
        """
        设置GUI配置（最高优先级）

        Args:
            max_threads: 最大线程数
            enable_threading: 是否启用多线程
            parallel_threshold_mb: 并行阈值（MB）
        """
        parallel_threshold = None
        if parallel_threshold_mb is not None:
            parallel_threshold = int(parallel_threshold_mb * 1024 * 1024)

        self.set_config(
            priority=ThreadPriority.GUI_OVERRIDE,
            source='gui_user_setting',
            max_threads=max_threads,
            enable_threading=enable_threading,
            parallel_threshold=parallel_threshold
        )

    def set_config_file_config(self, config: Dict[str, Any]) -> None:
        """
        设置配置文件配置（只在没有更高优先级配置时生效）

        Args:
            config: 配置字典
        """
        # 检查是否有更高优先级的配置
        current_priority = self.active_config.get('priority', ThreadPriority.SYSTEM_DEFAULT)
        if current_priority.value > ThreadPriority.CONFIG_FILE.value:
            self.logger.debug(f"跳过配置文件设置，当前优先级更高: {current_priority.name}")
            return

        threading_config = config.get("threading", {})

        if threading_config.get("auto_threading", True):
            max_threads = threading_config.get("max_threads")
            parallel_threshold_mb = threading_config.get("parallel_threshold_mb")

            parallel_threshold = None
            if parallel_threshold_mb:
                parallel_threshold = int(parallel_threshold_mb * 1024 * 1024)

            self.set_config(
                priority=ThreadPriority.CONFIG_FILE,
                source=f'config_file_{config.get("name", "unknown")}',
                max_threads=max_threads,
                parallel_threshold=parallel_threshold
            )

    def set_algorithm_recommendation(self, algorithm: str, recommended_threads: int) -> None:
        """
        设置算法推荐配置

        Args:
            algorithm: 算法名称
            recommended_threads: 推荐线程数
        """
        self.set_config(
            priority=ThreadPriority.ALGORITHM_RECOMMEND,
            source=f'algorithm_{algorithm}',
            max_threads=recommended_threads
        )

    def clear_config(self, priority: ThreadPriority) -> None:
        """
        清除指定优先级的配置

        Args:
            priority: 优先级
        """
        if priority in self.thread_configs:
            del self.thread_configs[priority]
            self._update_active_config()
            self.logger.info(f"清除线程配置 - 优先级: {priority.name}")

    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        config = self.get_config()
        return {
            'cpu_count': self.cpu_count,
            'active_source': config.get('source'),
            'active_priority': config.get('priority').name if config.get('priority') else 'unknown',
            'max_threads': self.get_max_threads(),
            'threading_enabled': self.is_threading_enabled(),
            'parallel_threshold_mb': self.get_parallel_threshold() / (1024 * 1024),
            'chunk_size_mb': self.get_chunk_size_base() / (1024 * 1024),
            'config_count': len(self.thread_configs)
        }

    def reset_to_defaults(self) -> None:
        """重置为默认配置"""
        self.thread_configs.clear()
        self.active_config = {
            'max_threads': self.cpu_count,
            'enable_threading': True,
            'parallel_threshold': 512 * 1024,
            'chunk_size_base': 1024 * 1024,
            'priority': ThreadPriority.SYSTEM_DEFAULT,
            'source': 'system_default'
        }
        self.logger.info("线程配置已重置为默认值")


# 全局单例实例
thread_manager = GlobalThreadManager()
