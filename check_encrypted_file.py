#!/usr/bin/env python3
"""
检查加密文件的元数据
"""

import os
import sys
import pickle

def check_encrypted_file(file_path):
    """检查加密文件的元数据"""
    print(f"检查文件: {file_path}")
    print("=" * 60)
    
    try:
        with open(file_path, 'rb') as f:
            package = pickle.load(f)
        
        metadata = package.get('metadata', {})
        encrypted_data = package.get('encrypted_data', b'')
        
        print(f"加密数据大小: {len(encrypted_data):,} 字节")
        print(f"引擎类型: {metadata.get('engine_type', 'unknown')}")
        print(f"安全级别: {metadata.get('security_level', 'unknown')}")
        print(f"原始大小: {metadata.get('original_size', 'unknown')}")
        print(f"GPU专用: {metadata.get('gpu_only', False)}")
        
        layers = metadata.get('layers', [])
        print(f"\n加密层数: {len(layers)}")
        
        for i, layer in enumerate(layers):
            print(f"\n--- 第 {i+1} 层 ---")
            algorithm = layer.get('algorithm', 'unknown')
            print(f"  算法: {algorithm}")
            print(f"  GPU加速: {layer.get('gpu_accelerated', False)}")
            print(f"  GPU专用: {layer.get('gpu_only', False)}")
            print(f"  后端信息: {layer.get('backend_info', 'unknown')}")
            
            # 检查特定算法的参数
            if 'matrix' in algorithm.lower():
                print(f"  矩阵大小: {layer.get('matrix_size', 'unknown')}")
                print(f"  种子: {layer.get('seed', 'unknown')}")
                print(f"  原始长度: {layer.get('original_length', 'unknown')}")
                print(f"  变换矩阵: {'已保存' if layer.get('transform_matrix') else '未保存'}")
            
            if 'chacha20' in algorithm.lower():
                print(f"  密钥长度: {len(layer.get('key', b''))} 字节")
                print(f"  Nonce长度: {len(layer.get('nonce', b''))} 字节")
            
            if 'salsa20' in algorithm.lower():
                print(f"  密钥长度: {len(layer.get('key', b''))} 字节")
                print(f"  Nonce长度: {len(layer.get('nonce', b''))} 字节")
            
            if 'aes' in algorithm.lower():
                print(f"  模式: {layer.get('mode', 'unknown')}")
                print(f"  密钥长度: {len(layer.get('key', b''))} 字节")
                print(f"  IV长度: {len(layer.get('iv', b''))} 字节")
            
            if 'blowfish' in algorithm.lower():
                print(f"  模式: {layer.get('mode', 'unknown')}")
                print(f"  密钥长度: {len(layer.get('key', b''))} 字节")
                print(f"  IV长度: {len(layer.get('iv', b''))} 字节")
        
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 检查桌面上的加密文件
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    
    # 查找加密文件
    encrypted_files = []
    for f in os.listdir(desktop):
        if f.endswith('.encrypted'):
            encrypted_files.append(os.path.join(desktop, f))
    
    if not encrypted_files:
        print("桌面上未找到加密文件")
        sys.exit(1)
    
    for file_path in encrypted_files:
        check_encrypted_file(file_path)
        print("\n")
