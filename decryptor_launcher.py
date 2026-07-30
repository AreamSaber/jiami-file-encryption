#!/usr/bin/env python3
"""
统一解密器启动器
自动检测加密类型并启动对应的解密器GUI
支持手动选择文件
"""

import os
import sys
import pickle
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 尝试导入GUI库
GUI_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText
    GUI_AVAILABLE = True
except ImportError:
    pass


class UniversalDecryptor:
    """通用解密器 - 支持所有加密类型"""

    def __init__(self):
        self.log_callback = None

    def set_log_callback(self, callback):
        self.log_callback = callback

    def log(self, message: str):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def detect_encryption_type(self, file_path: str) -> Dict[str, Any]:
        """检测加密文件类型"""
        try:
            with open(file_path, 'rb') as f:
                package = pickle.load(f)

            metadata = package.get('metadata', {})
            engine_type = metadata.get('engine_type', '')
            enc_type = metadata.get('type', '')

            info = {
                'engine_type': engine_type or enc_type or 'unknown',
                'security_level': metadata.get('security_level', 'unknown'),
                'layers': len(metadata.get('layers', [])),
                'gpu_only': metadata.get('gpu_only', False),
                'encrypted_size': len(package.get('encrypted_data', b'')),
                'metadata': metadata
            }

            # 判断具体类型
            if 'pure_gpu' in engine_type or info['gpu_only']:
                info['type'] = 'GPU'
            elif 'pure_cpu' in engine_type:
                info['type'] = 'CPU'
            else:
                info['type'] = 'Hybrid'

            return info

        except Exception as e:
            return {'error': str(e), 'type': 'unknown'}

    def decrypt_file(self, file_path: str, output_dir: str = None) -> Dict[str, Any]:
        """解密文件"""
        result = {
            'success': False,
            'output_file': None,
            'error': None
        }

        try:
            self.log(f"🔓 开始解密: {os.path.basename(file_path)}")

            # 读取加密包
            with open(file_path, 'rb') as f:
                package = pickle.load(f)

            metadata = package.get('metadata', {})
            encrypted_data = package.get('encrypted_data', b'')
            layers = metadata.get('layers', [])

            self.log(f"📋 加密层数: {len(layers)}")
            self.log(f"📋 数据大小: {len(encrypted_data):,} 字节")

            # 逐层解密
            decrypted_data = encrypted_data
            for i, layer in enumerate(reversed(layers)):
                layer_idx = len(layers) - i
                algorithm = layer.get('algorithm', 'unknown')
                self.log(f"🔓 解密第 {layer_idx} 层: {algorithm}")

                try:
                    decrypted_data = self._decrypt_layer(decrypted_data, layer)
                    self.log(f"   ✅ 成功")
                except Exception as e:
                    self.log(f"   ❌ 失败: {e}")
                    raise

            # 保存解密文件
            if output_dir is None:
                output_dir = os.path.dirname(file_path)

            output_file = self._generate_output_path(file_path, output_dir)

            with open(output_file, 'wb') as f:
                f.write(decrypted_data)

            self.log(f"✅ 解密完成: {os.path.basename(output_file)}")
            self.log(f"📁 输出大小: {len(decrypted_data):,} 字节")

            result['success'] = True
            result['output_file'] = output_file
            result['decrypted_size'] = len(decrypted_data)

        except Exception as e:
            self.log(f"❌ 解密失败: {e}")
            result['error'] = str(e)

        return result

    def _decrypt_layer(self, data: bytes, layer: Dict) -> bytes:
        """解密单层"""
        algorithm = layer.get('algorithm', '').lower().replace('-', '_').replace(' ', '_')

        if 'aes' in algorithm:
            return self._decrypt_aes(data, layer)
        elif 'chacha20' in algorithm:
            return self._decrypt_chacha20(data, layer)
        elif 'salsa20' in algorithm:
            return self._decrypt_salsa20(data, layer)
        elif 'blowfish' in algorithm:
            return self._decrypt_blowfish(data, layer)
        elif 'matrix' in algorithm:
            return self._decrypt_matrix(data, layer)
        elif 'rsa' in algorithm:
            return self._decrypt_rsa(data, layer)
        else:
            self.log(f"   ⚠️ 未知算法: {algorithm}")
            return data

    def _decrypt_aes(self, data: bytes, layer: Dict) -> bytes:
        """AES解密"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        key = layer.get('key')
        iv = layer.get('iv')
        mode_name = layer.get('mode', 'CBC')
        tag = layer.get('tag')

        if mode_name == 'GCM' and tag:
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        else:
            if len(iv) != 16:
                iv = iv[:16] if len(iv) > 16 else iv + b'\x00' * (16 - len(iv))
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded = decryptor.update(data) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            return unpadder.update(padded) + unpadder.finalize()

    def _decrypt_chacha20(self, data: bytes, layer: Dict) -> bytes:
        """ChaCha20解密"""
        key = layer.get('key')
        nonce = layer.get('nonce')

        # 检查是否是GPU自定义实现
        if layer.get('gpu_only', False) or 'GPU' in layer.get('backend_info', ''):
            return self._decrypt_chacha20_gpu(data, key, nonce)

        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None)
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    def _decrypt_chacha20_gpu(self, data: bytes, key: bytes, nonce: bytes) -> bytes:
        """GPU ChaCha20解密 - 纯Python实现"""
        result = bytearray(len(data))

        for i in range(len(data)):
            kb = key[i % 32]
            nb = nonce[i % 16]
            ks = kb ^ nb
            ks ^= (i & 0xFF)
            ks = ((ks << 3) | (ks >> 5)) & 0xFF
            ks ^= ((i >> 8) & 0xFF)
            for _ in range(20):
                ks = (ks + kb) & 0xFF
                ks ^= ((ks << 1) & 0xFF)
                ks = (ks + nb) & 0xFF
                ks ^= ((ks >> 1) & 0xFF)
            result[i] = data[i] ^ ks

        return bytes(result)

    def _decrypt_salsa20(self, data: bytes, layer: Dict) -> bytes:
        """Salsa20解密 - 匹配GPU OpenCL实现"""
        key = layer.get('key')
        nonce = layer.get('nonce')
        
        # 检查是否是GPU自定义实现
        backend_info = layer.get('backend_info', '')
        if 'GPU' in backend_info or layer.get('gpu_only', False):
            return self._decrypt_salsa20_gpu(data, key, nonce)
        
        # 标准Salsa20解密
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            cipher = Cipher(algorithms.Salsa20(key, nonce), mode=None)
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        except:
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
            nonce_byte = nonce[gid % 8]  # Salsa20使用8字节nonce
            
            # 生成密钥流字节 (Salsa20风格) - 与OpenCL内核完全匹配
            keystream = key_byte ^ nonce_byte
            keystream ^= (gid & 0xFF)  # 位置相关
            
            # Salsa20的四分之一轮操作 (简化版)
            for i in range(10):  # Salsa20/10
                keystream = (keystream + key_byte) & 0xFF
                keystream ^= ((keystream << 1) & 0xFF)
                keystream = (keystream + nonce_byte) & 0xFF
                keystream ^= ((keystream >> 1) & 0xFF)
                keystream = (keystream + ((gid >> (i % 8)) & 0xFF)) & 0xFF
                keystream = ((keystream << 2) | (keystream >> 6)) & 0xFF  # 旋转
            
            # 额外的混合 - 注意：最后一行是XOR赋值
            keystream ^= key[(gid + 16) % 32]
            keystream = (keystream + nonce[(gid + 4) % 8]) & 0xFF
            keystream ^= ((keystream << 3) | (keystream >> 5)) & 0xFF  # XOR赋值
            
            result[gid] = byte_val ^ keystream
        
        return bytes(result)

    def _decrypt_blowfish(self, data: bytes, layer: Dict) -> bytes:
        """Blowfish解密"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        key = layer.get('key')
        iv = layer.get('iv')

        if iv:
            cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        else:
            cipher = Cipher(algorithms.Blowfish(key), modes.ECB())

        decryptor = cipher.decryptor()
        padded = decryptor.update(data) + decryptor.finalize()
        unpadder = padding.PKCS7(64).unpadder()
        return unpadder.update(padded) + unpadder.finalize()

    def _decrypt_matrix(self, data: bytes, layer: Dict) -> bytes:
        """矩阵解密"""
        seed = layer.get('seed', 12345)
        original_length = layer.get('original_length', len(data))
        matrix_size = layer.get('matrix_size', 8)
        # 如果加密时保存了变换矩阵，直接使用
        transform_matrix = layer.get('transform_matrix', None)

        # 尝试使用numpy，如果不可用则使用纯Python
        try:
            import numpy as np
            return self._decrypt_matrix_numpy(data, seed, original_length, matrix_size, transform_matrix)
        except ImportError:
            return self._decrypt_matrix_pure(data, seed, original_length, matrix_size, transform_matrix)

    def _decrypt_matrix_numpy(self, data: bytes, seed: int, original_length: int, matrix_size: int, saved_matrix=None) -> bytes:
        """使用numpy的矩阵解密 - 匹配GPU OpenCL加密（XOR变换）"""
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

    def _decrypt_matrix_pure(self, data: bytes, seed: int, original_length: int, matrix_size: int, saved_matrix=None) -> bytes:
        """纯Python的矩阵解密 - 匹配GPU OpenCL加密（XOR变换）"""
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
        """RSA解密"""
        aes_meta = layer.get('aes_metadata', {})
        if aes_meta and 'key' in aes_meta:
            return self._decrypt_aes(data, aes_meta)
        return data

    def _generate_output_path(self, input_file: str, output_dir: str) -> str:
        """生成输出路径"""
        base = os.path.basename(input_file)
        if base.endswith('.encrypted'):
            base = base[:-10]

        # 清理文件名
        for suffix in ['_cpu_level', '_gpu_level', '_hybrid']:
            if suffix in base:
                base = base.split(suffix)[0]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(output_dir, f"{base}_decrypted_{timestamp}")


class DecryptorLauncherGUI:
    """解密器启动器GUI"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🔓 通用解密器 v2.0")
        self.root.geometry("750x600")
        self.root.minsize(650, 500)

        self.decryptor = UniversalDecryptor()
        self.decryptor.set_log_callback(self.log)

        self.last_output_dir = None
        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        # 主框架
        main = ttk.Frame(self.root, padding=15)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)

        # 标题
        ttk.Label(main, text="🔓 通用文件解密器",
                 font=("Arial", 20, "bold")).grid(row=0, column=0, pady=(0, 5))
        ttk.Label(main, text="支持CPU/GPU/混合加密文件 | 自动检测加密类型",
                 font=("Arial", 10), foreground="gray").grid(row=1, column=0, pady=(0, 15))

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

        # 文件信息
        self.info_frame = ttk.LabelFrame(main, text="📋 文件信息", padding=10)
        self.info_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        self.info_text = tk.StringVar(value="请选择加密文件...")
        ttk.Label(self.info_frame, textvariable=self.info_text,
                 font=("Arial", 10)).pack(anchor="w")

        # 输出目录
        out_frame = ttk.LabelFrame(main, text="📂 输出目录（可选）", padding=10)
        out_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
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
        action_frame.grid(row=5, column=0, pady=15)

        self.decrypt_btn = ttk.Button(action_frame, text="🔓 开始解密",
                                     command=self.decrypt)
        self.decrypt_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.open_btn = ttk.Button(action_frame, text="📂 打开输出目录",
                                  command=self.open_output, state=tk.DISABLED)
        self.open_btn.pack(side=tk.LEFT)

        # 进度
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.grid(row=6, column=0, sticky="ew", pady=(0, 10))

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(main, textvariable=self.status_var).grid(row=7, column=0, sticky="w")

        # 日志
        log_frame = ttk.LabelFrame(main, text="📋 日志", padding=10)
        log_frame.grid(row=8, column=0, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main.rowconfigure(8, weight=1)

        self.log_text = ScrolledText(log_frame, height=8, font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")

        self.log("🔓 通用解密器已启动")
        self.log("💡 支持CPU/GPU/混合加密文件")

    def browse_file(self):
        """浏览文件"""
        f = filedialog.askopenfilename(
            title="选择加密文件",
            filetypes=[("加密文件", "*.encrypted"), ("所有文件", "*.*")]
        )
        if f:
            self.file_var.set(f)
            self.log(f"✅ 已选择: {os.path.basename(f)}")
            self.show_file_info(f)

    def browse_output(self):
        """浏览输出目录"""
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_var.set(d)

    def auto_find(self):
        """自动查找"""
        files = [f for f in os.listdir('.') if f.endswith('.encrypted')]
        if not files:
            messagebox.showinfo("提示", "当前目录未找到加密文件")
            return
        if len(files) == 1:
            self.file_var.set(os.path.abspath(files[0]))
            self.log(f"✅ 自动选择: {files[0]}")
            self.show_file_info(files[0])
        else:
            self.log(f"📋 找到 {len(files)} 个文件")
            # 选择第一个
            self.file_var.set(os.path.abspath(files[0]))
            self.show_file_info(files[0])

    def show_file_info(self, path: str):
        """显示文件信息"""
        info = self.decryptor.detect_encryption_type(path)
        if 'error' in info:
            self.info_text.set(f"❌ 无法读取: {info['error']}")
        else:
            self.info_text.set(
                f"类型: {info['type']} | "
                f"安全级别: {info['security_level']} | "
                f"层数: {info['layers']} | "
                f"大小: {info['encrypted_size']:,} 字节"
            )

    def clear(self):
        """清空"""
        self.file_var.set("")
        self.output_var.set("")
        self.info_text.set("请选择加密文件...")
        self.progress['value'] = 0

    def decrypt(self):
        """解密"""
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
        self.progress['value'] = 20
        self.root.update()

        try:
            self.log("=" * 50)
            self.progress['value'] = 50
            self.root.update()

            result = self.decryptor.decrypt_file(path, output)

            self.progress['value'] = 100

            if result['success']:
                self.status_var.set("✅ 解密成功")
                self.last_output_dir = os.path.dirname(result['output_file'])
                self.open_btn.config(state=tk.NORMAL)
                messagebox.showinfo("成功",
                    f"解密成功!\n\n输出: {os.path.basename(result['output_file'])}\n"
                    f"大小: {result.get('decrypted_size', 0):,} 字节")
            else:
                self.status_var.set("❌ 解密失败")
                messagebox.showerror("失败", f"解密失败:\n{result['error']}")

        except Exception as e:
            self.status_var.set("❌ 错误")
            self.log(f"❌ {e}")
            messagebox.showerror("错误", str(e))

        finally:
            self.decrypt_btn.config(state=tk.NORMAL)

    def open_output(self):
        """打开输出目录"""
        if self.last_output_dir and os.path.exists(self.last_output_dir):
            if sys.platform == 'win32':
                os.startfile(self.last_output_dir)

    def log(self, msg: str):
        """日志"""
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def run(self):
        """运行"""
        self.root.mainloop()


def main():
    if GUI_AVAILABLE:
        app = DecryptorLauncherGUI()
        app.run()
    else:
        print("❌ 需要tkinter GUI库")
        if len(sys.argv) > 1:
            d = UniversalDecryptor()
            r = d.decrypt_file(sys.argv[1])
            print("成功" if r['success'] else f"失败: {r['error']}")


if __name__ == "__main__":
    main()
