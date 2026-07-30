"""
加密工具模块

提供各种加密相关的工具函数和辅助功能。
"""

import os
import hashlib
import secrets
import base64
from typing import Optional, Dict, Any

from .logger import Logger


class CryptoUtils:
    """加密工具类"""
    
    def __init__(self):
        """初始化加密工具"""
        self.logger = Logger("CryptoUtils")
    
    def generate_random_key(self, length: int = 32) -> bytes:
        """
        生成随机密钥
        
        Args:
            length: 密钥长度（字节）
            
        Returns:
            随机密钥
        """
        return secrets.token_bytes(length)
    
    def generate_random_string(self, length: int = 16) -> str:
        """
        生成随机字符串
        
        Args:
            length: 字符串长度
            
        Returns:
            随机字符串
        """
        return secrets.token_urlsafe(length)[:length]
    
    def hash_data(self, data: bytes, algorithm: str = 'sha256') -> str:
        """
        计算数据哈希值
        
        Args:
            data: 要哈希的数据
            algorithm: 哈希算法
            
        Returns:
            哈希值（十六进制字符串）
        """
        try:
            if algorithm == 'sha256':
                hasher = hashlib.sha256()
            elif algorithm == 'sha512':
                hasher = hashlib.sha512()
            elif algorithm == 'md5':
                hasher = hashlib.md5()
            else:
                raise ValueError(f"不支持的哈希算法: {algorithm}")
            
            hasher.update(data)
            return hasher.hexdigest()
            
        except Exception as e:
            self.logger.error(f"计算哈希失败: {e}")
            raise
    
    def derive_key(self, password: str, salt: bytes, iterations: int = 100000, key_length: int = 32) -> bytes:
        """
        从密码派生密钥
        
        Args:
            password: 密码
            salt: 盐值
            iterations: 迭代次数
            key_length: 密钥长度
            
        Returns:
            派生的密钥
        """
        try:
            # 尝试使用PBKDF2
            try:
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=key_length,
                    salt=salt,
                    iterations=iterations,
                )
                
                return kdf.derive(password.encode('utf-8'))
                
            except ImportError:
                # 回退到hashlib的pbkdf2
                return hashlib.pbkdf2_hmac(
                    'sha256',
                    password.encode('utf-8'),
                    salt,
                    iterations,
                    key_length
                )
                
        except Exception as e:
            self.logger.error(f"密钥派生失败: {e}")
            raise
    
    def encode_base64(self, data: bytes) -> str:
        """
        Base64编码
        
        Args:
            data: 要编码的数据
            
        Returns:
            Base64编码字符串
        """
        return base64.b64encode(data).decode('utf-8')
    
    def decode_base64(self, encoded: str) -> bytes:
        """
        Base64解码
        
        Args:
            encoded: Base64编码字符串
            
        Returns:
            解码后的数据
        """
        return base64.b64decode(encoded.encode('utf-8'))
    
    def xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """
        XOR加密
        
        Args:
            data: 要加密的数据
            key: 密钥
            
        Returns:
            加密后的数据
        """
        if len(key) == 0:
            raise ValueError("密钥不能为空")
        
        result = bytearray()
        for i, byte in enumerate(data):
            result.append(byte ^ key[i % len(key)])
        
        return bytes(result)
    
    def xor_decrypt(self, encrypted_data: bytes, key: bytes) -> bytes:
        """
        XOR解密（与加密相同）
        
        Args:
            encrypted_data: 加密的数据
            key: 密钥
            
        Returns:
            解密后的数据
        """
        return self.xor_encrypt(encrypted_data, key)
    
    def calculate_checksum(self, data: bytes) -> str:
        """
        计算校验和
        
        Args:
            data: 数据
            
        Returns:
            校验和
        """
        return self.hash_data(data, 'sha256')
    
    def verify_checksum(self, data: bytes, expected_checksum: str) -> bool:
        """
        验证校验和
        
        Args:
            data: 数据
            expected_checksum: 期望的校验和
            
        Returns:
            是否匹配
        """
        actual_checksum = self.calculate_checksum(data)
        return actual_checksum == expected_checksum
    
    def secure_random_int(self, min_val: int, max_val: int) -> int:
        """
        生成安全的随机整数
        
        Args:
            min_val: 最小值
            max_val: 最大值
            
        Returns:
            随机整数
        """
        return secrets.randbelow(max_val - min_val + 1) + min_val
    
    def obfuscate_data(self, data: bytes, rounds: int = 3) -> tuple:
        """
        混淆数据
        
        Args:
            data: 要混淆的数据
            rounds: 混淆轮数
            
        Returns:
            (混淆后的数据, 混淆密钥)
        """
        obfuscated = data
        keys = []
        
        for _ in range(rounds):
            key = self.generate_random_key(len(obfuscated))
            obfuscated = self.xor_encrypt(obfuscated, key)
            keys.append(key)
        
        return obfuscated, keys
    
    def deobfuscate_data(self, obfuscated_data: bytes, keys: list) -> bytes:
        """
        去混淆数据
        
        Args:
            obfuscated_data: 混淆的数据
            keys: 混淆密钥列表
            
        Returns:
            原始数据
        """
        data = obfuscated_data
        
        # 逆序应用密钥
        for key in reversed(keys):
            data = self.xor_decrypt(data, key)
        
        return data
    
    def split_data(self, data: bytes, parts: int) -> list:
        """
        分割数据
        
        Args:
            data: 要分割的数据
            parts: 分割份数
            
        Returns:
            数据分片列表
        """
        if parts <= 0:
            raise ValueError("分割份数必须大于0")
        
        chunk_size = len(data) // parts
        chunks = []
        
        for i in range(parts):
            start = i * chunk_size
            if i == parts - 1:  # 最后一片包含剩余数据
                end = len(data)
            else:
                end = start + chunk_size
            
            chunks.append(data[start:end])
        
        return chunks
    
    def combine_data(self, chunks: list) -> bytes:
        """
        合并数据分片
        
        Args:
            chunks: 数据分片列表
            
        Returns:
            合并后的数据
        """
        return b''.join(chunks)
    
    def pad_data(self, data: bytes, block_size: int) -> bytes:
        """
        数据填充（PKCS7）
        
        Args:
            data: 要填充的数据
            block_size: 块大小
            
        Returns:
            填充后的数据
        """
        padding_length = block_size - (len(data) % block_size)
        padding = bytes([padding_length] * padding_length)
        return data + padding
    
    def unpad_data(self, padded_data: bytes) -> bytes:
        """
        移除数据填充
        
        Args:
            padded_data: 填充的数据
            
        Returns:
            原始数据
        """
        if len(padded_data) == 0:
            raise ValueError("数据不能为空")
        
        padding_length = padded_data[-1]
        
        if padding_length > len(padded_data):
            raise ValueError("无效的填充")
        
        return padded_data[:-padding_length]
