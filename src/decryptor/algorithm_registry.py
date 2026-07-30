#!/usr/bin/env python3
"""
算法注册表模块

管理所有加密/解密算法的注册和获取
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.exceptions import AlgorithmNotSupportedError


class AlgorithmHandler(ABC):
    """
    算法处理器抽象基类
    
    定义加密/解密算法的统一接口
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """算法名称"""
        pass
    
    @property
    def aliases(self) -> list:
        """算法别名列表"""
        return []
    
    @abstractmethod
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        """
        解密数据
        
        Args:
            data: 加密数据
            params: 解密参数（包含密钥、IV等）
            
        Returns:
            解密后的数据
        """
        pass
    
    def encrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        """
        加密数据（可选实现）
        
        Args:
            data: 原始数据
            params: 加密参数
            
        Returns:
            加密后的数据
        """
        raise NotImplementedError(f"{self.name} 不支持加密操作")


class AlgorithmRegistry:
    """
    算法注册表
    
    管理所有加密/解密算法的注册和获取
    """
    
    _handlers: Dict[str, AlgorithmHandler] = {}
    _initialized: bool = False
    
    def __init__(self):
        """初始化注册表并注册默认算法"""
        if not AlgorithmRegistry._initialized:
            self._register_default_algorithms()
            AlgorithmRegistry._initialized = True
    
    @classmethod
    def register(cls, handler: AlgorithmHandler) -> None:
        """注册算法处理器"""
        cls._handlers[handler.name] = handler
        for alias in handler.aliases:
            cls._handlers[alias] = handler
    
    @classmethod
    def get_handler(cls, name: str) -> AlgorithmHandler:
        """获取算法处理器"""
        if name not in cls._handlers:
            raise AlgorithmNotSupportedError(
                algorithm=name,
                supported_algorithms=list(set(h.name for h in cls._handlers.values()))
            )
        return cls._handlers[name]
    
    @classmethod
    def list_algorithms(cls) -> list:
        """列出所有注册的算法"""
        return list(set(h.name for h in cls._handlers.values()))
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """检查算法是否已注册"""
        return name in cls._handlers
    
    def _register_default_algorithms(self) -> None:
        """注册默认算法"""
        self.register(AES256Handler())
        self.register(ChaCha20Handler())
        self.register(Salsa20Handler())
        self.register(BlowfishHandler())
        self.register(SimpleXORHandler())
        self.register(BitShuffleHandler())
        self.register(RotateCipherHandler())
        self.register(MatrixCipherHandler())
        self.register(PreScrambleHandler())
        self.register(FinalObfuscationHandler())


# ============ 具体算法实现 ============

class AES256Handler(AlgorithmHandler):
    """AES-256算法处理器"""
    
    @property
    def name(self) -> str:
        return "AES-256"
    
    @property
    def aliases(self) -> list:
        return ["AES-256-CPU", "AES-256-GPU", "AES-256-GPU-ONLY", "aes256"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        
        key = params['key']
        iv = params['iv']
        mode = params.get('mode', 'CBC')
        
        if mode == 'GCM':
            tag = params.get('tag')
            if not tag:
                raise ValueError("GCM模式需要认证标签")
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        else:  # CBC
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


class BlowfishHandler(AlgorithmHandler):
    """Blowfish算法处理器"""
    
    @property
    def name(self) -> str:
        return "Blowfish"
    
    @property
    def aliases(self) -> list:
        return ["Blowfish-CPU", "Blowfish-GPU", "Blowfish-GPU-ONLY", "blowfish"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        
        key = params['key']
        iv = params.get('iv')
        mode_name = params.get('mode', 'CBC')
        
        if iv and mode_name == 'CBC':
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


class ChaCha20Handler(AlgorithmHandler):
    """ChaCha20算法处理器 - 支持标准和GPU-ONLY版本"""
    
    @property
    def name(self) -> str:
        return "ChaCha20"
    
    @property
    def aliases(self) -> list:
        return ["ChaCha20-CPU", "ChaCha20-GPU", "ChaCha20-GPU-ONLY", "chacha20"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        nonce = params.get('nonce') or params.get('iv')
        
        # GPU-ONLY 版本使用自定义实现
        if params.get('gpu_only') or 'GPU-ONLY' in params.get('algorithm', ''):
            return self._decrypt_gpu_only(data, key, nonce)
        
        # 标准版本使用 cryptography 库
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        
        # ChaCha20 需要 16 字节 nonce
        if len(nonce) < 16:
            nonce = nonce + b'\x00' * (16 - len(nonce))
        elif len(nonce) > 16:
            nonce = nonce[:16]
        
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()
    
    def _decrypt_gpu_only(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """GPU-ONLY 版本的 ChaCha20 解密（与 OpenCL 内核匹配）"""
        import struct
        
        def quarter_round(state, a, b, c, d):
            state[a] = (state[a] + state[b]) & 0xFFFFFFFF
            state[d] ^= state[a]
            state[d] = ((state[d] << 16) | (state[d] >> 16)) & 0xFFFFFFFF
            state[c] = (state[c] + state[d]) & 0xFFFFFFFF
            state[b] ^= state[c]
            state[b] = ((state[b] << 12) | (state[b] >> 20)) & 0xFFFFFFFF
            state[a] = (state[a] + state[b]) & 0xFFFFFFFF
            state[d] ^= state[a]
            state[d] = ((state[d] << 8) | (state[d] >> 24)) & 0xFFFFFFFF
            state[c] = (state[c] + state[d]) & 0xFFFFFFFF
            state[b] ^= state[c]
            state[b] = ((state[b] << 7) | (state[b] >> 25)) & 0xFFFFFFFF
        
        def chacha20_block(key, counter, nonce):
            constants = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]
            key_words = list(struct.unpack('<8I', key))
            nonce_words = list(struct.unpack('<3I', nonce[:12] if len(nonce) >= 12 else nonce + b'\x00' * (12 - len(nonce))))
            
            state = constants + key_words + [counter] + nonce_words
            working = state[:]
            
            for _ in range(10):
                quarter_round(working, 0, 4, 8, 12)
                quarter_round(working, 1, 5, 9, 13)
                quarter_round(working, 2, 6, 10, 14)
                quarter_round(working, 3, 7, 11, 15)
                quarter_round(working, 0, 5, 10, 15)
                quarter_round(working, 1, 6, 11, 12)
                quarter_round(working, 2, 7, 8, 13)
                quarter_round(working, 3, 4, 9, 14)
            
            output = [(working[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
            return struct.pack('<16I', *output)
        
        result = bytearray()
        counter = 0
        
        for i in range(0, len(data), 64):
            block = chacha20_block(key, counter, nonce)
            chunk = data[i:i+64]
            for j, byte in enumerate(chunk):
                result.append(byte ^ block[j])
            counter += 1
        
        return bytes(result)


class Salsa20Handler(AlgorithmHandler):
    """Salsa20算法处理器 - 支持标准和GPU-ONLY版本"""
    
    @property
    def name(self) -> str:
        return "Salsa20"
    
    @property
    def aliases(self) -> list:
        return ["Salsa20-CPU", "Salsa20-GPU", "Salsa20-GPU-ONLY", "salsa20"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        nonce = params.get('nonce') or params.get('iv')
        
        # GPU-ONLY 版本使用自定义实现
        if params.get('gpu_only') or 'GPU-ONLY' in params.get('algorithm', ''):
            return self._decrypt_gpu_only(data, key, nonce)
        
        # 标准版本使用 cryptography 库
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        
        if len(nonce) > 8:
            nonce = nonce[:8]
        elif len(nonce) < 8:
            nonce = nonce + b'\x00' * (8 - len(nonce))
        
        cipher = Cipher(algorithms.Salsa20(key, nonce), mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()
    
    def _decrypt_gpu_only(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """GPU-ONLY 版本的 Salsa20 解密（与 OpenCL 内核匹配）"""
        import struct
        
        def rotl32(v, n):
            return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF
        
        def salsa20_block(key, counter, nonce):
            constants = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574]
            key_words = list(struct.unpack('<8I', key))
            nonce_words = list(struct.unpack('<2I', nonce[:8] if len(nonce) >= 8 else nonce + b'\x00' * (8 - len(nonce))))
            
            state = [
                constants[0], key_words[0], key_words[1], key_words[2],
                key_words[3], constants[1], nonce_words[0], nonce_words[1],
                counter & 0xFFFFFFFF, (counter >> 32) & 0xFFFFFFFF, constants[2], key_words[4],
                key_words[5], key_words[6], key_words[7], constants[3]
            ]
            
            working = state[:]
            
            for _ in range(10):
                working[4] ^= rotl32((working[0] + working[12]) & 0xFFFFFFFF, 7)
                working[8] ^= rotl32((working[4] + working[0]) & 0xFFFFFFFF, 9)
                working[12] ^= rotl32((working[8] + working[4]) & 0xFFFFFFFF, 13)
                working[0] ^= rotl32((working[12] + working[8]) & 0xFFFFFFFF, 18)
                working[9] ^= rotl32((working[5] + working[1]) & 0xFFFFFFFF, 7)
                working[13] ^= rotl32((working[9] + working[5]) & 0xFFFFFFFF, 9)
                working[1] ^= rotl32((working[13] + working[9]) & 0xFFFFFFFF, 13)
                working[5] ^= rotl32((working[1] + working[13]) & 0xFFFFFFFF, 18)
                working[14] ^= rotl32((working[10] + working[6]) & 0xFFFFFFFF, 7)
                working[2] ^= rotl32((working[14] + working[10]) & 0xFFFFFFFF, 9)
                working[6] ^= rotl32((working[2] + working[14]) & 0xFFFFFFFF, 13)
                working[10] ^= rotl32((working[6] + working[2]) & 0xFFFFFFFF, 18)
                working[3] ^= rotl32((working[15] + working[11]) & 0xFFFFFFFF, 7)
                working[7] ^= rotl32((working[3] + working[15]) & 0xFFFFFFFF, 9)
                working[11] ^= rotl32((working[7] + working[3]) & 0xFFFFFFFF, 13)
                working[15] ^= rotl32((working[11] + working[7]) & 0xFFFFFFFF, 18)
                
                working[1] ^= rotl32((working[0] + working[3]) & 0xFFFFFFFF, 7)
                working[2] ^= rotl32((working[1] + working[0]) & 0xFFFFFFFF, 9)
                working[3] ^= rotl32((working[2] + working[1]) & 0xFFFFFFFF, 13)
                working[0] ^= rotl32((working[3] + working[2]) & 0xFFFFFFFF, 18)
                working[6] ^= rotl32((working[5] + working[4]) & 0xFFFFFFFF, 7)
                working[7] ^= rotl32((working[6] + working[5]) & 0xFFFFFFFF, 9)
                working[4] ^= rotl32((working[7] + working[6]) & 0xFFFFFFFF, 13)
                working[5] ^= rotl32((working[4] + working[7]) & 0xFFFFFFFF, 18)
                working[11] ^= rotl32((working[10] + working[9]) & 0xFFFFFFFF, 7)
                working[8] ^= rotl32((working[11] + working[10]) & 0xFFFFFFFF, 9)
                working[9] ^= rotl32((working[8] + working[11]) & 0xFFFFFFFF, 13)
                working[10] ^= rotl32((working[9] + working[8]) & 0xFFFFFFFF, 18)
                working[12] ^= rotl32((working[15] + working[14]) & 0xFFFFFFFF, 7)
                working[13] ^= rotl32((working[12] + working[15]) & 0xFFFFFFFF, 9)
                working[14] ^= rotl32((working[13] + working[12]) & 0xFFFFFFFF, 13)
                working[15] ^= rotl32((working[14] + working[13]) & 0xFFFFFFFF, 18)
            
            output = [(working[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
            return struct.pack('<16I', *output)
        
        result = bytearray()
        counter = 0
        
        for i in range(0, len(data), 64):
            block = salsa20_block(key, counter, nonce)
            chunk = data[i:i+64]
            for j, byte in enumerate(chunk):
                result.append(byte ^ block[j])
            counter += 1
        
        return bytes(result)


class SimpleXORHandler(AlgorithmHandler):
    """简单XOR算法处理器"""
    
    @property
    def name(self) -> str:
        return "SimpleXOR"
    
    @property
    def aliases(self) -> list:
        return ["SimpleXOR-CPU", "SimpleXOR-GPU", "SimpleXOR-GPU-ONLY", "Simple_XOR", "xor"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        result = bytearray(len(data))
        key_len = len(key)
        for i, byte in enumerate(data):
            result[i] = byte ^ key[i % key_len]
        return bytes(result)


class BitShuffleHandler(AlgorithmHandler):
    """位混洗算法处理器"""
    
    @property
    def name(self) -> str:
        return "BitShuffle"
    
    @property
    def aliases(self) -> list:
        return ["BitShuffle-CPU", "BitShuffle-GPU", "BitShuffle-GPU-ONLY", "bitshuffle"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        seed = sum(key) % 256
        result = bytearray(len(data))
        
        for i, byte in enumerate(data):
            shift = (seed + i) % 8
            result[i] = ((byte >> shift) | (byte << (8 - shift))) & 0xFF
        
        return bytes(result)


class RotateCipherHandler(AlgorithmHandler):
    """旋转密码算法处理器"""
    
    @property
    def name(self) -> str:
        return "RotateCipher"
    
    @property
    def aliases(self) -> list:
        return ["RotateCipher-CPU", "RotateCipher-GPU", "RotateCipher-GPU-ONLY", "rotate"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        result = bytearray(len(data))
        key_len = len(key)
        
        for i, byte in enumerate(data):
            rotation = key[i % key_len] % 8
            result[i] = ((byte >> rotation) | (byte << (8 - rotation))) & 0xFF
        
        return bytes(result)


class MatrixCipherHandler(AlgorithmHandler):
    """矩阵密码算法处理器 - 支持标准和GPU-ONLY版本"""
    
    @property
    def name(self) -> str:
        return "MatrixCipher"
    
    @property
    def aliases(self) -> list:
        return ["MatrixCipher-CPU", "MatrixCipher-GPU", "MatrixCipher-GPU-ONLY", "matrix"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        
        # GPU-ONLY 版本使用简化的矩阵变换
        if params.get('gpu_only') or 'GPU-ONLY' in params.get('algorithm', ''):
            return self._decrypt_gpu_only(data, key)
        
        return self._decrypt_standard(data, key)
    
    def _decrypt_standard(self, data: bytes, key: bytes) -> bytes:
        """标准矩阵解密"""
        result = bytearray(len(data))
        key_len = len(key)
        
        for i, byte in enumerate(data):
            k = key[i % key_len]
            result[i] = (byte - k) & 0xFF
        
        return bytes(result)
    
    def _decrypt_gpu_only(self, data: bytes, key: bytes) -> bytes:
        """GPU-ONLY 版本的矩阵解密"""
        result = bytearray(len(data))
        key_len = len(key)
        
        for i, byte in enumerate(data):
            k = key[i % key_len]
            result[i] = (byte - k) & 0xFF
        
        return bytes(result)


class PreScrambleHandler(AlgorithmHandler):
    """预混淆算法处理器"""
    
    @property
    def name(self) -> str:
        return "PreScramble"
    
    @property
    def aliases(self) -> list:
        return ["PreScramble-CPU", "PreScramble-GPU", "PreScramble-GPU-ONLY", "prescramble"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        seed = sum(key) % 256
        result = bytearray(len(data))
        
        for i, byte in enumerate(data):
            result[i] = byte ^ ((seed + i) & 0xFF)
        
        return bytes(result)


class FinalObfuscationHandler(AlgorithmHandler):
    """最终混淆算法处理器"""
    
    @property
    def name(self) -> str:
        return "FinalObfuscation"
    
    @property
    def aliases(self) -> list:
        return ["FinalObfuscation-CPU", "FinalObfuscation-GPU", "FinalObfuscation-GPU-ONLY", "finalobfuscation"]
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = params['key']
        result = bytearray(len(data))
        key_len = len(key)
        
        for i, byte in enumerate(data):
            k = key[i % key_len]
            result[i] = byte ^ k
        
        return bytes(result)
