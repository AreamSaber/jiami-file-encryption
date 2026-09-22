#!/usr/bin/env python3
"""
pytest配置文件

配置测试框架、fixtures和Hypothesis设置
"""

import sys
from pathlib import Path

import pytest
from hypothesis import settings, Verbosity

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# 配置Hypothesis
settings.register_profile("ci", max_examples=100, verbosity=Verbosity.normal)
settings.register_profile("dev", max_examples=10, verbosity=Verbosity.verbose)
settings.register_profile("debug", max_examples=5, verbosity=Verbosity.verbose)

# 默认使用ci配置
settings.load_profile("ci")


# ============ Fixtures ============

@pytest.fixture(autouse=True)
def isolate_config_manager():
    """Config tests must not leave their deleted temporary directory active."""
    from src.utils.config_manager import ConfigManager
    ConfigManager._instance = None
    yield
    if ConfigManager._instance is not None:
        ConfigManager._instance.stop_watching()
    ConfigManager._instance = None

@pytest.fixture
def sample_encryptor():
    """提供测试用加密器"""
    try:
        from src.encryptor.main import FileEncryptor
        return FileEncryptor()
    except ImportError:
        pytest.skip("FileEncryptor不可用")


@pytest.fixture
def sample_config():
    """提供测试用配置"""
    return {
        "name": "test",
        "security_level": 1,
        "layers": [{"method": "aes256", "mode": "GCM"}]
    }


@pytest.fixture
def temp_file(tmp_path):
    """提供临时测试文件"""
    test_file = tmp_path / "test_data.bin"
    test_file.write_bytes(b"Test data for encryption " * 100)
    return test_file


@pytest.fixture
def config_manager(tmp_path):
    """提供测试用配置管理器"""
    try:
        from src.utils.config_manager import ConfigManager
        ConfigManager._instance = None
        return ConfigManager(str(tmp_path))
    except ImportError:
        pytest.skip("ConfigManager不可用")


@pytest.fixture
def algorithm_registry():
    """提供算法注册表"""
    try:
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        return AlgorithmRegistry()
    except ImportError:
        pytest.skip("AlgorithmRegistry不可用")


# ============ 测试标记 ============

def pytest_configure(config):
    """配置自定义标记"""
    config.addinivalue_line(
        "markers", "slow: 标记慢速测试"
    )
    config.addinivalue_line(
        "markers", "gpu: 标记需要GPU的测试"
    )
    config.addinivalue_line(
        "markers", "integration: 标记集成测试"
    )
