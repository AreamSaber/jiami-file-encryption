#!/usr/bin/env python3
"""测试entropy_increase的加密/解密"""
import hashlib

def test_entropy_increase():
    """测试entropy_increase"""
    print("=== 测试 entropy_increase ===\n")
    
    test_data = b"Hello, World!"
    print(f"原始数据: {test_data}")
    print(f"原始字节: {[hex(b) for b in test_data]}")
    
    # 生成密钥哈希
    obfuscation_key = b"test_key_12345678901234567890"
    key_hash = hashlib.sha256(obfuscation_key).digest()
    
    # 加密
    encrypted = bytearray(test_data)
    
    for j in range(len(encrypted)):
        entropy_factor = key_hash[j % len(key_hash)]
        encrypted[j] ^= entropy_factor
        encrypted[j] = (encrypted[j] + entropy_factor) % 256
    
    print(f"\n加密后: {bytes(encrypted)}")
    print(f"加密字节: {[hex(b) for b in encrypted]}")
    
    # 解密
    decrypted = bytearray(encrypted)
    
    for j in range(len(decrypted)):
        entropy_factor = key_hash[j % len(key_hash)]
        # 逆向：先减去entropy_factor，再XOR
        decrypted[j] = (decrypted[j] - entropy_factor) % 256
        decrypted[j] ^= entropy_factor
    
    print(f"\n解密后: {bytes(decrypted)}")
    print(f"解密字节: {[hex(b) for b in decrypted]}")
    
    if bytes(decrypted) == test_data:
        print("\n✅ entropy_increase 测试通过！")
        return True
    else:
        print("\n❌ entropy_increase 测试失败！")
        return False

if __name__ == '__main__':
    test_entropy_increase()
