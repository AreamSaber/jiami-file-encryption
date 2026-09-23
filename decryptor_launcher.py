#!/usr/bin/env python3
"""
统一解密器启动器
自动检测加密类型并启动对应的解密器GUI
支持手动选择文件
"""

import os
import sys
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


from src.decryptor.hybrid_decryptor_gui import HybridDecryptor


class UniversalDecryptor(HybridDecryptor):
    """The launcher never deserializes legacy executable object formats."""
    def detect_encryption_type(self, file_path):
        from src.decryptor.base_decryptor import load_package
        try:
            public, _, body = load_package(file_path)
            layers = public.get('layers', public.get('chunk_layers', []))
            return {'type':'v1', 'engine_type':'v1-cpu', 'security_level':public['profile'],
                    'layers':len(layers), 'gpu_only':False,
                    'encrypted_size':len(body), 'metadata':public}
        except Exception as exc:
            return {'error':str(exc), 'type':'unknown'}


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
        ttk.Label(main, text="v1 认证恢复 | recovery.jmis 须位于密文旁边",
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
            filetypes=[("加密文件", "*.jmi"), ("所有文件", "*.*")]
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
        files = [f for f in os.listdir('.') if f.endswith('.jmi')]
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
                    f"大小: {result.get('decrypted_size', 0):,} 字节\n{result.get('warning', '')}")
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
