"""
Salsa20加密算法实现
"""

import os
from typing import Tuple, Dict, Any

from ..utils.logger import Logger


class Salsa20Encryption:
    """Salsa20加密算法类"""

    def __init__(self):
        """初始化Salsa20加密"""
        self.logger = Logger("Salsa20Encryption")

    def encrypt(self, data: bytes, key: bytes = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        Salsa20加密

        Args:
            data: 要加密的数据
            key: 32字节密钥（可选）

        Returns:
            (加密数据, 元数据)
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            import os

            # 生成密钥和nonce
            if key is None:
                key = os.urandom(32)  # 256位密钥
            nonce = os.urandom(8)   # 64位nonce

            # 创建加密器
            algorithm = algorithms.Salsa20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            encryptor = cipher.encryptor()

            # 加密数据
            encrypted_data = encryptor.update(data) + encryptor.finalize()

            metadata = {
                'algorithm': 'Salsa20',
                'key': key,
                'nonce': nonce
            }

            self.logger.debug(f"Salsa20加密完成，数据大小: {len(encrypted_data)}")
            return encrypted_data, metadata

        except ImportError:
            self.logger.error("cryptography库未安装，无法使用Salsa20加密")
            # 回退到简单XOR加密
            return self._fallback_encrypt(data, key)
        except Exception as e:
            self.logger.error(f"Salsa20加密失败: {e}")
            raise

    def decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Salsa20解密

        Args:
            encrypted_data: 加密的数据
            metadata: 加密元数据

        Returns:
            解密后的数据
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

            key = metadata['key']
            nonce = metadata['nonce']

            # 创建解密器
            algorithm = algorithms.Salsa20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()

            # 解密数据
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

            self.logger.debug(f"Salsa20解密完成，数据大小: {len(decrypted_data)}")
            return decrypted_data

        except ImportError:
            # 回退解密
            return self._fallback_decrypt(encrypted_data, metadata)
        except Exception as e:
            self.logger.error(f"Salsa20解密失败: {e}")
            raise

    def _fallback_encrypt(self, data: bytes, key: bytes = None) -> Tuple[bytes, Dict[str, Any]]:
        """回退加密方法（简单XOR）"""
        if key is None:
            key = os.urandom(len(data))

        encrypted_data = bytes(a ^ b for a, b in zip(data, key))

        metadata = {
            'algorithm': 'Salsa20_Fallback',
            'key': key
        }

        return encrypted_data, metadata

    def _fallback_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """回退解密方法"""
        key = metadata['key']
        return bytes(a ^ b for a, b in zip(encrypted_data, key))

    def generate_key(self) -> bytes:
        """生成Salsa20密钥"""
        return os.urandom(32)

    def get_recommended_config(self) -> Dict[str, Any]:
        """获取推荐配置"""
        return {
            'description': 'Salsa20提供高性能的流加密',
            'key_size': 256,
            'nonce_size': 64
        }
