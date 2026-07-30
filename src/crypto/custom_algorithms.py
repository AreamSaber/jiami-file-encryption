"""
自定义加密算法实现
"""

import os
import random
from typing import Tuple, Dict, Any

from ..utils.logger import Logger


class CustomAlgorithms:
    """自定义加密算法类"""

    def __init__(self):
        """初始化自定义算法"""
        self.logger = Logger("CustomAlgorithms")

    def simple_xor_encrypt(self, data: bytes, key: bytes = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        简单XOR加密

        Args:
            data: 要加密的数据
            key: 密钥（可选）

        Returns:
            (加密数据, 元数据)
        """
        if key is None:
            import os
            key = os.urandom(len(data))

        encrypted_data = bytes(a ^ b for a, b in zip(data, key))

        metadata = {
            'algorithm': 'Simple_XOR',
            'key': key
        }

        self.logger.debug(f"XOR加密完成，数据大小: {len(encrypted_data)}")
        return encrypted_data, metadata

    def simple_xor_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """XOR解密"""
        key = metadata['key']
        decrypted_data = bytes(a ^ b for a, b in zip(encrypted_data, key))

        self.logger.debug(f"XOR解密完成，数据大小: {len(decrypted_data)}")
        return decrypted_data

    def bit_shuffle_encrypt(self, data: bytes, seed: int = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        位混洗加密

        Args:
            data: 要加密的数据
            seed: 随机种子

        Returns:
            (加密数据, 元数据)
        """
        if seed is None:
            seed = random.randint(1, 65535)

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

        self.logger.debug(f"位混洗加密完成，数据大小: {len(encrypted_data)}")
        return bytes(encrypted_data), metadata

    def bit_shuffle_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """位混洗解密"""
        bit_positions = metadata['bit_positions']

        # 创建逆映射
        reverse_positions = [0] * 8
        for i, pos in enumerate(bit_positions):
            reverse_positions[pos] = i

        decrypted_data = bytearray()
        for byte in encrypted_data:
            new_byte = 0
            for i, pos in enumerate(reverse_positions):
                if byte & (1 << i):
                    new_byte |= (1 << pos)
            decrypted_data.append(new_byte)

        self.logger.debug(f"位混洗解密完成，数据大小: {len(decrypted_data)}")
        return bytes(decrypted_data)

    def rotate_cipher_encrypt(self, data: bytes, rotation: int = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        旋转密码加密

        Args:
            data: 要加密的数据
            rotation: 旋转量

        Returns:
            (加密数据, 元数据)
        """
        if rotation is None:
            rotation = random.randint(1, 255)

        encrypted_data = bytearray()
        for byte in data:
            rotated = (byte + rotation) % 256
            encrypted_data.append(rotated)

        metadata = {
            'algorithm': 'Rotate_Cipher',
            'rotation': rotation
        }

        self.logger.debug(f"旋转密码加密完成，数据大小: {len(encrypted_data)}")
        return bytes(encrypted_data), metadata

    def rotate_cipher_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """旋转密码解密"""
        rotation = metadata['rotation']

        decrypted_data = bytearray()
        for byte in encrypted_data:
            rotated = (byte - rotation) % 256
            decrypted_data.append(rotated)

        self.logger.debug(f"旋转密码解密完成，数据大小: {len(decrypted_data)}")
        return bytes(decrypted_data)

    def substitution_cipher_encrypt(self, data: bytes, key: bytes = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        替换密码加密

        Args:
            data: 要加密的数据
            key: 替换表（256字节）

        Returns:
            (加密数据, 元数据)
        """
        if key is None:
            # 生成随机替换表
            key = list(range(256))
            random.shuffle(key)
            key = bytes(key)

        # 创建替换表
        substitution_table = list(key)

        encrypted_data = bytearray()
        for byte in data:
            encrypted_data.append(substitution_table[byte])

        metadata = {
            'algorithm': 'Substitution_Cipher',
            'substitution_table': substitution_table
        }

        self.logger.debug(f"替换密码加密完成，数据大小: {len(encrypted_data)}")
        return bytes(encrypted_data), metadata

    def substitution_cipher_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """替换密码解密"""
        substitution_table = metadata['substitution_table']

        # 创建逆替换表
        reverse_table = [0] * 256
        for i, val in enumerate(substitution_table):
            reverse_table[val] = i

        decrypted_data = bytearray()
        for byte in encrypted_data:
            decrypted_data.append(reverse_table[byte])

        self.logger.debug(f"替换密码解密完成，数据大小: {len(decrypted_data)}")
        return bytes(decrypted_data)

    def multi_layer_encrypt(self, data: bytes, layers: int = 3) -> Tuple[bytes, Dict[str, Any]]:
        """
        多层自定义加密

        Args:
            data: 要加密的数据
            layers: 加密层数

        Returns:
            (加密数据, 元数据)
        """
        encrypted_data = data
        layer_metadata = []

        algorithms = [
            self.simple_xor_encrypt,
            self.bit_shuffle_encrypt,
            self.rotate_cipher_encrypt
        ]

        for i in range(layers):
            algorithm = algorithms[i % len(algorithms)]
            encrypted_data, meta = algorithm(encrypted_data)
            meta['layer'] = i
            layer_metadata.append(meta)

        metadata = {
            'algorithm': 'Multi_Layer_Custom',
            'layers': layer_metadata,
            'layer_count': layers
        }

        self.logger.debug(f"多层加密完成，{layers}层，数据大小: {len(encrypted_data)}")
        return encrypted_data, metadata

    def multi_layer_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """多层自定义解密"""
        layer_metadata = metadata['layers']

        decrypted_data = encrypted_data

        # 逆序解密
        for layer_meta in reversed(layer_metadata):
            algorithm = layer_meta['algorithm']

            if algorithm == 'Simple_XOR':
                decrypted_data = self.simple_xor_decrypt(decrypted_data, layer_meta)
            elif algorithm == 'Bit_Shuffle':
                decrypted_data = self.bit_shuffle_decrypt(decrypted_data, layer_meta)
            elif algorithm == 'Rotate_Cipher':
                decrypted_data = self.rotate_cipher_decrypt(decrypted_data, layer_meta)
            elif algorithm == 'Substitution_Cipher':
                decrypted_data = self.substitution_cipher_decrypt(decrypted_data, layer_meta)

        self.logger.debug(f"多层解密完成，数据大小: {len(decrypted_data)}")
        return decrypted_data

    def get_available_algorithms(self) -> list:
        """获取可用的自定义算法"""
        return [
            'simple_xor',
            'bit_shuffle',
            'rotate_cipher',
            'substitution_cipher',
            'multi_layer'
        ]

    def encrypt(self, data: bytes, algorithm: str, **kwargs) -> Tuple[bytes, Dict[str, Any]]:
        """
        通用加密接口

        Args:
            data: 要加密的数据
            algorithm: 算法名称
            **kwargs: 算法参数

        Returns:
            (加密数据, 元数据)
        """
        if algorithm == 'simple_xor':
            return self.simple_xor_encrypt(data, kwargs.get('key'))
        elif algorithm == 'bit_shuffle':
            return self.bit_shuffle_encrypt(data, kwargs.get('seed'))
        elif algorithm == 'rotate_cipher':
            return self.rotate_cipher_encrypt(data, kwargs.get('rotation'))
        elif algorithm == 'substitution_cipher':
            return self.substitution_cipher_encrypt(data, kwargs.get('key'))
        elif algorithm == 'multi_layer':
            return self.multi_layer_encrypt(data, kwargs.get('layers', 3))
        else:
            raise ValueError(f"不支持的自定义算法: {algorithm}")

    def decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        通用解密接口

        Args:
            encrypted_data: 加密的数据
            metadata: 加密元数据

        Returns:
            解密后的数据
        """
        algorithm = metadata['algorithm']

        if algorithm == 'Simple_XOR':
            return self.simple_xor_decrypt(encrypted_data, metadata)
        elif algorithm == 'Bit_Shuffle':
            return self.bit_shuffle_decrypt(encrypted_data, metadata)
        elif algorithm == 'Rotate_Cipher':
            return self.rotate_cipher_decrypt(encrypted_data, metadata)
        elif algorithm == 'Substitution_Cipher':
            return self.substitution_cipher_decrypt(encrypted_data, metadata)
        elif algorithm == 'Multi_Layer_Custom':
            return self.multi_layer_decrypt(encrypted_data, metadata)
        else:
            raise ValueError(f"不支持的解密算法: {algorithm}")
