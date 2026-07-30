#!/usr/bin/env python3
"""检查加密文件的元数据结构"""
import pickle
import os

# 查找桌面上最新的加密文件
desktop = os.path.expanduser('~/Desktop')
encrypted_files = [f for f in os.listdir(desktop) if f.endswith('.encrypted')]
if encrypted_files:
    encrypted_files.sort(key=lambda x: os.path.getmtime(os.path.join(desktop, x)), reverse=True)
    latest = os.path.join(desktop, encrypted_files[0])
    print(f'检查文件: {latest}')
    
    with open(latest, 'rb') as f:
        pkg = pickle.load(f)
    
    metadata = pkg.get('metadata', {})
    print(f'加密类型: {metadata.get("type")}')
    print(f'层数: {len(metadata.get("layers", []))}')
    
    # 检查每一层的算法和参数类型
    for i, layer in enumerate(metadata.get('layers', [])):
        algo = layer.get('algorithm', 'unknown')
        print(f'\n层 {i+1}: {algo}')
        
        # 检查key和iv的类型
        if 'key' in layer:
            key = layer['key']
            print(f'  key类型: {type(key).__name__}, 长度: {len(key) if hasattr(key, "__len__") else "N/A"}')
        if 'iv' in layer:
            iv = layer['iv']
            print(f'  iv类型: {type(iv).__name__}, 长度: {len(iv) if hasattr(iv, "__len__") else "N/A"}')
        if 'nonce' in layer:
            nonce = layer['nonce']
            print(f'  nonce类型: {type(nonce).__name__}, 长度: {len(nonce) if hasattr(nonce, "__len__") else "N/A"}')
        if 'bit_positions' in layer:
            print(f'  bit_positions: {layer["bit_positions"]}')
        if 'obfuscation_level' in layer:
            print(f'  obfuscation_level: {layer["obfuscation_level"]}')
else:
    print('未找到加密文件')


# 详细检查所有层
print("\n=== 详细检查所有层 ===")
for i, layer in enumerate(metadata.get('layers', [])):
    algo = layer.get('algorithm', 'NOT SET')
    method = layer.get('method', 'NOT SET')
    print(f"\n层 {i+1}:")
    print(f"  algorithm: {algo}")
    print(f"  method: {method}")
    print(f"  所有键: {list(layer.keys())}")
    
    # 检查特定字段
    if 'key' in layer:
        print(f"  key长度: {len(layer.get('key', b''))} 字节")
    if 'iv' in layer:
        print(f"  iv长度: {len(layer.get('iv', b''))} 字节")
    if 'nonce' in layer:
        print(f"  nonce长度: {len(layer.get('nonce', b''))} 字节")
    if 'tag' in layer:
        print(f"  tag长度: {len(layer.get('tag', b''))} 字节")
    if 'mode' in layer:
        print(f"  mode: {layer.get('mode')}")
    if 'thread_count' in layer:
        print(f"  thread_count: {layer.get('thread_count')}")
    if 'chunks' in layer:
        print(f"  chunks数量: {len(layer['chunks'])}")
    if 'operations' in layer:
        print(f"  operations数量: {len(layer.get('operations', []))}")
    if 'seed' in layer:
        print(f"  seed: {layer.get('seed')}")
    if 'bit_positions' in layer:
        print(f"  bit_positions: {layer.get('bit_positions')}")
    if 'obfuscation_level' in layer:
        print(f"  obfuscation_level: {layer.get('obfuscation_level')}")


# 详细检查第1层（Pre_Scramble）的chunks
print("\n=== 详细检查第1层 (Pre_Scramble) 的chunks ===")
layer1 = metadata.get('layers', [])[0]
chunks = layer1.get('chunks', {})
print(f"chunks数量: {len(chunks)}")
for chunk_key, chunk_data in chunks.items():
    print(f"\nChunk {chunk_key}:")
    print(f"  所有键: {list(chunk_data.keys())}")
    if 'algorithm' in chunk_data:
        print(f"  algorithm: {chunk_data['algorithm']}")
    if 'operations' in chunk_data:
        print(f"  operations数量: {len(chunk_data['operations'])}")
    if 'scramble_operations' in chunk_data:
        print(f"  scramble_operations数量: {len(chunk_data['scramble_operations'])}")
