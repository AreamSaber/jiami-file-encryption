"""
手动打包工具

用于将Python解密器手动打包为exe文件。
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def find_python_decryptors(directory):
    """查找目录中的Python解密器"""
    decryptors = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('_decryptor.py'):
                decryptors.append(os.path.join(root, file))
    
    return decryptors

def check_pyinstaller():
    """检查PyInstaller是否可用"""
    try:
        result = subprocess.run(['pyinstaller', '--version'],
                                capture_output=True, text=True, encoding='utf-8', errors='replace',
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=10)
        if result.returncode == 0:
            print(f"✅ PyInstaller可用，版本: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ PyInstaller不可用，返回码: {result.returncode}")
            return False
    except Exception as e:
        print(f"❌ PyInstaller检查失败: {e}")
        return False

def package_decryptor(py_file, output_dir=None):
    """打包单个解密器"""
    try:
        py_path = Path(py_file)
        
        if output_dir is None:
            output_dir = py_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)
        
        # PyInstaller命令
        cmd = [
            'pyinstaller',
            '--onefile',
            '--console',
            '--name', py_path.stem,
            '--distpath', str(output_dir),
            str(py_path)
        ]
        
        print(f"🔧 正在打包: {py_file}")
        print(f"📁 输出目录: {output_dir}")
        
        # Match Python child output to the decoder; native build diagnostics may
        # still contain non-UTF-8 bytes, which must not hide the real exit status.
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=120)
        
        if result.returncode == 0:
            exe_path = output_dir / f"{py_path.stem}.exe"
            if exe_path.exists():
                print(f"✅ 打包成功: {exe_path}")
                
                # 清理临时文件
                cleanup_temp_files(py_path.stem)
                
                return str(exe_path)
            else:
                print(f"❌ 打包完成但未找到exe文件")
                return None
        else:
            print(f"❌ 打包失败:")
            print(f"错误信息: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ 打包过程出错: {e}")
        return None

def cleanup_temp_files(name):
    """清理PyInstaller生成的临时文件"""
    try:
        import shutil
        
        # 清理build目录
        build_dir = Path('build')
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)
            print("🧹 已清理build目录")
        
        # 清理spec文件
        spec_file = Path(f"{name}.spec")
        if spec_file.exists():
            spec_file.unlink()
            print(f"🧹 已清理{spec_file}")
            
    except Exception as e:
        print(f"⚠️  清理临时文件失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="手动打包Python解密器为exe文件")
    parser.add_argument('-f', '--file', help='指定要打包的Python解密器文件')
    parser.add_argument('-d', '--directory', help='搜索目录中的所有解密器')
    parser.add_argument('-o', '--output', help='输出目录（可选）')
    parser.add_argument('--list', action='store_true', help='仅列出找到的解密器')
    
    args = parser.parse_args()
    
    print("🔐 Python解密器手动打包工具 v1.0")
    print("=" * 50)
    
    # 检查PyInstaller
    if not check_pyinstaller():
        print("\n💡 解决方案:")
        print("1. 安装PyInstaller: pip install pyinstaller")
        print("2. 确保PyInstaller在PATH中")
        return 1
    
    decryptors = []
    
    if args.file:
        # 打包指定文件
        if os.path.exists(args.file) and args.file.endswith('.py'):
            decryptors = [args.file]
        else:
            print(f"❌ 文件不存在或不是Python文件: {args.file}")
            return 1
    elif args.directory:
        # 搜索目录
        decryptors = find_python_decryptors(args.directory)
        if not decryptors:
            print(f"❌ 在目录 {args.directory} 中未找到解密器文件")
            return 1
    else:
        # 搜索当前目录
        decryptors = find_python_decryptors('.')
        if not decryptors:
            print("❌ 在当前目录中未找到解密器文件")
            print("💡 使用 -d <目录> 指定搜索目录")
            return 1
    
    print(f"\n📋 找到 {len(decryptors)} 个解密器:")
    for i, decryptor in enumerate(decryptors, 1):
        print(f"  {i}. {decryptor}")
    
    if args.list:
        return 0
    
    print(f"\n🚀 开始打包...")
    
    success_count = 0
    for decryptor in decryptors:
        result = package_decryptor(decryptor, args.output)
        if result:
            success_count += 1
        print()  # 空行分隔
    
    print(f"📊 打包完成: {success_count}/{len(decryptors)} 成功")
    
    if success_count > 0:
        print("\n✅ 打包成功的exe文件可以独立运行，无需Python环境")
    
    return 0 if success_count == len(decryptors) else 1

if __name__ == "__main__":
    sys.exit(main())
