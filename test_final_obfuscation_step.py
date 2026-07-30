#!/usr/bin/env python3
"""逐步测试Final_Obfuscation的加密/解密"""
import os
import sys
import hashlib
import random

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_step_by_step():
    """逐步测试Final_Obfuscation"""
    print("=== 逐步测试 Final_Obfuscation ===\n")
    
    test_data = b"Hello"
    print(f"原始数据: {test_data}")
    print(f"原始字节: {[hex(b) for b in test_data]}")
    
    # 生成密钥
    obfuscation_key = os.urandom(32)
    key_hash = hashlib.sha256(obfuscation_key).digest()
    
    # 设置随机种子
    random.seed(int.from_bytes(key_hash[:4], 'big'))
    
    # 加密
    obfuscated_data = bytearray(test_data)
    applied_operations = []
    
    # 只执行3个操作
    operations_count = 3
    non_size_changing_ops = ['byte_substitution', 'bit_permutation', 'block_cipher', 'entropy_increase']
    
    for i in range(operations_count):
        operation = random.choice(non_size_changing_ops)
        
        print(f"\n--- 加密操作 {i+1}: {operation} ---")
        print(f"加密前: {[hex(b) for b in obfuscated_data]}")
        
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
                    if byte_val & (1 << bit_pos):
                        new_pos = (bit_pos * 3 + i) % 8
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
        
        print(f"加密后: {[hex(b) for b in obfuscated_data]}")
    
    encrypted = bytes(obfuscated_data)
    print(f"\n=== 加密完成 ===")
    print(f"加密数据: {[hex(b) for b in encrypted]}")
    print(f"操作: {[op[0] for op in applied_operations]}")
    
    # 解密
    print(f"\n=== 开始解密 ===")
    deobfuscated_data = bytearray(encrypted)
    
    for op_idx, operation in enumerate(reversed(applied_operations)):
        op_type = operation[0]
        original_idx = len(applied_operations) - 1 - op_idx
        
        print(f"\n--- 解密操作 {op_idx+1}: {op_type} (原始索引: {original_idx}) ---")
        print(f"解密前: {[hex(b) for b in deobfuscated_data]}")
        
        if op_type == 'byte_substitution':
            substitution_table = operation[1]
            inverse_table = [0] * 256
            for i, val in enumerate(substitution_table):
                inverse_table[val] = i
            for j in range(len(deobfuscated_data)):
                deobfuscated_data[j] = inverse_table[deobfuscated_data[j]]
        
        elif op_type == 'bit_permutation':
            i = operation[1]
            print(f"  使用 i={i}")
            for j in range(len(deobfuscated_data)):
                byte_val = deobfuscated_data[j]
                new_byte = 0
                for bit_pos in range(8):
                    new_pos = (bit_pos * 3 + i) % 8
                    if byte_val & (1 << new_pos):
                        new_byte |= (1 << bit_pos)
                deobfuscated_data[j] = new_byte
        
        elif op_type == 'block_cipher':
            round_key = operation[1]
            print(f"  使用 round_key={round_key}")
            block_size = 16
            for j in range(0, len(deobfuscated_data), block_size):
                block_end = min(j + block_size, len(deobfuscated_data))
                for k in range(j, block_end):
                    deobfuscated_data[k] = ((deobfuscated_data[k] >> 1) | (deobfuscated_data[k] << 7)) & 0xFF
                    deobfuscated_data[k] ^= round_key
        
        elif op_type == 'entropy_increase':
            for j in range(len(deobfuscated_data)):
                entropy_factor = key_hash[j % len(key_hash)]
                deobfuscated_data[j] = (deobfuscated_data[j] - entropy_factor) % 256
                deobfuscated_data[j] ^= entropy_factor
        
        print(f"解密后: {[hex(b) for b in deobfuscated_data]}")
    
    decrypted = bytes(deobfuscated_data)
    print(f"\n=== 解密完成 ===")
    print(f"解密数据: {decrypted}")
    print(f"解密字节: {[hex(b) for b in decrypted]}")
    
    if decrypted == test_data:
        print("\n✅ 测试通过！")
        return True
    else:
        print("\n❌ 测试失败！")
        return False

if __name__ == '__main__':
    test_step_by_step()
