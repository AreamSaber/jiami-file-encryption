#!/usr/bin/env python3
"""测试block_cipher的加密/解密"""
import hashlib

def test_block_cipher():
    """测试block_cipher"""
    print("=== 测试 block_cipher ===\n")
    
    test_data = b"Hello, World! This is a test message for block cipher."
    print(f"原始数据: {test_data}")
    print(f"原始长度: {len(test_data)}")
    
    # 生成密钥哈希
    obfuscation_key = b"test_key_12345678901234567890"
    key_hash = hashlib.sha256(obfuscation_key).digest()
    
    # 加密
    i = 3  # 操作索引
    round_key = key_hash[i % len(key_hash)]
    block_size = 16
    
    encrypted = bytearray(test_data)
    
    for j in range(0, len(encrypted), block_size):
        block_end = min(j + block_size, len(encrypted))
        for k in range(j, block_end):
            encrypted[k] ^= round_key
            encrypted[k] = ((encrypted[k] << 1) | (encrypted[k] >> 7)) & 0xFF
    
    print(f"\n加密后长度: {len(encrypted)}")
    
    # 解密
    decrypted = bytearray(encrypted)
    
    for j in range(0, len(decrypted), block_size):
        block_end = min(j + block_size, len(decrypted))
        for k in range(j, block_end):
            # 逆向：先右旋转，再XOR
            decrypted[k] = ((decrypted[k] >> 1) | (decrypted[k] << 7)) & 0xFF
            decrypted[k] ^= round_key
    
    print(f"解密后: {bytes(decrypted)}")
    print(f"解密长度: {len(decrypted)}")
    
    if bytes(decrypted) == test_data:
        print("\n✅ block_cipher 测试通过！")
        return True
    else:
        print("\n❌ block_cipher 测试失败！")
        return False

if __name__ == '__main__':
    test_block_cipher()
