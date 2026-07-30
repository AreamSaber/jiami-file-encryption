#!/usr/bin/env python3
"""
加密解密round-trip属性测试

Feature: tech-debt-refactor, Property 3: 加密解密round-trip
Validates: Requirements 2.3
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hypothesis import given, strategies as st, settings, assume, HealthCheck
import pytest


# ============ 测试策略定义 ============

# 二进制数据策略 - 限制大小以保证测试速度
binary_data = st.binary(min_size=1, max_size=1024)

# 较大的二进制数据策略 - 用于测试分块加密
large_binary_data = st.binary(min_size=1024, max_size=4096)

# 加密模式策略
aes_mode = st.sampled_from(['CBC', 'GCM'])

# 安全级别策略
security_level = st.integers(min_value=1, max_value=3)


class TestEncryptionDecryptionRoundTrip:
    """
    Property 3: 加密解密round-trip
    
    For any 输入数据和有效的加密配置，加密后再解密应该得到原始数据
    Validates: Requirements 2.3
    """

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_aes256_gcm_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        AES-256 GCM模式的加密解密round-trip
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        import os as crypto_os
        
        # 生成密钥和IV
        key = crypto_os.urandom(32)  # 256位密钥
        iv = crypto_os.urandom(12)   # 96位IV (GCM推荐)
        
        # 加密
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        tag = encryptor.tag
        
        # 解密
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # 验证round-trip
        assert decrypted_data == data, "AES-256 GCM解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_aes256_cbc_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        AES-256 CBC模式的加密解密round-trip
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        import os as crypto_os
        
        # 生成密钥和IV
        key = crypto_os.urandom(32)  # 256位密钥
        iv = crypto_os.urandom(16)   # 128位IV
        
        # 填充数据
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # 加密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # 解密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # 移除填充
        unpadder = padding.PKCS7(128).unpadder()
        decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()
        
        # 验证round-trip
        assert decrypted_data == data, "AES-256 CBC解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_chacha20_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        ChaCha20的加密解密round-trip
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        import os as crypto_os
        
        # 生成密钥和nonce
        key = crypto_os.urandom(32)   # 256位密钥
        nonce = crypto_os.urandom(16)  # 128位nonce
        
        # 加密
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        
        # 解密 (ChaCha20是对称流密码，加密和解密操作相同)
        cipher = Cipher(algorithm, mode=None)
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # 验证round-trip
        assert decrypted_data == data, "ChaCha20解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_algorithm_registry_aes256_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        通过算法注册表进行AES-256加密解密round-trip
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        import os as crypto_os
        
        # 生成密钥和IV
        key = crypto_os.urandom(32)
        iv = crypto_os.urandom(12)
        
        # 使用cryptography库加密
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        tag = encryptor.tag
        
        # 使用算法注册表解密
        registry = AlgorithmRegistry()
        handler = registry.get_handler('AES-256')
        
        params = {
            'key': key,
            'iv': iv,
            'mode': 'GCM',
            'tag': tag
        }
        
        decrypted_data = handler.decrypt(encrypted_data, params)
        
        # 验证round-trip
        assert decrypted_data == data, "通过算法注册表解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_algorithm_registry_chacha20_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        通过算法注册表进行ChaCha20加密解密round-trip
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        import os as crypto_os
        
        # 生成密钥和nonce
        key = crypto_os.urandom(32)
        nonce = crypto_os.urandom(16)
        
        # 使用cryptography库加密
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data) + encryptor.finalize()
        
        # 使用算法注册表解密
        registry = AlgorithmRegistry()
        handler = registry.get_handler('ChaCha20')
        
        params = {
            'key': key,
            'nonce': nonce
        }
        
        decrypted_data = handler.decrypt(encrypted_data, params)
        
        # 验证round-trip
        assert decrypted_data == data, "通过算法注册表解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_simple_xor_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        简单XOR加密解密round-trip
        """
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        import os as crypto_os
        
        # 生成密钥（与数据等长或更长）
        key = crypto_os.urandom(max(len(data), 32))
        
        # XOR加密
        encrypted_data = bytes(a ^ key[i % len(key)] for i, a in enumerate(data))
        
        # 使用算法注册表解密
        registry = AlgorithmRegistry()
        handler = registry.get_handler('Simple_XOR')
        
        params = {'key': key}
        decrypted_data = handler.decrypt(encrypted_data, params)
        
        # 验证round-trip (XOR是自反的)
        assert decrypted_data == data, "XOR解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_rotate_cipher_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        旋转密码加密解密round-trip
        """
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        import random
        
        # 随机旋转量
        rotation = random.randint(1, 255)
        
        # 加密（正向旋转）
        encrypted_data = bytes((byte + rotation) % 256 for byte in data)
        
        # 使用算法注册表解密
        registry = AlgorithmRegistry()
        handler = registry.get_handler('Rotate_Cipher')
        
        params = {'rotation': rotation}
        decrypted_data = handler.decrypt(encrypted_data, params)
        
        # 验证round-trip
        assert decrypted_data == data, "旋转密码解密后数据应与原始数据相同"

    @given(data=binary_data, mode=aes_mode)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_aes256_mode_roundtrip(self, data: bytes, mode: str):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        AES-256不同模式的加密解密round-trip
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes as cipher_modes
        from cryptography.hazmat.primitives import padding
        import os as crypto_os
        
        key = crypto_os.urandom(32)
        
        if mode == 'GCM':
            iv = crypto_os.urandom(12)
            cipher = Cipher(algorithms.AES(key), cipher_modes.GCM(iv))
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(data) + encryptor.finalize()
            tag = encryptor.tag
            
            cipher = Cipher(algorithms.AES(key), cipher_modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        else:  # CBC
            iv = crypto_os.urandom(16)
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            cipher = Cipher(algorithms.AES(key), cipher_modes.CBC(iv))
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            cipher = Cipher(algorithms.AES(key), cipher_modes.CBC(iv))
            decryptor = cipher.decryptor()
            decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()
            
            unpadder = padding.PKCS7(128).unpadder()
            decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()
        
        assert decrypted_data == data, f"AES-256 {mode}模式解密后数据应与原始数据相同"


class TestHybridEngineRoundTrip:
    """
    测试混合加密引擎的round-trip属性
    
    Feature: tech-debt-refactor, Property 3: 加密解密round-trip
    Validates: Requirements 2.3
    """

    @given(data=binary_data)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_layered_encryption_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        分层加密的round-trip测试
        """
        from src.encryptor.hybrid_engine import HybridEncryptionEngine
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        
        # 创建加密引擎
        engine = HybridEncryptionEngine()
        
        # 简单的单层配置
        config = {
            'strategy': 'layered',
            'layers': [
                {'method': 'aes256', 'mode': 'GCM'}
            ]
        }
        
        # 加密
        result = engine.encrypt_data(data, config)
        encrypted_data = result['encrypted_data']
        metadata = result['metadata']
        
        # 解密
        registry = AlgorithmRegistry()
        decrypted_data = encrypted_data
        
        for layer in reversed(metadata['layers']):
            algorithm = layer.get('algorithm', '')
            handler = registry.get_handler(algorithm)
            decrypted_data = handler.decrypt(decrypted_data, layer)
        
        # 截断到原始大小
        original_size = metadata.get('original_size', len(data))
        if len(decrypted_data) > original_size:
            decrypted_data = decrypted_data[:original_size]
        
        assert decrypted_data == data, "分层加密解密后数据应与原始数据相同"

    @given(data=binary_data)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_multi_layer_encryption_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        多层加密的round-trip测试
        """
        from src.encryptor.hybrid_engine import HybridEncryptionEngine
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        
        # 创建加密引擎
        engine = HybridEncryptionEngine()
        
        # 双层配置
        config = {
            'strategy': 'layered',
            'layers': [
                {'method': 'chacha20'},
                {'method': 'aes256', 'mode': 'GCM'}
            ]
        }
        
        # 加密
        result = engine.encrypt_data(data, config)
        encrypted_data = result['encrypted_data']
        metadata = result['metadata']
        
        # 解密（反向顺序）
        registry = AlgorithmRegistry()
        decrypted_data = encrypted_data
        
        for layer in reversed(metadata['layers']):
            algorithm = layer.get('algorithm', '')
            handler = registry.get_handler(algorithm)
            decrypted_data = handler.decrypt(decrypted_data, layer)
        
        # 截断到原始大小
        original_size = metadata.get('original_size', len(data))
        if len(decrypted_data) > original_size:
            decrypted_data = decrypted_data[:original_size]
        
        assert decrypted_data == data, "多层加密解密后数据应与原始数据相同"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
