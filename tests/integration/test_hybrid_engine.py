#!/usr/bin/env python3
"""
混合加密引擎集成测试

测试HybridEncryptionEngine的核心功能
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from src.encryptor.hybrid_engine import HybridEncryptionEngine
from src.decryptor.algorithm_registry import AlgorithmRegistry


class TestHybridEngineBasic:
    """混合加密引擎基础功能测试"""
    
    @pytest.fixture
    def engine(self):
        """创建加密引擎实例"""
        return HybridEncryptionEngine()
    
    @pytest.fixture
    def registry(self):
        """创建算法注册表实例"""
        return AlgorithmRegistry()
    
    def test_engine_initialization(self, engine):
        """测试引擎初始化"""
        assert engine is not None
        assert engine.encryption_methods is not None
        assert 'aes256' in engine.encryption_methods
        assert 'chacha20' in engine.encryption_methods
    
    def test_single_layer_aes256_gcm(self, engine, registry):
        """测试单层AES-256 GCM加密"""
        test_data = b"Hello, this is a test for AES-256 GCM encryption!"
        
        config = {
            'strategy': 'layered',
            'layers': [
                {'method': 'aes256', 'mode': 'GCM'}
            ]
        }
        
        # 加密
        result = engine.encrypt_data(test_data, config)
        assert 'encrypted_data' in result
        assert 'metadata' in result
        assert result['encrypted_data'] != test_data
        
        # 解密
        encrypted_data = result['encrypted_data']
        metadata = result['metadata']
        
        decrypted_data = encrypted_data
        for layer in reversed(metadata['layers']):
            algorithm = layer.get('algorithm', '')
            handler = registry.get_handler(algorithm)
            decrypted_data = handler.decrypt(decrypted_data, layer)
        
        # 截断到原始大小
        original_size = metadata.get('original_size', len(test_data))
        if len(decrypted_data) > original_size:
            decrypted_data = decrypted_data[:original_size]
        
        assert decrypted_data == test_data
    
    def test_single_layer_chacha20(self, engine, registry):
        """测试单层ChaCha20加密"""
        test_data = b"Hello, this is a test for ChaCha20 encryption!"
        
        config = {
            'strategy': 'layered',
            'layers': [
                {'method': 'chacha20'}
            ]
        }
        
        # 加密
        result = engine.encrypt_data(test_data, config)
        assert 'encrypted_data' in result
        assert 'metadata' in result
        
        # 解密
        encrypted_data = result['encrypted_data']
        metadata = result['metadata']
        
        decrypted_data = encrypted_data
        for layer in reversed(metadata['layers']):
            algorithm = layer.get('algorithm', '')
            handler = registry.get_handler(algorithm)
            decrypted_data = handler.decrypt(decrypted_data, layer)
        
        original_size = metadata.get('original_size', len(test_data))
        if len(decrypted_data) > original_size:
            decrypted_data = decrypted_data[:original_size]
        
        assert decrypted_data == test_data


class TestHybridEngineLayered:
    """分层加密测试"""
    
    @pytest.fixture
    def engine(self):
        return HybridEncryptionEngine()
    
    @pytest.fixture
    def registry(self):
        return AlgorithmRegistry()
    
    def test_two_layer_encryption(self, engine, registry):
        """测试双层加密"""
        test_data = b"Two layer encryption test data"
        
        config = {
            'strategy': 'layered',
            'layers': [
                {'method': 'chacha20'},
                {'method': 'aes256', 'mode': 'GCM'}
            ]
        }
        
        # 加密
        result = engine.encrypt_data(test_data, config)
        metadata = result['metadata']
        
        assert metadata['type'] == 'layered'
        assert len(metadata['layers']) == 2
        
        # 解密
        decrypted_data = result['encrypted_data']
        for layer in reversed(metadata['layers']):
            algorithm = layer.get('algorithm', '')
            handler = registry.get_handler(algorithm)
            decrypted_data = handler.decrypt(decrypted_data, layer)
        
        original_size = metadata.get('original_size', len(test_data))
        if len(decrypted_data) > original_size:
            decrypted_data = decrypted_data[:original_size]
        
        assert decrypted_data == test_data
    
    def test_metadata_contains_layer_info(self, engine):
        """测试元数据包含层信息"""
        test_data = b"Metadata test"
        
        config = {
            'strategy': 'layered',
            'layers': [
                {'method': 'aes256', 'mode': 'GCM'}
            ]
        }
        
        result = engine.encrypt_data(test_data, config)
        metadata = result['metadata']
        
        assert 'layers' in metadata
        assert 'original_size' in metadata
        assert metadata['original_size'] == len(test_data)
        
        layer = metadata['layers'][0]
        assert 'algorithm' in layer
        assert 'key' in layer
        assert 'iv' in layer


class TestHybridEngineStrategy:
    """加密策略测试"""
    
    @pytest.fixture
    def engine(self):
        return HybridEncryptionEngine()
    
    def test_layered_strategy_selection(self, engine):
        """测试分层策略选择"""
        test_data = b"Strategy test data"
        
        config = {
            'strategy': 'layered',
            'layers': [{'method': 'aes256', 'mode': 'GCM'}]
        }
        
        result = engine.encrypt_data(test_data, config)
        assert result['strategy_used'] == 'layered'
    
    def test_encryption_result_has_duration(self, engine):
        """测试加密结果包含耗时"""
        test_data = b"Duration test data"
        
        config = {
            'strategy': 'layered',
            'layers': [{'method': 'aes256', 'mode': 'GCM'}]
        }
        
        result = engine.encrypt_data(test_data, config)
        assert 'duration' in result
        assert result['duration'] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
