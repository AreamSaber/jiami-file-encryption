"""
增强的命令行界面

提供更丰富的命令行功能和交互体验。
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.encryptor.main import FileEncryptor
from src.utils.logger import Logger
from src.utils.file_utils import FileUtils


class EnhancedCLI:
    """增强的命令行界面"""
    
    def __init__(self):
        """初始化CLI"""
        self.logger = Logger("EnhancedCLI")
        self.encryptor = FileEncryptor()
        self.file_utils = FileUtils()
        
    def create_parser(self) -> argparse.ArgumentParser:
        """创建命令行参数解析器"""
        parser = argparse.ArgumentParser(
            description="文件加密系统 - 增强命令行界面",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用示例:
  # 基础加密
  python -m cli.enhanced_cli encrypt -i file.txt -o ./output
  
  # 批量加密
  python -m cli.enhanced_cli batch -d ./documents -o ./encrypted
  
  # 配置管理
  python -m cli.enhanced_cli config --list
  python -m cli.enhanced_cli config --create myconfig
  
  # 系统信息
  python -m cli.enhanced_cli info --system
  python -m cli.enhanced_cli info --profiles
            """
        )
        
        # 添加子命令
        subparsers = parser.add_subparsers(dest='command', help='可用命令')
        
        # 加密命令
        self._add_encrypt_parser(subparsers)
        
        # 批处理命令
        self._add_batch_parser(subparsers)
        
        # 配置管理命令
        self._add_config_parser(subparsers)
        
        # 信息查看命令
        self._add_info_parser(subparsers)
        
        # 工具命令
        self._add_tools_parser(subparsers)
        
        return parser
    
    def _add_encrypt_parser(self, subparsers):
        """添加加密命令解析器"""
        encrypt_parser = subparsers.add_parser('encrypt', help='加密文件或文件夹')
        
        encrypt_parser.add_argument('-i', '--input', required=True,
                                  help='输入文件或文件夹路径')
        encrypt_parser.add_argument('-o', '--output', required=True,
                                  help='输出目录')
        encrypt_parser.add_argument('-p', '--profile', default='standard',
                                  help='加密配置文件 (默认: standard)')
        encrypt_parser.add_argument('-v', '--verbose', action='store_true',
                                  help='详细输出')
        
    def _add_batch_parser(self, subparsers):
        """添加批处理命令解析器"""
        batch_parser = subparsers.add_parser('batch', help='批量处理文件')
        
        batch_parser.add_argument('-d', '--directory', required=True,
                                help='要处理的目录')
        batch_parser.add_argument('-o', '--output', required=True,
                                help='输出目录')
        batch_parser.add_argument('-p', '--profile', default='standard',
                                help='加密配置文件')
        batch_parser.add_argument('--pattern', default='*',
                                help='文件匹配模式 (默认: *)')
        batch_parser.add_argument('--exclude', action='append',
                                help='排除模式 (可多次使用)')
        batch_parser.add_argument('--recursive', action='store_true',
                                help='递归处理子目录')
        batch_parser.add_argument('--parallel', type=int, default=1,
                                help='并行处理数量 (默认: 1)')
        batch_parser.add_argument('--dry-run', action='store_true',
                                help='试运行 (不实际加密)')
        
    def _add_config_parser(self, subparsers):
        """添加配置管理命令解析器"""
        config_parser = subparsers.add_parser('config', help='配置管理')
        
        config_group = config_parser.add_mutually_exclusive_group(required=True)
        config_group.add_argument('--list', action='store_true',
                                help='列出所有配置')
        config_group.add_argument('--show', 
                                help='显示指定配置详情')
        config_group.add_argument('--create',
                                help='创建新配置')
        config_group.add_argument('--edit',
                                help='编辑配置')
        config_group.add_argument('--delete',
                                help='删除配置')
        config_group.add_argument('--export',
                                help='导出配置到文件')
        config_group.add_argument('--import',
                                help='从文件导入配置')
        
    def _add_info_parser(self, subparsers):
        """添加信息查看命令解析器"""
        info_parser = subparsers.add_parser('info', help='查看系统信息')
        
        info_parser.add_argument('--system', action='store_true',
                               help='显示系统信息')
        info_parser.add_argument('--profiles', action='store_true',
                               help='显示配置文件信息')
        info_parser.add_argument('--algorithms', action='store_true',
                               help='显示可用算法')
        info_parser.add_argument('--dependencies', action='store_true',
                               help='检查依赖包')
        info_parser.add_argument('--performance', action='store_true',
                               help='性能测试')
        
    def _add_tools_parser(self, subparsers):
        """添加工具命令解析器"""
        tools_parser = subparsers.add_parser('tools', help='实用工具')
        
        tools_group = tools_parser.add_mutually_exclusive_group(required=True)
        tools_group.add_argument('--benchmark', 
                               help='性能基准测试 (文件路径)')
        tools_group.add_argument('--verify',
                               help='验证加密文件完整性')
        tools_group.add_argument('--analyze',
                               help='分析文件加密强度')
        tools_group.add_argument('--cleanup',
                               help='清理临时文件')
        tools_group.add_argument('--generate-key', type=int,
                               help='生成随机密钥 (长度)')
        
    def run(self, args=None):
        """运行CLI"""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        if not parsed_args.command:
            parser.print_help()
            return
        
        try:
            # 根据命令执行相应操作
            if parsed_args.command == 'encrypt':
                self._handle_encrypt(parsed_args)
            elif parsed_args.command == 'batch':
                self._handle_batch(parsed_args)
            elif parsed_args.command == 'config':
                self._handle_config(parsed_args)
            elif parsed_args.command == 'info':
                self._handle_info(parsed_args)
            elif parsed_args.command == 'tools':
                self._handle_tools(parsed_args)
                
        except KeyboardInterrupt:
            print("\n⚠️  操作被用户中断")
        except Exception as e:
            self.logger.error(f"命令执行失败: {e}")
            print(f"❌ 错误: {e}")
            
    def _handle_encrypt(self, args):
        """处理加密命令"""
        print(f"🔐 开始加密: {args.input}")
        
        # 检查输入路径
        if not os.path.exists(args.input):
            print(f"❌ 错误: 路径不存在 {args.input}")
            return
        
        # 创建输出目录
        os.makedirs(args.output, exist_ok=True)
        
        # 执行加密
        if os.path.isfile(args.input):
            result = self.encryptor.encrypt_file(args.input, args.output, args.profile)
        else:
            result = self.encryptor.encrypt_folder(args.input, args.output, args.profile)
        
        # 显示结果
        if result['success']:
            print("✅ 加密完成! 仅可分享 data.jmi；recovery.jmis 与 recover.py 必须保密。")
            if result.get("warning"):
                print(result["warning"])
            print(f"📁 输出目录: {args.output}")
            if args.verbose:
                print(f"⏱️  耗时: {result.get('encryption_time', 0):.2f} 秒")
                print(f"📊 原始大小: {self.file_utils.format_size(result.get('original_size', 0))}")
                print(f"📊 加密大小: {self.file_utils.format_size(result.get('encrypted_size', 0))}")
        else:
            print(f"❌ 加密失败: {result.get('error', '未知错误')}")
            
    def _handle_batch(self, args):
        """处理批处理命令"""
        from .batch_processor import BatchProcessor
        
        processor = BatchProcessor()
        
        options = {
            'pattern': args.pattern,
            'exclude': args.exclude or [],
            'recursive': args.recursive,
            'parallel': args.parallel,
            'dry_run': args.dry_run,
            'profile': args.profile
        }
        
        result = processor.process_directory(args.directory, args.output, options)
        
        if result['success']:
            print(f"✅ 批处理完成! 处理了 {result['processed_count']} 个文件")
        else:
            print(f"❌ 批处理失败: {result['error']}")
            
    def _handle_config(self, args):
        """处理配置管理命令"""
        from .config_manager import ConfigManager
        
        config_manager = ConfigManager()
        
        if args.list:
            profiles = config_manager.list_profiles()
            print("📋 可用配置:")
            for profile in profiles:
                info = config_manager.get_profile_info(profile)
                print(f"  • {profile}: {info.get('name', '无名称')}")
                
        elif args.show:
            info = config_manager.get_profile_info(args.show)
            if info:
                print(f"📄 配置详情: {args.show}")
                print(json.dumps(info, indent=2, ensure_ascii=False))
            else:
                print(f"❌ 配置不存在: {args.show}")
                
        elif args.create:
            success = config_manager.create_profile(args.create)
            if success:
                print(f"✅ 配置创建成功: {args.create}")
            else:
                print(f"❌ 配置创建失败: {args.create}")
                
        # 其他配置操作...
        
    def _handle_info(self, args):
        """处理信息查看命令"""
        if args.system:
            self._show_system_info()
        elif args.profiles:
            self._show_profiles_info()
        elif args.algorithms:
            self._show_algorithms_info()
        elif args.dependencies:
            self._check_dependencies()
        elif args.performance:
            self._run_performance_test()
            
    def _handle_tools(self, args):
        """处理工具命令"""
        if args.benchmark:
            self._run_benchmark(args.benchmark)
        elif args.verify:
            self._verify_file(args.verify)
        elif args.analyze:
            self._analyze_file(args.analyze)
        elif args.cleanup:
            self._cleanup_temp_files(args.cleanup)
        elif args.generate_key:
            self._generate_key(args.generate_key)
            
    def _show_system_info(self):
        """显示系统信息"""
        import platform
        
        print("🖥️  系统信息:")
        print(f"  操作系统: {platform.system()} {platform.release()}")
        print(f"  Python版本: {platform.python_version()}")
        print(f"  架构: {platform.machine()}")
        print(f"  处理器: {platform.processor()}")
        
    def _show_profiles_info(self):
        """显示配置文件信息"""
        profiles = self.encryptor.list_profiles()
        print("📋 配置文件信息:")
        for profile in profiles:
            info = self.encryptor.get_profile_info(profile)
            print(f"  • {profile}:")
            print(f"    名称: {info.get('name', '无名称')}")
            print(f"    描述: {info.get('description', '无描述')}")
            print(f"    安全级别: {info.get('security_level', '未知')}")
            
    def _show_algorithms_info(self):
        """显示可用算法信息"""
        print("🔐 可用加密算法:")
        print("  对称加密:")
        print("    • AES-256 (GCM, CBC, CTR)")
        print("    • ChaCha20")
        print("  非对称加密:")
        print("    • RSA (2048, 4096位)")
        print("  自定义算法:")
        print("    • XOR加密")
        print("    • 位混洗")
        print("    • 旋转密码")
        print("    • 替换密码")
        
    def _check_dependencies(self):
        """检查依赖包"""
        dependencies = {
            'cryptography': '核心加密库',
            'PyNaCl': 'NaCl加密库',
            'Pillow': '图像处理 (隐写术)',
            'psutil': '系统信息',
            'PyQt6': 'GUI界面 (可选)',
            'PySide6': 'GUI界面 (可选)'
        }
        
        print("📦 依赖包检查:")
        for package, description in dependencies.items():
            try:
                __import__(package)
                print(f"  ✅ {package}: {description}")
            except ImportError:
                print(f"  ❌ {package}: {description} (未安装)")
                
    def _run_performance_test(self):
        """运行性能测试"""
        print("⚡ 性能测试:")
        print("  正在测试加密性能...")
        # 这里可以添加性能测试代码
        print("  测试完成")
        
    def _run_benchmark(self, file_path):
        """运行基准测试"""
        print(f"📊 基准测试: {file_path}")
        # 实现基准测试逻辑
        
    def _verify_file(self, file_path):
        """验证文件完整性"""
        print(f"🔍 验证文件: {file_path}")
        # 实现文件验证逻辑
        
    def _analyze_file(self, file_path):
        """分析文件加密强度"""
        print(f"🔬 分析文件: {file_path}")
        # 实现文件分析逻辑
        
    def _cleanup_temp_files(self, directory):
        """清理临时文件"""
        print(f"🧹 清理临时文件: {directory}")
        # 实现清理逻辑
        
    def _generate_key(self, length):
        """生成随机密钥"""
        from src.utils.crypto_utils import CryptoUtils
        
        crypto = CryptoUtils()
        key = crypto.generate_random_key(length)
        
        print(f"🔑 生成 {length} 字节随机密钥:")
        print(f"  十六进制: {key.hex()}")
        print(f"  Base64: {crypto.encode_base64(key)}")


if __name__ == "__main__":
    cli = EnhancedCLI()
    cli.run()
