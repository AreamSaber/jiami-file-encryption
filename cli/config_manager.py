"""
配置管理器

提供加密配置的创建、编辑、导入导出等功能。
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import Logger


class ConfigManager:
    """配置管理器类"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.logger = Logger("ConfigManager")
        self.config_dir = Path(__file__).parent.parent / "config"
        self.profiles_file = self.config_dir / "encryption_profiles.json"
        
    def list_profiles(self) -> List[str]:
        """列出所有配置文件"""
        try:
            if not self.profiles_file.exists():
                return []
            
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                profiles_data = json.load(f)
            
            return list(profiles_data.get('profiles', {}).keys())
            
        except Exception as e:
            self.logger.error(f"列出配置失败: {e}")
            return []
    
    def get_profile_info(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """获取配置详情"""
        try:
            if not self.profiles_file.exists():
                return None
            
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                profiles_data = json.load(f)
            
            return profiles_data.get('profiles', {}).get(profile_name)
            
        except Exception as e:
            self.logger.error(f"获取配置信息失败: {e}")
            return None
    
    def create_profile(self, profile_name: str, interactive: bool = True) -> bool:
        """创建新配置"""
        try:
            # 检查配置是否已存在
            if self.get_profile_info(profile_name):
                print(f"❌ 配置 '{profile_name}' 已存在")
                return False
            
            if interactive:
                profile_config = self._interactive_create_profile(profile_name)
            else:
                profile_config = self._create_default_profile(profile_name)
            
            # 保存配置
            return self._save_profile(profile_name, profile_config)
            
        except Exception as e:
            self.logger.error(f"创建配置失败: {e}")
            return False
    
    def _interactive_create_profile(self, profile_name: str) -> Dict[str, Any]:
        """交互式创建配置"""
        print(f"🔧 创建新配置: {profile_name}")
        print("请按照提示输入配置信息 (直接回车使用默认值):")
        
        # 基本信息
        display_name = input(f"显示名称 [{profile_name}]: ").strip() or profile_name
        description = input("描述 [自定义加密配置]: ").strip() or "自定义加密配置"
        
        # 安全级别
        print("\n安全级别:")
        print("1. 低 (快速)")
        print("2. 中 (平衡)")
        print("3. 高 (安全)")
        print("4. 极高 (最安全)")
        
        security_choice = input("选择安全级别 [2]: ").strip() or "2"
        security_levels = {
            "1": "low",
            "2": "medium", 
            "3": "high",
            "4": "extreme"
        }
        security_level = security_levels.get(security_choice, "medium")
        
        # 加密算法
        print("\n主要加密算法:")
        print("1. AES-256-GCM (推荐)")
        print("2. AES-256-CBC")
        print("3. ChaCha20")
        print("4. 混合模式")
        
        algo_choice = input("选择算法 [1]: ").strip() or "1"
        algorithms = {
            "1": "aes256",
            "2": "aes256",
            "3": "chacha20",
            "4": "custom"
        }
        algorithm = algorithms.get(algo_choice, "aes256")
        
        # 加密模式
        if algo_choice == "1":
            mode = "GCM"
        elif algo_choice == "2":
            mode = "CBC"
        else:
            mode = None
        
        # 加密层数
        if algorithm == "custom":
            layers_input = input("加密层数 [3]: ").strip() or "3"
            try:
                layers = int(layers_input)
            except ValueError:
                layers = 3
        else:
            layers = 1
        
        # 构建配置
        config = {
            "name": display_name,
            "description": description,
            "security_level": security_level,
            "layers": []
        }
        
        if algorithm == "custom":
            # 多层加密配置
            for i in range(layers):
                layer_config = {
                    "method": "custom",
                    "algorithm": "simple_xor" if i == 0 else "bit_shuffle"
                }
                config["layers"].append(layer_config)
        else:
            # 单层加密配置
            layer_config = {
                "method": algorithm,
                "algorithm": algorithm
            }
            if mode:
                layer_config["mode"] = mode
            
            config["layers"].append(layer_config)
        
        # 可选功能
        print("\n可选功能:")
        
        enable_compression = input("启用压缩? [y/N]: ").strip().lower()
        if enable_compression in ['y', 'yes']:
            config["compression"] = {"enabled": True, "level": 6}
        
        enable_steganography = input("启用隐写术? [y/N]: ").strip().lower()
        if enable_steganography in ['y', 'yes']:
            config["steganography"] = {"enabled": True, "method": "lsb_image"}
        
        enable_security = input("启用安全保护? [Y/n]: ").strip().lower()
        if enable_security not in ['n', 'no']:
            config["security"] = {
                "anti_debug": True,
                "anti_vm": True,
                "code_obfuscation": True
            }
        
        return config
    
    def _create_default_profile(self, profile_name: str) -> Dict[str, Any]:
        """创建默认配置"""
        return {
            "name": profile_name,
            "description": "默认加密配置",
            "security_level": "medium",
            "layers": [
                {
                    "method": "aes256",
                    "algorithm": "aes256",
                    "mode": "GCM"
                }
            ],
            "security": {
                "anti_debug": True,
                "anti_vm": True,
                "code_obfuscation": True
            }
        }
    
    def _save_profile(self, profile_name: str, profile_config: Dict[str, Any]) -> bool:
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            self.config_dir.mkdir(exist_ok=True)
            
            # 读取现有配置
            if self.profiles_file.exists():
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
            else:
                profiles_data = {"profiles": {}}
            
            # 添加新配置
            profiles_data["profiles"][profile_name] = profile_config
            
            # 保存到文件
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置保存成功: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False
    
    def edit_profile(self, profile_name: str) -> bool:
        """编辑配置"""
        try:
            current_config = self.get_profile_info(profile_name)
            if not current_config:
                print(f"❌ 配置不存在: {profile_name}")
                return False
            
            print(f"🔧 编辑配置: {profile_name}")
            print("当前配置:")
            print(json.dumps(current_config, indent=2, ensure_ascii=False))
            
            # 简单的编辑界面
            print("\n选择要编辑的项目:")
            print("1. 显示名称")
            print("2. 描述")
            print("3. 安全级别")
            print("4. 完整重新配置")
            
            choice = input("选择 [4]: ").strip() or "4"
            
            if choice == "1":
                new_name = input(f"新名称 [{current_config.get('name', '')}]: ").strip()
                if new_name:
                    current_config["name"] = new_name
            elif choice == "2":
                new_desc = input(f"新描述 [{current_config.get('description', '')}]: ").strip()
                if new_desc:
                    current_config["description"] = new_desc
            elif choice == "3":
                print("安全级别: 1=低, 2=中, 3=高, 4=极高")
                level_choice = input("选择: ").strip()
                levels = {"1": "low", "2": "medium", "3": "high", "4": "extreme"}
                if level_choice in levels:
                    current_config["security_level"] = levels[level_choice]
            elif choice == "4":
                current_config = self._interactive_create_profile(profile_name)
            
            # 保存修改
            return self._save_profile(profile_name, current_config)
            
        except Exception as e:
            self.logger.error(f"编辑配置失败: {e}")
            return False
    
    def delete_profile(self, profile_name: str) -> bool:
        """删除配置"""
        try:
            if not self.profiles_file.exists():
                print(f"❌ 配置文件不存在")
                return False
            
            with open(self.profiles_file, 'r', encoding='utf-8') as f:
                profiles_data = json.load(f)
            
            if profile_name not in profiles_data.get("profiles", {}):
                print(f"❌ 配置不存在: {profile_name}")
                return False
            
            # 确认删除
            confirm = input(f"确认删除配置 '{profile_name}'? [y/N]: ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("取消删除")
                return False
            
            # 删除配置
            del profiles_data["profiles"][profile_name]
            
            # 保存文件
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(profiles_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 配置删除成功: {profile_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除配置失败: {e}")
            return False
    
    def export_profile(self, profile_name: str, export_file: str) -> bool:
        """导出配置到文件"""
        try:
            config = self.get_profile_info(profile_name)
            if not config:
                print(f"❌ 配置不存在: {profile_name}")
                return False
            
            export_data = {
                "profile_name": profile_name,
                "config": config,
                "export_version": "1.0",
                "export_time": str(Path().cwd())
            }
            
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ 配置导出成功: {export_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return False
    
    def import_profile(self, import_file: str, new_name: Optional[str] = None) -> bool:
        """从文件导入配置"""
        try:
            if not os.path.exists(import_file):
                print(f"❌ 导入文件不存在: {import_file}")
                return False
            
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            profile_name = new_name or import_data.get("profile_name", "imported_profile")
            config = import_data.get("config")
            
            if not config:
                print("❌ 导入文件格式错误")
                return False
            
            # 检查是否已存在
            if self.get_profile_info(profile_name):
                overwrite = input(f"配置 '{profile_name}' 已存在，是否覆盖? [y/N]: ").strip().lower()
                if overwrite not in ['y', 'yes']:
                    print("取消导入")
                    return False
            
            # 保存配置
            success = self._save_profile(profile_name, config)
            if success:
                print(f"✅ 配置导入成功: {profile_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            return False
