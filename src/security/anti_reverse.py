"""
反逆向工程保护

提供代码混淆、反调试、完整性检查等安全保护功能。
"""

import os
import sys
import time
import hashlib
from typing import Dict, Any, Optional

from ..utils.logger import Logger


class AntiReverse:
    """反逆向工程保护类"""
    
    def __init__(self):
        """初始化反逆向保护"""
        self.logger = Logger("AntiReverse")
        self.protection_enabled = True
        
    def enable_protection(self, enabled: bool = True):
        """启用/禁用保护"""
        self.protection_enabled = enabled
        self.logger.info(f"反逆向保护: {'启用' if enabled else '禁用'}")
    
    def check_debugger(self) -> bool:
        """检测调试器"""
        if not self.protection_enabled:
            return False
        
        try:
            # Windows调试器检测
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                
                # IsDebuggerPresent检测
                if kernel32.IsDebuggerPresent():
                    self.logger.warning("检测到调试器 (IsDebuggerPresent)")
                    return True
                
                # CheckRemoteDebuggerPresent检测
                debug_flag = ctypes.c_bool()
                if kernel32.CheckRemoteDebuggerPresent(kernel32.GetCurrentProcess(), ctypes.byref(debug_flag)):
                    if debug_flag.value:
                        self.logger.warning("检测到远程调试器")
                        return True
            
            # 通用调试器检测方法
            # 检查sys.gettrace()
            if sys.gettrace() is not None:
                self.logger.warning("检测到Python调试器")
                return True
            
            # 时序检测
            start_time = time.time()
            time.sleep(0.001)  # 1毫秒
            end_time = time.time()
            
            if (end_time - start_time) > 0.01:  # 如果超过10毫秒
                self.logger.warning("检测到可能的调试器 (时序异常)")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"调试器检测失败: {e}")
            return False
    
    def check_vm_environment(self) -> bool:
        """检测虚拟机环境"""
        if not self.protection_enabled:
            return False
        
        try:
            vm_indicators = []
            
            # 检查常见的VM文件
            vm_files = [
                "C:\\windows\\system32\\drivers\\vmmouse.sys",
                "C:\\windows\\system32\\drivers\\vmhgfs.sys",
                "C:\\windows\\system32\\drivers\\VBoxMouse.sys",
                "C:\\windows\\system32\\drivers\\VBoxGuest.sys",
                "C:\\windows\\system32\\vboxdisp.dll",
                "C:\\windows\\system32\\vboxhook.dll"
            ]
            
            for vm_file in vm_files:
                if os.path.exists(vm_file):
                    vm_indicators.append(f"VM文件: {vm_file}")
            
            # 检查注册表项（Windows）
            if sys.platform == "win32":
                try:
                    import winreg
                    
                    vm_registry_keys = [
                        (winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Enum\\PCI\\VEN_80EE&DEV_BEEF"),
                        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\VMware, Inc.\\VMware Tools"),
                        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Oracle\\VirtualBox Guest Additions")
                    ]
                    
                    for hkey, subkey in vm_registry_keys:
                        try:
                            winreg.OpenKey(hkey, subkey)
                            vm_indicators.append(f"VM注册表: {subkey}")
                        except FileNotFoundError:
                            pass
                            
                except ImportError:
                    pass
            
            # 检查MAC地址
            try:
                import uuid
                mac = uuid.getnode()
                mac_str = ':'.join(['{:02x}'.format((mac >> i) & 0xff) for i in range(0, 48, 8)][::-1])
                
                vm_mac_prefixes = [
                    "00:05:69",  # VMware
                    "00:0C:29",  # VMware
                    "00:50:56",  # VMware
                    "08:00:27",  # VirtualBox
                    "00:03:FF"   # VirtualPC
                ]
                
                for prefix in vm_mac_prefixes:
                    if mac_str.upper().startswith(prefix.upper()):
                        vm_indicators.append(f"VM MAC地址: {mac_str}")
                        break
                        
            except Exception:
                pass
            
            if vm_indicators:
                self.logger.warning(f"检测到虚拟机环境: {vm_indicators}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"虚拟机检测失败: {e}")
            return False
    
    def check_file_integrity(self, file_path: str, expected_hash: Optional[str] = None) -> bool:
        """检查文件完整性"""
        if not self.protection_enabled:
            return True
        
        try:
            if not os.path.exists(file_path):
                self.logger.warning(f"文件不存在: {file_path}")
                return False
            
            # 计算文件哈希
            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_hash = hashlib.sha256(file_data).hexdigest()
            
            if expected_hash:
                if file_hash != expected_hash:
                    self.logger.warning(f"文件完整性检查失败: {file_path}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"文件完整性检查失败: {e}")
            return False
    
    def obfuscate_strings(self, strings: Dict[str, str]) -> Dict[str, str]:
        """混淆字符串"""
        if not self.protection_enabled:
            return strings
        
        try:
            obfuscated = {}
            
            for key, value in strings.items():
                # 简单的XOR混淆
                xor_key = 0x5A
                obfuscated_value = ''.join(chr(ord(c) ^ xor_key) for c in value)
                obfuscated[key] = obfuscated_value
            
            return obfuscated
            
        except Exception as e:
            self.logger.error(f"字符串混淆失败: {e}")
            return strings
    
    def deobfuscate_string(self, obfuscated_string: str) -> str:
        """去混淆字符串"""
        try:
            # 对应的XOR去混淆
            xor_key = 0x5A
            return ''.join(chr(ord(c) ^ xor_key) for c in obfuscated_string)
            
        except Exception as e:
            self.logger.error(f"字符串去混淆失败: {e}")
            return obfuscated_string
    
    def add_dummy_code(self, iterations: int = 100):
        """添加干扰代码"""
        if not self.protection_enabled:
            return
        
        try:
            # 执行一些无意义的计算来干扰分析
            dummy_result = 0
            for i in range(iterations):
                dummy_result += i * 2
                dummy_result = dummy_result % 1000
            
            # 随机延时
            import random
            time.sleep(random.uniform(0.001, 0.005))
            
        except Exception:
            pass
    
    def check_process_list(self) -> bool:
        """检查进程列表中的分析工具"""
        if not self.protection_enabled:
            return False
        
        try:
            import psutil
            
            # 常见的分析工具进程名
            analysis_tools = [
                "ollydbg.exe", "x64dbg.exe", "windbg.exe", "ida.exe", "ida64.exe",
                "idaq.exe", "idaq64.exe", "idaw.exe", "idaw64.exe",
                "wireshark.exe", "fiddler.exe", "procmon.exe", "procexp.exe",
                "cheatengine.exe", "ce.exe", "processhacker.exe"
            ]
            
            running_processes = [p.name().lower() for p in psutil.process_iter(['name'])]
            
            for tool in analysis_tools:
                if tool.lower() in running_processes:
                    self.logger.warning(f"检测到分析工具: {tool}")
                    return True
            
            return False
            
        except ImportError:
            # psutil未安装，跳过检查
            return False
        except Exception as e:
            self.logger.error(f"进程检查失败: {e}")
            return False
    
    def perform_security_check(self) -> Dict[str, bool]:
        """执行完整的安全检查"""
        if not self.protection_enabled:
            return {"protection_disabled": True}
        
        results = {
            "debugger_detected": self.check_debugger(),
            "vm_detected": self.check_vm_environment(),
            "analysis_tools_detected": self.check_process_list()
        }
        
        # 如果检测到威胁，添加干扰代码
        if any(results.values()):
            self.add_dummy_code(200)
        
        return results
    
    def get_protection_status(self) -> Dict[str, Any]:
        """获取保护状态"""
        return {
            "enabled": self.protection_enabled,
            "platform": sys.platform,
            "python_version": sys.version,
            "security_checks": self.perform_security_check()
        }
