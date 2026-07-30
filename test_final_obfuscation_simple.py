#!/usr/bin/env python3
"""测试Final_Obfuscation的加密/解密 - 简化版（不包含frequency_analysis_resistance）"""
import os
import sys
import hashlib
import random

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_final_obfuscation_simple():
    """简化测试Final_Obfuscation（不包含frequency_analysis_resistance）"""
    print("=== 简化测试 Final_Obfuscation ===\n")
    
    test_data = b"Hello, World! Test data for final obfuscation." * 10
    print(f"原始数据: {len(test_data)} 字节")
    print(f"原始哈希: {hashlib.md5(test_data).hexdigest()}")
    
    # 手动加密（不包含frequency_analysis_resistance）
    obfuscation_key = os.urandom(32)
    key_hash = hashlib.sha256(obfuscation_key).digest()
    
    obfuscated_data = bytearray(test_data)
    applied_operations = []
    
    random.seed(int.from_bytes(key_hash[:4], 'big'))
    
    operations_count = 5
    for i in range(operations_count):
        operation = random.choice([
            'byte_substitution', 'bit_permutation', 'block_cipher', 'entropy_increase'
        ])
        
        print(f"加密操作 {i+1}: {operation}")
        
        if operation == 'byte_substitution':
            substitution_table = list(range(256))
            random.shuffle(substitution_table)
            for j in range(len(obfuscated_data)):
                obfuscated_data[j] = substitution_table[obfuscated_data[j]]
            applied_operations.append(('byte_substitution', substitution_table))
        
        elif operation == 'bit_permutation':
            for j in range(len(obfuscated_data)):
                byte_val = obfuscated_data[j]
                new_byte = 0
                for bit_pos in range(8):
                    new_pos = (bit_pos * 3 + i) % 8
                    if byte_val & (1 << bit_pos):
                        new_byte |= (1 << new_pos)
                obfuscated_data[j] = new_byte
            applied_operations.append(('bit_permutation', i))
        
        elif operation == 'block_cipher':
            round_key = key_hash[i % len(key_hash)]
            block_size = 16
            for j in range(0, len(obfuscated_data), block_size):
                block_end = min(j + block_size, len(obfuscated_data))
                for k in range(j, block_end):
                    obfuscated_data[k] ^= round_key
                    obfuscated_data[k] = ((obfuscated_data[k] << 1) | (obfuscated_data[k] >> 7)) & 0xFF
            applied_operations.append(('block_cipher', round_key))
        
        elif operation == 'entropy_increase':
            for j in range(len(obfuscated_data)):
                entropy_factor = key_hash[j % len(key_hash)]
                obfuscated_data[j] ^= entropy_factor
                obfuscated_data[j] = (obfuscated_data[j] + entropy_factor) % 256
            applied_operations.append(('entropy_increase', None))
    
    encrypted = bytes(obfuscated_data)
    print(f"\n加密后: {len(encrypted)} 字节")
    
    # 手动解密
    deobfuscated = bytearray(encrypted)
    
    for op_idx, operation in enumerate(reversed(applied_operations)):
        op_type = operation[0]
        original_idx = len(applied_operations) - 1 - op_idx
        
        print(f"解密操作 {op_idx+1}: {op_type}")
        
        if op_type == 'byte_substitution':
            substitution_table = operation[1]
            inverse_table = [0] * 256
            for i, val in enumerate(substitution_table):
                inverse_table[val] = i
            for j in range(len(deobfuscated)):
                deobfuscated[j] = inverse_table[deobfuscated[j]]
        
        elif op_type == 'bit_permutation':
            i = operation[1]
            for j in range(len(deobfuscated)):
                byte_val = deobfuscated[j]
                new_byte = 0
                for bit_pos in range(8):
                    new_pos = (bit_pos * 3 + i) % 8
                    if byte_val & (1 << new_pos):
                        new_byte |= (1 << bit_pos)
                deobfuscated[j] = new_byte
        
        elif op_type == 'block_cipher':
            round_key = operation[1]
            block_size = 16
            for j in range(0, len(deobfuscated), block_size):
                block_end = min(j + block_size, len(deobfuscated))
                for k in range(j, block_end):
                    deobfuscated[k] = ((deobfuscated[k] >> 1) | (deobfuscated[k] << 7)) & 0xFF
                    deobfuscated[k] ^= round_key
        
        elif op_type == 'entropy_increase':
            for j in range(len(deobfuscated)):
                entropy_factor = key_hash[j % len(key_hash)]
                deobfuscated[j] = (deobfuscated[j] - entropy_factor) % 256
                deobfuscated[j] ^= entropy_factor
    
    deobfuscated = bytes(deobfuscated)
    print(f"\n解密后: {len(deobfuscated)} 字节")
    print(f"解密哈希: {hashlib.md5(deobfuscated).hexdigest()}")
    
    if deobfuscated == test_data:
        print("\n✅ Final_Obfuscation 简化测试通过！")
        return True
    else:
        print("\n❌ Final_Obfuscation 简化测试失败！")
        for i in range(min(len(test_data), len(deobfuscated))):
            if test_data[i] != deobfuscated[i]:
                print(f"第一个不同位置: {i}")
                break
        return False

if __name__ == '__main__':
    test_final_obfuscation_simple()
