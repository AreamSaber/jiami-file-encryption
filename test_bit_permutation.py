#!/usr/bin/env python3
"""测试bit_permutation的加密/解密"""

def test_bit_permutation():
    """测试bit_permutation"""
    print("=== 测试 bit_permutation ===\n")
    
    test_data = b"Hello"
    print(f"原始数据: {test_data}")
    print(f"原始字节: {[hex(b) for b in test_data]}")
    
    # 加密
    i = 5  # 操作索引
    encrypted = bytearray(test_data)
    
    for j in range(len(encrypted)):
        byte_val = encrypted[j]
        new_byte = 0
        for bit_pos in range(8):
            if byte_val & (1 << bit_pos):
                new_pos = (bit_pos * 3 + i) % 8
                new_byte |= (1 << new_pos)
        encrypted[j] = new_byte
    
    print(f"\n加密后: {bytes(encrypted)}")
    print(f"加密字节: {[hex(b) for b in encrypted]}")
    
    # 解密
    decrypted = bytearray(encrypted)
    
    for j in range(len(decrypted)):
        byte_val = decrypted[j]
        new_byte = 0
        for bit_pos in range(8):
            new_pos = (bit_pos * 3 + i) % 8
            if byte_val & (1 << new_pos):
                new_byte |= (1 << bit_pos)
        decrypted[j] = new_byte
    
    print(f"\n解密后: {bytes(decrypted)}")
    print(f"解密字节: {[hex(b) for b in decrypted]}")
    
    if bytes(decrypted) == test_data:
        print("\n✅ bit_permutation 测试通过！")
        return True
    else:
        print("\n❌ bit_permutation 测试失败！")
        return False

if __name__ == '__main__':
    test_bit_permutation()
