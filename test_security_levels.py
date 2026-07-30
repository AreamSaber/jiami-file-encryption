#!/usr/bin/env python3
"""测试不同安全级别的加密/解密"""
import os
import sys
import tempfile
import pickle
import hashlib

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.encryptor.pure_cpu_engine import PureCPUEngine
from src.encryptor.key_injector import KeyInjector

def test_security_level(level):
    """测试指定安全级别的加密/解密"""
    print(f"\n=== 测试安全级别 {level} ===")
    
    # 创建测试数据
    test_data = b"Hello, World! This is a test file for encryption and decryption." * 10
    print(f"原始数据: {len(test_data)} 字节, 哈希: {hashlib.md5(test_data).hexdigest()}")
    
    try:
        # 初始化加密引擎
        engine = PureCPUEngine(security_level=level)
        print(f"算法: {engine.current_algorithms}")
        
        # 加密数据
        result = engine.encrypt_with_security_level(test_data)
        
        encrypted_data = result['encrypted_data']
        metadata = result['metadata']
        
        print(f"加密后: {len(encrypted_data)} 字节")
        print(f"层数: {len(metadata.get('layers', []))}")
        
        # 添加原始大小到元数据
        metadata['original_size'] = len(test_data)
        
        # 创建加密包
        encrypted_package = {
            'encrypted_data': encrypted_data,
            'metadata': metadata
        }
        
        # 保存加密文件
        encrypted_file = tempfile.mktemp(suffix='.encrypted')
        with open(encrypted_file, 'wb') as f:
            pickle.dump(encrypted_package, f)
        
        # 生成解密器
        injector = KeyInjector()
        decryptor_file = tempfile.mktemp(suffix='_decryptor.py')
        injector.create_decryptor(metadata, decryptor_file)
        
        # 导入解密器
        import importlib.util
        spec = importlib.util.spec_from_file_location("decryptor", decryptor_file)
        decryptor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(decryptor_module)
        
        # 创建解密器实例
        decryptor = decryptor_module.FileDecryptor()
        
        if decryptor.metadata:
            # 解密文件
            output_path = encrypted_file.replace('.encrypted', '_decrypted.bin')
            result_path = decryptor.decrypt_file(encrypted_file, output_path)
            
            if result_path:
                # 读取解密后的数据
                with open(result_path, 'rb') as f:
                    decrypted_data = f.read()
                
                print(f"解密后: {len(decrypted_data)} 字节, 哈希: {hashlib.md5(decrypted_data).hexdigest()}")
                
                # 验证数据
                if decrypted_data == test_data:
                    print(f"✅ 安全级别 {level} 测试通过！")
                    return True
                else:
                    print(f"❌ 安全级别 {level} 测试失败！数据不匹配")
                    return False
            else:
                print(f"❌ 安全级别 {level} 解密失败")
                return False
        else:
            print(f"❌ 安全级别 {level} 解密器元数据加载失败")
            return False
            
    except Exception as e:
        print(f"❌ 安全级别 {level} 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    results = {}
    for level in range(1, 6):
        results[level] = test_security_level(level)
    
    print("\n=== 测试结果汇总 ===")
    for level, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"安全级别 {level}: {status}")
