#!/usr/bin/env python3
"""测试加密和解密流程"""
import os
import sys
import tempfile
import pickle

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.encryptor.pure_cpu_engine import PureCPUEngine
from src.encryptor.key_injector import KeyInjector

def test_encrypt_decrypt():
    """测试加密和解密"""
    print("=== 测试加密/解密流程 ===\n")
    
    # 创建测试数据
    test_data = b"Hello, World! This is a test file for encryption and decryption." * 100
    print(f"原始数据大小: {len(test_data)} 字节")
    
    try:
        # 初始化加密引擎（安全级别5）
        engine = PureCPUEngine(security_level=5)
        
        # 加密数据
        print("\n--- 加密 (安全级别5) ---")
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
            thread_count = layer.get('thread_count', 1)
            chunks_count = len(layer.get('chunks', {}))
            print(f"  层{i+1}: algorithm={algo}, method={method}, threads={thread_count}, chunks={chunks_count}")
            
            # 如果有chunks，检查第一个chunk的algorithm
            if chunks_count > 0:
                first_chunk = list(layer['chunks'].values())[0]
                chunk_algo = first_chunk.get('algorithm', 'NOT SET')
                print(f"       第一个chunk的algorithm: {chunk_algo}")
        
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
            print(f"加密类型: {decryptor.metadata.get('type')}")
            print(f"层数: {len(decryptor.metadata.get('layers', []))}")
            
            # 解密文件
            output_path = encrypted_file.replace('.encrypted', '_decrypted.bin')
            result_path = decryptor.decrypt_file(encrypted_file, output_path)
            
            if result_path:
                # 读取解密后的数据
                with open(result_path, 'rb') as f:
                    decrypted_data = f.read()
                
                print(f"\n解密后数据大小: {len(decrypted_data)} 字节")
                
                # 验证数据
                if decrypted_data == test_data:
                    print("\n✅ 解密成功！数据完全匹配！")
                else:
                    print(f"\n❌ 解密失败！数据不匹配")
                    print(f"   原始大小: {len(test_data)}")
                    print(f"   解密大小: {len(decrypted_data)}")
                    # 找出第一个不同的位置
                    for i in range(min(len(test_data), len(decrypted_data))):
                        if test_data[i] != decrypted_data[i]:
                            print(f"   第一个不同位置: {i}")
                            print(f"   原始: {test_data[max(0,i-5):i+10]}")
                            print(f"   解密: {decrypted_data[max(0,i-5):i+10]}")
                            break
                
                # 清理解密文件
                if os.path.exists(result_path):
                    # 检查是否是文件夹
                    if os.path.isdir(os.path.dirname(result_path)):
                        import shutil
                        shutil.rmtree(os.path.dirname(result_path), ignore_errors=True)
                    else:
                        os.remove(result_path)
            else:
                print("❌ 解密失败")
        else:
            print("❌ 解密器元数据加载失败")
        
        # 清理
        if os.path.exists(encrypted_file):
            os.remove(encrypted_file)
        if os.path.exists(decryptor_file):
            os.remove(decryptor_file)
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_encrypt_decrypt()
