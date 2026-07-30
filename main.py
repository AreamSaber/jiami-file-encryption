#!/usr/bin/env python3
"""
文件加密系统 - 主启动脚本

这是文件加密系统的主入口，提供命令行和图形界面两种使用方式。

使用方法：
1. 命令行模式：python main.py --cli [参数]
2. 图形界面模式：python main.py --gui
3. 帮助信息：python main.py --help
"""

import os
import sys
import argparse
from pathlib import Path

# 自动设置OpenCL环境变量，确保GPU加速功能正常工作
def _setup_gpu_environment():
    """自动设置GPU相关环境变量"""
    if 'PYOPENCL_CTX' not in os.environ:
        # 自动选择第一个可用的GPU设备
        os.environ['PYOPENCL_CTX'] = '0'

    if 'PYOPENCL_COMPILER_OUTPUT' not in os.environ:
        # 默认不显示编译器输出（减少日志噪音）
        os.environ['PYOPENCL_COMPILER_OUTPUT'] = '0'

# 在程序启动时设置环境变量
_setup_gpu_environment()

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from src.encryptor.main import FileEncryptor
    from src.encryptor.gpu_file_encryptor import GPUFileEncryptor
    from src.utils.logger import Logger
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保已安装所有依赖包：pip install -r requirements.txt")
    sys.exit(1)


def check_dependencies():
    """检查依赖包是否已安装"""
    # 核心依赖包（必需）
    core_packages = {
        'cryptography': 'cryptography'
    }

    # 可选依赖包
    optional_packages = {
        'Crypto': 'pycryptodome',
        'nacl': 'PyNaCl',
        'PIL': 'Pillow'
    }

    missing_core = []
    missing_optional = []

    # 检查核心依赖
    for import_name, display_name in core_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_core.append(display_name)

    # 检查可选依赖
    for import_name, display_name in optional_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_optional.append(display_name)

    # 如果缺少核心依赖，返回失败
    if missing_core:
        print("❌ 缺少核心依赖包:")
        for package in missing_core:
            print(f"   - {package}")
        print("\n请运行: pip install cryptography")
        return False

    # 如果缺少可选依赖，只显示警告
    if missing_optional:
        print("⚠️  缺少可选依赖包（部分功能可能不可用）:")
        for package in missing_optional:
            print(f"   - {package}")
        print("\n可选安装: pip install pycryptodome PyNaCl Pillow")
        print("✅ 核心功能可用，继续运行...\n")

    return True


def run_cli_mode(args):
    """运行命令行模式"""
    logger = Logger("Main")
    logger.info("启动命令行模式")

    try:
        # 创建加密器
        encryptor = FileEncryptor()

        # 处理不同的命令
        if args.list_profiles:
            print("📋 可用的加密配置文件:")
            profiles = encryptor.list_profiles()
            for profile in profiles:
                info = encryptor.get_profile_info(profile)
                print(f"   {profile}: {info.get('name', '无名称')} - {info.get('description', '无描述')}")
            return

        if not args.input:
            print("❌ 错误: 请指定要加密的文件或文件夹路径")
            print("使用方法: python main.py --cli -i <输入文件> -o <输出目录>")
            return

        if not args.output:
            # 如果没有指定输出目录，使用默认值
            args.output = "./encrypted_output"
            print(f"⚠️  未指定输出目录，使用默认目录: {args.output}")

        # 确保输出目录存在
        os.makedirs(args.output, exist_ok=True)

        # 执行加密
        print(f"🔒 开始加密: {args.input}")
        print(f"📁 输出目录: {args.output}")
        print(f"⚙️  使用配置: {args.profile}")

        if os.path.isfile(args.input):
            result = encryptor.encrypt_file(args.input, args.output, args.profile)
        elif os.path.isdir(args.input):
            result = encryptor.encrypt_folder(args.input, args.output, args.profile)
        else:
            print(f"❌ 错误: 路径不存在 {args.input}")
            return

        # 显示结果
        if result['success']:
            print("\n🎉 加密完成!")
            print(f"📄 加密文件: {result['encrypted_file']}")
            print(f"🔑 解密器: {result['decryptor_file']}")
            print(f"📊 原始大小: {result['original_size']:,} 字节")
            print(f"📊 加密大小: {result['encrypted_size']:,} 字节")
            print(f"📊 压缩比: {result['compression_ratio']:.2%}")
            print(f"⏱️  耗时: {result['encryption_time']:.2f} 秒")

            if 'file_count' in result:
                print(f"📁 文件数量: {result['file_count']}")
        else:
            print(f"\n❌ 加密失败: {result['error']}")

    except Exception as e:
        logger.error(f"命令行模式运行失败: {e}")
        print(f"❌ 运行失败: {e}")


def run_gui_mode():
    """运行图形界面模式"""
    logger = Logger("Main")
    logger.info("启动图形界面模式")

    try:
        # 检查GUI依赖
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:
            try:
                from PySide6.QtWidgets import QApplication
            except ImportError:
                print("❌ 错误: 未安装GUI库 (PyQt6 或 PySide6)")
                print("请运行: pip install PyQt6 或 pip install PySide6")
                return

        # 导入GUI模块
        try:
            from gui.main_window import MainWindow
        except ImportError:
            print("⚠️  GUI模块尚未实现，将启动命令行模式")
            print("请使用 --cli 参数运行命令行版本")
            return

        # 启动GUI应用
        app = QApplication(sys.argv)
        app.setApplicationName("文件加密系统")
        app.setApplicationVersion("1.0.0")

        window = MainWindow()
        window.show()

        print("✅ GUI界面已启动")
        sys.exit(app.exec())

    except Exception as e:
        logger.error(f"图形界面模式运行失败: {e}")
        print(f"❌ GUI启动失败: {e}")


def run_separate_engines_mode():
    """运行分离式加密引擎模式"""
    logger = Logger("Main")
    logger.info("启动分离式加密引擎模式")

    try:
        # 检查GUI依赖
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:
            try:
                from PySide6.QtWidgets import QApplication
            except ImportError:
                print("❌ 错误: 未安装GUI库 (PyQt6 或 PySide6)")
                print("请运行: pip install PyQt6 或 pip install PySide6")
                return

        # 导入分离式加密引擎GUI模块
        try:
            from separate_engines_gui import SeparateEnginesGUI
        except ImportError as e:
            print(f"❌ 错误: 无法导入分离式加密引擎GUI模块: {e}")
            print("请确保 separate_engines_gui.py 文件存在")
            return

        # 启动分离式加密引擎GUI应用
        app = QApplication(sys.argv)
        app.setApplicationName("CPU/GPU分离式加密引擎")
        app.setApplicationVersion("1.0.0")

        window = SeparateEnginesGUI()
        window.show()

        print("✅ 分离式加密引擎GUI已启动")
        print("💡 功能特性:")
        print("   - 🖥️ 纯CPU引擎: 使用CPU专用算法")
        print("   - 🚀 纯GPU引擎: 使用GPU专用算法")
        print("   - 🔧 专用解密器: 每种引擎生成对应解密器")
        print("   - 🎯 完美兼容: 解决高级加密配置兼容性问题")

        sys.exit(app.exec())

    except Exception as e:
        logger.error(f"分离式加密引擎模式运行失败: {e}")
        print(f"❌ 分离式加密引擎启动失败: {e}")
        import traceback
        traceback.print_exc()


def run_test_mode(args):
    """运行测试模式"""
    logger = Logger("Test")
    logger.info("启动测试模式")

    print("🧪 文件加密系统测试模式")
    print("=" * 50)

    try:
        # 创建测试目录
        test_dir = "encryption_test_output"
        os.makedirs(test_dir, exist_ok=True)
        print(f"📁 测试目录: {test_dir}")

        # 创建测试文件
        test_file = create_test_file(test_dir)
        if not test_file:
            print("❌ 创建测试文件失败")
            return

        # 根据测试类型执行不同的测试
        if args.test_cpu:
            test_cpu_encryptor(test_dir, test_file)
        elif args.test_gpu:
            test_gpu_encryptor(test_dir, test_file)
        elif args.test_both:
            test_both_encryptors(test_dir, test_file)
        elif args.test_compatibility:
            test_file_compatibility(test_dir, test_file)
        else:
            # 默认运行完整测试
            test_complete_system(test_dir, test_file)

    except Exception as e:
        logger.error(f"测试模式运行失败: {e}")
        print(f"❌ 测试失败: {e}")


def create_test_file(test_dir):
    """创建测试文件"""
    try:
        test_file = os.path.join(test_dir, "test_sample.txt")
        test_content = """这是jiami文件加密系统的测试文件。
This is a test file for jiami file encryption system.

测试内容包括：
- 中文字符测试
- English character test
- 数字测试: 123456789
- 特殊字符测试: !@#$%^&*()
- 换行符测试

系统功能测试：
1. CPU加密器测试
2. GPU加密器测试
3. 文件后缀统一测试
4. 解密器兼容性测试
5. 性能对比测试

测试时间: """ + str(os.times()) + "\n"

        # 重复内容以增加文件大小
        test_content = test_content * 50

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)

        file_size = os.path.getsize(test_file)
        print(f"✅ 测试文件创建成功: {os.path.basename(test_file)} ({file_size:,} 字节)")

        return test_file

    except Exception as e:
        print(f"❌ 创建测试文件失败: {e}")
        return None


def test_cpu_encryptor(test_dir, test_file):
    """测试CPU加密器"""
    print(f"\n🖥️ CPU加密器测试")
    print("-" * 30)

    try:
        # 创建CPU加密器
        cpu_encryptor = FileEncryptor()
        print("✅ CPU加密器初始化成功")

        # 执行加密
        print("🔐 开始CPU加密...")
        import time
        start_time = time.time()

        result = cpu_encryptor.encrypt_file(
            file_path=test_file,
            output_dir=test_dir,
            profile='standard'
        )

        encrypt_time = time.time() - start_time

        if result and result.get('success'):
            print(f"✅ CPU加密成功")
            print(f"   - 加密文件: {os.path.basename(result['encrypted_file'])}")
            print(f"   - 解密器: {os.path.basename(result['decryptor_file'])}")
            print(f"   - 原始大小: {result['original_size']:,} 字节")
            print(f"   - 加密大小: {result['encrypted_size']:,} 字节")
            print(f"   - 压缩比: {result['compression_ratio']:.2%}")
            print(f"   - 加密耗时: {encrypt_time:.3f} 秒")

            # 检查文件后缀
            encrypted_ext = os.path.splitext(result['encrypted_file'])[1]
            decryptor_ext = os.path.splitext(result['decryptor_file'])[1]
            print(f"   - 加密文件后缀: {encrypted_ext}")
            print(f"   - 解密器后缀: {decryptor_ext}")

            return result
        else:
            print(f"❌ CPU加密失败: {result.get('error', '未知错误')}")
            return None

    except Exception as e:
        print(f"❌ CPU加密器测试失败: {e}")
        return None


def test_gpu_encryptor(test_dir, test_file):
    """测试GPU加密器"""
    print(f"\n🎮 GPU加密器测试")
    print("-" * 30)

    try:
        # 创建GPU加密器
        gpu_encryptor = GPUFileEncryptor()
        print("✅ GPU加密器初始化成功")

        # 执行加密
        print("🔐 开始GPU加密...")
        import time
        start_time = time.time()

        result = gpu_encryptor.encrypt_file(
            input_file=test_file,
            output_dir=test_dir,
            security_level=2
        )

        encrypt_time = time.time() - start_time

        if result and result.get('success'):
            print(f"✅ GPU加密成功")
            print(f"   - 加密文件: {os.path.basename(result['encrypted_file'])}")
            print(f"   - Python解密器: {os.path.basename(result['decryptor_file'])}")
            if result.get('decryptor_exe'):
                print(f"   - exe解密器: {os.path.basename(result['decryptor_exe'])}")
            print(f"   - 原始大小: {result['original_size']:,} 字节")
            print(f"   - 加密大小: {result['encrypted_size']:,} 字节")
            print(f"   - 加密速度: {result['speed_mbps']:.2f} MB/s")
            print(f"   - 加密层数: {result['layers']}")
            print(f"   - GPU专用: {result['gpu_only']}")
            print(f"   - 加密耗时: {encrypt_time:.3f} 秒")

            # 检查文件后缀
            encrypted_ext = os.path.splitext(result['encrypted_file'])[1]
            print(f"   - 加密文件后缀: {encrypted_ext}")

            return result
        else:
            print(f"❌ GPU加密失败: {result.get('error', '未知错误')}")
            return None

    except Exception as e:
        print(f"❌ GPU加密器测试失败: {e}")
        return None


def test_both_encryptors(test_dir, test_file):
    """测试CPU和GPU加密器对比"""
    print(f"\n⚖️ CPU vs GPU加密器对比测试")
    print("-" * 40)

    # 测试CPU加密器
    cpu_result = test_cpu_encryptor(test_dir, test_file)

    # 测试GPU加密器
    gpu_result = test_gpu_encryptor(test_dir, test_file)

    # 对比结果
    print(f"\n📊 对比结果:")
    print("-" * 20)

    if cpu_result and gpu_result:
        print(f"✅ 两种加密器都工作正常")

        # 文件后缀对比
        cpu_ext = os.path.splitext(cpu_result['encrypted_file'])[1]
        gpu_ext = os.path.splitext(gpu_result['encrypted_file'])[1]

        print(f"📁 文件后缀对比:")
        print(f"   - CPU: {cpu_ext}")
        print(f"   - GPU: {gpu_ext}")
        print(f"   - 一致性: {'✅ 一致' if cpu_ext == gpu_ext else '❌ 不一致'}")

        # 性能对比
        cpu_time = cpu_result.get('encryption_time', 0)
        gpu_speed = gpu_result.get('speed_mbps', 0)

        print(f"⚡ 性能对比:")
        print(f"   - CPU加密时间: {cpu_time:.3f} 秒")
        print(f"   - GPU加密速度: {gpu_speed:.2f} MB/s")

        # 文件大小对比
        print(f"📊 文件大小对比:")
        print(f"   - CPU加密大小: {cpu_result['encrypted_size']:,} 字节")
        print(f"   - GPU加密大小: {gpu_result['encrypted_size']:,} 字节")

    elif cpu_result:
        print(f"⚠️ 仅CPU加密器工作正常")
    elif gpu_result:
        print(f"⚠️ 仅GPU加密器工作正常")
    else:
        print(f"❌ 两种加密器都无法正常工作")


def test_file_compatibility(test_dir, test_file):
    """测试文件兼容性"""
    print(f"\n🔍 文件兼容性测试")
    print("-" * 30)

    # 先进行加密
    cpu_result = test_cpu_encryptor(test_dir, test_file)
    gpu_result = test_gpu_encryptor(test_dir, test_file)

    if not cpu_result or not gpu_result:
        print("❌ 加密失败，无法进行兼容性测试")
        return

    print(f"\n🔍 检查生成的文件:")

    # 检查CPU生成的文件
    cpu_files = [cpu_result['encrypted_file'], cpu_result['decryptor_file']]
    print(f"📁 CPU生成的文件:")
    for file_path in cpu_files:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"   ✅ {os.path.basename(file_path)}: {file_size:,} 字节")
        else:
            print(f"   ❌ {os.path.basename(file_path)}: 不存在")

    # 检查GPU生成的文件
    gpu_files = [gpu_result['encrypted_file'], gpu_result['decryptor_file']]
    if gpu_result.get('decryptor_exe'):
        gpu_files.append(gpu_result['decryptor_exe'])

    print(f"📁 GPU生成的文件:")
    for file_path in gpu_files:
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"   ✅ {os.path.basename(file_path)}: {file_size:,} 字节")
        else:
            print(f"   ❌ {os.path.basename(file_path)}: 不存在")


def test_complete_system(test_dir, test_file):
    """完整系统测试"""
    print(f"\n🧪 完整系统测试")
    print("-" * 30)

    print("正在执行完整的系统测试，包括:")
    print("1. CPU加密器测试")
    print("2. GPU加密器测试")
    print("3. 性能对比测试")
    print("4. 文件兼容性测试")

    # 执行所有测试
    test_both_encryptors(test_dir, test_file)
    test_file_compatibility(test_dir, test_file)

    print(f"\n🎯 测试总结:")
    print("✅ 完整系统测试完成")
    print(f"📁 所有测试文件保存在: {test_dir}")
    print("💡 您可以手动运行生成的解密器来验证解密功能")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="文件加密系统 - 企业级数据保护解决方案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分离式加密引擎模式 (默认)
  python main.py
  python main.py --separate

  # 传统图形界面模式
  python main.py --gui

  # 命令行模式 - 加密文件
  python main.py --cli -i myfile.txt -o ./encrypted

  # 命令行模式 - 加密文件夹
  python main.py --cli -i ./myfolder -o ./encrypted -p high

  # 列出可用配置
  python main.py --cli --list-profiles

  # 测试模式 - 完整系统测试
  python main.py --test

  # 测试模式 - 仅测试CPU加密器
  python main.py --test --test-cpu

  # 测试模式 - 仅测试GPU加密器
  python main.py --test --test-gpu

  # 测试模式 - 对比CPU和GPU加密器
  python main.py --test --test-both

  # 测试模式 - 文件兼容性测试
  python main.py --test --test-compatibility

分离式加密引擎特性:
  🖥️ 纯CPU引擎 - 使用CPU专用算法，完美兼容性
  🚀 纯GPU引擎 - 使用GPU专用算法，极致性能
  🔧 专用解密器 - 每种引擎生成对应的专用解密器
  🎯 完美兼容 - 解决高级加密配置的兼容性问题
        """
    )

    # 模式选择
    mode_group = parser.add_mutually_exclusive_group(required=False)  # 改为非必需，允许默认模式
    mode_group.add_argument("--separate", action="store_true", help="启动分离式加密引擎模式 (默认)")
    mode_group.add_argument("--gui", action="store_true", help="启动传统图形界面模式")
    mode_group.add_argument("--cli", action="store_true", help="启动命令行模式")
    mode_group.add_argument("--test", action="store_true", help="启动测试模式")

    # 命令行参数
    parser.add_argument("-i", "--input", help="要加密的文件或文件夹路径")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("-p", "--profile", default="standard", help="加密配置文件 (默认: standard)")
    parser.add_argument("--list-profiles", action="store_true", help="列出可用的配置文件")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")
    parser.add_argument("--version", action="version", version="文件加密系统 v1.0.0")

    # 测试模式参数
    parser.add_argument("--test-cpu", action="store_true", help="仅测试CPU加密器")
    parser.add_argument("--test-gpu", action="store_true", help="仅测试GPU加密器")
    parser.add_argument("--test-both", action="store_true", help="对比测试CPU和GPU加密器")
    parser.add_argument("--test-compatibility", action="store_true", help="测试文件兼容性")

    args = parser.parse_args()

    # 显示欢迎信息
    print("🔐 文件加密系统 v1.0.0")
    print("=" * 50)

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 根据模式运行
    if args.separate or (not args.gui and not args.cli and not args.test):
        # 分离式加密引擎模式 (默认)
        run_separate_engines_mode()
    elif args.gui:
        # 传统图形界面模式
        run_gui_mode()
    elif args.cli:
        # 命令行模式
        run_cli_mode(args)
    elif args.test:
        # 测试模式
        run_test_mode(args)


if __name__ == "__main__":
    main()
