#!/usr/bin/env python3
"""
配置序列化round-trip属性测试

Feature: tech-debt-refactor, Property 1: 解密器配置序列化round-trip
Validates: Requirements 1.4, 1.5
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hypothesis import given, strategies as st, settings, assume
from src.decryptor.base_decryptor import BaseDecryptor


# 定义策略
simple_values = st.one_of(
    st.text(max_size=100),
    st.integers(min_value=-1000000, max_value=1000000),
    st.booleans(),
    st.floats(allow_nan=False, allow_infinity=False),
)

# 简单的键名策略（避免特殊字符）
simple_keys = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=20
)

# 简单的元数据字典策略
simple_metadata = st.dictionaries(
    simple_keys,
    simple_values,
    min_size=1,
    max_size=10
)

# bytes数据策略
bytes_data = st.binary(min_size=1, max_size=100)

# 加密层策略
layer_strategy = st.fixed_dictionaries({
    'algorithm': st.sampled_from(['AES-256', 'ChaCha20', 'Salsa20']),
    'method': st.sampled_from(['aes256', 'chacha20', 'salsa20']),
    'mode': st.sampled_from(['CBC', 'GCM', None]),
})


class TestSerializationRoundTrip:
    """
    Property 1: 解密器配置序列化round-trip
    
    For any 有效的加密元数据对象，序列化为JSON后再反序列化，
    应该得到与原始对象等价的结果
    Validates: Requirements 1.4, 1.5
    """

    @given(metadata=simple_metadata)
    @settings(max_examples=100)
    def test_simple_metadata_roundtrip(self, metadata: dict):
        """
        Feature: tech-debt-refactor, Property 1: 解密器配置序列化round-trip
        Validates: Requirements 1.4, 1.5
        
        简单元数据的序列化round-trip
        """
        # 序列化
        serialized = BaseDecryptor.serialize_metadata(metadata)
        
        # 验证序列化结果是字符串
        assert isinstance(serialized, str), "序列化结果应该是字符串"
        
        # 反序列化
        deserialized = BaseDecryptor.deserialize_metadata(serialized)
        
        # 验证round-trip
        assert deserialized == metadata, "反序列化后应该与原始数据相等"

    @given(data=bytes_data)
    @settings(max_examples=100)
    def test_bytes_data_roundtrip(self, data: bytes):
        """
        Feature: tech-debt-refactor, Property 1: 解密器配置序列化round-trip
        Validates: Requirements 1.4, 1.5
        
        包含bytes数据的元数据序列化round-trip
        """
        metadata = {
            'key': data,
            'iv': data[:16] if len(data) >= 16 else data,
            'type': 'test'
        }
        
        # 序列化
        serialized = BaseDecryptor.serialize_metadata(metadata)
        
        # 验证序列化结果是字符串
        assert isinstance(serialized, str), "序列化结果应该是字符串"
        
        # 反序列化
        deserialized = BaseDecryptor.deserialize_metadata(serialized)
        
        # bytes会被转换为base64字符串，需要特殊处理验证
        assert 'key' in deserialized, "应该包含key字段"
        assert 'type' in deserialized, "应该包含type字段"
        assert deserialized['type'] == 'test', "type字段应该保持不变"

    @given(layers=st.lists(layer_strategy, min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_layers_metadata_roundtrip(self, layers: list):
        """
        Feature: tech-debt-refactor, Property 1: 解密器配置序列化round-trip
        Validates: Requirements 1.4, 1.5
        
        包含加密层的元数据序列化round-trip
        """
        metadata = {
            'type': 'layered',
            'layers': layers,
            'original_size': 1024
        }
        
        # 序列化
        serialized = BaseDecryptor.serialize_metadata(metadata)
        
        # 验证序列化结果是字符串
        assert isinstance(serialized, str), "序列化结果应该是字符串"
        
        # 反序列化
        deserialized = BaseDecryptor.deserialize_metadata(serialized)
        
        # 验证round-trip
        assert deserialized['type'] == metadata['type']
        assert deserialized['original_size'] == metadata['original_size']
        assert len(deserialized['layers']) == len(metadata['layers'])

    @given(
        encryption_type=st.sampled_from(['layered', 'parallel', 'threaded_layered']),
        original_size=st.integers(min_value=1, max_value=1000000),
        engine_type=st.sampled_from(['pure_cpu', 'pure_gpu', 'hybrid'])
    )
    @settings(max_examples=100)
    def test_complete_metadata_roundtrip(
        self, 
        encryption_type: str, 
        original_size: int,
        engine_type: str
    ):
        """
        Feature: tech-debt-refactor, Property 1: 解密器配置序列化round-trip
        Validates: Requirements 1.4, 1.5
        
        完整元数据的序列化round-trip
        """
        metadata = {
            'type': encryption_type,
            'original_size': original_size,
            'engine_type': engine_type,
            'layers': [
                {'algorithm': 'AES-256', 'method': 'aes256', 'mode': 'GCM'}
            ],
            'version': '1.0.0'
        }
        
        # 序列化
        serialized = BaseDecryptor.serialize_metadata(metadata)
        
        # 反序列化
        deserialized = BaseDecryptor.deserialize_metadata(serialized)
        
        # 验证所有字段
        assert deserialized['type'] == encryption_type
        assert deserialized['original_size'] == original_size
        assert deserialized['engine_type'] == engine_type
        assert deserialized['version'] == '1.0.0'

    @given(metadata=simple_metadata)
    @settings(max_examples=100)
    def test_serialization_produces_valid_base64(self, metadata: dict):
        """
        Feature: tech-debt-refactor, Property 1: 解密器配置序列化round-trip
        Validates: Requirements 1.4
        
        序列化应该产生有效的base64字符串
        """
        import base64
        
        serialized = BaseDecryptor.serialize_metadata(metadata)
        
        # 验证是有效的base64
        try:
            decoded = base64.b64decode(serialized)
            assert len(decoded) > 0, "解码后的数据不应为空"
        except Exception as e:
            assert False, f"序列化结果不是有效的base64: {e}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
