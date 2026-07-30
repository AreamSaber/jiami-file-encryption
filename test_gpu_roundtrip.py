#!/usr/bin/env python3
"""测试 GPU 加密/解密往返 - 直接测试加密引擎"""

import os
import sys
import pickle
import zipfile
import tempfile

sys.path.insert(0, '.')

def test_roundtrip():
    # 创建测试 ZIP 文件
    test_dir = tempfile.mkdtemp()
    test_zip = os.path.join(test_dir, 'test.zip')
    test_content = b'This is test content for encryption test!'

    with zipfile.ZipFile(test_zip, 'w') as zf:
        zf.writestr('test.txt', test_content)

    print(f'创建测试 ZIP: {test_zip}')
    print(f'ZIP 大小: {os.path.getsize(test_zip)} 字节')

    with open(test_zip, 'rb') as f:
        original_data = f.read()
    print(f'原始数据头: {original_data[:4].hex()} ({original_data[:4]})')
    print(f'原始大小: {len(original_data)} 字节')

    # 直接使用 PureGPUOnlyEngine 加密
    from src.encryptor.pure_gpu_only_engine import PureGPUOnlyEngine
    
    engine = PureGPUOnlyEngine(security_level=5)
    result = engine.encrypt_with_security_level(original_data)
    
    encrypted_data = result['encrypted_data']
    metadata = result['metadata']
    
    print(f'加密成功!')
    print(f'加密后大小: {len(encrypted_data)} 字节')
    print(f'加密层数: {len(metadata["layers"])}')
    
    # 模拟保存和加载（添加 original_size）
    pkg = {
        'encrypted_data': encrypted_data,
        'metadata': metadata,
        'original_size': len(original_data)
    }

    # 解密
    from src.decryptor.gpu_template import AlgorithmRegistry
    
    print(f'\n开始解密...')

    # 逐层解密
    registry = AlgorithmRegistry()
    decrypted = pkg['encrypted_data']
    layers = pkg['metadata']['layers']

    for i, layer in enumerate(reversed(layers)):
        algo = layer.get('algorithm')
        print(f'解密层 {len(layers)-i}: {algo}')
        handler = registry.get_handler(algo)
        decrypted = handler.decrypt(decrypted, layer)
        print(f'  解密后大小: {len(decrypted)}')

    # 截断到原始大小
    orig_size = pkg.get('original_size') or pkg.get('metadata', {}).get('original_size')
    if orig_size:
        print(f'截断到原始大小: {orig_size}')
        decrypted = decrypted[:orig_size]

    print(f'解密后数据头: {decrypted[:4].hex()} ({decrypted[:4]})')

    if decrypted[:4] == b'PK\x03\x04':
        print('✅ 解密成功! 是有效的 ZIP 文件')
    else:
        print('❌ 解密失败! 不是有效的 ZIP 文件')
        print(f'原始: {original_data[:20].hex()}')
        print(f'解密: {decrypted[:20].hex()}')
        
        # 比较差异
        if original_data == decrypted:
            print('✅ 数据完全匹配!')
        else:
            diff_count = sum(1 for a, b in zip(original_data, decrypted) if a != b)
            print(f'❌ 数据不匹配! 差异字节数: {diff_count}')

if __name__ == '__main__':
    test_roundtrip()
