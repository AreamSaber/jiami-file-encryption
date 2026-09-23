"""
系统诊断工具

检查exe生成相关的系统环境和依赖。
"""

import sys
import os
import subprocess
import platform
from pathlib import Path

def check_python_version():
    """检查Python版本"""
    print("🐍 Python环境检查:")
    print(f"  版本: {sys.version}")
    print(f"  可执行文件: {sys.executable}")
    
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print("  ✅ Python版本符合要求 (3.8+)")
        return True
    else:
        print("  ❌ Python版本过低，需要3.8+")
        return False

def check_pyinstaller():
    """检查PyInstaller"""
    print("\n🔧 PyInstaller检查:")
    
    # 检查是否安装
    try:
        import PyInstaller
        print(f"  ✅ PyInstaller已安装: {PyInstaller.__version__}")
    except ImportError:
        print("  ❌ PyInstaller未安装")
        print("  💡 安装命令: pip install pyinstaller")
        return False
    
    # 检查命令行可用性
    try:
        result = subprocess.run(['pyinstaller', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"  ✅ 命令行可用: {result.stdout.strip()}")
            return True
        else:
            print(f"  ❌ 命令行不可用，返回码: {result.returncode}")
            return False
    except FileNotFoundError:
        print("  ❌ pyinstaller命令未找到")
        print("  💡 可能需要重新安装或添加到PATH")
        return False
    except Exception as e:
        print(f"  ❌ 检查失败: {e}")
        return False

def check_dependencies():
    """检查依赖包"""
    print("\n📦 依赖包检查:")
    
    required_packages = {
        'cryptography': '核心加密库',
        'psutil': '系统信息',
    }
    
    profile_packages = {
        'nacl.secret': ('PyNaCl', 'salsa20_stream 及所有含 salsa20 的配置')
    }

    optional_packages = {
        'PIL': ('Pillow', '图像处理'),
        'PyQt6': ('PyQt6', 'GUI界面'),
        'PySide6': ('PySide6', 'GUI界面（备选）')
    }
    
    all_good = True
    
    print("  必需包:")
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"    ✅ {package}: {description}")
        except ImportError:
            print(f"    ❌ {package}: {description} (未安装)")
            all_good = False
    
    print("  按配置必需包:")
    for import_name, (package, profiles) in profile_packages.items():
        try:
            __import__(import_name)
            print(f"    ✅ {package}: {profiles} 所需依赖已安装")
        except ImportError:
            print(f"    ❌ {package}: {profiles} 不可用")
            print(f"    💡 安装命令: pip install {package}")
            print("    其他配置仅在其依赖齐全时可用；不会替换加密算法。")
            all_good = False

    print("  可选包:")
    for import_name, (package, description) in optional_packages.items():
        try:
            __import__(import_name)
            print(f"    ✅ {package}: {description}")
        except ImportError:
            print(f"    ⚠️  {package}: {description} (未安装)")
    
    return all_good

def check_system_info():
    """检查系统信息"""
    print("\n🖥️  系统信息:")
    print(f"  操作系统: {platform.system()} {platform.release()}")
    print(f"  架构: {platform.machine()}")
    print(f"  处理器: {platform.processor()}")
    
    # 检查权限
    try:
        test_file = Path("test_write_permission.tmp")
        test_file.write_text("test")
        test_file.unlink()
        print("  ✅ 当前目录写入权限正常")
    except Exception as e:
        print(f"  ❌ 当前目录写入权限异常: {e}")

def check_path_environment():
    """检查PATH环境变量"""
    print("\n🛤️  PATH环境检查:")
    
    path_dirs = os.environ.get('PATH', '').split(os.pathsep)
    python_dir = Path(sys.executable).parent
    scripts_dir = python_dir / 'Scripts'
    
    print(f"  Python目录: {python_dir}")
    print(f"  Scripts目录: {scripts_dir}")
    
    if str(python_dir) in path_dirs:
        print("  ✅ Python目录在PATH中")
    else:
        print("  ⚠️  Python目录不在PATH中")
    
    if str(scripts_dir) in path_dirs:
        print("  ✅ Scripts目录在PATH中")
    else:
        print("  ⚠️  Scripts目录不在PATH中")
        print("  💡 这可能导致pyinstaller命令不可用")

def test_simple_packaging():
    """测试简单打包"""
    print("\n🧪 简单打包测试:")
    
    # 创建测试脚本
    test_script = Path("test_package.py")
    test_content = '''
import sys
print("Hello from packaged app!")
print(f"Arguments: {sys.argv}")
'''
    
    try:
        test_script.write_text(test_content)
        print(f"  📝 创建测试脚本: {test_script}")
        
        # 尝试打包
        cmd = [
            'pyinstaller',
            '--onefile',
            '--console',
            '--distpath', './test_dist',
            str(test_script)
        ]
        
        print("  🔧 尝试打包...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            exe_path = Path('./test_dist/test_package.exe')
            if exe_path.exists():
                print("  ✅ 打包成功")
                
                # 测试运行
                test_result = subprocess.run([str(exe_path), 'test'], 
                                           capture_output=True, text=True, timeout=10)
                if test_result.returncode == 0:
                    print("  ✅ exe运行成功")
                    print(f"  输出: {test_result.stdout.strip()}")
                else:
                    print("  ❌ exe运行失败")
                
                # 清理
                exe_path.unlink()
            else:
                print("  ❌ 打包完成但未找到exe文件")
        else:
            print("  ❌ 打包失败")
            print(f"  错误: {result.stderr}")
        
        # 清理
        test_script.unlink()
        
        # 清理临时目录
        import shutil
        for cleanup_dir in ['build', 'test_dist']:
            if Path(cleanup_dir).exists():
                shutil.rmtree(cleanup_dir, ignore_errors=True)
        
        spec_file = Path('test_package.spec')
        if spec_file.exists():
            spec_file.unlink()
            
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        
        # 清理
        if test_script.exists():
            test_script.unlink()

def provide_solutions():
    """提供解决方案"""
    print("\n💡 解决方案建议:")
    print("1. 如果PyInstaller未安装:")
    print("   pip install pyinstaller")
    print()
    print("2. 如果命令行不可用:")
    print("   python -m pip install --upgrade pip")
    print("   pip uninstall pyinstaller")
    print("   pip install pyinstaller")
    print()
    print("3. 如果权限问题:")
    print("   - 以管理员身份运行")
    print("   - 检查防病毒软件设置")
    print()
    print("4. 使用手动打包工具:")
    print("   python tools/manual_packager.py -d <目录>")
    print()
    print("5. 使用批处理文件:")
    print("   查找 *_decryptor.bat 文件并双击运行")

def main():
    print("🔍 文件加密系统 - 环境诊断工具")
    print("=" * 50)
    
    checks = [
        check_python_version(),
        check_pyinstaller(),
        check_dependencies(),
    ]
    
    check_system_info()
    check_path_environment()
    test_simple_packaging()
    
    print("\n📊 诊断结果:")
    if all(checks):
        print("✅ 所有核心检查通过，系统应该能正常生成exe文件")
    else:
        print("❌ 发现问题，请参考解决方案")
    
    provide_solutions()

if __name__ == "__main__":
    main()
