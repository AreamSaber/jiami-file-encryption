#!/usr/bin/env python3
"""
修复GPU解密文件大小问题
分析加密文件并确保正确截断到原始大小
"""

import os
import sys
import pickle

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def analyze_encrypted_file(encrypted_file_path):
    """分析加密文件结构"""
    print(f"📋 分析加密文件: {encrypted_file_path}")
    print("=" * 60)
    
    try:
        with open(encrypted_file_path, 'rb') as f:
            encrypted_package = pickle.load(f)
        
        # 检查顶层字段
        print("\n📦 加密包顶层字段:")
        for key in encrypted_package.keys():
            if key == 'encrypted_data':
                print(f"   {key}: {len(encrypted_package[key]):,} 字节")
            elif key == 'metadata':
                print(f"   {key}: <dict>")
            else:
                print(f"   {key}: {encrypted_package.get(key)}")
        
        # 检查metadata
        metadata = encrypted_package.get('metadata', {})
        print("\n📋 Metadata字段:")
        for key, value in metadata.items():
            if key == 'layers':
                print(f"   {key}: {len(value)} 层")
            elif isinstance(value, bytes):
                print(f"   {key}: <bytes, {len(value)} 字节>")
            elif isinstance(value, dict):
                print(f"   {key}: <dict>")
            else:
                print(f"   {key}: {value}")
        
        # 检查original_size
        top_level_size = encrypted_package.get('original_size')
        metadata_size = metadata.get('original_size')
        
        print("\n🔍 original_size检查:")
        print(f"   顶层: {top_level_size}")
        print(f"   metadata: {metadata_size}")
        
        if not top_level_size and not metadata_size:
            print("   ⚠️ 警告: 没有找到original_size字段!")
        
        # 检查加密层
        layers = metadata.get('layers', [])
        print(f"\n🔐 加密层详情 ({len(layers)} 层):")
        for i, layer in enumerate(layers):
            algorithm = layer.get('algorithm', 'Unknown')
            mode = layer.get('mode', 'N/A')
            print(f"   第{i+1}层: {algorithm} (模式: {mode})")
        
        return encrypted_package
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def fix_and_decrypt(encrypted_file_path, expected_original_size=None):
    """修复并解密文件"""
    print(f"\n🔧 修复并解密: {encrypted_file_path}")
    print("=" * 60)
    
    try:
        # 读取加密包
        with open(encrypted_file_path, 'rb') as f:
            encrypted_package = pickle.load(f)
        
        metadata = encrypted_package.get('metadata', {})
        encrypted_data = encrypted_package.get('encrypted_data')
        layers = metadata.get('layers', [])
        
        # 获取或推断original_size
        original_size = metadata.get('original_size') or encrypted_package.get('original_size')
        
        if not original_size and expected_original_size:
            original_size = expected_original_size
            print(f"📋 使用提供的原始大小: {original_size:,} 字节")
        elif original_size:
            print(f"📋 从加密包获取原始大小: {original_size:,} 字节")
        else:
            print("⚠️ 警告: 无法确定原始大小，将不进行截断")
        
        print(f"📋 加密数据大小: {len(encrypted_data):,} 字节")
        print(f"📋 加密层数: {len(layers)}")
        
        # 导入解密器
        from src.decryptor.gpu_template import AlgorithmRegistry
        
        registry = AlgorithmRegistry()
        
        # 逐层解密
        decrypted_data = encrypted_data
        for i, layer in enumerate(reversed(layers)):
            layer_idx = len(layers) - i
            algorithm = layer.get('algorithm', 'unknown')
            
            print(f"🔓 解密第 {layer_idx} 层: {algorithm}")
            
            try:
                handler = registry.get_handler(algorithm)
                decrypted_data = handler.decrypt(decrypted_data, layer)
                print(f"   ✅ 成功 - 数据大小: {len(decrypted_data):,} 字节")
            except Exception as e:
                print(f"   ❌ 失败: {e}")
                raise
        
        print(f"\n📊 解密完成:")
        print(f"   解密后大小: {len(decrypted_data):,} 字节")
        
        # 截断到原始大小
        if original_size:
            if len(decrypted_data) > original_size:
                print(f"   截断到原始大小: {len(decrypted_data):,} -> {original_size:,} 字节")
                decrypted_data = decrypted_data[:original_size]
            elif len(decrypted_data) < original_size:
                print(f"   ⚠️ 警告: 解密数据小于原始大小!")
            else:
                print(f"   ✅ 大小完全匹配!")
        
        # 保存解密文件
        output_dir = os.path.dirname(encrypted_file_path)
        base_name = os.path.splitext(os.path.basename(encrypted_file_path))[0]
        output_file = os.path.join(output_dir, f"{base_name}_fixed_decrypted")
        
        # 尝试恢复原始扩展名
        original_filename = encrypted_package.get('original_filename', '')
        if original_filename:
            _, ext = os.path.splitext(original_filename)
            if ext:
                output_file += ext
        
        with open(output_file, 'wb') as f:
            f.write(decrypted_data)
        
        print(f"\n✅ 解密文件已保存: {output_file}")
        print(f"   文件大小: {len(decrypted_data):,} 字节")
        
        return output_file, decrypted_data
        
    except Exception as e:
        print(f"❌ 解密失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    """主函数"""
    print("🔧 GPU解密文件大小修复工具")
    print("=" * 60)
    
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print(f"  python {sys.argv[0]} <加密文件路径> [原始文件大小(字节)]")
        print("\n示例:")
        print(f"  python {sys.argv[0]} C:\\Users\\Desktop\\file.encrypted")
        print(f"  python {sys.argv[0]} C:\\Users\\Desktop\\file.encrypted 886784")
        return
    
    encrypted_file = sys.argv[1]
    expected_size = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(encrypted_file):
        print(f"❌ 文件不存在: {encrypted_file}")
        return
    
    # 分析文件
    encrypted_package = analyze_encrypted_file(encrypted_file)
    
    if encrypted_package:
        # 修复并解密
        output_file, decrypted_data = fix_and_decrypt(encrypted_file, expected_size)
        
        if output_file:
            print(f"\n🎉 完成! 解密文件: {output_file}")


if __name__ == "__main__":
    main()
