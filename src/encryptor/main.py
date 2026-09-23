#!/usr/bin/env python3
"""
文件加密器主程序

这是加密系统的核心程序，负责：
1. 加密文件和文件夹
2. 生成包含密钥的解密器
3. 提供多种加密配置选项
4. 管理加密过程和状态
"""

import os
import sys
import json
import argparse
import logging
import copy
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .hybrid_engine import HybridEncryptionEngine
from src.package_format.cancellation import CancellationToken, OperationCancelled, checkpoint
from .key_injector import KeyInjector
from .file_processor import FileProcessor
from ..thread_pool.thread_manager import thread_manager, ThreadPriority
from ..utils.logger import Logger
from ..utils.file_utils import FileUtils
from ..utils.crypto_utils import CryptoUtils
from ..exceptions import (
    EncryptionError,
    ConfigurationError,
    ConfigNotFoundError,
)
from ..utils.config_manager import ConfigManager


class FileEncryptor:
    """文件加密器主类"""

    def __init__(self, config_dir: Optional[str] = None, max_threads: Optional[int] = None, *, thread_settings=None, resource_policy=None, resource_ledger=None):
        """
        初始化文件加密器

        Args:
            config_dir: 配置文件目录路径
            max_threads: 最大线程数
        """
        self.config_dir = config_dir or self._get_default_config_dir()
        self.logger = Logger("FileEncryptor")
        from src.resources.reservations import DEFAULT_LEDGER, ReservationLedger
        if resource_policy is not None and resource_ledger is not None:
            raise ValueError('Supply resource_policy or resource_ledger, not both')
        self.resource_ledger = (resource_ledger if resource_ledger is not None else
                                ReservationLedger(resource_policy) if resource_policy is not None else DEFAULT_LEDGER)

        # 初始化全局线程管理器
        self.thread_manager = thread_settings if thread_settings is not None else thread_manager

        # 如果指定了线程数，设置为用户配置
        if max_threads is not None:
            self.thread_manager.set_config(
                priority=ThreadPriority.USER_SETTING,
                source='file_encryptor_init',
                max_threads=max_threads
            )

        # 初始化组件
        self.hybrid_engine = HybridEncryptionEngine(thread_settings=self.thread_manager)
        self.key_injector = KeyInjector()
        self.file_processor = FileProcessor()

        # 初始化配置管理器
        self.config_manager = ConfigManager(self.config_dir)
        
        # 加载配置
        self.encryption_profiles = self._load_encryption_profiles()
        self.security_settings = self._load_security_settings()

        # 应用性能配置
        self._apply_performance_settings()

        self.logger.info("文件加密器初始化完成")

    def _apply_performance_settings(self):
        """应用性能配置设置"""
        try:
            perf_settings = self.security_settings.get("security_settings", {}).get("performance", {})
            threading_config = perf_settings.get("threading", {})

            # 配置多线程参数（通过全局线程管理器）
            max_threads = threading_config.get("max_threads")
            if max_threads:
                self.thread_manager.set_config(
                    priority=ThreadPriority.CONFIG_FILE,
                    source='security_settings_performance',
                    max_threads=max_threads
                )

            # 配置内存设置
            memory_config = perf_settings.get("memory", {})
            buffer_size = memory_config.get("buffer_size_mb", 64) * 1024 * 1024

            # 更新并行处理阈值
            self.hybrid_engine.configure_threading(
                parallel_threshold=buffer_size // 4,  # 缓冲区的1/4作为阈值
                chunk_size_base=buffer_size // 16     # 缓冲区的1/16作为基础块大小
            )

            config = self.thread_manager.get_config()
            self.logger.info(f"性能配置已应用 - 线程数: {config.get('max_threads')}, 来源: {config.get('source')}")

        except Exception as e:
            self.logger.warning(f"应用性能配置失败: {e}")

    def configure_threading(self,
                           max_threads: Optional[int] = None,
                           enable_threading: bool = True,
                           parallel_threshold_mb: Optional[int] = None) -> None:
        """
        配置多线程参数（通过全局线程管理器）

        Args:
            max_threads: 最大线程数
            enable_threading: 是否启用多线程
            parallel_threshold_mb: 并行处理阈值（MB）
        """
        parallel_threshold = None
        if parallel_threshold_mb is not None:
            parallel_threshold = int(parallel_threshold_mb * 1024 * 1024)

        # 通过全局线程管理器设置配置（用户设置优先级）
        self.thread_manager.set_config(
            priority=ThreadPriority.USER_SETTING,
            source='file_encryptor_configure',
            max_threads=max_threads,
            enable_threading=enable_threading,
            parallel_threshold=parallel_threshold
        )

        config = self.thread_manager.get_config()
        self.logger.info(f"多线程配置更新 - 线程数: {config.get('max_threads')}, "
                        f"启用: {config.get('enable_threading')}, 来源: {config.get('source')}")

    def get_performance_info(self) -> Dict:
        """获取性能信息"""
        engine_stats = self.hybrid_engine.get_performance_stats()
        status_info = self.thread_manager.get_status_info()

        return {
            'cpu_cores': status_info['cpu_count'],
            'max_threads': status_info['max_threads'],
            'threading_enabled': status_info['threading_enabled'],
            'parallel_threshold_mb': status_info['parallel_threshold_mb'],
            'chunk_size_kb': status_info['chunk_size_mb'] * 1024,
            'thread_pool_active': engine_stats['thread_pool_active'],
            'config_source': status_info['active_source'],
            'config_priority': status_info['active_priority']
        }

    def _get_default_config_dir(self) -> str:
        """获取默认配置目录"""
        return str(Path(__file__).parent.parent.parent / "config")

    def _load_encryption_profiles(self) -> Dict:
        """加载加密配置文件（使用ConfigManager）"""
        try:
            return self.config_manager.load_config("encryption_profiles")
        except ConfigNotFoundError:
            self.logger.warning("加密配置文件不存在，使用默认配置")
            return self._get_default_profiles()
        except Exception as e:
            self.logger.error(f"加载加密配置失败: {e}")
            return self._get_default_profiles()

    def _load_security_settings(self) -> Dict:
        """加载安全设置（使用ConfigManager）"""
        try:
            return self.config_manager.load_config("security_settings")
        except ConfigNotFoundError:
            self.logger.warning("安全设置文件不存在，使用默认配置")
            return self._get_default_security_settings()
        except Exception as e:
            self.logger.error(f"加载安全设置失败: {e}")
            return self._get_default_security_settings()

    def _get_default_profiles(self) -> Dict:
        """获取默认加密配置"""
        return {
            "encryption_profiles": {
                "basic": {
                    "name": "基础加密",
                    "security_level": 1,
                    "layers": [{"method": "aes256", "mode": "GCM"}]
                }
            }
        }

    def _get_default_security_settings(self) -> Dict:
        """获取默认安全设置"""
        return {
            "security_settings": {
                "key_management": {"key_generation": {"source": "os.urandom"}}
            }
        }

    def encrypt_file(self, file_path, output_dir, profile='standard', custom_config=None, *, cancellation=None):
        return self._encrypt_path(file_path, output_dir, profile, custom_config, 'file', cancellation=cancellation)

    def encrypt_folder(self, folder_path, output_dir, profile='standard', custom_config=None, exclude_patterns=None, *, cancellation=None):
        return self._encrypt_path(folder_path, output_dir, profile, custom_config, 'folder', exclude_patterns, cancellation=cancellation)

    def _encrypt_path(self, input_path, output_dir, profile, custom_config, kind, exclude_patterns=None, *, cancellation=None):
        from src.package_format.writer import write_package
        cancellation = cancellation or CancellationToken()
        original_settings = self.hybrid_engine.thread_manager
        try:
            checkpoint(cancellation)
            path = Path(input_path)
            if not (path.is_file() if kind == 'file' else path.is_dir()):
                raise FileNotFoundError(input_path)
            if kind == 'folder' and Path(output_dir).resolve().is_relative_to(path.resolve()):
                raise ValueError('Output must be outside the input folder')
            config = copy.deepcopy(custom_config or self._get_encryption_config(profile))
            if custom_config is None:
                # Keep admission/execution topology stable if another component
                # changes the shared GUI/default settings during this operation.
                self.hybrid_engine.thread_manager = original_settings.snapshot()
            folder_plan = None
            if kind == 'folder':
                from src.package_format.archive import plan_folder
                folder_plan = plan_folder(path, exclude_patterns or [], cancellation=cancellation)
                size = folder_plan.archive_size
            else:
                size = path.stat().st_size
            estimate = self.hybrid_engine.estimate_admission(size, config, profile=profile,
                                                            custom=custom_config is not None)
            if not estimate.guaranteed:
                self.logger.warning(estimate.reason + '; using existing post-hoc validation')
            # Entry metadata has its own allocation cost, beyond archived bytes.
            extra = len(folder_plan.entries) * 4096 if folder_plan is not None else 0
            with self.resource_ledger.reserve(estimate, extra_bytes=extra, cancellation=cancellation):
                if kind == 'file':
                    data = self.file_processor.read_file(path, expected_size=size if estimate.guaranteed else None, cancellation=cancellation)
                else:
                    data = self.file_processor.process_folder(path, exclude_patterns or [], plan=folder_plan, cancellation=cancellation)
                encrypted = self.hybrid_engine.encrypt_data(data, config, admission=estimate, cancellation=cancellation)
                if estimate.guaranteed and len(encrypted['encrypted_data']) != estimate.output_size:
                    raise ValueError('Produced size differs from admitted plan; output was not published')
                destination = Path(output_dir) / (path.name + '.jiami')
                publication = write_package(encrypted, data, destination, profile=profile, original_name=path.name, kind=kind, cancellation=cancellation)
                return {'success': True, 'package_dir': str(publication.path),
                        'encrypted_file': str(publication.path/'data.jmi'),
                        'recovery_file': str(publication.path/'recovery.jmis'),
                        'decryptor_file': str(publication.path/'recover.py'),
                        'original_size': len(data), 'encrypted_size': len(encrypted['encrypted_data']),
                        'compression_ratio': len(encrypted['encrypted_data'])/len(data) if data else 0,
                        'encryption_time': encrypted.get('duration', 0), 'profile_used': profile,
                        'backend_used': 'cpu', 'publication_state': 'published', 'durability': publication.durability,
                        'warning': '\n'.join(filter(None, (publication.warning, cancellation.completion_warning()))), 'admission': estimate.summary()}
        except Exception as exc:
            self.logger.error('Encryption failed: ' + str(exc))
            return {'success': False, 'cancelled': isinstance(exc, OperationCancelled), 'error': str(exc), 'error_code': getattr(exc, 'error_code', 'ENC000'),
                    'file_path': str(input_path), 'details': getattr(exc, '__notes__', [])}
        finally:
            self.hybrid_engine.thread_manager = original_settings

    def _get_encryption_config(self, profile: str) -> Dict:
        """获取加密配置"""
        profiles = self.encryption_profiles.get("encryption_profiles", {})
        if profile not in profiles:
            raise ValueError("Unknown encryption profile: " + profile)

        config = profiles.get(profile, profiles.get("basic", {}))

        # 应用配置文件中的多线程设置
        self._apply_profile_threading_config(config)

        return config

    def _apply_profile_threading_config(self, config: Dict) -> None:
        """应用配置文件中的多线程设置（通过全局线程管理器）"""
        # 通过全局线程管理器设置配置文件配置
        self.thread_manager.set_config_file_config(config)

        # 记录应用的配置
        threading_config = config.get("threading", {})
        if threading_config.get("auto_threading", True):
            max_threads = threading_config.get("max_threads")
            parallel_threshold_mb = threading_config.get("parallel_threshold_mb")

            self.logger.debug(f"应用配置文件多线程设置 - 线程数: {max_threads}, 阈值: {parallel_threshold_mb}MB")

    def list_profiles(self) -> List[str]:
        """列出可用的加密配置文件"""
        return list(self.encryption_profiles.get("encryption_profiles", {}).keys())

    def get_profile_info(self, profile: str) -> Dict:
        """获取配置文件信息"""
        profiles = self.encryption_profiles.get("encryption_profiles", {})
        return profiles.get(profile, {})


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="文件加密器")
    parser.add_argument("input", help="要加密的文件或文件夹路径")
    parser.add_argument("-o", "--output", required=True, help="输出目录")
    parser.add_argument("-p", "--profile", default="standard", help="加密配置文件")
    parser.add_argument("--list-profiles", action="store_true", help="列出可用的配置文件")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # 创建加密器
    encryptor = FileEncryptor()

    # 列出配置文件
    if args.list_profiles:
        profiles = encryptor.list_profiles()
        print("可用的加密配置文件:")
        for profile in profiles:
            info = encryptor.get_profile_info(profile)
            print(f"  {profile}: {info.get('description', '无描述')}")
        return

    # 执行加密
    if os.path.isfile(args.input):
        result = encryptor.encrypt_file(args.input, args.output, args.profile)
    elif os.path.isdir(args.input):
        result = encryptor.encrypt_folder(args.input, args.output, args.profile)
    else:
        print(f"错误: 路径不存在 {args.input}")
        return

    # 输出结果
    if result['success']:
        print(f"✅ 加密成功!")
        print(f"📁 加密文件: {result['encrypted_file']}")
        print(f"🔑 解密器: {result['decryptor_file']}")
        print(f"📊 压缩比: {result['compression_ratio']:.2%}")
        print(f"⏱️  耗时: {result['encryption_time']:.2f}秒")
    else:
        print(f"❌ 加密失败: {result['error']}")


if __name__ == "__main__":
    main()
