#!/usr/bin/env python3
"""
GPU加密数据专用解密器模板 v2.0
专门用于解密纯GPU混合加密引擎生成的加密文件

使用CPU算法解密GPU加密的数据，确保兼容性和可靠性
此文件是独立的解密器模板，不依赖外部模块
"""

import os
import sys
import pickle
import base64
import json
import hashlib
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod

# 加密元数据占位符 - 将被实际数据替换
ENCRYPTION_METADATA = b"__METADATA_PLACEHOLDER__"

# 版本信息
VERSION = "2.0.0"
ENGINE_TYPE = "GPU"


# ============ 异常类 ============

class DecryptionError(Exception):
    """解密错误"""
    def __init__(self, message: str, error_code: str = "DEC000", context: Dict = None):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(f"[{error_code}] {message}")


class AlgorithmNotSupportedError(DecryptionError):
    """算法不支持错误"""
    def __init__(self, algorithm: str):
        super().__init__(
            f"不支持的算法: {algorithm}",
            error_code="DEC001",
            context={'algorithm': algorithm}
        )


# ============ 算法处理器 ============

class AlgorithmHandler(ABC):
    """算法处理器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    def aliases(self) -> list:
        return []
    
    @abstractmethod
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        pass


class AES256Handler(AlgorithmHandler):
    """AES-256算法处理器"""
    
    @property
    def name(self) -> str:
        return "AES-256"
    
    @property
    def aliases(self) -> list:
        return ["AES-256-GPU", "AES-256-GPU-ONLY", "aes256", "AES256"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        
        key = self._decode_bytes(params['key'])
        iv = self._decode_bytes(params['iv'])
        mode_name = params.get('mode', 'CBC')
        
        if mode_name == 'GCM':
            tag = params.get('tag')
            if not tag:
                raise DecryptionError("GCM模式需要认证标签", "DEC002")
            tag = self._decode_bytes(tag)
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        else:
            if len(iv) != 16:
                iv = iv[:16] if len(iv) > 16 else iv + b'\x00' * (16 - len(iv))
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(data) + decryptor.finalize()
            try:
                unpadder = padding.PKCS7(128).unpadder()
                return unpadder.update(decrypted) + unpadder.finalize()
            except:
                return decrypted


class ChaCha20Handler(AlgorithmHandler):
    """ChaCha20算法处理器（支持GPU自定义实现）"""
    
    @property
    def name(self) -> str:
        return "ChaCha20"
    
    @property
    def aliases(self) -> list:
        return ["ChaCha20-GPU", "ChaCha20-GPU-ONLY", "chacha20"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = self._decode_bytes(params['key'])
        nonce = self._decode_bytes(params['nonce'])
        
        # 检查是否是GPU自定义实现
        backend_info = params.get('backend_info', '')
        if 'GPU' in backend_info or params.get('gpu_only', False):
            return self._decrypt_gpu_custom(data, key, nonce)
        
        # 标准ChaCha20解密
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        
        if len(nonce) != 16:
            nonce = nonce[:16] if len(nonce) > 16 else nonce + b'\x00' * (16 - len(nonce))
        
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()
    
    def _decrypt_gpu_custom(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """解密GPU自定义ChaCha20 - 与OpenCL内核完全匹配
        
        OpenCL内核逻辑:
        keystream = key_byte ^ nonce_byte
        keystream ^= (gid & 0xFF)
        keystream = (keystream << 3) | (keystream >> 5)  // 旋转
        keystream ^= ((gid >> 8) & 0xFF)
        for i in range(20):
            keystream += key_byte
            keystream ^= (keystream << 1)
            keystream += nonce_byte
            keystream ^= (keystream >> 1)
        """
        # 纯Python实现，不依赖numpy
        result = bytearray(len(data))
        
        for gid in range(len(data)):
            byte_val = data[gid]
            key_byte = key[gid % 32]
            nonce_byte = nonce[gid % 16]
            
            # 生成密钥流字节 - 与OpenCL内核完全匹配
            keystream = key_byte ^ nonce_byte
            keystream ^= (gid & 0xFF)  # 位置相关
            keystream = ((keystream << 3) | (keystream >> 5)) & 0xFF  # 旋转
            keystream ^= ((gid >> 8) & 0xFF)  # 高位影响
            
            # ChaCha20风格的四分之一轮 - 20轮
            for _ in range(20):
                keystream = (keystream + key_byte) & 0xFF
                keystream ^= (keystream << 1) & 0xFF
                keystream = (keystream + nonce_byte) & 0xFF
                keystream ^= (keystream >> 1) & 0xFF
            
            result[gid] = byte_val ^ keystream
        
        return bytes(result)


class Salsa20Handler(AlgorithmHandler):
    """Salsa20算法处理器 - 匹配GPU OpenCL实现"""
    
    @property
    def name(self) -> str:
        return "Salsa20"
    
    @property
    def aliases(self) -> list:
        return ["Salsa20-GPU", "Salsa20-GPU-ONLY", "salsa20"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = self._decode_bytes(params['key'])
        nonce = self._decode_bytes(params['nonce'])
        
        # 检查是否是GPU自定义实现
        backend_info = params.get('backend_info', '')
        if 'GPU' in backend_info or params.get('gpu_only', False):
            return self._decrypt_gpu_custom(data, key, nonce)
        
        # 标准Salsa20解密
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            cipher = Cipher(algorithms.Salsa20(key, nonce), mode=None)
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        except:
            return self._decrypt_gpu_custom(data, key, nonce)
    
    def _decrypt_gpu_custom(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """解密GPU自定义Salsa20 - 与OpenCL内核完全匹配
        
        OpenCL内核逻辑:
        keystream = key_byte ^ nonce_byte
        keystream ^= (gid & 0xFF)
        for i in range(10):
            keystream += key_byte
            keystream ^= (keystream << 1)
            keystream += nonce_byte
            keystream ^= (keystream >> 1)
            keystream += ((gid >> (i % 8)) & 0xFF)
            keystream = (keystream << 2) | (keystream >> 6)  // 旋转
        keystream ^= key[(gid + 16) % 32]
        keystream += nonce[(gid + 4) % 8]
        keystream ^= (keystream << 3) | (keystream >> 5)
        """
        # 确保nonce长度正确
        if len(nonce) < 8:
            nonce = nonce + b'\x00' * (8 - len(nonce))
        
        result = bytearray(len(data))
        
        for gid in range(len(data)):
            byte_val = data[gid]
            key_byte = key[gid % 32]
            nonce_byte = nonce[gid % 8]  # Salsa20使用8字节nonce
            
            # 生成密钥流字节 - 与OpenCL内核完全匹配
            keystream = key_byte ^ nonce_byte
            keystream ^= (gid & 0xFF)  # 位置相关
            
            # Salsa20的四分之一轮操作 (简化版) - 10轮
            for i in range(10):
                keystream = (keystream + key_byte) & 0xFF
                keystream ^= (keystream << 1) & 0xFF
                keystream = (keystream + nonce_byte) & 0xFF
                keystream ^= (keystream >> 1) & 0xFF
                keystream = (keystream + ((gid >> (i % 8)) & 0xFF)) & 0xFF
                keystream = ((keystream << 2) | (keystream >> 6)) & 0xFF  # 旋转
            
            # 额外的混合 - 与OpenCL内核完全匹配
            keystream ^= key[(gid + 16) % 32]
            keystream = (keystream + nonce[(gid + 4) % 8]) & 0xFF
            keystream ^= ((keystream << 3) | (keystream >> 5)) & 0xFF
            
            result[gid] = byte_val ^ keystream
        
        return bytes(result)


class MatrixCipherHandler(AlgorithmHandler):
    """矩阵变换算法处理器 - 支持新旧两种格式
    
    旧格式: 矩阵乘法 (result = data @ matrix % 256)
    新格式: XOR变换 (可逆)
    """
    
    @property
    def name(self) -> str:
        return "Matrix_Cipher"
    
    @property
    def aliases(self) -> list:
        return ["Matrix_Cipher-GPU", "Matrix_Cipher-GPU-ONLY", "matrix_cipher"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        matrix_size = params.get('matrix_size', 8)
        seed = params.get('seed', 12345)
        original_length = params.get('original_length', len(data))
        transform_matrix = params.get('transform_matrix', None)
        
        # 检测加密版本：如果有transform_matrix，使用新版XOR解密
        # 如果没有transform_matrix，尝试旧版矩阵乘法解密
        use_xor = transform_matrix is not None
        
        try:
            import numpy as np
            if use_xor:
                return self._decrypt_xor_numpy(data, matrix_size, seed, original_length, transform_matrix)
            else:
                # 旧版本：尝试矩阵乘法解密
                return self._decrypt_matrix_mult_numpy(data, matrix_size, seed, original_length)
        except ImportError:
            if use_xor:
                return self._decrypt_xor_python(data, matrix_size, seed, original_length, transform_matrix)
            else:
                return self._decrypt_matrix_mult_python(data, matrix_size, seed, original_length)
    
    def _decrypt_xor_numpy(self, data: bytes, matrix_size: int, seed: int, original_length: int, saved_matrix=None) -> bytes:
        """XOR变换解密（新版本）"""
        import numpy as np
        
        if saved_matrix is not None:
            transform_matrix = np.array(saved_matrix, dtype=np.uint8).flatten()
        else:
            np.random.seed(seed)
            transform_matrix = np.random.randint(0, 256, (matrix_size, matrix_size), dtype=np.uint8).flatten()
        
        block_size = matrix_size * matrix_size
        
        data_arr = np.frombuffer(data, dtype=np.uint8)
        padded_len = ((len(data_arr) + block_size - 1) // block_size) * block_size
        padded = np.zeros(padded_len, dtype=np.uint8)
        padded[:len(data_arr)] = data_arr
        
        result = np.zeros_like(padded)
        
        for gid in range(len(padded)):
            local_id = gid % block_size
            row = local_id // matrix_size
            col = local_id % matrix_size
            
            byte_val = padded[gid]
            matrix_idx = (row * matrix_size + col) % block_size
            
            byte_val ^= transform_matrix[(gid + row) % block_size]
            byte_val = ((byte_val >> 3) | (byte_val << 5)) & 0xFF
            byte_val ^= (gid & 0xFF)
            byte_val ^= transform_matrix[matrix_idx]
            
            result[gid] = byte_val
        
        return result[:original_length].tobytes()
    
    def _decrypt_matrix_mult_numpy(self, data: bytes, matrix_size: int, seed: int, original_length: int) -> bytes:
        """矩阵乘法解密（旧版本）- 使用伪逆矩阵"""
        import numpy as np
        
        np.random.seed(seed)
        transform_matrix = np.random.randint(0, 256, (matrix_size, matrix_size), dtype=np.uint8)
        
        # 计算伪逆矩阵
        try:
            matrix_float = transform_matrix.astype(np.float64)
            # 使用Moore-Penrose伪逆
            inv_matrix = np.linalg.pinv(matrix_float)
            # 缩放到0-255范围
            inv_matrix = np.round(inv_matrix * 256).astype(np.int64) % 256
            inv_matrix = inv_matrix.astype(np.uint8)
        except:
            # 如果伪逆失败，使用转置
            inv_matrix = transform_matrix.T
        
        block_size = matrix_size * matrix_size
        
        data_arr = np.frombuffer(data, dtype=np.uint8)
        padded_len = ((len(data_arr) + block_size - 1) // block_size) * block_size
        padded = np.zeros(padded_len, dtype=np.uint8)
        padded[:len(data_arr)] = data_arr
        
        result = np.zeros_like(padded)
        
        # 按块处理
        for block_id in range(padded_len // block_size):
            block_start = block_id * block_size
            block_data = padded[block_start:block_start + block_size].reshape(matrix_size, matrix_size)
            
            # 逆矩阵变换
            decrypted_block = np.zeros((matrix_size, matrix_size), dtype=np.uint8)
            for row in range(matrix_size):
                for col in range(matrix_size):
                    val = 0
                    for k in range(matrix_size):
                        val += int(block_data[row, k]) * int(inv_matrix[k, col])
                    decrypted_block[row, col] = val % 256
            
            result[block_start:block_start + block_size] = decrypted_block.flatten()
        
        return result[:original_length].tobytes()
    
    def _decrypt_xor_python(self, data: bytes, matrix_size: int, seed: int, original_length: int, saved_matrix=None) -> bytes:
        """XOR变换解密（纯Python）"""
        if saved_matrix is not None:
            if isinstance(saved_matrix, list):
                transform_list = []
                for row in saved_matrix:
                    transform_list.extend(row)
            else:
                transform_list = list(saved_matrix.flatten())
        else:
            try:
                import numpy as np
                np.random.seed(seed)
                transform_matrix = np.random.randint(0, 256, (matrix_size, matrix_size), dtype=np.uint8)
                transform_list = list(transform_matrix.flatten())
            except ImportError:
                random.seed(seed)
                transform_list = [random.randint(0, 255) for _ in range(matrix_size * matrix_size)]
        
        block_size = matrix_size * matrix_size
        
        # 填充数据
        data_list = list(data)
        padded_len = ((len(data_list) + block_size - 1) // block_size) * block_size
        padded = data_list + [0] * (padded_len - len(data_list))
        
        result = []
        
        # 逐字节解密
        for gid in range(len(padded)):
            local_id = gid % block_size
            row = local_id // matrix_size
            col = local_id % matrix_size
            
            byte_val = padded[gid]
            matrix_idx = (row * matrix_size + col) % block_size
            
            # 逆操作4
            byte_val ^= transform_list[(gid + row) % block_size]
            
            # 逆操作3: 逆旋转
            byte_val = ((byte_val >> 3) | (byte_val << 5)) & 0xFF
            
            # 逆操作2
            byte_val ^= (gid & 0xFF)
            
            # 逆操作1
            byte_val ^= transform_list[matrix_idx]
            
            result.append(byte_val)
        
        return bytes(result[:original_length])


class BlowfishHandler(AlgorithmHandler):
    """Blowfish算法处理器"""
    
    @property
    def name(self) -> str:
        return "Blowfish"
    
    @property
    def aliases(self) -> list:
        return ["Blowfish-GPU", "Blowfish-GPU-ONLY", "blowfish"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        
        key = self._decode_bytes(params['key'])
        iv = params.get('iv')
        if iv:
            iv = self._decode_bytes(iv)
        
        if iv:
            cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        else:
            cipher = Cipher(algorithms.Blowfish(key), modes.ECB())
        
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data) + decryptor.finalize()
        
        try:
            unpadder = padding.PKCS7(64).unpadder()
            return unpadder.update(decrypted) + unpadder.finalize()
        except:
            return decrypted


class RSAHandler(AlgorithmHandler):
    """RSA算法处理器"""
    
    @property
    def name(self) -> str:
        return "RSA"
    
    @property
    def aliases(self) -> list:
        return ["RSA-Hybrid", "rsa"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        aes_metadata = params.get('aes_metadata', {})
        if aes_metadata and 'key' in aes_metadata:
            handler = AES256Handler()
            return handler.decrypt(data, aes_metadata)
        return data


# ============ 算法注册表 ============

class AlgorithmRegistry:
    """算法注册表"""
    
    _handlers: Dict[str, AlgorithmHandler] = {}
    _initialized: bool = False
    
    def __init__(self):
        if not AlgorithmRegistry._initialized:
            self._register_default_algorithms()
            AlgorithmRegistry._initialized = True
    
    def _register_default_algorithms(self):
        handlers = [
            AES256Handler(),
            ChaCha20Handler(),
            Salsa20Handler(),
            MatrixCipherHandler(),
            BlowfishHandler(),
            RSAHandler(),
        ]
        for handler in handlers:
            self._handlers[handler.name] = handler
            for alias in handler.aliases:
                self._handlers[alias] = handler
    
    def get_handler(self, name: str) -> AlgorithmHandler:
        normalized = name.replace('-', '_').replace(' ', '_')
        
        if name in self._handlers:
            return self._handlers[name]
        if normalized in self._handlers:
            return self._handlers[normalized]
        
        name_lower = name.lower()
        for key, handler in self._handlers.items():
            if key.lower() == name_lower:
                return handler
        
        raise AlgorithmNotSupportedError(name)


# ============ GPU解密器核心 ============

class GPUDecryptor:
    """GPU加密数据专用解密器 v2.0"""
    
    def __init__(self):
        self.registry = AlgorithmRegistry()
        self.log_callback = None
    
    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
    
    def decrypt_file(self, encrypted_file: str, output_file: str = None) -> Dict[str, Any]:
        """解密文件"""
        result = {
            'success': False,
            'output_file': None,
            'decrypted_size': 0,
            'error': None
        }
        
        try:
            self.log(f"🔓 开始解密: {os.path.basename(encrypted_file)}")
            
            with open(encrypted_file, 'rb') as f:
                encrypted_package = pickle.load(f)
            
            if not self._verify_gpu_encryption(encrypted_package):
                raise DecryptionError("此文件不是GPU引擎加密的文件", "DEC003")
            
            metadata = encrypted_package['metadata']
            encrypted_data = encrypted_package['encrypted_data']
            layers = metadata.get('layers', [])
            
            self.log(f"📋 安全级别: {metadata.get('security_level', 'unknown')}")
            self.log(f"📋 加密层数: {len(layers)}")
            self.log(f"📋 数据大小: {len(encrypted_data):,} 字节")
            self.log(f"📋 解密模式: CPU算法解密GPU数据")
            
            decrypted_data = self._decrypt_layers(encrypted_data, layers)
            
            # 获取原始大小 - 优先从metadata，然后从包顶层
            original_size = metadata.get('original_size') or encrypted_package.get('original_size')
            if original_size:
                self.log(f"📋 原始大小: {original_size:,} 字节")
                if len(decrypted_data) > original_size:
                    self.log(f"📋 截断数据: {len(decrypted_data):,} -> {original_size:,} 字节")
                    decrypted_data = decrypted_data[:original_size]
                elif len(decrypted_data) < original_size:
                    self.log(f"⚠️ 警告: 解密数据小于原始大小: {len(decrypted_data):,} < {original_size:,}")
            
            if output_file is None:
                output_file = self._generate_output_path(encrypted_file)
            
            output_dir = self._create_output_folder(output_file)
            final_path = os.path.join(output_dir, os.path.basename(output_file))
            
            with open(final_path, 'wb') as f:
                f.write(decrypted_data)
            
            self.log(f"✅ 解密完成: {os.path.basename(final_path)}")
            self.log(f"📁 输出大小: {len(decrypted_data):,} 字节")
            
            result['success'] = True
            result['output_file'] = final_path
            result['decrypted_size'] = len(decrypted_data)
            
        except Exception as e:
            self.log(f"❌ 解密失败: {e}")
            result['error'] = str(e)
        
        return result
    
    def _verify_gpu_encryption(self, package: Dict) -> bool:
        """验证是否为GPU引擎加密"""
        metadata = package.get('metadata', {})
        
        if metadata.get('engine_type') == 'pure_gpu':
            return True
        if 'gpu_engine_info' in metadata:
            return True
        if metadata.get('gpu_only', False):
            return True
        
        layers = metadata.get('layers', [])
        gpu_count = 0
        for layer in layers:
            algorithm = layer.get('algorithm', '')
            if 'GPU' in algorithm or layer.get('gpu_accelerated', False):
                gpu_count += 1
        
        return gpu_count > len(layers) // 2
    
    def _decrypt_layers(self, data: bytes, layers: List[Dict]) -> bytes:
        """逐层解密"""
        decrypted = data
        
        for i, layer in enumerate(reversed(layers)):
            layer_idx = len(layers) - i
            algorithm = layer.get('algorithm', 'unknown')
            
            self.log(f"🔓 解密第 {layer_idx} 层: {algorithm}")
            
            try:
                handler = self.registry.get_handler(algorithm)
                decrypted = handler.decrypt(decrypted, layer)
                self.log(f"   ✅ 成功")
            except Exception as e:
                self.log(f"   ❌ 失败: {e}")
                raise
        
        return decrypted
    
    def _generate_output_path(self, encrypted_file: str) -> str:
        base = os.path.splitext(encrypted_file)[0]
        if base.endswith('.encrypted'):
            base = base[:-10]
        return base + '_decrypted'
    
    def _create_output_folder(self, output_path: str) -> str:
        try:
            output_dir = os.path.dirname(os.path.abspath(output_path))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            folder_name = f"GPU解密_{base_name}_{timestamp}"
            
            decrypted_folder = os.path.join(output_dir, folder_name)
            os.makedirs(decrypted_folder, exist_ok=True)
            
            self.log(f"📁 创建解密文件夹: {folder_name}")
            return decrypted_folder
        except:
            return os.path.dirname(os.path.abspath(output_path))


# ============ GUI界面 ============

def start_gui():
    """启动GUI解密器"""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
    
    class GPUDecryptorGUI:
        def __init__(self, root):
            self.root = root
            self.root.title(f"GPU加密数据解密器 v{VERSION}")
            self.root.geometry("700x550")
            self.root.minsize(600, 450)
            
            self.decryptor = GPUDecryptor()
            self.decryptor.set_log_callback(self.log)
            self.last_output_dir = None
            
            self.setup_ui()
        
        def setup_ui(self):
            main = ttk.Frame(self.root, padding=15)
            main.grid(row=0, column=0, sticky="nsew")
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)
            main.columnconfigure(0, weight=1)
            
            ttk.Label(main, text="🔓 GPU加密数据解密器",
                     font=("Arial", 18, "bold")).grid(row=0, column=0, pady=(0, 5))
            ttk.Label(main, text=f"v{VERSION} | 使用CPU算法解密GPU加密的数据，无需GPU硬件",
                     font=("Arial", 9), foreground="gray").grid(row=1, column=0, pady=(0, 15))
            
            file_frame = ttk.LabelFrame(main, text="📁 选择加密文件", padding=10)
            file_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
            file_frame.columnconfigure(0, weight=1)
            
            path_frame = ttk.Frame(file_frame)
            path_frame.grid(row=0, column=0, sticky="ew")
            path_frame.columnconfigure(0, weight=1)
            
            self.file_var = tk.StringVar()
            ttk.Entry(path_frame, textvariable=self.file_var,
                     font=("Arial", 10)).grid(row=0, column=0, sticky="ew", padx=(0, 10))
            ttk.Button(path_frame, text="浏览...",
                      command=self.browse_file).grid(row=0, column=1)
            
            btn_frame = ttk.Frame(file_frame)
            btn_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))
            ttk.Button(btn_frame, text="🔍 自动查找",
                      command=self.auto_find).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(btn_frame, text="🗑️ 清空",
                      command=self.clear).pack(side=tk.LEFT)
            
            out_frame = ttk.LabelFrame(main, text="📂 输出目录（可选）", padding=10)
            out_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
            out_frame.columnconfigure(0, weight=1)
            
            out_path = ttk.Frame(out_frame)
            out_path.grid(row=0, column=0, sticky="ew")
            out_path.columnconfigure(0, weight=1)
            
            self.output_var = tk.StringVar()
            ttk.Entry(out_path, textvariable=self.output_var,
                     font=("Arial", 10)).grid(row=0, column=0, sticky="ew", padx=(0, 10))
            ttk.Button(out_path, text="选择...",
                      command=self.browse_output).grid(row=0, column=1)
            
            action_frame = ttk.Frame(main)
            action_frame.grid(row=4, column=0, pady=15)
            
            self.decrypt_btn = ttk.Button(action_frame, text="🔓 开始解密",
                                         command=self.decrypt)
            self.decrypt_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            self.open_btn = ttk.Button(action_frame, text="📂 打开输出目录",
                                      command=self.open_output, state=tk.DISABLED)
            self.open_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Button(action_frame, text="退出",
                      command=self.root.quit).pack(side=tk.LEFT)
            
            self.progress = ttk.Progressbar(main, mode='determinate')
            self.progress.grid(row=5, column=0, sticky="ew", pady=(0, 10))
            
            self.status_var = tk.StringVar(value="就绪")
            ttk.Label(main, textvariable=self.status_var).grid(row=6, column=0, sticky="w")
            
            log_frame = ttk.LabelFrame(main, text="📋 解密日志", padding=10)
            log_frame.grid(row=7, column=0, sticky="nsew", pady=(10, 0))
            log_frame.columnconfigure(0, weight=1)
            log_frame.rowconfigure(0, weight=1)
            main.rowconfigure(7, weight=1)
            
            self.log_text = ScrolledText(log_frame, height=8, font=("Consolas", 9))
            self.log_text.grid(row=0, column=0, sticky="nsew")
            
            self.log(f"🔓 GPU加密数据解密器 v{VERSION} 已启动")
            self.log("💡 使用CPU算法解密GPU加密的数据，无需GPU硬件")
        
        def browse_file(self):
            f = filedialog.askopenfilename(
                title="选择GPU加密文件",
                filetypes=[("加密文件", "*.encrypted"), ("所有文件", "*.*")]
            )
            if f:
                self.file_var.set(f)
                self.log(f"✅ 已选择: {os.path.basename(f)}")
        
        def browse_output(self):
            d = filedialog.askdirectory(title="选择输出目录")
            if d:
                self.output_var.set(d)
        
        def auto_find(self):
            files = [f for f in os.listdir('.') if f.endswith('.encrypted')]
            if not files:
                messagebox.showinfo("提示", "当前目录未找到加密文件")
                return
            self.file_var.set(os.path.abspath(files[0]))
            self.log(f"✅ 自动选择: {files[0]}")
        
        def clear(self):
            self.file_var.set("")
            self.output_var.set("")
            self.progress['value'] = 0
        
        def decrypt(self):
            path = self.file_var.get().strip()
            if not path:
                messagebox.showerror("错误", "请选择文件")
                return
            if not os.path.exists(path):
                messagebox.showerror("错误", "文件不存在")
                return
            
            output = self.output_var.get().strip() or None
            
            self.decrypt_btn.config(state=tk.DISABLED)
            self.status_var.set("解密中...")
            self.progress['value'] = 30
            self.root.update()
            
            try:
                self.log("=" * 50)
                result = self.decryptor.decrypt_file(path, output)
                self.progress['value'] = 100
                
                if result['success']:
                    self.status_var.set("✅ 解密成功")
                    self.last_output_dir = os.path.dirname(result['output_file'])
                    self.open_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("成功",
                        f"解密成功!\n\n输出: {os.path.basename(result['output_file'])}\n"
                        f"大小: {result['decrypted_size']:,} 字节")
                else:
                    self.status_var.set("❌ 解密失败")
                    messagebox.showerror("失败", f"解密失败:\n{result['error']}")
            except Exception as e:
                self.status_var.set("❌ 错误")
                messagebox.showerror("错误", str(e))
            finally:
                self.decrypt_btn.config(state=tk.NORMAL)
        
        def open_output(self):
            if self.last_output_dir and os.path.exists(self.last_output_dir):
                if sys.platform == 'win32':
                    os.startfile(self.last_output_dir)
        
        def log(self, msg: str):
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_text.see(tk.END)
            self.root.update()
    
    root = tk.Tk()
    app = GPUDecryptorGUI(root)
    root.mainloop()


def main():
    """主函数"""
    if len(sys.argv) > 1 and '--cli' in sys.argv:
        import argparse
        parser = argparse.ArgumentParser(description=f"GPU加密数据解密器 v{VERSION}")
        parser.add_argument("encrypted_file", help="加密文件路径")
        parser.add_argument("-o", "--output", help="输出文件路径")
        parser.add_argument("--cli", action="store_true")
        
        args = parser.parse_args()
        
        print(f"GPU加密数据解密器 v{VERSION}")
        print("=" * 40)
        print("使用CPU算法解密GPU加密的数据")
        
        decryptor = GPUDecryptor()
        result = decryptor.decrypt_file(args.encrypted_file, args.output)
        sys.exit(0 if result['success'] else 1)
    else:
        try:
            start_gui()
        except ImportError:
            print(f"GPU加密数据解密器 v{VERSION}")
            print("=" * 40)
            print("GUI不可用，使用自动模式...")
            
            decryptor = GPUDecryptor()
            for f in os.listdir('.'):
                if f.endswith('.encrypted'):
                    print(f"找到: {f}")
                    decryptor.decrypt_file(f)
            
            input("按回车键退出...")


if __name__ == "__main__":
    main()
