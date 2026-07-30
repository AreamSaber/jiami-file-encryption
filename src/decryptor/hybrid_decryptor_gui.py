#!/usr/bin/env python3
"""
混合加密解密器 - 带GUI文件选择功能
支持CPU和GPU混合加密文件的解密，提供友好的图形界面
"""

import os
import sys
import pickle
import hashlib
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

# 尝试导入GUI库
GUI_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
    GUI_AVAILABLE = True
except ImportError:
    pass


class HybridDecryptor:
    """混合加密解密器核心类"""

    def __init__(self):
        """初始化解密器"""
        self.supported_algorithms = [
            'aes256', 'aes-256', 'aes-256-cpu', 'aes-256-gpu-only',
            'chacha20', 'chacha20-cpu', 'chacha20-gpu-only',
            'salsa20', 'salsa20-gpu-only',
            'blowfish', 'blowfish-gpu-only',
            'matrix_cipher', 'matrix_cipher-gpu-only',
            'rsa', 'rsa-hybrid',
            'steganography', 'simple_xor', 'bit_shuffle',
            'rotate_cipher', 'pre_scramble', 'final_obfuscation'
        ]
        self.log_callback = None

    def set_log_callback(self, callback):
        """设置日志回调函数"""
        self.log_callback = callback

    def log(self, message: str):
        """输出日志"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def decrypt_file(self, encrypted_file: str, output_dir: str = None) -> Dict[str, Any]:
        """
        解密文件

        Args:
            encrypted_file: 加密文件路径
            output_dir: 输出目录

        Returns:
            解密结果字典
        """
        result = {
            'success': False,
            'output_file': None,
            'original_size': 0,
            'decrypted_size': 0,
            'engine_type': 'unknown',
            'error': None
        }

        try:
            self.log(f"🔓 开始解密: {os.path.basename(encrypted_file)}")

            # 读取加密文件
            with open(encrypted_file, 'rb') as f:
                encrypted_package = pickle.load(f)

            # 检测加密类型
            engine_type = self._detect_engine_type(encrypted_package)
            result['engine_type'] = engine_type
            self.log(f"📋 检测到加密类型: {engine_type}")

            # 提取元数据和加密数据
            metadata = encrypted_package.get('metadata', {})
            encrypted_data = encrypted_package.get('encrypted_data', b'')

            # 获取层信息
            layers = metadata.get('layers', [])
            if not layers:
                # 尝试从其他位置获取层信息
                layers = encrypted_package.get('layers', [])

            self.log(f"📋 加密层数: {len(layers)}")
            self.log(f"📋 加密数据大小: {len(encrypted_data):,} 字节")

            # 逐层解密
            decrypted_data = self._decrypt_layers(encrypted_data, layers)
            result['decrypted_size'] = len(decrypted_data)

            # 确定输出路径
            if output_dir is None:
                output_dir = os.path.dirname(encrypted_file)

            # 生成输出文件名
            output_file = self._generate_output_path(encrypted_file, output_dir, engine_type)
            result['output_file'] = output_file

            # 保存解密文件
            with open(output_file, 'wb') as f:
                f.write(decrypted_data)

            self.log(f"✅ 解密完成: {os.path.basename(output_file)}")
            self.log(f"📁 输出大小: {len(decrypted_data):,} 字节")

            result['success'] = True
            return result

        except Exception as e:
            error_msg = str(e)
            self.log(f"❌ 解密失败: {error_msg}")
            result['error'] = error_msg
            return result

    def _detect_engine_type(self, package: Dict) -> str:
        """检测加密引擎类型"""
        metadata = package.get('metadata', {})

        # 检查engine_type字段
        engine_type = metadata.get('engine_type', '')
        if engine_type:
            return engine_type

        # 检查type字段
        enc_type = metadata.get('type', '')
        if enc_type:
            return enc_type

        # 检查是否有GPU标记
        if metadata.get('gpu_only', False):
            return 'pure_gpu'

        # 检查cpu_engine_info
        if 'cpu_engine_info' in package or 'cpu_engine_info' in metadata:
            return 'pure_cpu'

        # 检查层信息
        layers = metadata.get('layers', [])
        for layer in layers:
            if layer.get('gpu_accelerated', False) or 'GPU' in layer.get('algorithm', ''):
                return 'hybrid_gpu'

        return 'hybrid_cpu'

    def _decrypt_layers(self, data: bytes, layers: List[Dict]) -> bytes:
        """逐层解密数据"""
        decrypted_data = data

        # 反向解密（从最后一层开始）
        for i, layer in enumerate(reversed(layers)):
            layer_index = len(layers) - 1 - i
            algorithm = layer.get('algorithm', 'unknown')

            self.log(f"🔓 解密第 {layer_index + 1} 层: {algorithm}")

            try:
                decrypted_data = self._decrypt_single_layer(decrypted_data, layer)
                self.log(f"   ✅ 成功: {len(decrypted_data):,} 字节")
            except Exception as e:
                self.log(f"   ❌ 失败: {e}")
                raise

        return decrypted_data

    def _decrypt_single_layer(self, data: bytes, layer: Dict) -> bytes:
        """解密单层数据"""
        algorithm = layer.get('algorithm', '').lower().replace('-', '_').replace(' ', '_')

        # AES-256
        if 'aes' in algorithm:
            return self._decrypt_aes256(data, layer)
        # ChaCha20
        elif 'chacha20' in algorithm:
            return self._decrypt_chacha20(data, layer)
        # Salsa20
        elif 'salsa20' in algorithm:
            return self._decrypt_salsa20(data, layer)
        # Blowfish
        elif 'blowfish' in algorithm:
            return self._decrypt_blowfish(data, layer)
        # Matrix Cipher
        elif 'matrix' in algorithm:
            return self._decrypt_matrix_cipher(data, layer)
        # RSA
        elif 'rsa' in algorithm:
            return self._decrypt_rsa(data, layer)
        # 其他算法
        else:
            self.log(f"   ⚠️ 未知算法: {algorithm}，尝试通用解密")
            return self._decrypt_generic(data, layer)

    def _decrypt_aes256(self, data: bytes, layer: Dict) -> bytes:
        """解密AES-256"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        key = layer.get('key')
        iv = layer.get('iv')
        mode_name = layer.get('mode', 'CBC')
        tag = layer.get('tag')

        if not key:
            raise ValueError("缺少AES密钥")

        if mode_name == 'GCM' and tag:
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        else:
            # CBC模式
            if len(iv) != 16:
                iv = iv[:16] if len(iv) > 16 else iv + b'\x00' * (16 - len(iv))
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(data) + decryptor.finalize()
            # 移除PKCS7填充
            unpadder = padding.PKCS7(128).unpadder()
            return unpadder.update(padded_data) + unpadder.finalize()

    def _decrypt_chacha20(self, data: bytes, layer: Dict) -> bytes:
        """解密ChaCha20"""
        key = layer.get('key')
        nonce = layer.get('nonce')

        if not key or not nonce:
            raise ValueError("缺少ChaCha20密钥或nonce")

        # 检查是否是GPU自定义实现
        backend_info = layer.get('backend_info', '')
        if 'GPU' in backend_info or layer.get('gpu_only', False):
            return self._decrypt_chacha20_gpu_custom(data, key, nonce)

        # 标准ChaCha20解密
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    def _decrypt_chacha20_gpu_custom(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """解密GPU自定义ChaCha20 - 纯Python实现，不依赖numpy"""
        result = bytearray(len(data))

        for gid in range(len(data)):
            byte_val = data[gid]
            key_byte = key[gid % 32]
            nonce_byte = nonce[gid % 16]

            # 重新生成密钥流字节
            keystream = key_byte ^ nonce_byte
            keystream ^= (gid & 0xFF)
            keystream = ((keystream << 3) | (keystream >> 5)) & 0xFF
            keystream ^= ((gid >> 8) & 0xFF)

            # ChaCha20风格的四分之一轮
            for _ in range(20):
                keystream = (keystream + key_byte) & 0xFF
                keystream ^= ((keystream << 1) & 0xFF)
                keystream = (keystream + nonce_byte) & 0xFF
                keystream ^= ((keystream >> 1) & 0xFF)

            result[gid] = byte_val ^ keystream

        return bytes(result)

    def _decrypt_salsa20(self, data: bytes, layer: Dict) -> bytes:
        """解密Salsa20"""
        key = layer.get('key')
        nonce = layer.get('nonce')

        if not key or not nonce:
            raise ValueError("缺少Salsa20密钥或nonce")

        # 检查是否是GPU自定义实现
        backend_info = layer.get('backend_info', '')
        if 'GPU' in backend_info or layer.get('gpu_only', False):
            return self._decrypt_salsa20_gpu(data, key, nonce)

        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            algorithm = algorithms.Salsa20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        except Exception:
            # 使用GPU实现作为回退
            return self._decrypt_salsa20_gpu(data, key, nonce)

    def _decrypt_salsa20_gpu(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """GPU Salsa20解密 - 与OpenCL内核完全匹配"""
        # 确保nonce长度正确
        if len(nonce) < 8:
            nonce = nonce + b'\x00' * (8 - len(nonce))
        
        result = bytearray(len(data))
        
        for gid in range(len(data)):
            byte_val = data[gid]
            key_byte = key[gid % 32]
            nonce_byte = nonce[gid % 8]
            
            keystream = key_byte ^ nonce_byte
            keystream ^= (gid & 0xFF)
            
            for i in range(10):
                keystream = (keystream + key_byte) & 0xFF
                keystream ^= ((keystream << 1) & 0xFF)
                keystream = (keystream + nonce_byte) & 0xFF
                keystream ^= ((keystream >> 1) & 0xFF)
                keystream = (keystream + ((gid >> (i % 8)) & 0xFF)) & 0xFF
                keystream = ((keystream << 2) | (keystream >> 6)) & 0xFF
            
            keystream ^= key[(gid + 16) % 32]
            keystream = (keystream + nonce[(gid + 4) % 8]) & 0xFF
            keystream ^= ((keystream << 3) | (keystream >> 5)) & 0xFF
            
            result[gid] = byte_val ^ keystream
        
        return bytes(result)

    def _decrypt_blowfish(self, data: bytes, layer: Dict) -> bytes:
        """解密Blowfish"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        key = layer.get('key')
        iv = layer.get('iv')
        mode_name = layer.get('mode', 'CBC')

        if not key:
            raise ValueError("缺少Blowfish密钥")

        if mode_name == 'CBC' and iv:
            cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        else:
            cipher = Cipher(algorithms.Blowfish(key), modes.ECB())

        decryptor = cipher.decryptor()
        padded_data = decryptor.update(data) + decryptor.finalize()

        # 移除PKCS7填充
        unpadder = padding.PKCS7(64).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()

    def _decrypt_matrix_cipher(self, data: bytes, layer: Dict) -> bytes:
        """解密矩阵变换"""
        matrix_size = layer.get('matrix_size', 8)
        seed = layer.get('seed', 12345)
        original_length = layer.get('original_length', len(data))
        # 如果加密时保存了变换矩阵，直接使用
        transform_matrix = layer.get('transform_matrix', None)

        # 尝试使用numpy，如果不可用则使用纯Python实现
        try:
            import numpy as np
            return self._decrypt_matrix_with_numpy(data, matrix_size, seed, original_length, transform_matrix)
        except ImportError:
            return self._decrypt_matrix_pure_python(data, matrix_size, seed, original_length, transform_matrix)

    def _decrypt_matrix_with_numpy(self, data: bytes, matrix_size: int, seed: int, original_length: int, saved_matrix=None) -> bytes:
        """使用numpy的矩阵解密实现 - 匹配GPU OpenCL加密（XOR变换）"""
        import numpy as np

        # 获取变换矩阵
        if saved_matrix is not None:
            transform_matrix = np.array(saved_matrix, dtype=np.uint8).flatten()
        else:
            np.random.seed(seed)
            transform_matrix = np.random.randint(0, 256, (matrix_size, matrix_size), dtype=np.uint8).flatten()
        
        block_size = matrix_size * matrix_size

        data_arr = np.frombuffer(data, dtype=np.uint8)
        padded_len = ((len(data_arr) + block_size - 1) // block_size) * block_size
        padded = np.zeros(padded_len, dtype=np.uint8)
        padded[:len(data_arr)] = data_arr

        result = np.zeros_like(padded)

        # 逐字节解密（逆序执行加密操作）
        for gid in range(len(padded)):
            local_id = gid % block_size
            row = local_id // matrix_size
            col = local_id % matrix_size
            
            byte_val = padded[gid]
            matrix_idx = (row * matrix_size + col) % block_size
            
            # 逆操作4: XOR matrix[(gid + row) % block_size]
            byte_val ^= transform_matrix[(gid + row) % block_size]
            
            # 逆操作3: 逆旋转
            byte_val = ((byte_val >> 3) | (byte_val << 5)) & 0xFF
            
            # 逆操作2: XOR (gid & 0xFF)
            byte_val ^= (gid & 0xFF)
            
            # 逆操作1: XOR matrix_val
            byte_val ^= transform_matrix[matrix_idx]
            
            result[gid] = byte_val

        return result[:original_length].tobytes()

    def _decrypt_matrix_pure_python(self, data: bytes, matrix_size: int, seed: int, original_length: int, saved_matrix=None) -> bytes:
        """纯Python的矩阵解密实现 - 匹配GPU OpenCL加密（XOR变换）"""
        import random

        # 获取变换矩阵
        if saved_matrix is not None:
            if isinstance(saved_matrix, list):
                transform_list = []
                for row in saved_matrix:
                    transform_list.extend(row)
            else:
                transform_list = list(saved_matrix.flatten())
        else:
            try:
                import numpy as np
                np.random.seed(seed)
                transform_matrix = np.random.randint(0, 256, (matrix_size, matrix_size), dtype=np.uint8)
                transform_list = list(transform_matrix.flatten())
            except ImportError:
                random.seed(seed)
                transform_list = [random.randint(0, 255) for _ in range(matrix_size * matrix_size)]
        
        block_size = matrix_size * matrix_size

        data_list = list(data)
        padded_len = ((len(data_list) + block_size - 1) // block_size) * block_size
        padded = data_list + [0] * (padded_len - len(data_list))

        result = []

        # 逐字节解密
        for gid in range(len(padded)):
            local_id = gid % block_size
            row = local_id // matrix_size
            col = local_id % matrix_size
            
            byte_val = padded[gid]
            matrix_idx = (row * matrix_size + col) % block_size
            
            # 逆操作4
            byte_val ^= transform_list[(gid + row) % block_size]
            
            # 逆操作3: 逆旋转
            byte_val = ((byte_val >> 3) | (byte_val << 5)) & 0xFF
            
            # 逆操作2
            byte_val ^= (gid & 0xFF)
            
            # 逆操作1
            byte_val ^= transform_list[matrix_idx]
            
            result.append(byte_val)

        return bytes(result[:original_length])

    def _decrypt_rsa(self, data: bytes, layer: Dict) -> bytes:
        """解密RSA"""
        # RSA混合加密解密
        aes_metadata = layer.get('aes_metadata', {})
        encrypted_aes_key = layer.get('encrypted_aes_key')
        private_key = layer.get('private_key')

        if aes_metadata and 'key' in aes_metadata:
            # 直接使用存储的AES密钥解密
            return self._decrypt_aes256(data, aes_metadata)

        # 如果有私钥，先解密AES密钥
        if private_key and encrypted_aes_key:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            aes_key = private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            aes_metadata['key'] = aes_key
            return self._decrypt_aes256(data, aes_metadata)

        raise ValueError("RSA解密缺少必要的密钥信息")

    def _decrypt_generic(self, data: bytes, layer: Dict) -> bytes:
        """通用解密（尝试常见方法）"""
        # 尝试XOR解密
        if 'key' in layer:
            key = layer['key']
            if isinstance(key, bytes):
                return bytes(a ^ b for a, b in zip(data, (key * (len(data) // len(key) + 1))[:len(data)]))

        # 无法解密，返回原数据
        return data

    def _generate_output_path(self, encrypted_file: str, output_dir: str, engine_type: str) -> str:
        """生成输出文件路径"""
        base_name = os.path.basename(encrypted_file)

        # 移除.encrypted后缀
        if base_name.endswith('.encrypted'):
            base_name = base_name[:-10]

        # 移除引擎类型后缀
        for suffix in ['_cpu_level', '_gpu_level', '_hybrid_level']:
            if suffix in base_name:
                parts = base_name.split(suffix)
                base_name = parts[0]
                break

        # 添加解密标记
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{base_name}_decrypted_{timestamp}"

        return os.path.join(output_dir, output_name)


class HybridDecryptorGUI:
    """混合加密解密器GUI"""

    def __init__(self, root=None):
        """初始化GUI"""
        if root is None:
            self.root = tk.Tk()
            self.is_standalone = True
        else:
            self.root = root
            self.is_standalone = False

        self.root.title("混合加密解密器 v2.0")
        self.root.geometry("700x550")
        self.root.resizable(True, True)

        # 设置最小尺寸
        self.root.minsize(600, 450)

        self.decryptor = HybridDecryptor()
        self.decryptor.set_log_callback(self.log)

        self.setup_ui()
        self.setup_styles()

    def setup_styles(self):
        """设置样式"""
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Arial", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("Arial", 10), foreground="gray")
        style.configure("Success.TLabel", foreground="green")
        style.configure("Error.TLabel", foreground="red")
        style.configure("Big.TButton", font=("Arial", 11, "bold"), padding=10)

    def setup_ui(self):
        """设置用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # 标题区域
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        title_label = ttk.Label(title_frame, text="🔓 混合加密解密器",
                               style="Title.TLabel")
        title_label.pack()

        subtitle_label = ttk.Label(title_frame,
                                  text="支持CPU和GPU混合加密文件的解密",
                                  style="Subtitle.TLabel")
        subtitle_label.pack()

        # 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="📁 选择加密文件", padding="10")
        file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)

        # 文件路径输入
        path_frame = ttk.Frame(file_frame)
        path_frame.grid(row=0, column=0, sticky="ew")
        path_frame.columnconfigure(0, weight=1)

        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(path_frame, textvariable=self.file_path_var,
                                   font=("Arial", 10))
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        browse_btn = ttk.Button(path_frame, text="浏览文件...",
                               command=self.browse_file)
        browse_btn.grid(row=0, column=1)

        # 快捷按钮
        quick_frame = ttk.Frame(file_frame)
        quick_frame.grid(row=1, column=0, sticky="w", pady=(10, 0))

        auto_find_btn = ttk.Button(quick_frame, text="🔍 自动查找",
                                  command=self.auto_find_files)
        auto_find_btn.pack(side=tk.LEFT, padx=(0, 10))

        clear_btn = ttk.Button(quick_frame, text="🗑️ 清空",
                              command=self.clear_selection)
        clear_btn.pack(side=tk.LEFT)

        # 输出目录选择
        output_frame = ttk.LabelFrame(main_frame, text="📂 输出目录（可选）", padding="10")
        output_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)

        output_path_frame = ttk.Frame(output_frame)
        output_path_frame.grid(row=0, column=0, sticky="ew")
        output_path_frame.columnconfigure(0, weight=1)

        self.output_path_var = tk.StringVar()
        self.output_entry = ttk.Entry(output_path_frame, textvariable=self.output_path_var,
                                     font=("Arial", 10))
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        output_browse_btn = ttk.Button(output_path_frame, text="选择目录...",
                                      command=self.browse_output_dir)
        output_browse_btn.grid(row=0, column=1)

        # 操作按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, pady=15)

        self.decrypt_btn = ttk.Button(button_frame, text="🔓 开始解密",
                                     command=self.start_decrypt,
                                     style="Big.TButton")
        self.decrypt_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.open_folder_btn = ttk.Button(button_frame, text="📂 打开输出目录",
                                         command=self.open_output_folder,
                                         state=tk.DISABLED)
        self.open_folder_btn.pack(side=tk.LEFT)

        # 状态显示
        self.status_var = tk.StringVar(value="就绪 - 请选择要解密的文件")
        status_label = ttk.Label(main_frame, textvariable=self.status_var,
                                font=("Arial", 10))
        status_label.grid(row=4, column=0, sticky="w", pady=(0, 10))

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var,
                                           maximum=100, mode='determinate')
        self.progress_bar.grid(row=5, column=0, sticky="ew", pady=(0, 10))

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="📋 解密日志", padding="10")
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)

        self.log_text = ScrolledText(log_frame, height=10, font=("Consolas", 9),
                                    wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # 底部信息
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=7, column=0, sticky="ew")

        info_label = ttk.Label(info_frame,
                              text="支持格式: .encrypted | 支持引擎: CPU/GPU混合加密",
                              font=("Arial", 8), foreground="gray")
        info_label.pack(side=tk.LEFT)

        # 初始化日志
        self.log("🔓 混合加密解密器已启动")
        self.log("📋 支持CPU和GPU混合加密文件")
        self.log("💡 点击\"浏览文件\"或\"自动查找\"选择加密文件")

        # 保存最后输出目录
        self.last_output_dir = None

    def browse_file(self):
        """浏览选择加密文件"""
        initial_dir = os.getcwd()

        # 如果已有文件路径，使用其目录
        current_path = self.file_path_var.get()
        if current_path and os.path.exists(os.path.dirname(current_path)):
            initial_dir = os.path.dirname(current_path)

        filename = filedialog.askopenfilename(
            title="选择加密文件",
            initialdir=initial_dir,
            filetypes=[
                ("加密文件", "*.encrypted"),
                ("所有文件", "*.*")
            ]
        )

        if filename:
            self.file_path_var.set(filename)
            self.log(f"✅ 已选择: {os.path.basename(filename)}")
            self.status_var.set(f"已选择: {os.path.basename(filename)}")

    def browse_output_dir(self):
        """浏览选择输出目录"""
        initial_dir = os.getcwd()

        # 如果已有输入文件，使用其目录
        input_path = self.file_path_var.get()
        if input_path and os.path.exists(os.path.dirname(input_path)):
            initial_dir = os.path.dirname(input_path)

        dirname = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=initial_dir
        )

        if dirname:
            self.output_path_var.set(dirname)
            self.log(f"📂 输出目录: {dirname}")

    def auto_find_files(self):
        """自动查找当前目录的加密文件"""
        current_dir = os.getcwd()
        encrypted_files = []

        # 搜索当前目录
        for f in os.listdir(current_dir):
            if f.endswith('.encrypted'):
                encrypted_files.append(os.path.join(current_dir, f))

        if not encrypted_files:
            self.log("⚠️ 当前目录未找到加密文件")
            messagebox.showinfo("提示", "当前目录未找到.encrypted文件\n请手动选择文件")
            return

        if len(encrypted_files) == 1:
            # 只有一个文件，直接选择
            self.file_path_var.set(encrypted_files[0])
            self.log(f"✅ 自动选择: {os.path.basename(encrypted_files[0])}")
            self.status_var.set(f"已选择: {os.path.basename(encrypted_files[0])}")
        else:
            # 多个文件，显示选择对话框
            self.log(f"📋 找到 {len(encrypted_files)} 个加密文件")
            self._show_file_selection_dialog(encrypted_files)

    def _show_file_selection_dialog(self, files: List[str]):
        """显示文件选择对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("选择加密文件")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="找到多个加密文件，请选择:",
                 font=("Arial", 11)).pack(pady=10)

        # 文件列表
        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(listbox_frame, font=("Arial", 10),
                            yscrollcommand=scrollbar.set)
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for f in files:
            listbox.insert(tk.END, os.path.basename(f))

        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_file = files[selection[0]]
                self.file_path_var.set(selected_file)
                self.log(f"✅ 已选择: {os.path.basename(selected_file)}")
                self.status_var.set(f"已选择: {os.path.basename(selected_file)}")
                dialog.destroy()

        ttk.Button(dialog, text="选择", command=on_select).pack(pady=10)

    def clear_selection(self):
        """清空选择"""
        self.file_path_var.set("")
        self.output_path_var.set("")
        self.progress_var.set(0)
        self.status_var.set("就绪 - 请选择要解密的文件")
        self.log("🗑️ 已清空选择")

    def start_decrypt(self):
        """开始解密"""
        file_path = self.file_path_var.get().strip()

        if not file_path:
            messagebox.showerror("错误", "请先选择要解密的文件")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在:\n{file_path}")
            return

        output_dir = self.output_path_var.get().strip() or None

        # 禁用按钮
        self.decrypt_btn.config(state=tk.DISABLED)
        self.status_var.set("正在解密...")
        self.progress_var.set(10)
        self.root.update()

        try:
            self.log("=" * 50)
            self.progress_var.set(30)
            self.root.update()

            result = self.decryptor.decrypt_file(file_path, output_dir)

            self.progress_var.set(90)
            self.root.update()

            if result['success']:
                self.progress_var.set(100)
                self.status_var.set("✅ 解密成功!")
                self.last_output_dir = os.path.dirname(result['output_file'])
                self.open_folder_btn.config(state=tk.NORMAL)

                messagebox.showinfo("成功",
                    f"解密成功!\n\n"
                    f"输出文件: {os.path.basename(result['output_file'])}\n"
                    f"文件大小: {result['decrypted_size']:,} 字节\n"
                    f"引擎类型: {result['engine_type']}")
            else:
                self.progress_var.set(0)
                self.status_var.set("❌ 解密失败")
                messagebox.showerror("失败", f"解密失败:\n{result['error']}")

        except Exception as e:
            self.progress_var.set(0)
            self.status_var.set("❌ 解密出错")
            self.log(f"❌ 错误: {e}")
            messagebox.showerror("错误", f"解密过程出错:\n{e}")

        finally:
            self.decrypt_btn.config(state=tk.NORMAL)

    def open_output_folder(self):
        """打开输出目录"""
        if self.last_output_dir and os.path.exists(self.last_output_dir):
            if sys.platform == 'win32':
                os.startfile(self.last_output_dir)
            elif sys.platform == 'darwin':
                os.system(f'open "{self.last_output_dir}"')
            else:
                os.system(f'xdg-open "{self.last_output_dir}"')

    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def run(self):
        """运行GUI"""
        if self.is_standalone:
            self.root.mainloop()


def main():
    """主函数"""
    if GUI_AVAILABLE:
        app = HybridDecryptorGUI()
        app.run()
    else:
        print("❌ 错误: 未安装tkinter GUI库")
        print("请使用命令行模式或安装tkinter")

        # 命令行模式
        if len(sys.argv) > 1:
            decryptor = HybridDecryptor()
            result = decryptor.decrypt_file(sys.argv[1])
            if result['success']:
                print(f"✅ 解密成功: {result['output_file']}")
            else:
                print(f"❌ 解密失败: {result['error']}")
        else:
            print("\n用法: python hybrid_decryptor_gui.py <加密文件>")


if __name__ == "__main__":
    main()
