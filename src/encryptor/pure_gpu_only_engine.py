#!/usr/bin/env python3
"""
纯GPU专用加密引擎
完全移除CPU回退机制，实现100%GPU加密
"""

import os
import sys
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import Logger


class PureGPUOnlyEngine:
    """纯GPU专用加密引擎 - 无CPU回退"""

    def __init__(self, security_level: int = 1):
        """
        初始化纯GPU专用加密引擎

        Args:
            security_level: 安全级别 (1-5)
        """
        self.logger = Logger("PureGPUOnlyEngine")
        self.security_level = security_level
        self.gpu_available = False

        # 强制GPU模式，无回退
        self._initialize_gpu_only_mode()

        # 配置GPU算法
        self._configure_gpu_algorithms()

        self.logger.info(f"纯GPU专用引擎初始化完成 - 安全级别: {security_level}")

    def _initialize_gpu_only_mode(self):
        """初始化纯GPU模式"""
        try:
            import os
            # 设置OpenCL环境变量
            os.environ['PYOPENCL_CTX'] = '0'

            from src.gpu.gpu_manager import gpu_manager

            # 强制禁用CPU模式
            gpu_manager.force_cpu_mode = False

            # 设置极低阈值，所有数据都使用GPU
            gpu_manager.min_data_size_for_gpu = 1  # 1字节即可使用GPU
            gpu_manager.set_threshold(1)

            # 检查GPU可用性
            if not gpu_manager.is_gpu_available():
                raise Exception("GPU不可用，纯GPU引擎无法启动")

            self.gpu_available = True
            self.logger.info("✅ 纯GPU模式已启用")

            # 验证GPU功能
            test_result = gpu_manager.should_use_gpu(1024, 'aes256')
            if not test_result:
                raise Exception("GPU功能测试失败")

            self.logger.info("✅ GPU功能验证通过")

        except Exception as e:
            self.logger.error(f"GPU初始化失败: {e}")
            raise Exception(f"纯GPU引擎启动失败: {e}")

    def _configure_gpu_algorithms(self):
        """配置GPU算法"""
        self.gpu_algorithms = {
            1: {
                'name': 'GPU基础加密',
                'algorithms': ['aes256'],
                'description': '单层GPU AES-256加密'
            },
            2: {
                'name': 'GPU标准加密',
                'algorithms': ['chacha20', 'aes256'],
                'description': '双层GPU加密：ChaCha20 + AES-256'
            },
            3: {
                'name': 'GPU高级加密',
                'algorithms': ['chacha20', 'matrix_cipher', 'aes256'],
                'description': '三层GPU加密：ChaCha20 + 矩阵变换 + AES-256'
            },
            4: {
                'name': 'GPU专业加密',
                'algorithms': ['chacha20', 'salsa20', 'matrix_cipher', 'aes256'],
                'description': '四层GPU加密：多种流密码 + 矩阵变换 + AES-256'
            },
            5: {
                'name': 'GPU极限加密',
                'algorithms': ['chacha20', 'salsa20', 'matrix_cipher', 'blowfish', 'aes256'],
                'description': '五层GPU加密：所有GPU算法组合，AES-256最后'
            }
        }

        config = self.gpu_algorithms.get(self.security_level, self.gpu_algorithms[1])
        self.encryption_name = config['name']
        self.algorithm_list = config['algorithms']
        self.description = config['description']

        self.logger.info(f"配置GPU算法: {self.encryption_name}")
        self.logger.info(f"算法列表: {self.algorithm_list}")

    def encrypt_with_security_level(self, data: bytes, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        使用指定安全级别进行GPU加密

        Args:
            data: 要加密的数据
            progress_callback: 进度回调函数

        Returns:
            包含加密结果的字典
        """
        try:
            start_time = time.time()
            self.logger.info(f"开始{self.encryption_name} - {len(data)} 字节")
            self.logger.info(f"描述: {self.description}")

            if progress_callback:
                progress_callback(0, "开始GPU加密...")

            # 执行多层GPU加密
            encrypted_data = data
            layers = []

            for i, algorithm in enumerate(self.algorithm_list):
                layer_start = time.time()

                if progress_callback:
                    progress = int((i / len(self.algorithm_list)) * 80) + 10
                    progress_callback(progress, f"GPU加密第{i+1}层: {algorithm}")

                self.logger.info(f"执行第{i+1}层GPU加密: {algorithm}")

                # 执行GPU加密
                encrypted_data, layer_metadata = self._encrypt_single_layer_gpu_only(
                    encrypted_data, algorithm
                )

                layer_time = time.time() - layer_start
                layer_metadata['layer_index'] = i + 1
                layer_metadata['layer_time'] = layer_time
                layers.append(layer_metadata)

                self.logger.info(f"第{i+1}层GPU加密完成 - 耗时: {layer_time:.3f}秒")

            total_time = time.time() - start_time

            if progress_callback:
                progress_callback(100, "GPU加密完成")

            # 构建结果
            result = {
                'encrypted_data': encrypted_data,
                'metadata': {
                    'engine_type': 'pure_gpu_only',
                    'security_level': self.security_level,
                    'encryption_name': self.encryption_name,
                    'total_layers': len(layers),
                    'layers': layers,
                    'total_time': total_time,
                    'gpu_only': True,
                    'cpu_fallback': False,
                    'gpu_engine_info': {
                        'security_level': self.security_level,
                        'algorithm_count': len(self.algorithm_list),
                        'algorithms': self.algorithm_list,
                        'description': self.description
                    }
                }
            }

            self.logger.info(f"{self.encryption_name}完成 - 耗时: {total_time:.2f}秒")
            return result

        except Exception as e:
            self.logger.error(f"GPU加密失败: {e}")
            raise Exception(f"纯GPU加密失败: {e}")

    def _encrypt_single_layer_gpu_only(self, data: bytes, algorithm: str) -> tuple:
        """
        执行单层GPU加密（无CPU回退）

        Args:
            data: 要加密的数据
            algorithm: 算法名称

        Returns:
            (加密数据, 元数据)
        """
        try:
            if algorithm == 'aes256':
                return self._encrypt_aes256_gpu_only(data)
            elif algorithm == 'chacha20':
                return self._encrypt_chacha20_gpu_only(data)
            elif algorithm == 'salsa20':
                return self._encrypt_salsa20_gpu_only(data)
            elif algorithm == 'matrix_cipher':
                return self._encrypt_matrix_cipher_gpu_only(data)
            elif algorithm == 'blowfish':
                return self._encrypt_blowfish_gpu_only(data)
            else:
                raise Exception(f"不支持的GPU算法: {algorithm}")

        except Exception as e:
            self.logger.error(f"GPU算法 {algorithm} 加密失败: {e}")
            raise Exception(f"GPU算法 {algorithm} 加密失败: {e}")

    def _encrypt_aes256_gpu_only(self, data: bytes) -> tuple:
        """纯GPU AES-256加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和IV（确保长度正确）
            key = os.urandom(32)  # 256位密钥
            iv = os.urandom(16)   # 128位IV（CBC模式需要）
            mode = 'CBC'          # 明确指定CBC模式

            self.logger.info(f"🚀 纯GPU AES-256加密开始 - 数据大小: {len(data)} 字节, 模式: {mode}")

            # 强制GPU加密，无回退
            gpu_result = gpu_manager.encrypt_data(data, 'aes256', {
                'key': key,
                'iv': iv,
                'mode': mode
            })

            if not gpu_result or 'encrypted_data' not in gpu_result:
                raise Exception("GPU AES-256加密返回空结果")

            self.logger.info("✅ 纯GPU AES-256加密成功")

            metadata = {
                'algorithm': 'AES-256-GPU-ONLY',
                'mode': mode,
                'key': key,
                'iv': iv,
                'gpu_accelerated': True,
                'gpu_only': True,
                'cpu_fallback': False,
                'gpu_performance': gpu_result.get('performance', {}),
                'backend_info': gpu_result.get('backend_info', 'GPU')
            }

            # 添加认证标签（如果有）
            if 'tag' in gpu_result:
                metadata['tag'] = gpu_result['tag']

            return gpu_result['encrypted_data'], metadata

        except Exception as e:
            raise Exception(f"纯GPU AES-256加密失败: {e}")

    def _encrypt_chacha20_gpu_only(self, data: bytes) -> tuple:
        """纯GPU ChaCha20加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和nonce（确保长度正确）
            key = os.urandom(32)  # 256位密钥
            nonce = os.urandom(16)  # 128位nonce（与解密器匹配）

            self.logger.info(f"🚀 纯GPU ChaCha20加密开始 - 数据大小: {len(data)} 字节")

            # 强制GPU加密，无回退
            gpu_result = gpu_manager.encrypt_data(data, 'chacha20', {
                'key': key,
                'nonce': nonce,
                'rounds': 20
            })

            if not gpu_result or 'encrypted_data' not in gpu_result:
                raise Exception("GPU ChaCha20加密返回空结果")

            self.logger.info("✅ 纯GPU ChaCha20加密成功")

            metadata = {
                'algorithm': 'ChaCha20-GPU-ONLY',
                'key': key,
                'nonce': nonce,
                'rounds': 20,
                'gpu_accelerated': True,
                'gpu_only': True,
                'cpu_fallback': False,
                'gpu_performance': gpu_result.get('performance', {}),
                'backend_info': gpu_result.get('backend_info', 'GPU')
            }

            return gpu_result['encrypted_data'], metadata

        except Exception as e:
            raise Exception(f"纯GPU ChaCha20加密失败: {e}")

    def _encrypt_salsa20_gpu_only(self, data: bytes) -> tuple:
        """纯GPU Salsa20加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和nonce（确保长度正确）
            key = os.urandom(32)  # 256位密钥
            nonce = os.urandom(8)  # 64位nonce（Salsa20标准）

            self.logger.info(f"🚀 纯GPU Salsa20加密开始 - 数据大小: {len(data)} 字节")

            # 强制GPU加密，无回退
            gpu_result = gpu_manager.encrypt_data(data, 'salsa20', {
                'key': key,
                'nonce': nonce
            })

            if not gpu_result or 'encrypted_data' not in gpu_result:
                raise Exception("GPU Salsa20加密返回空结果")

            self.logger.info("✅ 纯GPU Salsa20加密成功")

            metadata = {
                'algorithm': 'Salsa20-GPU-ONLY',
                'key': key,
                'nonce': nonce,
                'gpu_accelerated': True,
                'gpu_only': True,
                'cpu_fallback': False,
                'gpu_performance': gpu_result.get('performance', {}),
                'backend_info': gpu_result.get('backend_info', 'GPU')
            }

            return gpu_result['encrypted_data'], metadata

        except Exception as e:
            raise Exception(f"纯GPU Salsa20加密失败: {e}")

    def _encrypt_matrix_cipher_gpu_only(self, data: bytes) -> tuple:
        """纯GPU矩阵变换加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os
            import random

            # 生成矩阵参数
            matrix_size = 8  # 8x8矩阵
            seed = random.randint(1000, 99999)
            original_length = len(data)

            self.logger.info(f"🚀 纯GPU矩阵变换加密开始 - 数据大小: {len(data)} 字节, 矩阵大小: {matrix_size}x{matrix_size}")

            # 强制GPU加密，无回退
            gpu_result = gpu_manager.encrypt_data(data, 'matrix_cipher', {
                'matrix_size': matrix_size,
                'seed': seed,
                'original_length': original_length
            })

            if not gpu_result or 'encrypted_data' not in gpu_result:
                raise Exception("GPU矩阵变换加密返回空结果")

            self.logger.info("✅ 纯GPU矩阵变换加密成功")

            metadata = {
                'algorithm': 'Matrix_Cipher-GPU-ONLY',
                'matrix_size': matrix_size,
                'seed': seed,
                'original_length': original_length,
                'gpu_accelerated': True,
                'gpu_only': True,
                'cpu_fallback': False,
                'gpu_performance': gpu_result.get('performance', {}),
                'backend_info': gpu_result.get('backend_info', 'GPU')
            }
            
            # 保存 transform_matrix 用于解密
            if 'transform_matrix' in gpu_result:
                metadata['transform_matrix'] = gpu_result['transform_matrix']

            return gpu_result['encrypted_data'], metadata

        except Exception as e:
            raise Exception(f"纯GPU矩阵变换加密失败: {e}")

    def _encrypt_blowfish_gpu_only(self, data: bytes) -> tuple:
        """纯GPU Blowfish加密"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            import os

            # 生成密钥和IV
            key = os.urandom(16)  # 128位密钥
            iv = os.urandom(8)    # 64位IV

            self.logger.info(f"🚀 纯GPU Blowfish加密开始 - 数据大小: {len(data)} 字节")

            # 强制GPU加密，无回退
            gpu_result = gpu_manager.encrypt_data(data, 'blowfish', {
                'key': key,
                'iv': iv,
                'mode': 'CBC'
            })

            if not gpu_result or 'encrypted_data' not in gpu_result:
                raise Exception("GPU Blowfish加密返回空结果")

            self.logger.info("✅ 纯GPU Blowfish加密成功")

            metadata = {
                'algorithm': 'Blowfish-GPU-ONLY',
                'mode': 'CBC',
                'key': key,
                'iv': iv,
                'gpu_accelerated': True,
                'gpu_only': True,
                'cpu_fallback': False,
                'gpu_performance': gpu_result.get('performance', {}),
                'backend_info': gpu_result.get('backend_info', 'GPU')
            }

            return gpu_result['encrypted_data'], metadata

        except Exception as e:
            raise Exception(f"纯GPU Blowfish加密失败: {e}")


def main():
    """测试纯GPU引擎"""
    print("🚀 纯GPU专用加密引擎测试")
    print("=" * 50)

    try:
        # 创建测试数据
        test_data = os.urandom(1024 * 1024)  # 1MB测试数据
        print(f"📁 测试数据: {len(test_data)} 字节")

        # 测试所有安全级别
        for level in range(1, 6):
            print(f"\n🔐 测试安全级别 {level}")
            print("-" * 30)

            try:
                engine = PureGPUOnlyEngine(security_level=level)

                start_time = time.time()
                result = engine.encrypt_with_security_level(test_data)
                end_time = time.time()

                print(f"✅ 级别{level}成功 - 耗时: {end_time - start_time:.3f}秒")
                print(f"   引擎: {result['metadata']['encryption_name']}")
                print(f"   层数: {result['metadata']['total_layers']}")
                print(f"   GPU专用: {result['metadata']['gpu_only']}")

            except Exception as e:
                print(f"❌ 级别{level}失败: {e}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    main()
