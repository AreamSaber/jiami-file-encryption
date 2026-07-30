#!/usr/bin/env python3
"""检查加密文件并测试解密"""
import pickle
import os
import sys

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

desktop = os.path.expanduser('~/Desktop')
encrypted_files = [f for f in os.listdir(desktop) if f.endswith('.encrypted')]
if encrypted_files:
    encrypted_files.sort(key=lambda x: os.path.getmtime(os.path.join(desktop, x)), reverse=True)
    latest = os.path.join(desktop, encrypted_files[0])
    print(f'最新加密文件: {os.path.basename(latest)}')
    
    with open(latest, 'rb') as f:
        pkg = pickle.load(f)
    
    metadata = pkg.get('metadata', {})
    layers = metadata.get('layers', [])
    
    # 检查第1层的chunks
    layer1 = layers[0]
    chunks = layer1.get('chunks', {})
    first_chunk_key = list(chunks.keys())[0]
    first_chunk = chunks[first_chunk_key]
    
    print(f'第1层 algorithm: {layer1.get("algorithm", "NOT SET")}')
    print(f'第1层 method: {layer1.get("method")}')
    print(f'第1层 chunks数量: {len(chunks)}')
    print(f'第一个chunk的algorithm: {first_chunk.get("algorithm")}')
    print(f'第一个chunk的operations数量: {len(first_chunk.get("operations", []))}')
    
    # 测试解密
    print('\n=== 测试解密 ===')
    from src.decryptor.template import FileDecryptor
    
    decryptor = FileDecryptor()
    if decryptor.metadata:
        print(f'元数据加载成功')
        print(f'加密类型: {decryptor.metadata.get("type")}')
        print(f'层数: {len(decryptor.metadata.get("layers", []))}')
    else:
        print('元数据加载失败 - 这是模板文件')
else:
    print('未找到加密文件')
