#!/usr/bin/env python3
"""ConfigManager单元测试"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from src.utils.config_manager import ConfigManager
from src.exceptions import (
    ConfigNotFoundError,
    ConfigLoadError,
    SchemaValidationError,
)


class TestConfigManagerBasic:
    """ConfigManager基础功能测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建schemas子目录
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """创建配置管理器实例"""
        # 重置单例
        ConfigManager._instance = None
        return ConfigManager(temp_config_dir)
    
    def test_initialization(self, config_manager, temp_config_dir):
        """测试初始化"""
        assert config_manager is not None
        assert config_manager.config_dir == Path(temp_config_dir)
    
    def test_load_config_not_found(self, config_manager):
        """测试加载不存在的配置"""
        with pytest.raises(ConfigNotFoundError):
            config_manager.load_config("nonexistent")
    
    def test_load_valid_config(self, config_manager, temp_config_dir):
        """测试加载有效配置"""
        # 创建测试配置文件
        config_path = Path(temp_config_dir) / "test.json"
        config_data = {"key": "value", "number": 123}
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        loaded = config_manager.load_config("test")
        assert loaded == config_data
    
    def test_load_invalid_json(self, config_manager, temp_config_dir):
        """测试加载无效JSON"""
        config_path = Path(temp_config_dir) / "invalid.json"
        with open(config_path, 'w') as f:
            f.write("not valid json {")
        
        with pytest.raises(ConfigLoadError):
            config_manager.load_config("invalid")


class TestConfigManagerCaching:
    """ConfigManager缓存测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        ConfigManager._instance = None
        return ConfigManager(temp_config_dir)
    
    def test_config_is_cached(self, config_manager, temp_config_dir):
        """测试配置被缓存"""
        config_path = Path(temp_config_dir) / "cached.json"
        with open(config_path, 'w') as f:
            json.dump({"value": 1}, f)
        
        # 第一次加载
        config_manager.load_config("cached")
        
        # 修改文件（但不更新时间戳）
        # 由于缓存，应该返回旧值
        assert "cached" in config_manager._configs
    
    def test_force_reload(self, config_manager, temp_config_dir):
        """测试强制重新加载"""
        config_path = Path(temp_config_dir) / "reload.json"
        with open(config_path, 'w') as f:
            json.dump({"value": 1}, f)
        
        config_manager.load_config("reload")
        
        # 修改文件
        with open(config_path, 'w') as f:
            json.dump({"value": 2}, f)
        
        # 强制重新加载
        loaded = config_manager.load_config("reload", force_reload=True)
        assert loaded["value"] == 2


class TestConfigManagerGetConfig:
    """ConfigManager get_config方法测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        ConfigManager._instance = None
        cm = ConfigManager(temp_config_dir)
        
        # 创建测试配置
        config_path = Path(temp_config_dir) / "nested.json"
        with open(config_path, 'w') as f:
            json.dump({
                "level1": {
                    "level2": {
                        "value": "deep"
                    }
                },
                "simple": "value"
            }, f)
        
        return cm
    
    def test_get_entire_config(self, config_manager):
        """测试获取整个配置"""
        config = config_manager.get_config("nested")
        assert "level1" in config
        assert "simple" in config
    
    def test_get_simple_key(self, config_manager):
        """测试获取简单键"""
        value = config_manager.get_config("nested", "simple")
        assert value == "value"
    
    def test_get_nested_key(self, config_manager):
        """测试获取嵌套键"""
        value = config_manager.get_config("nested", "level1.level2.value")
        assert value == "deep"
    
    def test_get_missing_key_returns_default(self, config_manager):
        """测试获取不存在的键返回默认值"""
        value = config_manager.get_config("nested", "nonexistent", default="default")
        assert value == "default"
    
    def test_get_missing_config_returns_default(self, config_manager):
        """测试获取不存在的配置返回默认值"""
        value = config_manager.get_config("nonexistent", default="default")
        assert value == "default"


class TestConfigManagerWatchers:
    """ConfigManager观察者测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        ConfigManager._instance = None
        return ConfigManager(temp_config_dir)
    
    def test_watch_changes(self, config_manager, temp_config_dir):
        """测试注册观察者"""
        callback_called = []
        
        def callback(name, config):
            callback_called.append((name, config))
        
        config_manager.watch_changes(callback)
        
        # 创建并加载配置
        config_path = Path(temp_config_dir) / "watched.json"
        with open(config_path, 'w') as f:
            json.dump({"key": "value"}, f)
        
        config_manager.load_config("watched")
        
        assert len(callback_called) == 1
        assert callback_called[0][0] == "watched"
    
    def test_unwatch_changes(self, config_manager, temp_config_dir):
        """测试取消注册观察者"""
        callback_called = []
        
        def callback(name, config):
            callback_called.append((name, config))
        
        config_manager.watch_changes(callback)
        config_manager.unwatch_changes(callback)
        
        # 创建并加载配置
        config_path = Path(temp_config_dir) / "unwatched.json"
        with open(config_path, 'w') as f:
            json.dump({"key": "value"}, f)
        
        config_manager.load_config("unwatched")
        
        assert len(callback_called) == 0


class TestConfigManagerSerialization:
    """ConfigManager序列化测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        ConfigManager._instance = None
        cm = ConfigManager(temp_config_dir)
        
        config_path = Path(temp_config_dir) / "serialize.json"
        with open(config_path, 'w') as f:
            json.dump({"key": "value", "number": 42}, f)
        
        return cm
    
    def test_to_json(self, config_manager):
        """测试序列化为JSON"""
        json_str = config_manager.to_json("serialize")
        
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42


class TestConfigManagerListConfigs:
    """ConfigManager列出配置测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            
            # 创建多个配置文件
            for name in ["config1", "config2", "config3"]:
                with open(Path(tmpdir) / f"{name}.json", 'w') as f:
                    json.dump({}, f)
            
            # 创建一个schema文件（不应该被列出）
            with open(schemas_dir / "config1.schema.json", 'w') as f:
                json.dump({}, f)
            
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        ConfigManager._instance = None
        return ConfigManager(temp_config_dir)
    
    def test_list_configs(self, config_manager):
        """测试列出配置"""
        configs = config_manager.list_configs()
        
        assert "config1" in configs
        assert "config2" in configs
        assert "config3" in configs
        # schema文件不应该被列出
        assert "config1.schema" not in configs


class TestConfigManagerHotReload:
    """ConfigManager热加载测试"""
    
    @pytest.fixture
    def temp_config_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            schemas_dir = Path(tmpdir) / "schemas"
            schemas_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        ConfigManager._instance = None
        return ConfigManager(temp_config_dir)
    
    def test_start_stop_watching(self, config_manager):
        """测试启动和停止监控"""
        assert not config_manager.is_watching()
        
        config_manager.start_watching(interval=0.1)
        assert config_manager.is_watching()
        
        config_manager.stop_watching()
        assert not config_manager.is_watching()
    
    def test_get_watch_status(self, config_manager):
        """测试获取监控状态"""
        status = config_manager.get_watch_status()
        
        assert 'watching' in status
        assert 'interval' in status
        assert 'watched_configs' in status
        assert 'watcher_count' in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
