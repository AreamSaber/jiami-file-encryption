#!/usr/bin/env python3
"""测试Final_Obfuscation的加密/解密 - 使用新的加密引擎"""
import os
import sys
import hashlib
import tempfile
import pickle

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.encryptor.hybrid_engine import HybridEncryptionEngine
from src.encryptor.key_injector import KeyInjector

def test_final_obfuscation_only():
    """只测试Final_Obfuscation"""
    print("=== 测试 Final_Obfuscation (使用新引擎) ===\n")
    
    engine = HybridEncryptionEngine()
    test_data = b"Hello, World! Test data for final obfuscation." * 10
    print(f"原始数据: {len(test_data)} 字节")
    print(f"原始哈希: {hashlib.md5(test_data).hexdigest()}")
    
    # 加密
    encrypted, metadata = engine._encrypt_final_obfuscation(test_data, {'obfuscation_level': 'maximum'})
    print(f"\n加密后: {len(encrypted)} 字节")
    print(f"操作数量: {len(metadata.get('applied_operations', []))}")
    
    # 检查操作类型
    ops = metadata.get('applied_operations', [])
    op_types = [op[0] for op in ops]
    print(f"操作类型: {op_types}")
    
    # 创建加密包
    full_metadata = {
        'type': 'layered',
        'layers': [metadata],
        'original_size': len(test_data)
    }
    
    encrypted_package = {
        'encrypted_data': encrypted,
        'metadata': full_metadata
    }
    
    # 保存加密文件
    encrypted_file = tempfile.mktemp(suffix='.encrypted')
    with open(encrypted_file, 'wb') as f:
        pickle.dump(encrypted_package, f)
    
    # 生成解密器
    injector = KeyInjector()
    decryptor_file = tempfile.mktemp(suffix='_decryptor.py')
    injector.create_decryptor(full_metadata, decryptor_file)
    
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
            
            print(f"\n解密后: {len(decrypted_data)} 字节")
            print(f"解密哈希: {hashlib.md5(decrypted_data).hexdigest()}")
            
            if decrypted_data == test_data:
                print("\n✅ Final_Obfuscation 测试通过！")
                return True
            else:
                print("\n❌ Final_Obfuscation 测试失败！")
                for i in range(min(len(test_data), len(decrypted_data))):
                    if test_data[i] != decrypted_data[i]:
                        print(f"第一个不同位置: {i}")
                        print(f"原始: {test_data[max(0,i-5):i+10]}")
                        print(f"解密: {decrypted_data[max(0,i-5):i+10]}")
                        break
                return False
        else:
            print("❌ 解密失败")
            return False
    else:
        print("❌ 解密器元数据加载失败")
        return False

if __name__ == '__main__':
    test_final_obfuscation_only()
