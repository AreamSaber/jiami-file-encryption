#!/usr/bin/env python3
"""
配置管理属性测试

Feature: tech-debt-refactor
Property 6: 配置Schema验证
Property 7: 配置序列化格式
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hypothesis import given, strategies as st, settings
import pytest


# 定义策略
valid_config_names = st.sampled_from(['encryption_profiles', 'security_settings'])
invalid_json_strings = st.text(min_size=1, max_size=100).filter(
    lambda x: not x.strip().startswith('{')
)


class TestConfigSchemaValidation:
    """
    Property 6: 配置Schema验证
    
    For any 格式错误的配置JSON，ConfigManager应该抛出SchemaValidationError
    并包含具体的验证错误信息
    Validates: Requirements 4.2
    """

    def test_valid_config_loads_successfully(self):
        """
        Feature: tech-debt-refactor, Property 6: 配置Schema验证
        Validates: Requirements 4.2
        
        有效配置应该成功加载
        """
        try:
            from src.utils.config_manager import ConfigManager
        except ImportError:
            pytest.skip("ConfigManager不可用")
        
        # 创建临时配置目录
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # 创建有效配置
            valid_config = {
                "encryption_profiles": {
                    "test": {
                        "name": "测试配置",
                        "security_level": 1,
                        "layers": [{"method": "aes256"}]
                    }
                }
            }
            
            config_path = config_dir / "test_config.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(valid_config, f)
            
            # 重置单例
            ConfigManager._instance = None
            manager = ConfigManager(str(config_dir))
            
            # 加载配置
            config = manager.load_config("test_config")
            
            assert config is not None
            assert "encryption_profiles" in config

    def test_invalid_json_raises_error(self):
        """
        Feature: tech-debt-refactor, Property 6: 配置Schema验证
        Validates: Requirements 4.2
        
        无效JSON应该抛出错误
        """
        try:
            from src.utils.config_manager import ConfigManager
            from src.exceptions import ConfigLoadError
        except ImportError:
            pytest.skip("依赖不可用")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # 创建无效JSON文件
            config_path = config_dir / "invalid.json"
            with open(config_path, 'w') as f:
                f.write("{ invalid json }")
            
            ConfigManager._instance = None
            manager = ConfigManager(str(config_dir))
            
            with pytest.raises(ConfigLoadError):
                manager.load_config("invalid")

    def test_missing_config_raises_not_found(self):
        """
        Feature: tech-debt-refactor, Property 6: 配置Schema验证
        Validates: Requirements 4.2
        
        不存在的配置应该抛出ConfigNotFoundError
        """
        try:
            from src.utils.config_manager import ConfigManager
            from src.exceptions import ConfigNotFoundError
        except ImportError:
            pytest.skip("依赖不可用")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            ConfigManager._instance = None
            manager = ConfigManager(str(temp_dir))
            
            with pytest.raises(ConfigNotFoundError):
                manager.load_config("nonexistent")


class TestConfigSerializationFormat:
    """
    Property 7: 配置序列化格式
    
    For any 配置对象，序列化输出应该是有效的JSON字符串
    Validates: Requirements 4.5
    """

    @given(
        name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
        value=st.one_of(st.text(max_size=50), st.integers(), st.booleans())
    )
    @settings(max_examples=50)
    def test_config_serializes_to_valid_json(self, name: str, value):
        """
        Feature: tech-debt-refactor, Property 7: 配置序列化格式
        Validates: Requirements 4.5
        
        配置应该序列化为有效JSON
        """
        try:
            from src.utils.config_manager import ConfigManager
        except ImportError:
            pytest.skip("ConfigManager不可用")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # 创建配置
            config = {name: value}
            
            config_path = config_dir / "test.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f)
            
            ConfigManager._instance = None
            manager = ConfigManager(str(config_dir))
            
            # 序列化
            json_str = manager.to_json("test")
            
            # 验证是有效JSON
            parsed = json.loads(json_str)
            assert parsed == config

    def test_config_to_json_produces_string(self):
        """
        Feature: tech-debt-refactor, Property 7: 配置序列化格式
        Validates: Requirements 4.5
        
        to_json应该返回字符串
        """
        try:
            from src.utils.config_manager import ConfigManager
        except ImportError:
            pytest.skip("ConfigManager不可用")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            config = {"test": "value", "number": 123}
            config_path = config_dir / "test.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f)
            
            ConfigManager._instance = None
            manager = ConfigManager(str(config_dir))
            
            result = manager.to_json("test")
            
            assert isinstance(result, str)
            assert len(result) > 0

    @given(nested_value=st.dictionaries(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
        st.integers(),
        min_size=1,
        max_size=5
    ))
    @settings(max_examples=20)
    def test_nested_config_serializes_correctly(self, nested_value: dict):
        """
        Feature: tech-debt-refactor, Property 7: 配置序列化格式
        Validates: Requirements 4.5
        
        嵌套配置应该正确序列化
        """
        try:
            from src.utils.config_manager import ConfigManager
        except ImportError:
            pytest.skip("ConfigManager不可用")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            config = {"nested": nested_value}
            config_path = config_dir / "nested.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f)
            
            ConfigManager._instance = None
            manager = ConfigManager(str(config_dir))
            
            json_str = manager.to_json("nested")
            parsed = json.loads(json_str)
            
            assert parsed == config
            assert parsed["nested"] == nested_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
