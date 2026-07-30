#!/usr/bin/env python3
"""算法注册表单元测试"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest


class TestAlgorithmRegistry:
    """算法注册表测试"""
    
    def test_registry_initialization(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        assert registry is not None
    
    def test_list_algorithms(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        algorithms = registry.list_algorithms()
        assert isinstance(algorithms, list)
        assert len(algorithms) > 0
    
    def test_get_aes_handler(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        handler = registry.get_handler("AES-256")
        assert handler is not None
        assert handler.name == "AES-256"
    
    def test_get_chacha20_handler(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        handler = registry.get_handler("ChaCha20")
        assert handler is not None
    
    def test_get_handler_by_alias(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        handler = registry.get_handler("aes256")
        assert handler is not None
        assert handler.name == "AES-256"
    
    def test_unknown_algorithm_raises_error(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        from src.exceptions import AlgorithmNotSupportedError
        
        registry = AlgorithmRegistry()
        with pytest.raises(AlgorithmNotSupportedError):
            registry.get_handler("UnknownAlgorithm")
    
    def test_is_registered(self):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        assert registry.is_registered("AES-256")
        assert registry.is_registered("ChaCha20")
        assert not registry.is_registered("FakeAlgorithm")


class TestAES256Handler:
    """AES-256处理器测试"""
    
    def test_decrypt_cbc_mode(self):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
        except ImportError:
            pytest.skip("cryptography库不可用")
        
        from src.decryptor.algorithm_registry import AES256Handler
        handler = AES256Handler()
        
        # 准备测试数据
        key = os.urandom(32)
        iv = os.urandom(16)
        plaintext = b"Test data for AES encryption"
        
        # 加密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        
        # 解密
        params = {'key': key, 'iv': iv, 'mode': 'CBC'}
        decrypted = handler.decrypt(ciphertext, params)
        
        assert decrypted == plaintext


class TestChaCha20Handler:
    """ChaCha20处理器测试"""
    
    def test_decrypt(self):
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        except ImportError:
            pytest.skip("cryptography库不可用")
        
        from src.decryptor.algorithm_registry import ChaCha20Handler
        handler = ChaCha20Handler()
        
        # 准备测试数据
        key = os.urandom(32)
        nonce = os.urandom(16)
        plaintext = b"Test data for ChaCha20"
        
        # 加密
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # 解密
        params = {'key': key, 'nonce': nonce}
        decrypted = handler.decrypt(ciphertext, params)
        
        assert decrypted == plaintext
