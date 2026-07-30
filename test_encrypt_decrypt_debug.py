#!/usr/bin/env python3
"""测试加密和解密流程 - 调试版"""
import os
import sys
import tempfile
import pickle
import hashlib

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.encryptor.pure_cpu_engine import PureCPUEngine
from src.encryptor.key_injector import KeyInjector

def test_single_layer():
    """测试单层加密/解密"""
    print("=== 测试单层加密/解密 ===\n")
    
    # 创建测试数据
    test_data = b"Hello, World! This is a test." * 10
    print(f"原始数据大小: {len(test_data)} 字节")
    print(f"原始数据哈希: {hashlib.md5(test_data).hexdigest()}")
    
    try:
        # 初始化加密引擎（安全级别1 - 只有AES）
        engine = PureCPUEngine(security_level=1)
        
        # 加密数据
        print("\n--- 加密 (安全级别1 - 只有AES) ---")
        result = engine.encrypt_with_security_level(test_data)
        
        encrypted_data = result['encrypted_data']
        metadata = result['metadata']
        
        print(f"加密成功")
        print(f"加密后数据大小: {len(encrypted_data)} 字节")
        print(f"加密类型: {metadata.get('type')}")
        
        layers = metadata.get('layers', [])
        print(f"层数: {len(layers)}")
        
        for i, layer in enumerate(layers):
            algo = layer.get('algorithm', 'NOT SET')
            method = layer.get('method', 'NOT SET')
            mode = layer.get('mode', 'NOT SET')
            print(f"  层{i+1}: algorithm={algo}, method={method}, mode={mode}")
        
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
        print(f"\n加密文件: {encrypted_file}")
        
        # 生成解密器
        print("\n--- 生成解密器 ---")
        injector = KeyInjector()
        decryptor_file = tempfile.mktemp(suffix='_decryptor.py')
        injector.create_decryptor(metadata, decryptor_file)
        print(f"解密器文件: {decryptor_file}")
        
        # 测试解密
        print("\n--- 解密 ---")
        
        # 导入解密器
        import importlib.util
        spec = importlib.util.spec_from_file_location("decryptor", decryptor_file)
        decryptor_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(decryptor_module)
        
        # 创建解密器实例
        decryptor = decryptor_module.FileDecryptor()
        
        if decryptor.metadata:
            print(f"解密器元数据加载成功")
            
            # 解密文件
            output_path = encrypted_file.replace('.encrypted', '_decrypted.bin')
            result_path = decryptor.decrypt_file(encrypted_file, output_path)
            
            if result_path:
                # 读取解密后的数据
                with open(result_path, 'rb') as f:
                    decrypted_data = f.read()
                
                print(f"\n解密后数据大小: {len(decrypted_data)} 字节")
                print(f"解密后数据哈希: {hashlib.md5(decrypted_data).hexdigest()}")
                
                # 验证数据
                if decrypted_data == test_data:
                    print("\n✅ 解密成功！数据完全匹配！")
                    return True
                else:
                    print(f"\n❌ 解密失败！数据不匹配")
                    return False
            else:
                print("❌ 解密失败")
                return False
        else:
            print("❌ 解密器元数据加载失败")
            return False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理
        for f in [encrypted_file, decryptor_file]:
            if 'f' in dir() and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

if __name__ == '__main__':
    test_single_layer()
