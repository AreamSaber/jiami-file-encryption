"""
测试模块

提供全面的单元测试、集成测试和性能测试。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 测试配置
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_OUTPUT_DIR = Path(__file__).parent / "test_output"

# 确保测试目录存在
TEST_DATA_DIR.mkdir(exist_ok=True)
TEST_OUTPUT_DIR.mkdir(exist_ok=True)

# 测试工具函数
def create_test_file(filename: str, content: bytes = None, size: int = None) -> Path:
    """创建测试文件"""
    if content is None and size is None:
        content = b"Test file content for encryption testing."
    elif size is not None:
        content = os.urandom(size)
    
    file_path = TEST_DATA_DIR / filename
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path

def cleanup_test_files():
    """清理测试文件"""
    import shutil
    
    if TEST_OUTPUT_DIR.exists():
        shutil.rmtree(TEST_OUTPUT_DIR)
    TEST_OUTPUT_DIR.mkdir(exist_ok=True)

def get_test_config():
    """获取测试配置"""
    return {
        'test_data_dir': TEST_DATA_DIR,
        'test_output_dir': TEST_OUTPUT_DIR,
        'small_file_size': 1024,          # 1KB
        'medium_file_size': 1024 * 1024,  # 1MB
        'large_file_size': 10 * 1024 * 1024,  # 10MB
    }
