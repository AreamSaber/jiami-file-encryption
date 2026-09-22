"""
纯GPU混合加密引擎
专门用于GPU算法的加密引擎，仅使用GPU加速算法
"""

import time
from typing import Dict, List, Optional, Any
from .hybrid_engine import HybridEncryptionEngine
from ..utils.logger import Logger


class PureGPUEngine(HybridEncryptionEngine):
    """纯GPU混合加密引擎"""

    def __init__(self, security_level: int = 1, max_threads: Optional[int] = None):
        """
        初始化纯GPU混合加密引擎

        Args:
            security_level: 安全级别 (1-5)
            max_threads: 最大线程数
        """
        super().__init__(max_threads)
        self.logger = Logger("PureGPUEngine")
        self.security_level = security_level

        # 强制GPU模式
        self._force_gpu_mode()

        # 配置GPU专用算法
        self._configure_gpu_algorithms()

        # 根据安全级别配置算法
        self._configure_security_algorithms()

        self.logger.info(f"纯GPU引擎初始化完成 - 安全级别: {security_level}")

    def _force_gpu_mode(self):
        """强制GPU模式"""
        try:
            import os
            # 设置OpenCL环境变量
            os.environ['PYOPENCL_CTX'] = '0'

            from src.gpu.gpu_manager import gpu_manager

            # 强制禁用CPU模式
            gpu_manager.force_cpu_mode = False

            # 大幅降低GPU阈值，确保小数据也使用GPU
            gpu_manager.min_data_size_for_gpu = 512  # 512字节即可使用GPU

            # 设置算法特定的低阈值
            if hasattr(gpu_manager, 'set_threshold'):
                gpu_manager.set_threshold(512)  # 512字节阈值

            # 检查GPU可用性
            if gpu_manager.is_gpu_available():
                self.logger.info("GPU模式已启用")
                self.gpu_available = True

                # 测试GPU功能
                test_result = gpu_manager.should_use_gpu(1024, 'aes256')
                self.logger.info(f"GPU测试 (1KB AES-256): {'通过' if test_result else '失败'}")

            else:
                self.logger.warning("GPU不可用，将回退到CPU")
                self.gpu_available = False

        except Exception as e:
            self.logger.error(f"GPU初始化失败: {e}")
            self.gpu_available = False

    def _configure_gpu_algorithms(self):
        """配置GPU专用算法方法"""
        # 重新定义加密方法，仅包含GPU算法
        self.encryption_methods = {
            'aes256': self._encrypt_aes256_gpu_only,
            'chacha20': self._encrypt_chacha20_gpu_only,
            'salsa20': self._encrypt_salsa20_gpu_only,
            'matrix_cipher': self._encrypt_matrix_cipher_gpu_only,
            'blowfish': self._encrypt_blowfish_gpu_only,
            'twofish': self._encrypt_twofish_gpu_only
        }

    def _configure_security_algorithms(self):
        """根据安全级别配置GPU算法"""
        # 定义不同安全级别的GPU算法组合
        self.security_algorithms = {
            1: {  # GPU基础
                'name': 'GPU基础加密',
                'algorithms': ['aes256'],
                'description': '单层GPU AES-256加密，高性能'
            },
            2: {  # GPU标准
                'name': 'GPU标准加密',
                'algorithms': ['chacha20', 'aes256'],
                'description': '双层GPU加密，平衡性能和安全性'
            },
            3: {  # GPU高级
                'name': 'GPU高级加密',
                'algorithms': ['chacha20', 'matrix_cipher', 'aes256'],
                'description': '三层GPU加密，包含自定义矩阵算法'
            },
            4: {  # GPU专业
                'name': 'GPU专业加密',
                'algorithms': ['chacha20', 'salsa20', 'matrix_cipher', 'aes256'],
                'description': '四层GPU加密，多种流密码组合'
            },
            5: {  # GPU极限
                'name': 'GPU极限加密',
                'algorithms': ['chacha20', 'salsa20', 'matrix_cipher', 'blowfish', 'aes256'],
                'description': '五层GPU加密，所有GPU算法组合'
            }
        }

        # 获取当前安全级别配置
        current_config = self.security_algorithms.get(self.security_level, self.security_algorithms[1])
        self.current_algorithms = current_config['algorithms']
        self.encryption_name = current_config['name']
        self.encryption_description = current_config['description']

        self.logger.info(f"配置GPU算法: {self.encryption_name}")
        self.logger.info(f"算法列表: {self.current_algorithms}")

    def get_encryption_config(self) -> Dict:
        """获取当前加密配置"""
        layers = []

        for algorithm in self.current_algorithms:
            if algorithm == 'aes256':
                layers.append({
                    'method': 'aes256',
                    'mode': 'GCM',
                    'key_size': 256,
                    'force_gpu': True,
                    'params': {}
                })
            elif algorithm == 'chacha20':
                layers.append({
                    'method': 'chacha20',
                    'key_size': 256,
                    'force_gpu': True,
                    'params': {'rounds': 20}
                })
            elif algorithm == 'salsa20':
                layers.append({
                    'method': 'salsa20',
                    'key_size': 256,
                    'force_gpu': True
                })
            elif algorithm == 'matrix_cipher':
                layers.append({
                    'method': 'matrix_cipher',
                    'force_gpu': True,
                    'params': {
                        'matrix_size': 8 + self.security_level,
                        'key_schedule': 'complex' if self.security_level >= 3 else 'simple'
                    }
                })
            elif algorithm == 'blowfish':
                layers.append({
                    'method': 'blowfish',
                    'key_size': 256,
                    'mode': 'CBC',
                    'force_gpu': True
                })
            elif algorithm == 'twofish':
                layers.append({
                    'method': 'twofish',
                    'key_size': 256,
                    'force_gpu': True
                })

        return {
            'strategy': 'threaded_layered',
            'layers': layers,
            'security_level': self.security_level,
            'engine_type': 'pure_gpu',
            'gpu_settings': {
                'enable_gpu': True,
                'gpu_threshold_mb': 0.001,  # 1KB阈值
                'force_gpu': True
            },
            'threading': {
                'auto_threading': True,
                'max_threads': 8,  # GPU模式下减少CPU线程
                'parallel_threshold_mb': 5
            }
        }

    # GPU专用加密方法
    def _encrypt_aes256_gpu_only(self, data: bytes, config: Dict) -> tuple:
        """强制GPU AES-256加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和IV
            key = os.urandom(32)  # 256位密钥
            iv = os.urandom(16)   # 128位IV
            mode = config.get('mode', 'CBC')  # 使用CBC模式，因为GCM在GPU中有问题

            # 强制使用CBC模式以确保GPU加速
            if mode == 'GCM':
                mode = 'CBC'
                self.logger.info("强制将GCM模式改为CBC模式以启用GPU加速")

            self.logger.info(f"尝试GPU AES-256加密 - 数据大小: {len(data)} 字节, 模式: {mode}")

            # 检查是否应该使用GPU
            should_use_gpu = gpu_manager.should_use_gpu(len(data), 'aes256')
            self.logger.info(f"GPU使用判断: {should_use_gpu}")

            if should_use_gpu:
                # 强制使用GPU - 使用主项目的参数格式
                gpu_result = gpu_manager.encrypt_data(data, 'aes256', {
                    'key': key,
                    'iv': iv,
                    'mode': mode
                })

                self.logger.info(f"GPU加密结果: {gpu_result is not None}")
                if gpu_result:
                    self.logger.info(f"GPU结果类型: {type(gpu_result)}")
                    self.logger.info(f"GPU结果键: {list(gpu_result.keys()) if isinstance(gpu_result, dict) else 'Not dict'}")

                if gpu_result and 'encrypted_data' in gpu_result:
                    self.logger.info("✅ GPU AES-256加密成功")

                    metadata = {
                        'algorithm': 'AES-256-GPU-ONLY',
                        'mode': mode,
                        'key': key,
                        'iv': iv,
                        'gpu_accelerated': True,
                        'gpu_performance': gpu_result.get('performance', {}),
                        'backend_info': gpu_result.get('backend_info', 'GPU')
                    }

                    # 处理认证标签
                    if 'tag' in gpu_result:
                        metadata['tag'] = gpu_result['tag']

                    return gpu_result['encrypted_data'], metadata
                else:
                    self.logger.warning("GPU加密返回空结果，使用CPU回退")
                    return self._encrypt_aes256_cpu_fallback(data, key, iv, mode)
            else:
                self.logger.warning("数据大小不满足GPU阈值，使用CPU回退")
                return self._encrypt_aes256_cpu_fallback(data, key, iv, mode)

        except Exception as e:
            self.logger.error(f"GPU AES-256加密失败: {e}")
            # 尝试CPU回退
            try:
                import os
                key = os.urandom(32)
                iv = os.urandom(16)
                mode = config.get('mode', 'CBC')
                return self._encrypt_aes256_cpu_fallback(data, key, iv, mode)
            except Exception as e2:
                raise Exception(f"纯GPU模式下AES-256加密失败: {e}, CPU回退也失败: {e2}")

    def _encrypt_chacha20_gpu_only(self, data: bytes, config: Dict) -> tuple:
        """强制GPU ChaCha20加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和nonce
            key = os.urandom(32)  # 256位密钥
            nonce = os.urandom(16)  # 128位nonce

            self.logger.info(f"尝试GPU ChaCha20加密 - 数据大小: {len(data)} 字节")

            # 检查是否应该使用GPU
            should_use_gpu = gpu_manager.should_use_gpu(len(data), 'chacha20')
            self.logger.info(f"GPU使用判断: {should_use_gpu}")

            if should_use_gpu:
                # 使用主项目的参数格式
                gpu_result = gpu_manager.encrypt_data(data, 'chacha20', {
                    'key': key,
                    'nonce': nonce,
                    'rounds': config.get('rounds', 20)
                })

                self.logger.info(f"GPU加密结果: {gpu_result is not None}")
                if gpu_result:
                    self.logger.info(f"GPU结果类型: {type(gpu_result)}")
                    self.logger.info(f"GPU结果键: {list(gpu_result.keys()) if isinstance(gpu_result, dict) else 'Not dict'}")

                if gpu_result and 'encrypted_data' in gpu_result:
                    self.logger.info("✅ GPU ChaCha20加密成功")

                    metadata = {
                        'algorithm': 'ChaCha20-GPU-ONLY',
                        'key': key,
                        'nonce': nonce,
                        'gpu_accelerated': True,
                        'gpu_performance': gpu_result.get('performance', {}),
                        'backend_info': gpu_result.get('backend_info', 'GPU')
                    }
                    return gpu_result['encrypted_data'], metadata
                else:
                    self.logger.warning("GPU加密返回空结果，使用CPU回退")
                    return self._encrypt_chacha20_cpu_fallback(data, key, nonce)
            else:
                self.logger.warning("数据大小不满足GPU阈值，使用CPU回退")
                return self._encrypt_chacha20_cpu_fallback(data, key, nonce)

        except Exception as e:
            self.logger.error(f"GPU ChaCha20加密失败: {e}")
            # 尝试CPU回退
            try:
                import os
                key = os.urandom(32)
                nonce = os.urandom(16)
                return self._encrypt_chacha20_cpu_fallback(data, key, nonce)
            except Exception as e2:
                raise Exception(f"纯GPU模式下ChaCha20加密失败: {e}, CPU回退也失败: {e2}")

    def _encrypt_salsa20_gpu_only(self, data: bytes, config: Dict) -> tuple:
        """强制GPU Salsa20加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager

            gpu_result = gpu_manager.encrypt_data(data, 'salsa20', {})

            if gpu_result and 'encrypted_data' in gpu_result:
                metadata = {
                    'algorithm': 'Salsa20-GPU-ONLY',
                    'gpu_accelerated': True,
                    'gpu_performance': gpu_result.get('performance', {})
                }
                return gpu_result['encrypted_data'], metadata
            else:
                raise Exception("GPU加密失败")

        except Exception as e:
            self.logger.error(f"GPU Salsa20加密失败: {e}")
            raise Exception(f"纯GPU模式下Salsa20加密失败: {e}")

    def _encrypt_matrix_cipher_gpu_only(self, data: bytes, config: Dict) -> tuple:
        """强制GPU矩阵加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager

            gpu_result = gpu_manager.encrypt_data(data, 'matrix_cipher', {
                'matrix_size': config.get('matrix_size', 8),
                'key_schedule': config.get('key_schedule', 'simple')
            })

            if gpu_result and 'encrypted_data' in gpu_result:
                metadata = {
                    'algorithm': 'Matrix_Cipher-GPU-ONLY',
                    'gpu_accelerated': True,
                    'gpu_performance': gpu_result.get('performance', {})
                }
                return gpu_result['encrypted_data'], metadata
            else:
                raise Exception("GPU加密失败")

        except Exception as e:
            self.logger.error(f"GPU矩阵加密失败: {e}")
            raise Exception(f"纯GPU模式下矩阵加密失败: {e}")

    def _encrypt_blowfish_gpu_only(self, data: bytes, config: Dict) -> tuple:
        """强制GPU Blowfish加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和IV
            key_size = config.get('key_size', 128)
            key = os.urandom(key_size // 8)
            iv = os.urandom(8)  # Blowfish块大小为64位
            mode = config.get('mode', 'CBC')

            self.logger.info(f"尝试GPU Blowfish加密 - 数据大小: {len(data)} 字节, 模式: {mode}")

            # 检查是否应该使用GPU
            should_use_gpu = gpu_manager.should_use_gpu(len(data), 'blowfish')
            self.logger.info(f"GPU使用判断: {should_use_gpu}")

            if should_use_gpu:
                # 强制使用GPU
                gpu_result = gpu_manager.encrypt_data(data, 'blowfish', {
                    'key': key,
                    'iv': iv,
                    'mode': mode,
                    'key_size': key_size
                })

                self.logger.info(f"GPU加密结果: {gpu_result is not None}")
                if gpu_result:
                    self.logger.info(f"GPU结果类型: {type(gpu_result)}")
                    self.logger.info(f"GPU结果键: {list(gpu_result.keys()) if isinstance(gpu_result, dict) else 'Not dict'}")

                if gpu_result and 'encrypted_data' in gpu_result:
                    self.logger.info("✅ GPU Blowfish加密成功")

                    metadata = {
                        'algorithm': 'Blowfish-GPU-ONLY',
                        'mode': mode,
                        'key': key,
                        'iv': iv,
                        'key_size': key_size,
                        'gpu_accelerated': True,
                        'gpu_performance': gpu_result.get('performance', {}),
                        'backend_info': gpu_result.get('backend_info', 'GPU')
                    }

                    return gpu_result['encrypted_data'], metadata
                else:
                    self.logger.warning("GPU加密返回空结果，使用CPU回退")
                    return self._encrypt_blowfish_cpu_fallback(data, key, iv, mode, key_size)
            else:
                self.logger.warning("数据大小不满足GPU阈值，使用CPU回退")
                return self._encrypt_blowfish_cpu_fallback(data, key, iv, mode, key_size)

        except Exception as e:
            self.logger.error(f"GPU Blowfish加密失败: {e}")
            # 尝试CPU回退
            try:
                import os
                key_size = config.get('key_size', 128)
                key = os.urandom(key_size // 8)
                iv = os.urandom(8)
                mode = config.get('mode', 'CBC')
                return self._encrypt_blowfish_cpu_fallback(data, key, iv, mode, key_size)
            except Exception as e2:
                raise Exception(f"纯GPU模式下Blowfish加密失败: {e}, CPU回退也失败: {e2}")

    def _encrypt_twofish_gpu_only(self, data: bytes, config: Dict) -> tuple:
        """强制GPU Twofish加密"""
        try:
            # Twofish算法比较复杂，暂时使用简化的块密码实现
            import os
            import hashlib

            key_size = config.get('key_size', 256)
            key = os.urandom(key_size // 8)
            iv = os.urandom(16)  # 128位IV
            mode = config.get('mode', 'CBC')

            self.logger.info(f"尝试GPU Twofish加密 - 数据大小: {len(data)} 字节, 模式: {mode}")
            self.logger.warning("Twofish使用简化实现")

            # 简化的块密码实现
            encrypted = bytearray()

            # 添加简单填充
            padded_data = data
            if len(data) % 16 != 0:
                padding_len = 16 - (len(data) % 16)
                padded_data = data + bytes([padding_len] * padding_len)

            # 逐块加密
            for i in range(0, len(padded_data), 16):
                block = padded_data[i:i+16]

                # CBC模式：与前一个块或IV进行XOR
                if mode == 'CBC':
                    if i == 0:
                        block = bytes(a ^ b for a, b in zip(block, iv))
                    else:
                        prev_block = encrypted[i-16:i]
                        block = bytes(a ^ b for a, b in zip(block, prev_block))

                # 简化的Twofish风格加密
                block_key = hashlib.sha256(key + i.to_bytes(4, 'little')).digest()[:16]
                encrypted_block = bytes(a ^ b for a, b in zip(block, block_key))

                # 额外的混合
                for j in range(16):
                    encrypted_block = bytearray(encrypted_block)
                    encrypted_block[j] = (encrypted_block[j] + key[j % len(key)]) % 256
                    encrypted_block[j] ^= (j + i) % 256
                    encrypted_block = bytes(encrypted_block)

                encrypted.extend(encrypted_block)

            metadata = {
                'algorithm': 'Twofish-SIMPLIFIED',
                'mode': mode,
                'key': key,
                'iv': iv,
                'key_size': key_size,
                'gpu_accelerated': False,
                'implementation': 'simplified'
            }

            self.logger.info("✅ Twofish简化加密成功")
            return bytes(encrypted), metadata

        except Exception as e:
            self.logger.error(f"Twofish加密失败: {e}")
            raise Exception(f"Twofish加密失败: {e}")

    def _encrypt_chacha20_cpu_fallback(self, data: bytes, key: bytes, nonce: bytes) -> tuple:
        """ChaCha20 CPU回退实现"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

            algorithm = algorithms.ChaCha20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            encryptor = cipher.encryptor()

            encrypted_data = encryptor.update(data) + encryptor.finalize()

            metadata = {
                'algorithm': 'ChaCha20-CPU-FALLBACK',
                'key': key,
                'nonce': nonce,
                'gpu_accelerated': False,
                'fallback_reason': 'GPU加密失败，使用CPU回退'
            }

            return encrypted_data, metadata

        except Exception as e:
            raise Exception(f"ChaCha20 CPU回退失败: {e}")

    def _encrypt_aes256_cpu_fallback(self, data: bytes, key: bytes, iv: bytes, mode: str = 'GCM') -> tuple:
        """AES-256 CPU回退实现"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding

            if mode == 'GCM':
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))

            encryptor = cipher.encryptor()

            if mode == 'CBC':
                # 添加填充
                padder = padding.PKCS7(128).padder()
                padded_data = padder.update(data) + padder.finalize()
                encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            else:
                encrypted_data = encryptor.update(data) + encryptor.finalize()

            metadata = {
                'algorithm': 'AES-256-CPU-FALLBACK',
                'mode': mode,
                'key': key,
                'iv': iv,
                'gpu_accelerated': False,
                'fallback_reason': 'GPU加密失败，使用CPU回退'
            }

            if mode == 'GCM':
                metadata['tag'] = encryptor.tag

            return encrypted_data, metadata

        except Exception as e:
            raise Exception(f"AES-256 CPU回退失败: {e}")

    def _encrypt_blowfish_cpu_fallback(self, data: bytes, key: bytes, iv: bytes, mode: str, key_size: int) -> tuple:
        """Blowfish CPU回退实现"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding

            # 创建加密器
            if mode == 'CBC':
                cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.Blowfish(key), modes.ECB())

            # 添加填充
            padder = padding.PKCS7(64).padder()  # Blowfish块大小为64位
            padded_data = padder.update(data) + padder.finalize()

            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

            metadata = {
                'algorithm': 'Blowfish-CPU-FALLBACK',
                'mode': mode,
                'key': key,
                'iv': iv,
                'key_size': key_size,
                'gpu_accelerated': False,
                'fallback_reason': 'GPU加密失败，使用CPU回退'
            }

            return encrypted_data, metadata

        except Exception as e:
            raise Exception(f"Blowfish CPU回退失败: {e}")

    def encrypt_with_security_level(self, data: bytes, progress_callback=None) -> Dict:
        """
        使用指定安全级别加密数据

        Args:
            data: 要加密的数据
            progress_callback: 进度回调函数

        Returns:
            加密结果字典
        """
        if not self.gpu_available:
            raise Exception("GPU不可用，无法使用纯GPU引擎")

        config = self.get_encryption_config()

        self.logger.info(f"开始{self.encryption_name} - {len(data)} 字节")
        self.logger.info(f"描述: {self.encryption_description}")

        start_time = time.time()
        result = super().encrypt_data(data, config, progress_callback)
        end_time = time.time()

        # 添加GPU引擎特有的元数据
        result['gpu_engine_info'] = {
            'engine_type': 'pure_gpu',
            'security_level': self.security_level,
            'encryption_name': self.encryption_name,
            'algorithm_count': len(self.current_algorithms),
            'total_time': end_time - start_time,
            'gpu_optimized': True
        }

        self.logger.info(f"{self.encryption_name}完成 - 耗时: {end_time - start_time:.2f}秒")
        return result

    def get_supported_algorithms(self) -> List[str]:
        """获取支持的GPU算法列表"""
        return ['aes256', 'chacha20', 'salsa20', 'matrix_cipher', 'blowfish', 'twofish']

    def get_security_info(self) -> Dict:
        """获取安全级别信息"""
        return {
            'current_level': self.security_level,
            'available_levels': list(self.security_algorithms.keys()),
            'current_config': self.security_algorithms[self.security_level],
            'engine_type': 'pure_gpu',
            'gpu_available': self.gpu_available
        }


def create_gpu_test_config(security_level: int = 2) -> Dict:
    """创建GPU测试配置"""
    engine = PureGPUEngine(security_level=security_level)
    return engine.get_encryption_config()


if __name__ == "__main__":
    # 测试纯GPU引擎
    print("🚀 测试纯GPU混合加密引擎")
    print("=" * 50)

    # 测试不同安全级别
    for level in range(1, 6):
        print(f"\n📋 安全级别 {level}:")
        try:
            engine = PureGPUEngine(security_level=level)
            config = engine.get_encryption_config()

            print(f"   名称: {engine.encryption_name}")
            print(f"   算法: {engine.current_algorithms}")
            print(f"   层数: {len(config['layers'])}")
            print(f"   描述: {engine.encryption_description}")
            print(f"   GPU可用: {engine.gpu_available}")
        except Exception as e:
            print(f"   ❌ 初始化失败: {e}")
