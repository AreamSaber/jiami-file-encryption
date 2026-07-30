#!/usr/bin/env python3
"""
测试文件大小修复
验证加密和解密后文件大小是否一致
"""

import os
import sys
import pickle
import tempfile
import shutil

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_original_size_in_metadata():
    """测试original_size是否正确保存在metadata中"""
    print("=" * 60)
    print("测试1: 验证original_size在metadata中的保存")
    print("=" * 60)
    
    try:
        from src.encryptor.gpu_file_encryptor import GPUFileEncryptor
        
        # 创建测试文件
        test_dir = tempfile.mkdtemp()
        test_file = os.path.join(test_dir, "test_file.txt")
        
        # 创建特定大小的测试数据 (866KB，模拟用户的情况)
        test_data = os.urandom(866 * 1024)  # 866KB
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        original_size = os.path.getsize(test_file)
        print(f"✅ 创建测试文件: {original_size:,} 字节 ({original_size/1024:.1f} KB)")
        
        # 加密文件
        encryptor = GPUFileEncryptor(allow_fallback=True)
        result = encryptor.encrypt_file(test_file, test_dir, security_level=3)
        
        if not result.get('success'):
            print(f"❌ 加密失败: {result.get('error')}")
            return False
        
        encrypted_file = result['encrypted_file']
        print(f"✅ 加密完成: {encrypted_file}")
        
        # 读取加密包，检查original_size
        with open(encrypted_file, 'rb') as f:
            encrypted_package = pickle.load(f)
        
        # 检查顶层original_size
        top_level_size = encrypted_package.get('original_size')
        print(f"📋 顶层 original_size: {top_level_size:,} 字节" if top_level_size else "❌ 顶层缺少 original_size")
        
        # 检查metadata中的original_size
        metadata = encrypted_package.get('metadata', {})
        metadata_size = metadata.get('original_size')
        print(f"📋 metadata original_size: {metadata_size:,} 字节" if metadata_size else "❌ metadata缺少 original_size")
        
        # 验证
        if top_level_size == original_size and metadata_size == original_size:
            print(f"✅ original_size 正确保存在两个位置")
            success = True
        else:
            print(f"❌ original_size 不匹配!")
            print(f"   期望: {original_size:,}")
            print(f"   顶层: {top_level_size}")
            print(f"   metadata: {metadata_size}")
            success = False
        
        # 清理
        shutil.rmtree(test_dir)
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_decryption_size():
    """测试解密后文件大小是否正确"""
    print("\n" + "=" * 60)
    print("测试2: 验证解密后文件大小")
    print("=" * 60)
    
    try:
        from src.encryptor.gpu_file_encryptor import GPUFileEncryptor
        
        # 创建测试文件
        test_dir = tempfile.mkdtemp()
        test_file = os.path.join(test_dir, "test_file.bin")
        
        # 创建特定大小的测试数据
        test_data = os.urandom(866 * 1024)  # 866KB
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        original_size = os.path.getsize(test_file)
        print(f"✅ 原始文件大小: {original_size:,} 字节")
        
        # 加密
        encryptor = GPUFileEncryptor(allow_fallback=True)
        result = encryptor.encrypt_file(test_file, test_dir, security_level=3)
        
        if not result.get('success'):
            print(f"❌ 加密失败: {result.get('error')}")
            return False
        
        encrypted_file = result['encrypted_file']
        encrypted_size = os.path.getsize(encrypted_file)
        print(f"✅ 加密文件大小: {encrypted_size:,} 字节")
        
        # 检查加密包中的engine_type来选择正确的解密器
        with open(encrypted_file, 'rb') as f:
            encrypted_package = pickle.load(f)
        
        engine_type = encrypted_package.get('engine_type') or encrypted_package.get('metadata', {}).get('engine_type')
        print(f"📋 加密引擎类型: {engine_type}")
        
        # 根据引擎类型选择解密器
        if engine_type == 'pure_gpu_only':
            print("📋 使用GPU模板解密器...")
            from src.decryptor.gpu_template import GPUDecryptor
            decryptor = GPUDecryptor()
        else:
            print("📋 使用CPU模板解密器...")
            from src.decryptor.cpu_template import CPUDecryptor
            decryptor = CPUDecryptor()
        
        decrypt_result = decryptor.decrypt_file(encrypted_file)
        
        if decrypt_result.get('success'):
            decrypted_size = decrypt_result.get('decrypted_size', 0)
            print(f"✅ 解密成功")
            print(f"📋 解密文件大小: {decrypted_size:,} 字节")
            
            if decrypted_size == original_size:
                print(f"✅ 文件大小匹配!")
                success = True
            else:
                print(f"❌ 文件大小不匹配!")
                print(f"   差异: {decrypted_size - original_size:+,} 字节")
                success = False
        else:
            print(f"❌ 解密失败: {decrypt_result.get('error')}")
            success = False
        
        # 清理
        shutil.rmtree(test_dir)
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_content_integrity():
    """测试解密后内容是否完整"""
    print("\n" + "=" * 60)
    print("测试3: 验证解密后内容完整性")
    print("=" * 60)
    
    try:
        from src.encryptor.gpu_file_encryptor import GPUFileEncryptor
        
        # 创建测试文件
        test_dir = tempfile.mkdtemp()
        test_file = os.path.join(test_dir, "test_content.bin")
        
        # 创建可验证的测试数据
        test_data = b"START_MARKER" + os.urandom(866 * 1024 - 24) + b"END_MARKER"
        with open(test_file, 'wb') as f:
            f.write(test_data)
        
        original_size = len(test_data)
        print(f"✅ 原始数据大小: {original_size:,} 字节")
        
        # 加密
        encryptor = GPUFileEncryptor(allow_fallback=True)
        result = encryptor.encrypt_file(test_file, test_dir, security_level=3)
        
        if not result.get('success'):
            print(f"❌ 加密失败: {result.get('error')}")
            return False
        
        encrypted_file = result['encrypted_file']
        print(f"✅ 加密完成")
        
        # 检查加密包中的engine_type来选择正确的解密器
        with open(encrypted_file, 'rb') as f:
            encrypted_package = pickle.load(f)
        
        engine_type = encrypted_package.get('engine_type') or encrypted_package.get('metadata', {}).get('engine_type')
        print(f"📋 加密引擎类型: {engine_type}")
        
        # 根据引擎类型选择解密器
        if engine_type == 'pure_gpu_only':
            print("📋 使用GPU模板解密器...")
            from src.decryptor.gpu_template import GPUDecryptor
            decryptor = GPUDecryptor()
        else:
            print("📋 使用CPU模板解密器...")
            from src.decryptor.cpu_template import CPUDecryptor
            decryptor = CPUDecryptor()
        
        decrypt_result = decryptor.decrypt_file(encrypted_file)
        
        if not decrypt_result.get('success'):
            print(f"❌ 解密失败: {decrypt_result.get('error')}")
            return False
        
        # 读取解密后的文件
        output_file = decrypt_result.get('output_file')
        with open(output_file, 'rb') as f:
            decrypted_data = f.read()
        
        print(f"✅ 解密完成")
        print(f"📋 解密数据大小: {len(decrypted_data):,} 字节")
        
        # 验证内容
        if decrypted_data == test_data:
            print(f"✅ 内容完全匹配!")
            success = True
        else:
            print(f"❌ 内容不匹配!")
            
            # 检查标记
            has_start = decrypted_data[:12] == b"START_MARKER"
            has_end = decrypted_data[-10:] == b"END_MARKER"
            
            print(f"   开始标记: {'✅' if has_start else '❌'}")
            print(f"   结束标记: {'✅' if has_end else '❌'}")
            print(f"   大小差异: {len(decrypted_data) - len(test_data):+,} 字节")
            
            success = False
        
        # 清理
        shutil.rmtree(test_dir)
        return success
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("🔧 文件大小修复测试")
    print("=" * 60)
    
    results = []
    
    # 测试1: original_size保存
    results.append(("original_size保存", test_original_size_in_metadata()))
    
    # 测试2: 解密大小
    results.append(("解密文件大小", test_decryption_size()))
    
    # 测试3: 内容完整性
    results.append(("内容完整性", test_content_integrity()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
