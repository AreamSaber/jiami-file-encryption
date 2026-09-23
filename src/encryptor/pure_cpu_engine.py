"""
纯CPU混合加密引擎
专门用于CPU算法的加密引擎，不涉及GPU计算
"""

import time
from typing import Dict, List, Optional, Any
from .hybrid_engine import HybridEncryptionEngine
from ..utils.logger import Logger


class PureCPUEngine(HybridEncryptionEngine):
    """纯CPU混合加密引擎"""

    def __init__(self, security_level: int = 1, max_threads: Optional[int] = None):
        """
        初始化纯CPU混合加密引擎

        Args:
            security_level: 安全级别 (1-5)
            max_threads: 最大线程数
        """
        super().__init__(max_threads)
        self.logger = Logger("PureCPUEngine")
        self.security_level = security_level

        # 强制CPU模式
        self._force_cpu_mode()

        # 根据安全级别配置算法
        self._configure_security_algorithms()

        self.logger.info(f"纯CPU引擎初始化完成 - 安全级别: {security_level}")

    def _force_cpu_mode(self):
        """强制CPU模式"""
        try:
            from src.gpu.gpu_manager import gpu_manager
            gpu_manager.force_cpu_mode = True
            self.logger.info("已强制启用CPU模式")
        except Exception as e:
            self.logger.debug(f"GPU管理器设置失败: {e}")

    def _configure_security_algorithms(self):
        """根据安全级别配置算法"""
        # 定义不同安全级别的算法组合
        self.security_algorithms = {
            1: {  # 基础安全
                'name': '基础CPU加密',
                'algorithms': ['aes256'],
                'description': '单层AES-256加密，适合日常文件'
            },
            2: {  # 标准安全
                'name': '标准CPU加密',
                'algorithms': ['chacha20', 'aes256'],
                'description': '双层加密，平衡性能和安全性'
            },
            3: {  # 高级安全
                'name': '高级CPU加密',
                'algorithms': ['rsa', 'chacha20', 'aes256'],
                'description': '三层加密，包含非对称加密'
            },
            4: {  # 隐蔽安全
                'name': '隐蔽CPU加密',
                'algorithms': ['rsa', 'aes256', 'steganography', 'custom'],
                'description': '包含隐写术的隐蔽加密'
            },
            5: {  # 偏执安全
                'name': '偏执CPU加密',
                'algorithms': ['custom', 'rsa', 'chacha20', 'aes256', 'custom', 'custom'],
                'description': '最高安全级别，多层复杂加密'
            }
        }

        # 获取当前安全级别配置
        current_config = self.security_algorithms.get(self.security_level, self.security_algorithms[1])
        self.current_algorithms = current_config['algorithms']
        self.encryption_name = current_config['name']
        self.encryption_description = current_config['description']

        self.logger.info(f"配置算法: {self.encryption_name}")
        self.logger.info(f"算法列表: {self.current_algorithms}")

    def get_encryption_config(self) -> Dict:
        """获取当前加密配置"""
        layers = []

        for i, algorithm in enumerate(self.current_algorithms):
            if algorithm == 'aes256':
                layers.append({
                    'method': 'aes256',
                    'mode': 'GCM',
                    'key_size': 256,
                    'params': {}
                })
            elif algorithm == 'chacha20':
                layers.append({
                    'method': 'chacha20',
                    'key_size': 256,
                    'params': {'rounds': 20}
                })
            elif algorithm == 'rsa':
                layers.append({
                    'method': 'rsa',
                    'key_size': 2048 if self.security_level <= 2 else 4096,
                    'params': {'padding': 'OAEP'}
                })
            elif algorithm == 'steganography':
                layers.append({
                    'method': 'steganography',
                    'cover_type': 'image',
                    'params': {
                        'format': 'PNG',
                        'channel': 'LSB'
                    }
                })
            elif algorithm == 'custom':
                # 根据层数选择不同的自定义算法
                custom_algorithms = ['pre_scramble', 'bit_shuffle', 'final_obfuscation']
                custom_alg = custom_algorithms[i % len(custom_algorithms)]
                layers.append({
                    'method': 'custom',
                    'algorithm': custom_alg,
                    'params': self._get_custom_params(custom_alg)
                })

        return {
            'strategy': 'threaded_layered',
            'layers': layers,
            'security_level': self.security_level,
            'engine_type': 'pure_cpu',
            'threading': {
                'auto_threading': True,
                'max_threads': 12,
                'parallel_threshold_mb': 1
            }
        }

    def _get_custom_params(self, algorithm: str) -> Dict:
        """获取自定义算法参数"""
        params = {
            'pre_scramble': {
                'scramble_rounds': min(3 + self.security_level, 8)
            },
            'bit_shuffle': {
                'seed': 'random',
                'rounds': min(2 + self.security_level, 6)
            },
            'final_obfuscation': {
                'obfuscation_level': ['low', 'medium', 'high', 'maximum', 'maximum'][self.security_level - 1]
            }
        }
        return params.get(algorithm, {})

    def encrypt_with_security_level(self, data: bytes, progress_callback=None) -> Dict:
        """
        使用指定安全级别加密数据

        Args:
            data: 要加密的数据
            progress_callback: 进度回调函数

        Returns:
            加密结果字典
        """
        config = self.get_encryption_config()

        self.logger.info(f"开始{self.encryption_name} - {len(data)} 字节")
        self.logger.info(f"描述: {self.encryption_description}")

        start_time = time.perf_counter()
        result = super().encrypt_data(data, config, progress_callback)
        end_time = time.perf_counter()

        # 添加CPU引擎特有的元数据
        result['cpu_engine_info'] = {
            'engine_type': 'pure_cpu',
            'security_level': self.security_level,
            'encryption_name': self.encryption_name,
            'algorithm_count': len(self.current_algorithms),
            'total_time': end_time - start_time,
            'cpu_optimized': True
        }

        self.logger.info(f"{self.encryption_name}完成 - 耗时: {end_time - start_time:.2f}秒")
        return result

    def get_supported_algorithms(self) -> List[str]:
        """获取支持的算法列表"""
        return [
            'aes256', 'chacha20', 'salsa20', 'blowfish', 'twofish',
            'rsa', 'steganography', 'simple_xor', 'bit_shuffle',
            'rotate_cipher', 'pre_scramble', 'final_obfuscation'
        ]

    def get_security_info(self) -> Dict:
        """获取安全级别信息"""
        return {
            'current_level': self.security_level,
            'available_levels': list(self.security_algorithms.keys()),
            'current_config': self.security_algorithms[self.security_level],
            'engine_type': 'pure_cpu'
        }


def create_cpu_test_config(security_level: int = 2) -> Dict:
    """创建CPU测试配置"""
    engine = PureCPUEngine(security_level=security_level)
    return engine.get_encryption_config()


if __name__ == "__main__":
    # 测试纯CPU引擎
    print("🖥️ 测试纯CPU混合加密引擎")
    print("=" * 50)

    # 测试不同安全级别
    for level in range(1, 6):
        print(f"\n📋 安全级别 {level}:")
        engine = PureCPUEngine(security_level=level)
        config = engine.get_encryption_config()

        print(f"   名称: {engine.encryption_name}")
        print(f"   算法: {engine.current_algorithms}")
        print(f"   层数: {len(config['layers'])}")
        print(f"   描述: {engine.encryption_description}")
