"""
混合加密引擎

支持多种加密算法的组合使用，提供分层和并行加密功能。
"""

import os
import time
import json
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from ..utils.logger import Logger
from ..utils.crypto_utils import CryptoUtils
from ..thread_pool.thread_manager import thread_manager, ThreadPriority


class HybridEncryptionEngine:
    """混合加密引擎"""

    def __init__(self, max_threads: Optional[int] = None, *, thread_settings=None):
        """
        初始化混合加密引擎

        Args:
            max_threads: 最大线程数，None表示使用全局线程管理器
        """
        self.logger = Logger("HybridEngine")
        self.crypto_utils = CryptoUtils()

        # 使用全局线程管理器
        self.thread_manager = thread_settings if thread_settings is not None else thread_manager

        # 如果指定了线程数，设置为用户配置
        if max_threads is not None:
            self.thread_manager.set_config(
                priority=ThreadPriority.USER_SETTING,
                source='hybrid_engine_init',
                max_threads=max_threads
            )

        self.thread_pool = None

        # 支持的加密方法
        self.encryption_methods = {
            'aes256': self._encrypt_aes256,
            'chacha20': self._encrypt_chacha20,
            'salsa20': self._encrypt_salsa20,
            'blowfish': self._encrypt_blowfish,
            'twofish': self._encrypt_twofish,
            'rsa': self._encrypt_rsa,
            'custom': self._encrypt_custom,
            'steganography': self._encrypt_steganography
        }

        config = self.thread_manager.get_config()
        self.logger.info(f"混合加密引擎初始化完成 - CPU核心数: {self.thread_manager.cpu_count}, "
                        f"最大线程数: {config.get('max_threads')}, 配置来源: {config.get('source')}")

    def configure_threading(self,
                           max_threads: Optional[int] = None,
                           enable_threading: bool = True,
                           parallel_threshold: Optional[int] = None,
                           chunk_size_base: Optional[int] = None) -> None:
        """
        配置多线程参数（通过全局线程管理器）

        Args:
            max_threads: 最大线程数
            enable_threading: 是否启用多线程
            parallel_threshold: 并行处理阈值（字节）
            chunk_size_base: 基础块大小（字节）
        """
        # 通过全局线程管理器设置配置
        self.thread_manager.set_config(
            priority=ThreadPriority.USER_SETTING,
            source='hybrid_engine_configure',
            max_threads=max_threads,
            enable_threading=enable_threading,
            parallel_threshold=parallel_threshold,
            chunk_size_base=chunk_size_base
        )

        # 关闭现有线程池
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
            self.thread_pool = None

        config = self.thread_manager.get_config()
        self.logger.info(f"多线程配置更新 - 线程数: {config.get('max_threads')}, "
                        f"启用: {config.get('enable_threading')}, 来源: {config.get('source')}")

    def get_optimal_thread_count(self, data_size: int, algorithm: str = "aes256") -> int:
        """
        根据数据大小和算法获取最优线程数（使用全局线程管理器）

        Args:
            data_size: 数据大小（字节）
            algorithm: 算法名称

        Returns:
            最优线程数
        """
        # 使用全局线程管理器计算最优线程数
        optimal_threads = self.thread_manager.get_optimal_thread_count(data_size, algorithm)

        # 记录算法推荐（但不覆盖更高优先级的配置）
        current_config = self.thread_manager.get_config()
        if current_config.get('priority').value <= ThreadPriority.ALGORITHM_RECOMMEND.value:
            self.thread_manager.set_algorithm_recommendation(algorithm, optimal_threads)

        return optimal_threads

    def get_optimal_chunk_size(self, data_size: int, thread_count: int) -> int:
        """
        获取最优块大小（使用全局线程管理器配置）

        Args:
            data_size: 数据大小
            thread_count: 线程数

        Returns:
            最优块大小
        """
        if thread_count <= 1:
            return data_size

        # 从全局线程管理器获取基础块大小
        chunk_size_base = self.thread_manager.get_chunk_size_base()

        # 针对大文件优化的块大小计算
        if data_size >= 100 * 1024 * 1024:  # >= 100MB
            # 大文件使用更大的块，减少线程间开销
            base_chunk = 8 * 1024 * 1024  # 8MB块
        elif data_size >= 10 * 1024 * 1024:  # >= 10MB
            # 中等文件使用中等块大小
            base_chunk = 4 * 1024 * 1024  # 4MB块
        else:
            # 小文件使用配置的基础块大小
            base_chunk = chunk_size_base

        # 确保每个线程至少有2-3个块来保持忙碌
        min_chunk = data_size // (thread_count * 3)
        max_chunk = data_size // thread_count

        optimal_chunk = max(min_chunk, min(base_chunk, max_chunk))

        # 确保块大小合理，最小256KB
        return max(256 * 1024, optimal_chunk)

    def encrypt_data(self, data: bytes, config: Dict, progress_callback=None) -> Dict:
        """
        使用混合加密配置加密数据

        Args:
            data: 要加密的数据
            config: 加密配置
            progress_callback: 进度回调函数

        Returns:
            包含加密结果的字典
        """
        try:
            for layer in config.get('layers', []):
                if layer.get('method') == 'twofish':
                    __import__('src.crypto.twofish_backend')
                if layer.get('method') == 'salsa20':
                    __import__('nacl.secret')
            start_time = time.perf_counter()
            data_size = len(data)
            self.logger.info(f"开始混合加密，数据大小: {data_size} 字节")

            # 设置进度回调
            self.progress_callback = progress_callback
            if self.progress_callback:
                self.progress_callback(0, "开始加密...")

            # 智能选择加密策略
            encryption_strategy = self._choose_encryption_strategy(data, config)

            if self.progress_callback:
                self.progress_callback(10, f"使用策略: {encryption_strategy}")

            if encryption_strategy == 'parallel':
                result = self._parallel_encrypt(data, config)
            elif encryption_strategy == 'threaded_layered':
                result = self._threaded_layered_encrypt(data, config)
            else:
                result = self._layered_encrypt(data, config)

            # 计算耗时
            duration = time.perf_counter() - start_time
            result['duration'] = duration
            result['strategy_used'] = encryption_strategy

            if self.progress_callback:
                self.progress_callback(100, "加密完成")

            self.logger.info(f"混合加密完成，耗时: {duration:.2f}秒，策略: {encryption_strategy}")
            return result

        except Exception as e:
            self.logger.error(f"混合加密失败: {e}")
            raise

    def _choose_encryption_strategy(self, data: bytes, config: Dict) -> str:
        """
        选择最优的加密策略 - 更积极的并行策略

        Args:
            data: 数据
            config: 配置

        Returns:
            加密策略名称
        """
        data_size = len(data)
        layers = config.get('layers', [])

        # 强制指定策略
        forced_strategy = config.get('strategy')
        if forced_strategy in ['parallel', 'threaded_layered', 'layered']:
            return forced_strategy

        # 强制并行模式（向后兼容）
        if config.get('parallel', False):
            return 'parallel'

        # 禁用多线程
        if not self.thread_manager.is_threading_enabled():
            return 'layered'

        # 优化策略选择 - 考虑GPU效率
        num_layers = len(layers)

        # 对于GPU加速，大数据块使用单层处理更高效
        if data_size >= 50 * 1024 * 1024:
            if num_layers == 1:
                return 'parallel'  # 单层大数据，使用并行
            elif num_layers <= 3:
                return 'layered'   # 多层大数据，使用顺序处理
            else:
                return 'threaded_layered'  # 超多层，使用线程分层
        elif data_size >= self.thread_manager.get_parallel_threshold() and num_layers >= 2:
            return 'threaded_layered'
        else:
            return 'layered'

    def _threaded_layered_encrypt(self, data: bytes, config: Dict) -> Dict:
        """
        线程化分层加密 - 对大数据进行分块并行处理每一层
        """
        layers = config.get('layers', [])
        if not layers:
            raise ValueError("未指定加密层")

        data_size = len(data)
        encrypted_data = data
        metadata = []

        # 逐层加密
        for i, layer in enumerate(layers):
            method = layer.get('method')
            if method not in self.encryption_methods:
                raise ValueError(f"不支持的加密方法: {method}")

            self.logger.debug(f"应用第 {i+1} 层加密: {method} (线程化)")

            # 获取最优线程数
            thread_count = self.get_optimal_thread_count(len(encrypted_data), method)

            if thread_count > 1 and len(encrypted_data) > self.thread_manager.get_parallel_threshold():
                # 使用多线程处理
                encrypted_data, layer_metadata = self._encrypt_layer_threaded(
                    encrypted_data, layer, method, thread_count
                )
            else:
                # 单线程处理
                encrypted_data, layer_metadata = self._run_layer(encrypted_data, layer, method)

            # 保存元数据
            layer_metadata['layer_index'] = i
            layer_metadata['method'] = method
            layer_metadata['thread_count'] = thread_count
            metadata.append(layer_metadata)

        return {
            'encrypted_data': encrypted_data,
            'metadata': {
                'type': 'threaded_layered',
                'layers': metadata,
                'original_size': data_size,
                'encrypted_size': len(encrypted_data)
            }
        }

    def _encrypt_layer_threaded(self, data: bytes, layer: Dict, method: str, thread_count: int) -> tuple:
        """
        使用多线程加密单个层

        Args:
            data: 要加密的数据
            layer: 层配置
            method: 加密方法
            thread_count: 线程数

        Returns:
            (加密数据, 元数据)
        """
        data_size = len(data)
        chunk_size = self.get_optimal_chunk_size(data_size, thread_count)

        # 分割数据
        chunks = []
        for index, offset in enumerate(range(0, data_size, chunk_size)):
            chunk = data[offset:offset + chunk_size]
            chunks.append((index, chunk))

        # 创建线程池
        if not self.thread_pool:
            max_workers = self.thread_manager.get_max_threads()
            self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

        # 并行加密块
        encrypted_chunks = {}
        chunk_metadata = {}

        try:
            # 提交任务
            future_to_index = {}
            for index, chunk in chunks:
                future = self.thread_pool.submit(
                    self._encrypt_chunk_safe, chunk, layer, method
                )
                future_to_index[future] = index

            # 收集结果
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    encrypted_chunk, chunk_meta = future.result()
                    encrypted_chunks[index] = encrypted_chunk
                    chunk_metadata[index] = chunk_meta
                except Exception as e:
                    self.logger.error(f"加密块 {index} 失败: {e}")
                    raise

            # 重组数据 - 按索引顺序重组，确保数据完整性
            result_data = bytearray()
            combined_metadata = {'chunks': {}, 'thread_count': thread_count, 'input_size': len(data), 'output_size': sum(map(len, encrypted_chunks.values()))}

            # 按索引顺序重组数据
            sorted_indices = sorted(encrypted_chunks.keys())
            for index in sorted_indices:
                if index in encrypted_chunks:
                    result_data.extend(encrypted_chunks[index])
                    combined_metadata['chunks'][index] = chunk_metadata[index]
                    
                    # 从第一个chunk提取algorithm到顶层元数据
                    if 'algorithm' not in combined_metadata and 'algorithm' in chunk_metadata[index]:
                        combined_metadata['algorithm'] = chunk_metadata[index]['algorithm']
                else:
                    self.logger.error(f"缺失数据块: {index}")
                    raise ValueError(f"数据块 {index} 加密失败")

            # 验证数据完整性
            expected_chunks = len(chunks)
            actual_chunks = len(encrypted_chunks)
            if expected_chunks != actual_chunks:
                self.logger.error(f"数据块数量不匹配: 期望 {expected_chunks}, 实际 {actual_chunks}")
                raise ValueError("多线程加密数据完整性验证失败")

            self.logger.debug(f"多线程加密完成: {actual_chunks} 个数据块, 总大小: {len(result_data)} 字节")
            return bytes(result_data), combined_metadata

        except Exception as e:
            self.logger.error(f"多线程加密失败: {e}")
            # A failed chunk invalidates the attempt; never silently retry a new plan.
            raise

    def _run_layer(self, data, layer, method):
        options = {**layer, **layer.get('params', {})}
        if options.get('seed') == 'random':
            options['seed'] = int.from_bytes(os.urandom(8), 'big')
        if options.get('rotation') == 'random':
            options['rotation'] = os.urandom(1)[0]
        encrypted, metadata = self.encryption_methods[method](data, options)
        metadata.update(method=method, input_size=len(data), output_size=len(encrypted))
        return bytes(encrypted), metadata

    def _encrypt_chunk_safe(self, chunk: bytes, layer: Dict, method: str) -> tuple:
        """
        线程安全的块加密方法

        Args:
            chunk: 数据块
            layer: 层配置
            method: 加密方法

        Returns:
            (加密数据, 元数据)
        """
        try:
            return self._run_layer(chunk, layer, method)
        except Exception as e:
            self.logger.error(f"块加密失败: {e}")
            raise

    def _layered_encrypt(self, data: bytes, config: Dict) -> Dict:
        """分层加密 - 一层套一层"""
        layers = config.get('layers', [])
        if not layers:
            raise ValueError("未指定加密层")

        encrypted_data = data
        metadata = []

        # 逐层加密
        for i, layer in enumerate(layers):
            method = layer.get('method')
            if method not in self.encryption_methods:
                raise ValueError(f"不支持的加密方法: {method}")

            self.logger.debug(f"应用第 {i+1} 层加密: {method}")

            # 执行加密
            encrypted_data, layer_metadata = self._run_layer(encrypted_data, layer, method)

            # 保存元数据
            layer_metadata['layer_index'] = i
            layer_metadata['method'] = method
            metadata.append(layer_metadata)

        return {
            'encrypted_data': encrypted_data,
            'metadata': {
                'type': 'layered',
                'layers': metadata,
                'original_size': len(data),
                'encrypted_size': len(encrypted_data)
            }
        }

    def _parallel_encrypt(self, data: bytes, config: Dict) -> Dict:
        """
        并行加密 - 数据分片后用不同方法并行加密
        """
        layers = config.get('layers', [])
        chunk_count = config.get('chunk_count', len(layers))

        if not layers:
            raise ValueError("未指定加密层")

        # 优化分块策略 - 优先大块处理
        data_size = len(data)
        max_threads = self.thread_manager.get_max_threads()

        # 对于GPU加速，使用更大的块以提高效率
        min_gpu_chunk_size = 16 * 1024 * 1024  # 16MB最小GPU块

        if data_size >= min_gpu_chunk_size:
            # 大数据：使用较少的大块
            optimal_chunk_count = max(1, min(4, max_threads))
        else:
            # 小数据：使用传统分块
            optimal_chunk_count = max(1, min(chunk_count, max_threads, max(1, data_size)))

        # 数据分片
        chunk_size = data_size // optimal_chunk_count
        chunks = []

        for i in range(optimal_chunk_count):
            start = i * chunk_size
            if i == optimal_chunk_count - 1:  # 最后一片包含剩余数据
                end = data_size
            else:
                end = start + chunk_size

            chunks.append((i, data[start:end]))

        # 创建线程池
        if not self.thread_pool:
            max_workers = self.thread_manager.get_max_threads()
            self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

        # 并行加密每个分片
        encrypted_chunks = {}

        try:
            # 提交任务
            future_to_index = {}
            for i, chunk in chunks:
                layer = layers[i % len(layers)]  # 循环使用层配置
                future = self.thread_pool.submit(
                    self._encrypt_chunk_with_layer, chunk, layer, i
                )
                future_to_index[future] = i

            # 收集结果
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    encrypted_chunks[index] = result
                except Exception as e:
                    self.logger.error(f"加密分片 {index} 失败: {e}")
                    raise

            # 按顺序组合结果
            ordered_chunks = []
            chunks_dict = {}
            for i in range(optimal_chunk_count):
                if i in encrypted_chunks:
                    chunk = encrypted_chunks[i]
                    ordered_chunks.append(chunk)
                    chunks_dict[i] = chunk

            return {
                'encrypted_data': self._combine_chunks(ordered_chunks),
                'metadata': {
                    'type': 'parallel',
                    'chunks': chunks_dict,  # 使用字典格式，解密器期望的格式
                    'chunk_count': optimal_chunk_count,
                    'original_size': data_size,
                    'thread_count': max_threads
                }
            }

        except Exception as e:
            self.logger.error(f"并行加密失败: {e}")
            # Never silently change parallel-chunk topology after an error.
            raise

    def _encrypt_chunk_with_layer(self, chunk: bytes, layer: Dict, index: int) -> Dict:
        """
        使用指定层配置加密数据块

        Args:
            chunk: 数据块
            layer: 层配置
            index: 块索引

        Returns:
            加密结果字典
        """
        method = layer.get('method')
        if method not in self.encryption_methods:
            raise ValueError(f"不支持的加密方法: {method}")

        self.logger.debug(f"加密分片 {index+1}: {method}")

        encrypted_chunk, chunk_metadata = self._run_layer(chunk, layer, method)

        return {
            'index': index,
            'data': encrypted_chunk,
            'metadata': chunk_metadata,
            'original_size': len(chunk),
            'method': method
        }

    def _combine_chunks(self, chunks: List[Dict]) -> bytes:
        """合并加密分片"""
        combined = b''
        for chunk in sorted(chunks, key=lambda x: x['index']):
            combined += chunk['data']
        return combined

    def _encrypt_aes256(self, data: bytes, config: Dict) -> tuple:
        # The v1 baseline uses the standard backend; GPU acceleration is opt-in
        # only after backend parity is established, never a different cipher.
        return self._encrypt_aes256_cpu(data, config)

    def _encrypt_aes256_gpu(self, data: bytes, config: Dict) -> tuple:
        """GPU加速的AES-256加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 使用传入的密钥或生成新密钥
            key = config.get('key', os.urandom(32))  # 256位密钥
            mode = config.get('mode', 'GCM')

            if mode == 'GCM':
                iv = os.urandom(12)  # GCM推荐96位IV
            else:
                iv = os.urandom(16)  # 其他模式128位IV

            # 调用GPU管理器进行加密
            gpu_result = gpu_manager.encrypt_data(data, 'aes256', {
                'key': key,
                'iv': iv,
                'mode': mode
            })

            if gpu_result and 'encrypted_data' in gpu_result:
                metadata = {
                    'algorithm': 'AES-256-GPU',
                    'mode': mode,
                    'key': key,
                    'iv': iv,
                    'gpu_accelerated': True,
                    'gpu_performance': gpu_result.get('performance', {})
                }

                if mode == 'GCM' and 'tag' in gpu_result:
                    metadata['tag'] = gpu_result['tag']

                return gpu_result['encrypted_data'], metadata
            else:
                # GPU失败，回退到CPU
                self.logger.warning("GPU加密失败，回退到CPU")
                return self._encrypt_aes256_cpu(data, config)

        except Exception as e:
            self.logger.warning(f"GPU AES-256加密失败: {e}，回退到CPU")
            return self._encrypt_aes256_cpu(data, config)

    def _encrypt_aes256_cpu(self, data: bytes, config: Dict) -> tuple:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        mode = config.get('mode', 'CBC')
        key = config.get('key', os.urandom(32))
        iv = config.get('iv', os.urandom(12 if mode == 'GCM' else 16))
        if mode == 'CBC':
            cipher_mode = modes.CBC(iv)
            padder = padding.PKCS7(128).padder()
            payload = padder.update(data) + padder.finalize()
        elif mode == 'GCM':
            cipher_mode, payload = modes.GCM(iv), data
        elif mode == 'CTR':
            iv = config.get('initial_counter', iv)
            cipher_mode, payload = modes.CTR(iv), data
        else:
            raise ValueError('Unsupported AES mode: ' + str(mode))
        encryptor = Cipher(algorithms.AES(key), cipher_mode).encryptor()
        encrypted = encryptor.update(payload) + encryptor.finalize()
        metadata = {'algorithm': 'AES-256', 'mode': mode, 'key': key, 'iv': iv}
        if mode == 'GCM':
            metadata['tag'] = encryptor.tag
        return encrypted, metadata

    def _encrypt_chacha20(self, data, config):
        return self._encrypt_chacha20_cpu(data, config)

    def _encrypt_chacha20_gpu(self, data: bytes, config: Dict) -> tuple:
        """GPU加速的ChaCha20加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和nonce
            key = os.urandom(32)  # 256位密钥
            nonce = os.urandom(16)  # 128位nonce (cryptography库要求16字节)

            # 调用GPU管理器进行加密
            gpu_result = gpu_manager.encrypt_data(data, 'chacha20', {
                'key': key,
                'nonce': nonce,
                'rounds': config.get('rounds', 20)
            })

            if gpu_result and 'encrypted_data' in gpu_result:
                metadata = {
                    'algorithm': 'ChaCha20-GPU-ONLY',  # 使用 GPU-ONLY 标记，确保解密时使用匹配的自定义实现
                    'key': key,
                    'nonce': nonce,
                    'gpu_accelerated': True,
                    'gpu_only': True,  # 标记为 GPU-ONLY 模式
                    'gpu_performance': gpu_result.get('performance', {})
                }

                return gpu_result['encrypted_data'], metadata
            else:
                # GPU失败，回退到CPU
                self.logger.warning("GPU ChaCha20加密失败，回退到CPU")
                return self._encrypt_chacha20_cpu(data, config)

        except Exception as e:
            self.logger.warning(f"GPU ChaCha20加密失败: {e}，回退到CPU")
            return self._encrypt_chacha20_cpu(data, config)

    def _encrypt_chacha20_cpu(self, data: bytes, config: Dict) -> tuple:
        """CPU版本的ChaCha20加密"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        import os

        key = os.urandom(32)
        nonce = os.urandom(16)

        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        encryptor = cipher.encryptor()

        encrypted_data = encryptor.update(data) + encryptor.finalize()

        metadata = {
            'algorithm': 'ChaCha20-CPU',
            'key': key,
            'nonce': nonce,
            'gpu_accelerated': False
        }

        return encrypted_data, metadata

    def _encrypt_salsa20(self, data: bytes, config: Dict) -> tuple:
        """Salsa20加密"""
        try:
            # 尝试使用PyNaCl库的Salsa20实现
            from nacl.secret import SecretBox
            from nacl.utils import random
            import os

            key = os.urandom(32)  # 256位密钥
            box = SecretBox(key)

            # PyNaCl会自动处理nonce
            encrypted_data = box.encrypt(data)

            metadata = {
                'algorithm': 'Salsa20_PyNaCl',
                'key': key,
                'encrypted_with_nonce': True
            }

            return encrypted_data, metadata

        except ImportError:
            # The configured cipher must be available.
            raise ImportError('PyNaCl is required; Salsa20_Simple fallback is disabled')

    def _encrypt_blowfish(self, data: bytes, config: Dict) -> tuple:
        """Blowfish加密"""
        try:
            # 使用新的decrepit模块避免弃用警告
            from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish
            from cryptography.hazmat.primitives.ciphers import Cipher, modes
            from cryptography.hazmat.primitives import padding
            import os

            # 获取配置参数
            key_size = config.get('key_size', 256)  # 默认256位
            mode = config.get('mode', 'CBC')  # 默认CBC模式

            # 生成密钥和IV
            key = os.urandom(key_size // 8)
            iv = os.urandom(8)  # Blowfish块大小为64位

            # 创建加密器
            if mode == 'CBC':
                cipher = Cipher(Blowfish(key), modes.CBC(iv))

                # 填充数据
                padder = padding.PKCS7(64).padder()  # Blowfish块大小为64位
                padded_data = padder.update(data) + padder.finalize()

            elif mode == 'ECB':
                cipher = Cipher(Blowfish(key), modes.ECB())
                iv = None  # ECB模式不需要IV

                # 填充数据
                padder = padding.PKCS7(64).padder()
                padded_data = padder.update(data) + padder.finalize()

            else:
                raise ValueError(f"不支持的Blowfish模式: {mode}")

            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

            metadata = {
                'algorithm': 'Blowfish',
                'key_size': key_size,
                'mode': mode,
                'key': key,
                'iv': iv
            }

            return encrypted_data, metadata

        except ImportError:
            # The configured cipher must be available.
            raise ImportError('Required standard cipher dependency is unavailable')

    def _encrypt_twofish(self, data: bytes, config: Dict) -> tuple:
        """Twofish加密"""
        try:
            # 尝试使用专门的twofish库
            from src.crypto.twofish_backend import Twofish
            import os

            key_size = config.get('key_size', 256)  # 默认256位
            if key_size not in [128, 192, 256]:
                key_size = 256  # 回退到256位

            # 生成密钥
            key = os.urandom(key_size // 8)

            # 创建Twofish实例
            tf = Twofish(key)

            # 填充数据到16字节边界
            padded_data = self._pad_data_pkcs7(data, 16)

            # 分块加密
            encrypted_data = bytearray()
            for i in range(0, len(padded_data), 16):
                block = padded_data[i:i+16]
                encrypted_block = tf.encrypt(block)
                encrypted_data.extend(encrypted_block)

            metadata = {
                'algorithm': 'Twofish',
                'key_size': key_size,
                'key': key,
                'original_length': len(data)
            }

            return bytes(encrypted_data), metadata

        except ImportError:
            # The configured cipher must be available.
            raise ImportError('twofish is required; Twofish_Simple fallback is disabled')

    def _encrypt_twofish_simple(self, data: bytes, config: Dict) -> tuple:
        """简化的Twofish加密实现"""
        import os

        key_size = config.get('key_size', 256)
        key = os.urandom(key_size // 8)

        # 使用多轮XOR和位操作模拟Twofish
        encrypted_data = bytearray(data)

        # 多轮加密
        for round_num in range(16):  # Twofish使用16轮
            round_key = self._derive_round_key(key, round_num)

            for i in range(len(encrypted_data)):
                # 简化的轮函数
                encrypted_data[i] ^= round_key[i % len(round_key)]
                encrypted_data[i] = self._s_box_substitute(encrypted_data[i])
                encrypted_data[i] = ((encrypted_data[i] << 1) | (encrypted_data[i] >> 7)) & 0xFF

        metadata = {
            'algorithm': 'Twofish_Simple',
            'key_size': key_size,
            'key': key,
            'rounds': 16
        }

        return bytes(encrypted_data), metadata

    def _pad_data_pkcs7(self, data: bytes, block_size: int) -> bytes:
        """PKCS7填充"""
        padding_length = block_size - (len(data) % block_size)
        padding = bytes([padding_length] * padding_length)
        return data + padding

    def _derive_round_key(self, key: bytes, round_num: int) -> bytes:
        """派生轮密钥"""
        import hashlib
        round_data = key + round_num.to_bytes(4, 'big')
        return hashlib.sha256(round_data).digest()[:len(key)]

    def _s_box_substitute(self, byte_val: int) -> int:
        """S盒替换（简化版）"""
        # 简化的S盒，实际Twofish有复杂的S盒
        s_box = [
            0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
            0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
            0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
            0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
            0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
            0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
            0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
            0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
            0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
            0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
            0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
            0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
            0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
            0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
            0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
            0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
        ]
        return s_box[byte_val]

    def _encrypt_rsa(self, data: bytes, config: Dict) -> tuple:
        """RSA加密（仅用于小数据或密钥加密）"""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.hazmat.primitives import hashes
            import os

            # 生成RSA密钥对
            key_size = config.get('key_size', 2048)
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            public_key = private_key.public_key()

            # RSA只能加密小数据，对于大数据使用混合加密
            if len(data) > (key_size // 8 - 2 * hashes.SHA256().digest_size - 2):  # OAEP填充的限制
                # 生成AES密钥加密数据
                aes_key = os.urandom(32)
                encrypted_data, aes_metadata = self._encrypt_aes256(data, {
                    'mode': 'GCM',
                    'key': aes_key  # 传递正确的密钥
                })

                # 用RSA加密AES密钥
                encrypted_aes_key = public_key.encrypt(
                    aes_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )

                # 序列化私钥为PEM格式
                from cryptography.hazmat.primitives import serialization
                private_key_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')  # 转换为字符串

                metadata = {
                    'algorithm': 'RSA-Hybrid',
                    'key_size': key_size,
                    'private_key_pem': private_key_pem,
                    'encrypted_aes_key': encrypted_aes_key,
                    'aes_metadata': aes_metadata
                }

                return encrypted_data, metadata
            else:
                # 直接RSA加密
                encrypted_data = public_key.encrypt(
                    data,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )

                # 序列化私钥为PEM格式
                from cryptography.hazmat.primitives import serialization
                private_key_pem = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode('utf-8')  # 转换为字符串

                metadata = {
                    'algorithm': 'RSA',
                    'key_size': key_size,
                    'private_key_pem': private_key_pem
                }

                return encrypted_data, metadata

        except ImportError:
            raise ImportError('Required standard cipher dependency is unavailable')

    def _encrypt_custom(self, data: bytes, config: Dict) -> tuple:
        """自定义加密算法"""
        algorithm = config.get('algorithm', 'simple_xor')

        if algorithm == 'simple_xor':
            return self._encrypt_simple_xor(data, config)
        elif algorithm == 'bit_shuffle':
            return self._encrypt_bit_shuffle(data, config)
        elif algorithm == 'rotate_cipher':
            return self._encrypt_rotate_cipher(data, config)
        elif algorithm == 'matrix_cipher':
            return self._encrypt_matrix_cipher(data, config)
        elif algorithm == 'pre_scramble':
            return self._encrypt_pre_scramble(data, config)
        elif algorithm == 'final_obfuscation':
            return self._encrypt_final_obfuscation(data, config)
        else:
            raise ValueError(f"不支持的自定义算法: {algorithm}")

    def _encrypt_steganography(self, data: bytes, config: Dict) -> tuple:
        """隐写术加密"""
        # 这里是简化实现，实际应该将数据隐藏在图片中
        cover_data = self._generate_cover_data(len(data) * 8)  # 8倍大小的掩护数据

        # 简单的LSB隐写
        hidden_data = bytearray(cover_data)
        data_bits = ''.join(format(byte, '08b') for byte in data)

        for i, bit in enumerate(data_bits):
            if i < len(hidden_data):
                hidden_data[i] = (hidden_data[i] & 0xFE) | int(bit)

        metadata = {
            'algorithm': 'LSB_Steganography',
            'cover_size': len(cover_data),
            'data_size': len(data)
        }

        return bytes(hidden_data), metadata

    def _encrypt_simple_xor(self, data: bytes, config: Dict) -> tuple:
        """简单XOR加密（用作备用方案）"""
        import os

        key = os.urandom(len(data))
        encrypted_data = bytes(a ^ b for a, b in zip(data, key))

        metadata = {
            'algorithm': 'Simple_XOR',
            'key': key
        }

        return encrypted_data, metadata

    def _encrypt_bit_shuffle(self, data: bytes, config: Dict) -> tuple:
        """位混洗加密"""
        import random

        seed = config.get('seed', 12345)
        random.seed(seed)

        # 生成位置映射
        bit_positions = list(range(8))
        random.shuffle(bit_positions)

        encrypted_data = bytearray()
        for byte in data:
            new_byte = 0
            for i, pos in enumerate(bit_positions):
                if byte & (1 << i):
                    new_byte |= (1 << pos)
            encrypted_data.append(new_byte)

        metadata = {
            'algorithm': 'Bit_Shuffle',
            'seed': seed,
            'bit_positions': bit_positions
        }

        return bytes(encrypted_data), metadata

    def _encrypt_rotate_cipher(self, data: bytes, config: Dict) -> tuple:
        """旋转密码"""
        rotation = config.get('rotation', 13)

        encrypted_data = bytearray()
        for byte in data:
            rotated = (byte + rotation) % 256
            encrypted_data.append(rotated)

        metadata = {
            'algorithm': 'Rotate_Cipher',
            'rotation': rotation
        }

        return bytes(encrypted_data), metadata

    def _generate_cover_data(self, size: int) -> bytes:
        """生成掩护数据"""
        import os
        return os.urandom(size)

    def _encrypt_matrix_cipher(self, data, config):
        return self._encrypt_matrix_cipher_cpu(data, config)

    def _encrypt_matrix_cipher_gpu(self, data: bytes, config: Dict) -> tuple:
        """GPU加速的矩阵变换加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os
            import random

            matrix_size = config.get('matrix_size', 8)
            key_schedule = config.get('key_schedule', 'dynamic')

            # 生成变换矩阵的种子
            if key_schedule == 'dynamic':
                seed = random.randint(1, 65535)
            else:
                seed = config.get('seed', 12345)

            # 调用GPU管理器进行加密
            gpu_result = gpu_manager.encrypt_data(data, 'matrix_cipher', {
                'matrix_size': matrix_size,
                'key_schedule': key_schedule,
                'seed': seed
            })

            if gpu_result and 'encrypted_data' in gpu_result:
                metadata = {
                    'algorithm': 'Matrix_Cipher-GPU',
                    'matrix_size': matrix_size,
                    'key_schedule': key_schedule,
                    'seed': seed,
                    'original_length': len(data),
                    'gpu_accelerated': True,
                    'gpu_performance': gpu_result.get('performance', {})
                }

                if 'transform_matrix' in gpu_result:
                    metadata['transform_matrix'] = gpu_result['transform_matrix']

                return gpu_result['encrypted_data'], metadata
            else:
                # GPU失败，回退到CPU
                self.logger.warning("GPU矩阵变换加密失败，回退到CPU")
                return self._encrypt_matrix_cipher_cpu(data, config)

        except Exception as e:
            self.logger.warning(f"GPU矩阵变换加密失败: {e}，回退到CPU")
            return self._encrypt_matrix_cipher_cpu(data, config)

    def _encrypt_matrix_cipher_cpu(self, data: bytes, config: Dict) -> tuple:
        """CPU版本的矩阵变换加密"""
        import os
        import random

        matrix_size = config.get('matrix_size', 8)
        key_schedule = config.get('key_schedule', 'dynamic')

        if key_schedule == 'dynamic':
            seed = random.randint(1, 65535)
        else:
            seed = config.get('seed', 12345)

        random.seed(seed)
        transform_matrix = self._generate_transform_matrix(matrix_size)
        block_size = matrix_size * matrix_size
        padded_data = self._pad_data_to_size(data, block_size)

        encrypted_data = bytearray()

        for i in range(0, len(padded_data), block_size):
            block = padded_data[i:i+block_size]
            matrix = [list(block[j:j+matrix_size]) for j in range(0, len(block), matrix_size)]
            transformed_matrix = self._apply_matrix_transform(matrix, transform_matrix)

            for row in transformed_matrix:
                encrypted_data.extend(row)

        metadata = {
            'algorithm': 'Matrix_Cipher-CPU',
            'matrix_size': matrix_size,
            'key_schedule': key_schedule,
            'seed': seed,
            'transform_matrix': transform_matrix,
            'original_length': len(data),
            'gpu_accelerated': False
        }

        return bytes(encrypted_data), metadata

    def _encrypt_pre_scramble(self, data: bytes, config: Dict) -> tuple:
        """预处理数据混淆"""
        import os
        import random

        scramble_rounds = config.get('scramble_rounds', 5)

        # 生成混淆种子
        seed = random.randint(1, 65535)
        random.seed(seed)

        scrambled_data = bytearray(data)
        scramble_operations = []

        for round_num in range(scramble_rounds):
            operation = random.choice(['swap', 'reverse', 'rotate', 'xor'])

            if operation == 'swap':
                # 随机交换字节位置
                if len(scrambled_data) > 1:
                    pos1 = random.randint(0, len(scrambled_data) - 1)
                    pos2 = random.randint(0, len(scrambled_data) - 1)
                    scrambled_data[pos1], scrambled_data[pos2] = scrambled_data[pos2], scrambled_data[pos1]
                    scramble_operations.append(('swap', pos1, pos2))

            elif operation == 'reverse':
                # 反转部分数据
                if len(scrambled_data) > 1:
                    start = random.randint(0, len(scrambled_data) // 2)
                    end = random.randint(start + 1, len(scrambled_data))
                    scrambled_data[start:end] = scrambled_data[start:end][::-1]
                    scramble_operations.append(('reverse', start, end))

            elif operation == 'rotate':
                # 循环移位
                if len(scrambled_data) > 1:
                    shift = random.randint(1, len(scrambled_data) - 1)
                    scrambled_data = scrambled_data[shift:] + scrambled_data[:shift]
                    scramble_operations.append(('rotate', shift))

            elif operation == 'xor':
                # XOR混淆
                xor_key = random.randint(1, 255)
                for i in range(len(scrambled_data)):
                    scrambled_data[i] ^= xor_key
                scramble_operations.append(('xor', xor_key))

        metadata = {
            'algorithm': 'Pre_Scramble',
            'scramble_rounds': scramble_rounds,
            'seed': seed,
            'operations': scramble_operations
        }

        return bytes(scrambled_data), metadata

    def _encrypt_final_obfuscation(self, data: bytes, config: Dict) -> tuple:
        """最终数据混淆"""
        import os
        import random
        import hashlib

        obfuscation_level = config.get('obfuscation_level', 'maximum')

        # 根据混淆级别确定操作数量
        if obfuscation_level == 'low':
            operations_count = 3
        elif obfuscation_level == 'medium':
            operations_count = 5
        elif obfuscation_level == 'high':
            operations_count = 8
        else:  # maximum
            operations_count = 12

        # 生成混淆密钥
        obfuscation_key = os.urandom(32)
        key_hash = hashlib.sha256(obfuscation_key).digest()

        obfuscated_data = bytearray(data)
        applied_operations = []

        # 使用密钥哈希作为随机种子
        random.seed(int.from_bytes(key_hash[:4], 'big'))

        # 注意：frequency_analysis_resistance 会改变数据大小，
        # 这会影响 entropy_increase 的逆向操作（因为它依赖于数据位置）
        # 所以我们把 frequency_analysis_resistance 放在最后执行
        non_size_changing_ops = ['byte_substitution', 'bit_permutation', 'block_cipher', 'entropy_increase']
        
        # 先执行不改变大小的操作
        for i in range(operations_count - 1):
            operation = random.choice(non_size_changing_ops)

            if operation == 'byte_substitution':
                # 字节替换
                substitution_table = list(range(256))
                random.shuffle(substitution_table)
                for j in range(len(obfuscated_data)):
                    obfuscated_data[j] = substitution_table[obfuscated_data[j]]
                applied_operations.append(('byte_substitution', substitution_table))

            elif operation == 'bit_permutation':
                # 位排列
                for j in range(len(obfuscated_data)):
                    byte_val = obfuscated_data[j]
                    # 重新排列位
                    new_byte = 0
                    for bit_pos in range(8):
                        if byte_val & (1 << bit_pos):
                            new_pos = (bit_pos * 3 + i) % 8
                            new_byte |= (1 << new_pos)
                    obfuscated_data[j] = new_byte
                applied_operations.append(('bit_permutation', i))

            elif operation == 'block_cipher':
                # 简单分组密码
                block_size = 16
                round_key = key_hash[i % len(key_hash)]
                for j in range(0, len(obfuscated_data), block_size):
                    block_end = min(j + block_size, len(obfuscated_data))
                    for k in range(j, block_end):
                        obfuscated_data[k] ^= round_key
                        obfuscated_data[k] = ((obfuscated_data[k] << 1) | (obfuscated_data[k] >> 7)) & 0xFF
                applied_operations.append(('block_cipher', round_key))

            elif operation == 'entropy_increase':
                # 增加熵
                for j in range(len(obfuscated_data)):
                    entropy_factor = key_hash[j % len(key_hash)]
                    obfuscated_data[j] ^= entropy_factor
                    obfuscated_data[j] = (obfuscated_data[j] + entropy_factor) % 256
                applied_operations.append(('entropy_increase', None))

        # 最后执行 frequency_analysis_resistance（因为它会改变数据大小）
        if obfuscation_level in ['high', 'maximum'] and len(obfuscated_data) > 10:
            dummy_bytes = os.urandom(len(obfuscated_data) // 10)
            if len(dummy_bytes) > 0 and len(dummy_bytes) <= len(obfuscated_data):
                insertion_positions = sorted(random.sample(range(len(obfuscated_data)), len(dummy_bytes)))
                for pos, dummy_byte in zip(reversed(insertion_positions), reversed(dummy_bytes)):
                    obfuscated_data.insert(pos, dummy_byte)
                applied_operations.append(('frequency_analysis_resistance', insertion_positions))

        metadata = {
            'algorithm': 'Final_Obfuscation',
            'obfuscation_level': obfuscation_level,
            'operations_count': len(applied_operations),  # 使用实际操作数量
            'obfuscation_key': obfuscation_key,
            'applied_operations': applied_operations,
            'original_length': len(data)
        }

        return bytes(obfuscated_data), metadata

    def _generate_transform_matrix(self, size: int) -> list:
        """生成变换矩阵"""
        import random

        # 创建单位矩阵
        matrix = [[0] * size for _ in range(size)]
        for i in range(size):
            matrix[i][i] = 1

        # 应用随机变换
        for _ in range(size):
            # 随机行交换
            row1 = random.randint(0, size - 1)
            row2 = random.randint(0, size - 1)
            matrix[row1], matrix[row2] = matrix[row2], matrix[row1]

            # 随机列交换
            col1 = random.randint(0, size - 1)
            col2 = random.randint(0, size - 1)
            for i in range(size):
                matrix[i][col1], matrix[i][col2] = matrix[i][col2], matrix[i][col1]

        return matrix

    def _apply_matrix_transform(self, data_matrix: list, transform_matrix: list) -> list:
        # The producer constructs a permutation matrix, not a general matrix.
        indexes = [next(i for i, row in enumerate(transform_matrix) if row[j] == 1)
                   for j in range(len(transform_matrix))]
        return [[row[i] for i in indexes] for row in data_matrix]

    def _pad_data_to_size(self, data: bytes, block_size: int) -> bytes:
        """将数据填充到指定块大小"""
        padding_length = block_size - (len(data) % block_size)
        if padding_length == block_size:
            padding_length = 0

        if padding_length > 0:
            padding = bytes([padding_length] * padding_length)
            return data + padding
        return data

    def _encrypt_salsa20_simple(self, data: bytes, config: Dict) -> tuple:
        """简化的Salsa20加密实现"""
        import os
        import struct

        key = os.urandom(32)  # 256位密钥
        nonce = os.urandom(8)  # 64位nonce

        # 简化实现：使用更简单的流密码模拟Salsa20
        def simple_stream_cipher(key, nonce, data_len):
            """简化的流密码实现"""
            import hashlib

            keystream = bytearray()
            counter = 0

            while len(keystream) < data_len:
                # 使用哈希函数生成伪随机流
                block_input = key + nonce + counter.to_bytes(8, 'little')
                block_hash = hashlib.sha256(block_input).digest()
                keystream.extend(block_hash)
                counter += 1

            return keystream[:data_len]

        # 生成密钥流并加密
        keystream = simple_stream_cipher(key, nonce, len(data))
        encrypted_data = bytes(a ^ b for a, b in zip(data, keystream))

        metadata = {
            'algorithm': 'Salsa20_Simple',
            'key': key,
            'nonce': nonce
        }

        return encrypted_data, metadata

    def _rotl32(self, value: int, amount: int) -> int:
        """32位左旋转"""
        return ((value << amount) | (value >> (32 - amount))) & 0xffffffff

    def shutdown(self):
        """关闭引擎并清理资源"""
        if self.thread_pool:
            self.logger.info("正在关闭线程池...")
            self.thread_pool.shutdown(wait=True)
            self.thread_pool = None
        self.logger.info("混合加密引擎已关闭")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.shutdown()

    def get_performance_stats(self) -> Dict:
        """获取性能统计信息"""
        config = self.thread_manager.get_config()
        return {
            'cpu_count': self.thread_manager.cpu_count,
            'max_threads': self.thread_manager.get_max_threads(),
            'threading_enabled': self.thread_manager.is_threading_enabled(),
            'parallel_threshold': self.thread_manager.get_parallel_threshold(),
            'chunk_size_base': self.thread_manager.get_chunk_size_base(),
            'thread_pool_active': self.thread_pool is not None,
            'config_source': config.get('source'),
            'config_priority': config.get('priority').name if config.get('priority') else 'unknown'
        }
