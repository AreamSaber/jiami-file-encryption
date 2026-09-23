#!/usr/bin/env python3
"""
GPU相关属性测试

Feature: tech-debt-refactor
Property 2: GPU降级一致性
Property 3: 加密解密round-trip
Property 4: 性能指标完整性
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hypothesis import given, strategies as st, settings, assume
import pytest


# 定义策略
binary_data = st.binary(min_size=100, max_size=10000)
security_levels = st.integers(min_value=1, max_value=5)


class TestGPUFallbackConsistency:
    """
    Property 2: GPU降级一致性
    
    For any 输入数据和加密参数，当GPU不可用时，
    CPU降级加密的结果应该能被正确解密还原原始数据
    Validates: Requirements 2.2
    """

    @given(data=binary_data)
    @settings(max_examples=10, deadline=None)  # Real fsync latency is not a cipher correctness property.
    def test_cpu_fallback_produces_decryptable_output(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 2: GPU降级一致性
        Validates: Requirements 2.2
        
        CPU降级加密应该产生可解密的输出
        """
        import tempfile
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(data)
            temp_file = f.name
        
        try:
            # 尝试导入加密器
            try:
                from src.encryptor.main import FileEncryptor
            except ImportError:
                pytest.skip("FileEncryptor不可用")
            
            # 创建加密器
            encryptor = FileEncryptor()
            
            # 创建临时输出目录
            with tempfile.TemporaryDirectory() as output_dir:
                # 加密
                result = encryptor.encrypt_file(temp_file, output_dir, 'basic')
                
                assert result['success'], result
                from src.decryptor.cpu_decryptor import CPUDecryptor
                recovered, metadata = CPUDecryptor().decrypt_bytes(result['encrypted_file'])
                assert recovered == data
                assert metadata['original_size'] == len(data)
                encryptor.hybrid_engine.shutdown()

        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass


class TestPerformanceMetricsCompleteness:
    """
    Property 4: 性能指标完整性
    
    For any 成功的GPU加密操作，返回结果应该包含speed_mbps字段且值大于0
    Validates: Requirements 2.4
    """

    def test_encryption_result_has_speed_metric(self):
        """
        Feature: tech-debt-refactor, Property 4: 性能指标完整性
        Validates: Requirements 2.4
        
        加密结果应该包含速度指标
        """
        import tempfile
        
        # 创建测试数据
        test_data = b"Test data for encryption " * 100
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(test_data)
            temp_file = f.name
        
        try:
            try:
                from src.encryptor.main import FileEncryptor
            except ImportError:
                pytest.skip("FileEncryptor不可用")
            
            encryptor = FileEncryptor()
            
            with tempfile.TemporaryDirectory() as output_dir:
                result = encryptor.encrypt_file(temp_file, output_dir, 'basic')
                
                assert result['success'], result
                if result['success']:
                    # 验证包含加密时间
                    assert 'encryption_time' in result, "结果应该包含encryption_time"
                    assert result['encryption_time'] >= 0, "加密时间应该非负"
                    
                    # 验证包含大小信息
                    assert 'original_size' in result, "结果应该包含original_size"
                    assert 'encrypted_size' in result, "结果应该包含encrypted_size"
                    assert result['original_size'] > 0, "原始大小应该大于0"
                    
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass

    @given(data_size=st.integers(min_value=100, max_value=10000))
    @settings(max_examples=5, deadline=None)  # Real encryption/fsync latency is not a metric-validity property.
    def test_speed_calculation_is_valid(self, data_size: int):
        """
        Feature: tech-debt-refactor, Property 4: 性能指标完整性
        Validates: Requirements 2.4
        
        速度计算应该是有效的正数
        """
        import tempfile
        
        test_data = os.urandom(data_size)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as f:
            f.write(test_data)
            temp_file = f.name
        
        try:
            try:
                from src.encryptor.main import FileEncryptor
            except ImportError:
                pytest.skip("FileEncryptor不可用")
            
            encryptor = FileEncryptor()
            
            with tempfile.TemporaryDirectory() as output_dir:
                result = encryptor.encrypt_file(temp_file, output_dir, 'basic')
                
                assert result['success'], result
                assert result['encryption_time'] > 0
                if result['encryption_time'] > 0:
                    # 计算速度
                    speed = result['original_size'] / result['encryption_time']
                    assert speed > 0, "速度应该大于0"
                    
        finally:
            try:
                os.unlink(temp_file)
            except:
                pass


class TestEncryptionDecryptionRoundTrip:
    """
    Property 3: 加密解密round-trip
    
    For any 输入数据和有效的加密配置，加密后再解密应该得到原始数据
    Validates: Requirements 2.3
    """

    @given(data=st.binary(min_size=10, max_size=1000))
    @settings(max_examples=5)
    def test_algorithm_registry_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 3: 加密解密round-trip
        Validates: Requirements 2.3
        
        使用算法注册表的加密解密应该是可逆的
        """
        try:
            from src.decryptor.algorithm_registry import AlgorithmRegistry, AES256Handler
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
        except ImportError:
            pytest.skip("依赖不可用")
        
        # 生成密钥和IV
        key = os.urandom(32)
        iv = os.urandom(16)
        
        # 加密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        
        # 添加填充
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        
        # 使用算法注册表解密
        registry = AlgorithmRegistry()
        handler = registry.get_handler('AES-256')
        
        params = {
            'key': key,
            'iv': iv,
            'mode': 'CBC'
        }
        
        decrypted = handler.decrypt(encrypted, params)
        
        # 验证round-trip
        assert decrypted == data, "解密后应该与原始数据相等"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
