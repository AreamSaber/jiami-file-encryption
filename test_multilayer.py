#!/usr/bin/env python3
"""测试多层 GPU 加密/解密 - 逐层验证"""

import os
import sys
sys.path.insert(0, '.')

def test_multilayer():
    print("=" * 60)
    print("测试 5 层 GPU 加密/解密")
    print("=" * 60)
    
    from src.encryptor.pure_gpu_only_engine import PureGPUOnlyEngine
    from src.decryptor.gpu_template import AlgorithmRegistry
    
    # 测试数据
    original_data = b'PK\x03\x04' + b'Hello World!' * 10
    print(f"原始数据: {original_data[:20].hex()}")
    print(f"原始大小: {len(original_data)} 字节")
    
    # 加密
    engine = PureGPUOnlyEngine(security_level=5)
    result = engine.encrypt_with_security_level(original_data)
    
    encrypted_data = result['encrypted_data']
    layers = result['metadata']['layers']
    
    print(f"\n加密完成!")
    print(f"加密后大小: {len(encrypted_data)} 字节")
    print(f"加密层数: {len(layers)}")
    
    # 打印每层的详细信息
    print("\n加密层详情:")
    for i, layer in enumerate(layers):
        algo = layer.get('algorithm')
        has_key = 'key' in layer
        has_nonce = 'nonce' in layer
        has_iv = 'iv' in layer
        has_matrix = 'transform_matrix' in layer
        gpu_only = layer.get('gpu_only', False)
        backend = layer.get('backend_info', 'N/A')
        print(f"  层 {i+1}: {algo}")
        print(f"    - gpu_only: {gpu_only}, backend: {backend}")
        print(f"    - has_key: {has_key}, has_nonce: {has_nonce}, has_iv: {has_iv}, has_matrix: {has_matrix}")
    
    # 逐层解密并验证
    print("\n开始逐层解密...")
    registry = AlgorithmRegistry()
    
    # 保存每层解密后的数据用于调试
    decrypted = encrypted_data
    
    for i, layer in enumerate(reversed(layers)):
        layer_idx = len(layers) - i
        algo = layer.get('algorithm')
        
        print(f"\n解密层 {layer_idx}: {algo}")
        print(f"  输入大小: {len(decrypted)}")
        print(f"  输入前8字节: {decrypted[:8].hex()}")
        
        handler = registry.get_handler(algo)
        decrypted = handler.decrypt(decrypted, layer)
        
        print(f"  输出大小: {len(decrypted)}")
        print(f"  输出前8字节: {decrypted[:8].hex()}")
    
    # 最终比较
    print("\n" + "=" * 60)
    print("最终结果")
    print("=" * 60)
    print(f"原始数据头: {original_data[:20].hex()}")
    print(f"解密数据头: {decrypted[:20].hex()}")
    
    if decrypted == original_data:
        print("✅ 多层加密/解密测试通过!")
        return True
    else:
        print("❌ 多层加密/解密测试失败!")
        diff = sum(1 for a, b in zip(original_data, decrypted) if a != b)
        print(f"差异字节数: {diff}/{len(original_data)}")
        
        # 找出第一个不同的位置
        for i, (a, b) in enumerate(zip(original_data, decrypted)):
            if a != b:
                print(f"第一个差异位置: {i}, 原始: {a:02x}, 解密: {b:02x}")
                break
        return False

if __name__ == '__main__':
    test_multilayer()
