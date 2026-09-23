#!/usr/bin/env python3
"""
全局线程管理器集成测试

测试线程管理器的优先级管理和配置覆盖功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from src.thread_pool.thread_manager import thread_manager, ThreadPriority


class TestThreadManagerPriority:
    """线程管理器优先级测试"""
    
    @pytest.fixture(autouse=True)
    def reset_manager(self, monkeypatch):
        """每个测试前重置线程管理器"""
        # Priority selection must not depend on the machine's CPU clamp.
        monkeypatch.setattr(thread_manager, 'cpu_count', 8)
        thread_manager.reset_to_defaults()
        yield
        thread_manager.reset_to_defaults()
    
    def test_default_state(self):
        """测试默认状态"""
        status = thread_manager.get_status_info()
        assert status['max_threads'] > 0
        assert status['active_source'] == 'system_default'

    def test_thread_limit_on_two_core_machine(self, monkeypatch):
        monkeypatch.setattr(thread_manager, 'cpu_count', 2)
        thread_manager.set_gui_config(max_threads=12)
        assert thread_manager.get_max_threads() == 4
        assert thread_manager.get_status_info()['active_priority'] == 'GUI_OVERRIDE'
    
    def test_config_file_priority(self):
        """测试配置文件优先级"""
        thread_manager.set_config(
            priority=ThreadPriority.CONFIG_FILE,
            source='test_config_file',
            max_threads=4
        )
        
        status = thread_manager.get_status_info()
        assert status['max_threads'] == 4
        assert status['active_source'] == 'test_config_file'
    
    def test_algorithm_recommend_overrides_config(self):
        """测试算法推荐覆盖配置文件"""
        # 先设置配置文件
        thread_manager.set_config(
            priority=ThreadPriority.CONFIG_FILE,
            source='test_config_file',
            max_threads=4
        )
        
        # 再设置算法推荐
        thread_manager.set_algorithm_recommendation('aes256', 6)
        
        status = thread_manager.get_status_info()
        assert status['max_threads'] == 6
    
    def test_user_setting_overrides_algorithm(self):
        """测试用户设置覆盖算法推荐"""
        # 先设置算法推荐
        thread_manager.set_algorithm_recommendation('aes256', 6)
        
        # 再设置用户配置
        thread_manager.set_config(
            priority=ThreadPriority.USER_SETTING,
            source='test_user_setting',
            max_threads=8
        )
        
        status = thread_manager.get_status_info()
        assert status['max_threads'] == 8
    
    def test_gui_override_highest_priority(self):
        """测试GUI覆盖具有最高优先级"""
        # 设置用户配置
        thread_manager.set_config(
            priority=ThreadPriority.USER_SETTING,
            source='test_user_setting',
            max_threads=8
        )
        
        # 设置GUI配置
        thread_manager.set_gui_config(max_threads=12)
        
        status = thread_manager.get_status_info()
        assert status['max_threads'] == 12
        assert status['active_priority'] == 'GUI_OVERRIDE'
    
    def test_lower_priority_cannot_override_higher(self):
        """测试低优先级不能覆盖高优先级"""
        # 先设置GUI配置（最高优先级）
        thread_manager.set_gui_config(max_threads=12)
        
        # 尝试用配置文件覆盖（低优先级）
        thread_manager.set_config(
            priority=ThreadPriority.CONFIG_FILE,
            source='test_config_file',
            max_threads=4
        )
        
        status = thread_manager.get_status_info()
        # GUI配置应该保持不变
        assert status['max_threads'] == 12
        assert status['active_priority'] == 'GUI_OVERRIDE'


class TestThreadManagerConfig:
    """线程管理器配置测试"""
    
    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """每个测试前重置线程管理器"""
        thread_manager.reset_to_defaults()
        yield
        thread_manager.reset_to_defaults()
    
    def test_get_config(self):
        """测试获取配置"""
        config = thread_manager.get_config()
        assert 'max_threads' in config
        assert 'enable_threading' in config
        assert 'source' in config
        assert 'priority' in config
    
    def test_get_max_threads(self):
        """测试获取最大线程数"""
        max_threads = thread_manager.get_max_threads()
        assert max_threads > 0
        assert isinstance(max_threads, int)
    
    def test_is_threading_enabled(self):
        """测试线程启用状态"""
        enabled = thread_manager.is_threading_enabled()
        assert isinstance(enabled, bool)
    
    def test_disable_threading(self):
        """测试禁用线程"""
        thread_manager.set_config(
            priority=ThreadPriority.USER_SETTING,
            source='test',
            enable_threading=False
        )
        
        assert not thread_manager.is_threading_enabled()
    
    def test_get_optimal_thread_count(self):
        """测试获取最优线程数"""
        # 小数据
        small_count = thread_manager.get_optimal_thread_count(1024, 'aes256')
        assert small_count >= 1
        
        # 大数据
        large_count = thread_manager.get_optimal_thread_count(100 * 1024 * 1024, 'aes256')
        assert large_count >= 1
        assert large_count <= thread_manager.get_max_threads()


class TestThreadManagerStatus:
    """线程管理器状态测试"""
    
    @pytest.fixture(autouse=True)
    def reset_manager(self):
        thread_manager.reset_to_defaults()
        yield
        thread_manager.reset_to_defaults()
    
    def test_get_status_info(self):
        """测试获取状态信息"""
        status = thread_manager.get_status_info()
        
        assert 'cpu_count' in status
        assert 'max_threads' in status
        assert 'threading_enabled' in status
        assert 'active_source' in status
        assert 'active_priority' in status
    
    def test_cpu_count_positive(self):
        """测试CPU核心数为正数"""
        assert thread_manager.cpu_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
