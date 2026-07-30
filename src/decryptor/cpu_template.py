#!/usr/bin/env python3
"""
纯CPU解密器模板 v2.0
专门用于解密纯CPU混合加密引擎生成的加密文件

基于新架构设计，整合统一的算法注册表和错误处理
此文件是独立的解密器模板，不依赖外部模块
"""

import os
import sys
import pickle
import base64
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from abc import ABC, abstractmethod

# 加密元数据占位符 - 将被实际数据替换
ENCRYPTION_METADATA = b"__METADATA_PLACEHOLDER__"

# 版本信息
VERSION = "2.0.0"
ENGINE_TYPE = "CPU"


# ============ 异常类 ============

class DecryptionError(Exception):
    """解密错误"""
    def __init__(self, message: str, error_code: str = "DEC000", context: Dict = None):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(f"[{error_code}] {message}")


class AlgorithmNotSupportedError(DecryptionError):
    """算法不支持错误"""
    def __init__(self, algorithm: str):
        super().__init__(
            f"不支持的算法: {algorithm}",
            error_code="DEC001",
            context={'algorithm': algorithm}
        )


# ============ 算法处理器 ============

class AlgorithmHandler(ABC):
    """算法处理器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @property
    def aliases(self) -> list:
        return []
    
    @abstractmethod
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        pass


class AES256Handler(AlgorithmHandler):
    """AES-256算法处理器"""
    
    @property
    def name(self) -> str:
        return "AES-256"
    
    @property
    def aliases(self) -> list:
        return ["AES-256-CPU", "aes256", "AES256"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        
        key = self._decode_bytes(params['key'])
        iv = self._decode_bytes(params['iv'])
        mode_name = params.get('mode', 'CBC')
        
        if mode_name == 'GCM':
            tag = params.get('tag')
            if not tag:
                raise DecryptionError("GCM模式需要认证标签", "DEC002")
            tag = self._decode_bytes(tag)
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        else:
            # 确保IV长度正确
            if len(iv) != 16:
                iv = iv[:16] if len(iv) > 16 else iv + b'\x00' * (16 - len(iv))
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(data) + decryptor.finalize()
            try:
                unpadder = padding.PKCS7(128).unpadder()
                return unpadder.update(decrypted) + unpadder.finalize()
            except:
                return decrypted


class ChaCha20Handler(AlgorithmHandler):
    """ChaCha20算法处理器"""
    
    @property
    def name(self) -> str:
        return "ChaCha20"
    
    @property
    def aliases(self) -> list:
        return ["ChaCha20-CPU", "chacha20"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        
        key = self._decode_bytes(params['key'])
        nonce = self._decode_bytes(params['nonce'])
        
        # 确保nonce长度正确（16字节）
        if len(nonce) != 16:
            nonce = nonce[:16] if len(nonce) > 16 else nonce + b'\x00' * (16 - len(nonce))
        
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()


class Salsa20Handler(AlgorithmHandler):
    """Salsa20算法处理器"""
    
    @property
    def name(self) -> str:
        return "Salsa20"
    
    @property
    def aliases(self) -> list:
        return ["Salsa20-CPU", "Salsa20_PyNaCl", "Salsa20_Simple", "salsa20"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        algorithm = params.get('algorithm', 'Salsa20')
        
        if algorithm == 'Salsa20_PyNaCl':
            try:
                from nacl.secret import SecretBox
                key = self._decode_bytes(params['key'])
                box = SecretBox(key)
                return box.decrypt(data)
            except ImportError:
                pass
        
        # 简化实现
        key = self._decode_bytes(params['key'])
        nonce = self._decode_bytes(params['nonce'])
        
        keystream = bytearray()
        counter = 0
        
        while len(keystream) < len(data):
            block_input = key + nonce + counter.to_bytes(8, 'little')
            block_hash = hashlib.sha256(block_input).digest()
            keystream.extend(block_hash)
            counter += 1
        
        return bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))


class BlowfishHandler(AlgorithmHandler):
    """Blowfish算法处理器"""
    
    @property
    def name(self) -> str:
        return "Blowfish"
    
    @property
    def aliases(self) -> list:
        return ["Blowfish-CPU", "blowfish"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding
        
        key = self._decode_bytes(params['key'])
        iv = params.get('iv')
        if iv:
            iv = self._decode_bytes(iv)
        
        if iv:
            cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        else:
            cipher = Cipher(algorithms.Blowfish(key), modes.ECB())
        
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data) + decryptor.finalize()
        
        try:
            unpadder = padding.PKCS7(64).unpadder()
            return unpadder.update(decrypted) + unpadder.finalize()
        except:
            return decrypted


class SimpleXORHandler(AlgorithmHandler):
    """简单XOR算法处理器"""
    
    @property
    def name(self) -> str:
        return "Simple_XOR"
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        key = self._decode_bytes(params['key'])
        if len(key) >= len(data):
            return bytes(a ^ b for a, b in zip(data, key))
        else:
            return bytes(a ^ key[i % len(key)] for i, a in enumerate(data))


class BitShuffleHandler(AlgorithmHandler):
    """位混洗算法处理器"""
    
    @property
    def name(self) -> str:
        return "Bit_Shuffle"
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        bit_positions = params['bit_positions']
        
        reverse_positions = [0] * 8
        for i, pos in enumerate(bit_positions):
            reverse_positions[pos] = i
        
        decrypted = bytearray()
        for byte in data:
            new_byte = 0
            for i, pos in enumerate(reverse_positions):
                if byte & (1 << i):
                    new_byte |= (1 << pos)
            decrypted.append(new_byte)
        
        return bytes(decrypted)


class RotateCipherHandler(AlgorithmHandler):
    """旋转密码算法处理器"""
    
    @property
    def name(self) -> str:
        return "Rotate_Cipher"
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        rotation = params['rotation']
        return bytes((byte - rotation) % 256 for byte in data)


class RSAHandler(AlgorithmHandler):
    """RSA算法处理器"""
    
    @property
    def name(self) -> str:
        return "RSA"
    
    @property
    def aliases(self) -> list:
        return ["RSA-Hybrid", "rsa"]
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            raise DecryptionError(f"无法解码参数: {type(value)}", "DEC004")
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        # RSA混合加密：先用RSA解密AES密钥，再用AES解密数据
        aes_metadata = params.get('aes_metadata', {})
        if aes_metadata and 'key' in aes_metadata:
            handler = AES256Handler()
            return handler.decrypt(data, aes_metadata)
        return data


class PreScrambleHandler(AlgorithmHandler):
    """预处理混淆算法处理器"""
    
    @property
    def name(self) -> str:
        return "Pre_Scramble"
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        # 兼容两种字段名：operations 和 scramble_operations
        scramble_operations = params.get('operations', params.get('scramble_operations', []))
        
        if not scramble_operations:
            # 如果没有操作记录，使用简化的逆向方法
            scramble_rounds = params.get('scramble_rounds', 3)
            result = bytearray(data)
            for _ in range(scramble_rounds):
                for i in range(len(result) // 2):
                    j = len(result) - 1 - i
                    result[i], result[j] = result[j], result[i]
            return bytes(result)
        
        # 逆序执行混淆操作
        descrambled_data = bytearray(data)
        
        for operation in reversed(scramble_operations):
            op_type = operation[0]
            
            if op_type == 'swap':
                pos1, pos2 = operation[1], operation[2]
                if pos1 < len(descrambled_data) and pos2 < len(descrambled_data):
                    descrambled_data[pos1], descrambled_data[pos2] = descrambled_data[pos2], descrambled_data[pos1]
            
            elif op_type == 'reverse':
                start, end = operation[1], operation[2]
                if start < len(descrambled_data) and end <= len(descrambled_data):
                    descrambled_data[start:end] = descrambled_data[start:end][::-1]
            
            elif op_type == 'rotate':
                shift = operation[1]
                if len(descrambled_data) > 1:
                    # 逆向旋转
                    descrambled_data = descrambled_data[-shift:] + descrambled_data[:-shift]
            
            elif op_type == 'xor':
                xor_key = operation[1]
                for i in range(len(descrambled_data)):
                    descrambled_data[i] ^= xor_key
        
        return bytes(descrambled_data)


class FinalObfuscationHandler(AlgorithmHandler):
    """最终混淆算法处理器"""
    
    @property
    def name(self) -> str:
        return "Final_Obfuscation"
    
    def _decode_bytes(self, value) -> bytes:
        """将base64字符串或bytes转换为bytes"""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return base64.b64decode(value)
        else:
            return b''
    
    def decrypt(self, data: bytes, params: Dict[str, Any]) -> bytes:
        # 兼容两种字段名：applied_operations 和 obfuscation_operations
        obfuscation_operations = params.get('applied_operations', params.get('obfuscation_operations', []))
        obfuscation_key = params.get('obfuscation_key', b'')
        
        # 解码obfuscation_key
        if isinstance(obfuscation_key, str):
            obfuscation_key = self._decode_bytes(obfuscation_key)
        
        if not obfuscation_operations:
            # 如果没有操作记录，使用简化的逆向方法
            obfuscation_level = params.get('obfuscation_level', 'medium')
            if obfuscation_level == 'maximum':
                return bytes(b ^ 0xAA for b in data)
            elif obfuscation_level == 'high':
                return bytes(b ^ 0x55 for b in data)
            else:
                return data
        
        # 计算密钥哈希
        key_hash = hashlib.sha256(obfuscation_key).digest() if obfuscation_key else b'\x00' * 32
        
        # 逆序执行混淆操作
        deobfuscated_data = bytearray(data)
        
        for op_idx, operation in enumerate(reversed(obfuscation_operations)):
            op_type = operation[0]
            original_idx = len(obfuscation_operations) - 1 - op_idx
            
            if op_type == 'frequency_analysis_resistance':
                # 逆向频率分析抗性 - 移除虚假数据
                # 加密时是按 reversed(sorted_positions) 顺序插入的（先插入大位置，再插入小位置）
                # 解密时按升序移除：移除小位置后，大位置的数据自动向前移动到正确位置
                dummy_positions = operation[1]
                for pos in sorted(dummy_positions):
                    if pos < len(deobfuscated_data):
                        deobfuscated_data.pop(pos)
            
            elif op_type == 'byte_substitution':
                substitution_table = operation[1]
                inverse_table = [0] * 256
                for i, val in enumerate(substitution_table):
                    inverse_table[val] = i
                for j in range(len(deobfuscated_data)):
                    deobfuscated_data[j] = inverse_table[deobfuscated_data[j]]
            
            elif op_type == 'bit_permutation':
                i = operation[1]
                for j in range(len(deobfuscated_data)):
                    byte_val = deobfuscated_data[j]
                    new_byte = 0
                    for bit_pos in range(8):
                        new_pos = (bit_pos * 3 + i) % 8
                        if byte_val & (1 << new_pos):
                            new_byte |= (1 << bit_pos)
                    deobfuscated_data[j] = new_byte
            
            elif op_type == 'block_cipher':
                round_key = operation[1]
                block_size = 16
                for j in range(0, len(deobfuscated_data), block_size):
                    block_end = min(j + block_size, len(deobfuscated_data))
                    for k in range(j, block_end):
                        deobfuscated_data[k] = ((deobfuscated_data[k] >> 1) | (deobfuscated_data[k] << 7)) & 0xFF
                        deobfuscated_data[k] ^= round_key
            
            elif op_type == 'entropy_increase':
                for j in range(len(deobfuscated_data)):
                    entropy_factor = key_hash[j % len(key_hash)]
                    deobfuscated_data[j] = (deobfuscated_data[j] - entropy_factor) % 256
                    deobfuscated_data[j] ^= entropy_factor
        
        return bytes(deobfuscated_data)


# ============ 算法注册表 ============

class AlgorithmRegistry:
    """算法注册表"""
    
    _handlers: Dict[str, AlgorithmHandler] = {}
    _initialized: bool = False
    
    def __init__(self):
        if not AlgorithmRegistry._initialized:
            self._register_default_algorithms()
            AlgorithmRegistry._initialized = True
    
    def _register_default_algorithms(self):
        handlers = [
            AES256Handler(),
            ChaCha20Handler(),
            Salsa20Handler(),
            BlowfishHandler(),
            SimpleXORHandler(),
            BitShuffleHandler(),
            RotateCipherHandler(),
            RSAHandler(),
            PreScrambleHandler(),
            FinalObfuscationHandler(),
        ]
        for handler in handlers:
            self._handlers[handler.name] = handler
            for alias in handler.aliases:
                self._handlers[alias] = handler
    
    def get_handler(self, name: str) -> AlgorithmHandler:
        # 标准化算法名称
        normalized = name.replace('-', '_').replace(' ', '_')
        
        if name in self._handlers:
            return self._handlers[name]
        if normalized in self._handlers:
            return self._handlers[normalized]
        
        # 尝试模糊匹配
        name_lower = name.lower()
        for key, handler in self._handlers.items():
            if key.lower() == name_lower:
                return handler
        
        raise AlgorithmNotSupportedError(name)


# ============ CPU解密器核心 ============

class CPUDecryptor:
    """纯CPU解密器 v2.0"""
    
    def __init__(self):
        self.registry = AlgorithmRegistry()
        self.log_callback = None
    
    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)
    
    def decrypt_file(self, encrypted_file: str, output_file: str = None) -> Dict[str, Any]:
        """解密文件"""
        result = {
            'success': False,
            'output_file': None,
            'decrypted_size': 0,
            'error': None
        }
        
        try:
            self.log(f"🔓 开始解密: {os.path.basename(encrypted_file)}")
            
            # 读取加密文件
            with open(encrypted_file, 'rb') as f:
                encrypted_package = pickle.load(f)
            
            # 验证加密类型
            if not self._verify_cpu_encryption(encrypted_package):
                raise DecryptionError("此文件不是CPU引擎加密的文件", "DEC003")
            
            metadata = encrypted_package['metadata']
            encrypted_data = encrypted_package['encrypted_data']
            layers = metadata.get('layers', [])
            
            self.log(f"📋 安全级别: {metadata.get('security_level', 'unknown')}")
            self.log(f"📋 加密层数: {len(layers)}")
            self.log(f"📋 数据大小: {len(encrypted_data):,} 字节")
            
            # 逐层解密
            decrypted_data = self._decrypt_layers(encrypted_data, layers)
            
            # 截断到原始大小 - 优先从metadata，然后从包顶层
            original_size = metadata.get('original_size') or encrypted_package.get('original_size')
            if original_size:
                self.log(f"📋 原始大小: {original_size:,} 字节")
                if len(decrypted_data) > original_size:
                    self.log(f"📋 截断数据: {len(decrypted_data):,} -> {original_size:,} 字节")
                    decrypted_data = decrypted_data[:original_size]
                elif len(decrypted_data) < original_size:
                    self.log(f"⚠️ 警告: 解密数据小于原始大小: {len(decrypted_data):,} < {original_size:,}")
            
            # 确定输出路径
            if output_file is None:
                output_file = self._generate_output_path(encrypted_file)
            
            # 创建输出文件夹
            output_dir = self._create_output_folder(output_file)
            final_path = os.path.join(output_dir, os.path.basename(output_file))
            
            # 保存解密文件
            with open(final_path, 'wb') as f:
                f.write(decrypted_data)
            
            self.log(f"✅ 解密完成: {os.path.basename(final_path)}")
            self.log(f"📁 输出大小: {len(decrypted_data):,} 字节")
            
            result['success'] = True
            result['output_file'] = final_path
            result['decrypted_size'] = len(decrypted_data)
            
        except Exception as e:
            self.log(f"❌ 解密失败: {e}")
            result['error'] = str(e)
        
        return result
    
    def _verify_cpu_encryption(self, package: Dict) -> bool:
        """验证是否为CPU引擎加密"""
        metadata = package.get('metadata', {})
        
        if metadata.get('engine_type') == 'pure_cpu':
            return True
        if 'cpu_engine_info' in metadata:
            return True
        
        layers = metadata.get('layers', [])
        for layer in layers:
            if layer.get('gpu_accelerated', False):
                return False
            algorithm = layer.get('algorithm', '')
            if 'GPU' in algorithm and 'CPU' not in algorithm:
                return False
        
        return True
    
    def _decrypt_layers(self, data: bytes, layers: List[Dict]) -> bytes:
        """逐层解密"""
        decrypted = data
        
        for i, layer in enumerate(reversed(layers)):
            layer_idx = len(layers) - i
            algorithm = layer.get('algorithm', 'unknown')
            
            self.log(f"🔓 解密第 {layer_idx} 层: {algorithm}")
            
            try:
                handler = self.registry.get_handler(algorithm)
                decrypted = handler.decrypt(decrypted, layer)
                self.log(f"   ✅ 成功")
            except Exception as e:
                self.log(f"   ❌ 失败: {e}")
                raise
        
        return decrypted
    
    def _generate_output_path(self, encrypted_file: str) -> str:
        base = os.path.splitext(encrypted_file)[0]
        if base.endswith('.encrypted'):
            base = base[:-10]
        return base + '_decrypted'
    
    def _create_output_folder(self, output_path: str) -> str:
        try:
            output_dir = os.path.dirname(os.path.abspath(output_path))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(output_path))[0]
            folder_name = f"CPU解密_{base_name}_{timestamp}"
            
            decrypted_folder = os.path.join(output_dir, folder_name)
            os.makedirs(decrypted_folder, exist_ok=True)
            
            self.log(f"📁 创建解密文件夹: {folder_name}")
            return decrypted_folder
        except:
            return os.path.dirname(os.path.abspath(output_path))


# ============ GUI界面 ============

def start_gui():
    """启动GUI解密器"""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
    
    class CPUDecryptorGUI:
        def __init__(self, root):
            self.root = root
            self.root.title(f"纯CPU解密器 v{VERSION}")
            self.root.geometry("700x550")
            self.root.minsize(600, 450)
            
            self.decryptor = CPUDecryptor()
            self.decryptor.set_log_callback(self.log)
            self.last_output_dir = None
            
            self.setup_ui()
        
        def setup_ui(self):
            # 主框架
            main = ttk.Frame(self.root, padding=15)
            main.grid(row=0, column=0, sticky="nsew")
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)
            main.columnconfigure(0, weight=1)
            
            # 标题
            ttk.Label(main, text="🔓 纯CPU解密器",
                     font=("Arial", 18, "bold")).grid(row=0, column=0, pady=(0, 5))
            ttk.Label(main, text=f"v{VERSION} | 专门解密CPU混合加密引擎生成的加密文件",
                     font=("Arial", 9), foreground="gray").grid(row=1, column=0, pady=(0, 15))
            
            # 文件选择
            file_frame = ttk.LabelFrame(main, text="📁 选择加密文件", padding=10)
            file_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
            file_frame.columnconfigure(0, weight=1)
            
            path_frame = ttk.Frame(file_frame)
            path_frame.grid(row=0, column=0, sticky="ew")
            path_frame.columnconfigure(0, weight=1)
            
            self.file_var = tk.StringVar()
            ttk.Entry(path_frame, textvariable=self.file_var,
                     font=("Arial", 10)).grid(row=0, column=0, sticky="ew", padx=(0, 10))
            ttk.Button(path_frame, text="浏览...",
                      command=self.browse_file).grid(row=0, column=1)
            
            btn_frame = ttk.Frame(file_frame)
            btn_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))
            ttk.Button(btn_frame, text="🔍 自动查找",
                      command=self.auto_find).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(btn_frame, text="🗑️ 清空",
                      command=self.clear).pack(side=tk.LEFT)
            
            # 输出目录
            out_frame = ttk.LabelFrame(main, text="📂 输出目录（可选）", padding=10)
            out_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))
            out_frame.columnconfigure(0, weight=1)
            
            out_path = ttk.Frame(out_frame)
            out_path.grid(row=0, column=0, sticky="ew")
            out_path.columnconfigure(0, weight=1)
            
            self.output_var = tk.StringVar()
            ttk.Entry(out_path, textvariable=self.output_var,
                     font=("Arial", 10)).grid(row=0, column=0, sticky="ew", padx=(0, 10))
            ttk.Button(out_path, text="选择...",
                      command=self.browse_output).grid(row=0, column=1)
            
            # 操作按钮
            action_frame = ttk.Frame(main)
            action_frame.grid(row=4, column=0, pady=15)
            
            self.decrypt_btn = ttk.Button(action_frame, text="🔓 开始解密",
                                         command=self.decrypt)
            self.decrypt_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            self.open_btn = ttk.Button(action_frame, text="📂 打开输出目录",
                                      command=self.open_output, state=tk.DISABLED)
            self.open_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Button(action_frame, text="退出",
                      command=self.root.quit).pack(side=tk.LEFT)
            
            # 进度
            self.progress = ttk.Progressbar(main, mode='determinate')
            self.progress.grid(row=5, column=0, sticky="ew", pady=(0, 10))
            
            self.status_var = tk.StringVar(value="就绪")
            ttk.Label(main, textvariable=self.status_var).grid(row=6, column=0, sticky="w")
            
            # 日志
            log_frame = ttk.LabelFrame(main, text="📋 解密日志", padding=10)
            log_frame.grid(row=7, column=0, sticky="nsew", pady=(10, 0))
            log_frame.columnconfigure(0, weight=1)
            log_frame.rowconfigure(0, weight=1)
            main.rowconfigure(7, weight=1)
            
            self.log_text = ScrolledText(log_frame, height=8, font=("Consolas", 9))
            self.log_text.grid(row=0, column=0, sticky="nsew")
            
            self.log(f"🔓 纯CPU解密器 v{VERSION} 已启动")
            self.log("💡 支持拖拽文件或点击浏览按钮选择文件")
        
        def browse_file(self):
            f = filedialog.askopenfilename(
                title="选择CPU加密文件",
                filetypes=[("加密文件", "*.encrypted"), ("所有文件", "*.*")]
            )
            if f:
                self.file_var.set(f)
                self.log(f"✅ 已选择: {os.path.basename(f)}")
        
        def browse_output(self):
            d = filedialog.askdirectory(title="选择输出目录")
            if d:
                self.output_var.set(d)
        
        def auto_find(self):
            files = [f for f in os.listdir('.') if f.endswith('.encrypted')]
            if not files:
                messagebox.showinfo("提示", "当前目录未找到加密文件")
                return
            self.file_var.set(os.path.abspath(files[0]))
            self.log(f"✅ 自动选择: {files[0]}")
        
        def clear(self):
            self.file_var.set("")
            self.output_var.set("")
            self.progress['value'] = 0
        
        def decrypt(self):
            path = self.file_var.get().strip()
            if not path:
                messagebox.showerror("错误", "请选择文件")
                return
            if not os.path.exists(path):
                messagebox.showerror("错误", "文件不存在")
                return
            
            output = self.output_var.get().strip() or None
            
            self.decrypt_btn.config(state=tk.DISABLED)
            self.status_var.set("解密中...")
            self.progress['value'] = 30
            self.root.update()
            
            try:
                self.log("=" * 50)
                result = self.decryptor.decrypt_file(path, output)
                self.progress['value'] = 100
                
                if result['success']:
                    self.status_var.set("✅ 解密成功")
                    self.last_output_dir = os.path.dirname(result['output_file'])
                    self.open_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("成功",
                        f"解密成功!\n\n输出: {os.path.basename(result['output_file'])}\n"
                        f"大小: {result['decrypted_size']:,} 字节")
                else:
                    self.status_var.set("❌ 解密失败")
                    messagebox.showerror("失败", f"解密失败:\n{result['error']}")
            except Exception as e:
                self.status_var.set("❌ 错误")
                messagebox.showerror("错误", str(e))
            finally:
                self.decrypt_btn.config(state=tk.NORMAL)
        
        def open_output(self):
            if self.last_output_dir and os.path.exists(self.last_output_dir):
                if sys.platform == 'win32':
                    os.startfile(self.last_output_dir)
        
        def log(self, msg: str):
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_text.see(tk.END)
            self.root.update()
    
    root = tk.Tk()
    app = CPUDecryptorGUI(root)
    root.mainloop()


def main():
    """主函数"""
    if len(sys.argv) > 1 and '--cli' in sys.argv:
        # 命令行模式
        import argparse
        parser = argparse.ArgumentParser(description=f"纯CPU解密器 v{VERSION}")
        parser.add_argument("encrypted_file", help="加密文件路径")
        parser.add_argument("-o", "--output", help="输出文件路径")
        parser.add_argument("--cli", action="store_true")
        
        args = parser.parse_args()
        
        print(f"纯CPU解密器 v{VERSION}")
        print("=" * 40)
        
        decryptor = CPUDecryptor()
        result = decryptor.decrypt_file(args.encrypted_file, args.output)
        sys.exit(0 if result['success'] else 1)
    else:
        # GUI模式
        try:
            start_gui()
        except ImportError:
            print(f"纯CPU解密器 v{VERSION}")
            print("=" * 40)
            print("GUI不可用，使用自动模式...")
            
            decryptor = CPUDecryptor()
            for f in os.listdir('.'):
                if f.endswith('.encrypted'):
                    print(f"找到: {f}")
                    decryptor.decrypt_file(f)
            
            input("按回车键退出...")


if __name__ == "__main__":
    main()
