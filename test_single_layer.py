#!/usr/bin/env python3
"""逐层测试 GPU 加密/解密"""

import os
import sys
sys.path.insert(0, '.')

def test_chacha20():
    """测试 ChaCha20 单层加密解密"""
    print("=" * 60)
    print("测试 ChaCha20")
    print("=" * 60)
    
    from src.gpu.gpu_manager import gpu_manager
    from src.decryptor.gpu_template import ChaCha20Handler
    
    # 测试数据
    test_data = b'PK\x03\x04' + b'Hello World!' * 10
    key = os.urandom(32)
    nonce = os.urandom(16)
    
    print(f"原始数据: {test_data[:20].hex()}")
    
    # GPU 加密
    result = gpu_manager.encrypt_data(test_data, 'chacha20', {
        'key': key,
        'nonce': nonce
    })
    
    if not result:
        print("GPU 加密失败!")
        return False
    
    encrypted = result['encrypted_data']
    print(f"加密后: {encrypted[:20].hex()}")
    
    # 解密
    handler = ChaCha20Handler()
    decrypted = handler._decrypt_gpu_custom(encrypted, key, nonce)
    print(f"解密后: {decrypted[:20].hex()}")
    
    if decrypted == test_data:
        print("✅ ChaCha20 测试通过!")
        return True
    else:
        print("❌ ChaCha20 测试失败!")
        diff = sum(1 for a, b in zip(test_data, decrypted) if a != b)
        print(f"差异字节数: {diff}/{len(test_data)}")
        return False

def test_salsa20():
    """测试 Salsa20 单层加密解密"""
    print("\n" + "=" * 60)
    print("测试 Salsa20")
    print("=" * 60)
    
    from src.gpu.gpu_manager import gpu_manager
    from src.decryptor.gpu_template import Salsa20Handler
    
    # 测试数据
    test_data = b'PK\x03\x04' + b'Hello World!' * 10
    key = os.urandom(32)
    nonce = os.urandom(8)
    
    print(f"原始数据: {test_data[:20].hex()}")
    
    # GPU 加密
    result = gpu_manager.encrypt_data(test_data, 'salsa20', {
        'key': key,
        'nonce': nonce
    })
    
    if not result:
        print("GPU 加密失败!")
        return False
    
    encrypted = result['encrypted_data']
    print(f"加密后: {encrypted[:20].hex()}")
    
    # 解密
    handler = Salsa20Handler()
    decrypted = handler._decrypt_gpu_custom(encrypted, key, nonce)
    print(f"解密后: {decrypted[:20].hex()}")
    
    if decrypted == test_data:
        print("✅ Salsa20 测试通过!")
        return True
    else:
        print("❌ Salsa20 测试失败!")
        diff = sum(1 for a, b in zip(test_data, decrypted) if a != b)
        print(f"差异字节数: {diff}/{len(test_data)}")
        return False

def test_matrix_cipher():
    """测试 Matrix Cipher 单层加密解密"""
    print("\n" + "=" * 60)
    print("测试 Matrix Cipher")
    print("=" * 60)
    
    from src.gpu.gpu_manager import gpu_manager
    from src.decryptor.gpu_template import MatrixCipherHandler
    
    # 测试数据
    test_data = b'PK\x03\x04' + b'Hello World!' * 10
    matrix_size = 8
    seed = 12345
    
    print(f"原始数据: {test_data[:20].hex()}")
    
    # GPU 加密
    result = gpu_manager.encrypt_data(test_data, 'matrix_cipher', {
        'matrix_size': matrix_size,
        'seed': seed,
        'original_length': len(test_data)
    })
    
    if not result:
        print("GPU 加密失败!")
        return False
    
    encrypted = result['encrypted_data']
    transform_matrix = result.get('transform_matrix')
    print(f"加密后: {encrypted[:20].hex()}")
    print(f"有 transform_matrix: {transform_matrix is not None}")
    
    # 解密
    handler = MatrixCipherHandler()
    decrypted = handler.decrypt(encrypted, {
        'matrix_size': matrix_size,
        'seed': seed,
        'original_length': len(test_data),
        'transform_matrix': transform_matrix
    })
    print(f"解密后: {decrypted[:20].hex()}")
    
    if decrypted == test_data:
        print("✅ Matrix Cipher 测试通过!")
        return True
    else:
        print("❌ Matrix Cipher 测试失败!")
        diff = sum(1 for a, b in zip(test_data, decrypted) if a != b)
        print(f"差异字节数: {diff}/{len(test_data)}")
        return False

if __name__ == '__main__':
    results = []
    results.append(("ChaCha20", test_chacha20()))
    results.append(("Salsa20", test_salsa20()))
    results.append(("Matrix Cipher", test_matrix_cipher()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
