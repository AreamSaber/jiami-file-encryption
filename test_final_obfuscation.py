#!/usr/bin/env python3
"""测试Final_Obfuscation的加密/解密"""
import os
import sys
import hashlib

# 添加src到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.encryptor.hybrid_engine import HybridEncryptionEngine

def test_final_obfuscation_detailed():
    """详细测试Final_Obfuscation"""
    print("=== 详细测试 Final_Obfuscation ===\n")
    
    engine = HybridEncryptionEngine()
    test_data = b"Hello, World! Test data for final obfuscation." * 10
    print(f"原始数据: {len(test_data)} 字节")
    print(f"原始哈希: {hashlib.md5(test_data).hexdigest()}")
    
    # 加密
    encrypted, metadata = engine._encrypt_final_obfuscation(test_data, {'obfuscation_level': 'maximum'})
    print(f"\n加密后: {len(encrypted)} 字节")
    
    obfuscation_key = metadata.get('obfuscation_key', b'')
    applied_operations = metadata.get('applied_operations', [])
    
    print(f"obfuscation_key长度: {len(obfuscation_key)}")
    print(f"操作数量: {len(applied_operations)}")
    
    # 计算密钥哈希
    key_hash = hashlib.sha256(obfuscation_key).digest()
    
    # 手动解密
    deobfuscated = bytearray(encrypted)
    
    for op_idx, operation in enumerate(reversed(applied_operations)):
        op_type = operation[0]
        original_idx = len(applied_operations) - 1 - op_idx
        
        print(f"\n逆向操作 {op_idx+1}: {op_type}")
        print(f"  数据大小: {len(deobfuscated)}")
        
        if op_type == 'frequency_analysis_resistance':
            dummy_positions = operation[1]
            print(f"  移除 {len(dummy_positions)} 个虚假字节")
            for pos in sorted(dummy_positions, reverse=True):
                if pos < len(deobfuscated):
                    deobfuscated.pop(pos)
            print(f"  移除后大小: {len(deobfuscated)}")
        
        elif op_type == 'byte_substitution':
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
                    # 逆向：先右旋转，再XOR
                    deobfuscated[k] = ((deobfuscated[k] >> 1) | (deobfuscated[k] << 7)) & 0xFF
                    deobfuscated[k] ^= round_key
        
        elif op_type == 'entropy_increase':
            for j in range(len(deobfuscated)):
                entropy_factor = key_hash[j % len(key_hash)]
                # 逆向：先减去entropy_factor，再XOR
                deobfuscated[j] = (deobfuscated[j] - entropy_factor) % 256
                deobfuscated[j] ^= entropy_factor
    
    deobfuscated = bytes(deobfuscated)
    print(f"\n解密后: {len(deobfuscated)} 字节")
    print(f"解密哈希: {hashlib.md5(deobfuscated).hexdigest()}")
    
    if deobfuscated == test_data:
        print("\n✅ Final_Obfuscation 测试通过！")
        return True
    else:
        print("\n❌ Final_Obfuscation 测试失败！")
        # 找出第一个不同的位置
        for i in range(min(len(test_data), len(deobfuscated))):
            if test_data[i] != deobfuscated[i]:
                print(f"第一个不同位置: {i}")
                print(f"原始: {test_data[max(0,i-5):i+10]}")
                print(f"解密: {deobfuscated[max(0,i-5):i+10]}")
                break
        return False

if __name__ == '__main__':
    test_final_obfuscation_detailed()
