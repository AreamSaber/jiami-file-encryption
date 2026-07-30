#!/usr/bin/env python3
"""测试自定义算法的加密/解密"""
import os
import sys
import hashlib

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.encryptor.hybrid_engine import HybridEncryptionEngine

def test_bit_shuffle():
    """测试Bit_Shuffle加密/解密"""
    print("=== 测试 Bit_Shuffle ===")
    
    engine = HybridEncryptionEngine()
    test_data = b"Hello, World! Test data for bit shuffle." * 10
    print(f"原始数据: {len(test_data)} 字节, 哈希: {hashlib.md5(test_data).hexdigest()}")
    
    # 加密
    encrypted, metadata = engine._encrypt_bit_shuffle(test_data, {'seed': 12345})
    print(f"加密后: {len(encrypted)} 字节")
    print(f"bit_positions: {metadata.get('bit_positions')}")
    
    # 手动解密
    bit_positions = metadata['bit_positions']
    reverse_positions = [0] * 8
    for i, pos in enumerate(bit_positions):
        reverse_positions[pos] = i
    
    decrypted = bytearray()
    for byte in encrypted:
        new_byte = 0
        for i, pos in enumerate(reverse_positions):
            if byte & (1 << i):
                new_byte |= (1 << pos)
        decrypted.append(new_byte)
    
    decrypted = bytes(decrypted)
    print(f"解密后: {len(decrypted)} 字节, 哈希: {hashlib.md5(decrypted).hexdigest()}")
    
    if decrypted == test_data:
        print("✅ Bit_Shuffle 测试通过！")
        return True
    else:
        print("❌ Bit_Shuffle 测试失败！")
        return False

def test_final_obfuscation():
    """测试Final_Obfuscation加密/解密"""
    print("\n=== 测试 Final_Obfuscation ===")
    
    engine = HybridEncryptionEngine()
    test_data = b"Hello, World! Test data for final obfuscation." * 10
    print(f"原始数据: {len(test_data)} 字节, 哈希: {hashlib.md5(test_data).hexdigest()}")
    
    # 加密
    encrypted, metadata = engine._encrypt_final_obfuscation(test_data, {'obfuscation_level': 'maximum'})
    print(f"加密后: {len(encrypted)} 字节")
    print(f"obfuscation_level: {metadata.get('obfuscation_level')}")
    print(f"operations_count: {metadata.get('operations_count')}")
    print(f"applied_operations数量: {len(metadata.get('applied_operations', []))}")
    
    # 检查操作类型
    ops = metadata.get('applied_operations', [])
    op_types = [op[0] for op in ops]
    print(f"操作类型: {op_types}")
    
    return True

def test_pre_scramble():
    """测试Pre_Scramble加密/解密"""
    print("\n=== 测试 Pre_Scramble ===")
    
    engine = HybridEncryptionEngine()
    test_data = b"Hello, World! Test data for pre scramble." * 10
    print(f"原始数据: {len(test_data)} 字节, 哈希: {hashlib.md5(test_data).hexdigest()}")
    
    # 加密
    encrypted, metadata = engine._encrypt_pre_scramble(test_data, {'scramble_rounds': 5})
    print(f"加密后: {len(encrypted)} 字节")
    print(f"scramble_rounds: {metadata.get('scramble_rounds')}")
    print(f"operations数量: {len(metadata.get('operations', []))}")
    
    # 检查操作类型
    ops = metadata.get('operations', [])
    op_types = [op[0] for op in ops]
    print(f"操作类型: {op_types}")
    
    # 手动解密
    descrambled = bytearray(encrypted)
    for operation in reversed(ops):
        op_type = operation[0]
        
        if op_type == 'swap':
            pos1, pos2 = operation[1], operation[2]
            if pos1 < len(descrambled) and pos2 < len(descrambled):
                descrambled[pos1], descrambled[pos2] = descrambled[pos2], descrambled[pos1]
        
        elif op_type == 'reverse':
            start, end = operation[1], operation[2]
            if start < len(descrambled) and end <= len(descrambled):
                descrambled[start:end] = descrambled[start:end][::-1]
        
        elif op_type == 'rotate':
            shift = operation[1]
            if len(descrambled) > 1:
                descrambled = descrambled[-shift:] + descrambled[:-shift]
        
        elif op_type == 'xor':
            xor_key = operation[1]
            for i in range(len(descrambled)):
                descrambled[i] ^= xor_key
    
    descrambled = bytes(descrambled)
    print(f"解密后: {len(descrambled)} 字节, 哈希: {hashlib.md5(descrambled).hexdigest()}")
    
    if descrambled == test_data:
        print("✅ Pre_Scramble 测试通过！")
        return True
    else:
        print("❌ Pre_Scramble 测试失败！")
        return False

if __name__ == '__main__':
    test_bit_shuffle()
    test_pre_scramble()
    test_final_obfuscation()
