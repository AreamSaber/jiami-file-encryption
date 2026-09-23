#!/usr/bin/env python3
"""
混合加密解密器 - 带GUI文件选择功能
支持CPU和GPU混合加密文件的解密，提供友好的图形界面
"""

import os
import sys
import hashlib
import time
from pathlib import Path
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
    """GUI adapter to the same authenticated runtime as the CLI."""
    def __init__(self):
        self.log_callback = None

    def set_log_callback(self, callback):
        self.log_callback = callback

    def log(self, message):
        (self.log_callback or print)(message)

    def decrypt_file(self, encrypted_file, output_dir=None):
        from src.decryptor.cpu_decryptor import CPUDecryptor
        from src.decryptor.base_decryptor import load_package
        try:
            public, _, _ = load_package(encrypted_file)
            destination = Path(output_dir or Path(encrypted_file).parent) / ('restored-' + public['original_name'])
            decryptor = CPUDecryptor()
            output = decryptor.decrypt_file(encrypted_file, destination)
            self.log('Recovered: ' + output)
            if decryptor.last_publication.warning:
                self.log(decryptor.last_publication.warning)
            return {'success': True, 'output_file': output, 'original_size': public['original_size'],
                    'decrypted_size': public['original_size'], 'engine_type': 'v1-cpu',
                    'warning': decryptor.last_publication.warning, 'error': None}
        except Exception as exc:
            self.log('Recovery failed: ' + str(exc))
            return {'success': False, 'output_file': None, 'error': str(exc)}


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
                              text="支持格式: data.jmi | recovery.jmis 须位于密文旁边",
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
                ("加密文件", "*.jmi"),
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
            if f.endswith('.jmi'):
                encrypted_files.append(os.path.join(current_dir, f))

        if not encrypted_files:
            self.log("⚠️ 当前目录未找到加密文件")
            messagebox.showinfo("提示", "当前目录未找到 .jmi 文件\n请手动选择文件")
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
                    f"引擎类型: {result['engine_type']}\n{result.get('warning', '')}")
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
