"""
加密对话框

提供详细的加密配置选项。
"""

import sys
from pathlib import Path

# 尝试导入GUI库
try:
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QComboBox, QSpinBox, QCheckBox,
                                QGroupBox, QFormLayout, QTextEdit, QTabWidget,
                                QWidget, QSlider, QProgressBar)
    from PyQt6.QtCore import Qt, pyqtSignal
    GUI_AVAILABLE = True
except ImportError:
    try:
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                      QPushButton, QComboBox, QSpinBox, QCheckBox,
                                      QGroupBox, QFormLayout, QTextEdit, QTabWidget,
                                      QWidget, QSlider, QProgressBar)
        from PySide6.QtCore import Qt, Signal as pyqtSignal
        GUI_AVAILABLE = True
    except ImportError:
        GUI_AVAILABLE = False

if GUI_AVAILABLE:
    sys.path.insert(0, str(Path(__file__).parent.parent))


class EncryptionDialog(QDialog):
    """加密配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        if not GUI_AVAILABLE:
            raise ImportError("没有可用的GUI库")

        self.config = {}
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("加密配置")
        self.setGeometry(200, 200, 600, 500)

        layout = QVBoxLayout(self)

        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # 基础设置标签页
        self.create_basic_tab(tab_widget)

        # 高级设置标签页
        self.create_advanced_tab(tab_widget)

        # 安全设置标签页
        self.create_security_tab(tab_widget)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.ok_button = QPushButton("确定")
        self.cancel_button = QPushButton("取消")
        self.preview_button = QPushButton("预览配置")

        button_layout.addWidget(self.preview_button)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # 连接信号
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.preview_button.clicked.connect(self.preview_config)

    def create_basic_tab(self, tab_widget):
        """创建基础设置标签页"""
        basic_widget = QWidget()
        layout = QVBoxLayout(basic_widget)

        # 加密算法选择
        algorithm_group = QGroupBox("加密算法")
        algorithm_layout = QFormLayout(algorithm_group)

        self.primary_algorithm = QComboBox()
        self.primary_algorithm.addItems([
            "AES-256-GCM", "AES-256-CBC", "ChaCha20",
            "RSA-2048", "RSA-4096", "自定义组合"
        ])
        algorithm_layout.addRow("主要算法:", self.primary_algorithm)

        self.secondary_algorithm = QComboBox()
        self.secondary_algorithm.addItems([
            "无", "XOR", "位混洗", "旋转密码", "替换密码"
        ])
        algorithm_layout.addRow("辅助算法:", self.secondary_algorithm)

        layout.addWidget(algorithm_group)

        # 加密模式
        mode_group = QGroupBox("加密模式")
        mode_layout = QFormLayout(mode_group)

        self.encryption_mode = QComboBox()
        self.encryption_mode.addItems(["分层加密", "并行加密", "混合模式"])
        mode_layout.addRow("加密模式:", self.encryption_mode)

        self.layer_count = QSpinBox()
        self.layer_count.setRange(1, 10)
        self.layer_count.setValue(3)
        mode_layout.addRow("加密层数:", self.layer_count)

        layout.addWidget(mode_group)

        # 压缩选项
        compression_group = QGroupBox("压缩选项")
        compression_layout = QFormLayout(compression_group)

        self.enable_compression = QCheckBox("启用压缩")
        self.enable_compression.setChecked(True)
        compression_layout.addRow(self.enable_compression)

        self.compression_level = QSlider(Qt.Orientation.Horizontal)
        self.compression_level.setRange(1, 9)
        self.compression_level.setValue(6)
        self.compression_level.setEnabled(False)
        compression_layout.addRow("压缩级别:", self.compression_level)

        # 连接压缩复选框
        self.enable_compression.toggled.connect(self.compression_level.setEnabled)

        layout.addWidget(compression_group)
        layout.addStretch()

        tab_widget.addTab(basic_widget, "基础设置")

    def create_advanced_tab(self, tab_widget):
        """创建高级设置标签页"""
        advanced_widget = QWidget()
        layout = QVBoxLayout(advanced_widget)

        # 密钥设置
        key_group = QGroupBox("密钥设置")
        key_layout = QFormLayout(key_group)

        self.key_derivation = QComboBox()
        self.key_derivation.addItems(["PBKDF2", "Scrypt", "Argon2", "自动生成"])
        key_layout.addRow("密钥派生:", self.key_derivation)

        self.iterations = QSpinBox()
        self.iterations.setRange(1000, 1000000)
        self.iterations.setValue(100000)
        key_layout.addRow("迭代次数:", self.iterations)

        layout.addWidget(key_group)

        # 隐写术设置
        steganography_group = QGroupBox("隐写术")
        steganography_layout = QFormLayout(steganography_group)

        self.enable_steganography = QCheckBox("启用隐写术")
        steganography_layout.addRow(self.enable_steganography)

        self.steganography_method = QComboBox()
        self.steganography_method.addItems(["LSB图像", "文本空白", "音频LSB"])
        self.steganography_method.setEnabled(False)
        steganography_layout.addRow("隐写方法:", self.steganography_method)

        # 连接隐写术复选框
        self.enable_steganography.toggled.connect(self.steganography_method.setEnabled)

        layout.addWidget(steganography_group)

        # GPU加速设置
        gpu_group = QGroupBox("GPU加速")
        gpu_layout = QFormLayout(gpu_group)

        self.enable_gpu = QCheckBox("启用GPU加速")
        self.enable_gpu.setChecked(False)
        gpu_layout.addRow(self.enable_gpu)

        # GPU状态显示
        self.gpu_status_label = QLabel("检测中...")
        gpu_layout.addRow("GPU状态:", self.gpu_status_label)

        # GPU阈值设置
        self.gpu_threshold = QSpinBox()
        self.gpu_threshold.setRange(1, 1000)
        self.gpu_threshold.setValue(10)
        self.gpu_threshold.setSuffix(" MB")
        self.gpu_threshold.setEnabled(False)
        gpu_layout.addRow("GPU阈值:", self.gpu_threshold)

        # GPU算法选择
        self.gpu_algorithms = QComboBox()
        self.gpu_algorithms.addItems(["自动选择", "仅AES256", "仅ChaCha20", "仅Salsa20", "仅矩阵变换"])
        self.gpu_algorithms.setEnabled(False)
        gpu_layout.addRow("GPU算法:", self.gpu_algorithms)

        # 连接GPU复选框
        self.enable_gpu.toggled.connect(self.gpu_threshold.setEnabled)
        self.enable_gpu.toggled.connect(self.gpu_algorithms.setEnabled)
        self.enable_gpu.toggled.connect(self.update_gpu_status)

        layout.addWidget(gpu_group)

        # 多线程设置
        threading_group = QGroupBox("多线程设置")
        threading_layout = QFormLayout(threading_group)

        self.thread_count = QSpinBox()
        self.thread_count.setRange(1, 32)
        self.thread_count.setValue(12)
        threading_layout.addRow("线程数:", self.thread_count)

        self.parallel_threshold = QSpinBox()
        self.parallel_threshold.setRange(1, 100)
        self.parallel_threshold.setValue(1)
        self.parallel_threshold.setSuffix(" MB")
        threading_layout.addRow("并行阈值:", self.parallel_threshold)

        layout.addWidget(threading_group)

        # 文件处理
        file_group = QGroupBox("文件处理")
        file_layout = QFormLayout(file_group)

        self.delete_original = QCheckBox("加密后删除原文件")
        file_layout.addRow(self.delete_original)

        self.create_backup = QCheckBox("创建备份")
        self.create_backup.setChecked(True)
        file_layout.addRow(self.create_backup)

        self.split_large_files = QCheckBox("分割大文件")
        file_layout.addRow(self.split_large_files)

        self.max_file_size = QSpinBox()
        self.max_file_size.setRange(1, 1000)
        self.max_file_size.setValue(100)
        self.max_file_size.setSuffix(" MB")
        self.max_file_size.setEnabled(False)
        file_layout.addRow("最大文件大小:", self.max_file_size)

        # 连接分割文件复选框
        self.split_large_files.toggled.connect(self.max_file_size.setEnabled)

        layout.addWidget(file_group)

        # 初始化GPU状态检测
        self.check_gpu_availability()
        layout.addStretch()

        tab_widget.addTab(advanced_widget, "高级设置")

    def create_security_tab(self, tab_widget):
        """创建安全设置标签页"""
        security_widget = QWidget()
        layout = QVBoxLayout(security_widget)

        # 安全保护
        protection_group = QGroupBox("安全保护")
        protection_layout = QFormLayout(protection_group)

        self.anti_debug = QCheckBox("反调试保护")
        self.anti_debug.setChecked(True)
        protection_layout.addRow(self.anti_debug)

        self.anti_vm = QCheckBox("反虚拟机检测")
        self.anti_vm.setChecked(True)
        protection_layout.addRow(self.anti_vm)

        self.code_obfuscation = QCheckBox("代码混淆")
        self.code_obfuscation.setChecked(True)
        protection_layout.addRow(self.code_obfuscation)

        layout.addWidget(protection_group)

        # 完整性检查
        integrity_group = QGroupBox("完整性检查")
        integrity_layout = QFormLayout(integrity_group)

        self.enable_checksum = QCheckBox("启用校验和")
        self.enable_checksum.setChecked(True)
        integrity_layout.addRow(self.enable_checksum)

        self.checksum_algorithm = QComboBox()
        self.checksum_algorithm.addItems(["SHA-256", "SHA-512", "MD5", "CRC32"])
        integrity_layout.addRow("校验算法:", self.checksum_algorithm)

        layout.addWidget(integrity_group)

        # 访问控制
        access_group = QGroupBox("访问控制")
        access_layout = QFormLayout(access_group)

        self.password_protect = QCheckBox("密码保护")
        access_layout.addRow(self.password_protect)

        self.time_limit = QCheckBox("时间限制")
        access_layout.addRow(self.time_limit)

        self.usage_limit = QCheckBox("使用次数限制")
        access_layout.addRow(self.usage_limit)

        layout.addWidget(access_group)
        layout.addStretch()

        tab_widget.addTab(security_widget, "安全设置")

    def check_gpu_availability(self):
        """检查GPU可用性"""
        try:
            import os
            os.environ['PYOPENCL_CTX'] = '0'

            from src.gpu.gpu_manager import gpu_manager

            gpu_info = gpu_manager.get_performance_info()

            if gpu_info['gpu_available']:
                device_name = gpu_info.get('device_name', 'AMD GPU')
                memory_gb = gpu_info.get('memory_info', {}).get('total', 0) // 1024 // 1024 // 1024
                status_text = f"✅ {device_name} ({memory_gb}GB)"
                self.gpu_status_label.setStyleSheet("color: green;")

                # 更新GPU算法选项
                supported_algorithms = gpu_info.get('supported_algorithms', [])
                algorithm_items = ["自动选择"]
                for alg in supported_algorithms:
                    if alg == 'aes256':
                        algorithm_items.append("仅AES-256")
                    elif alg == 'chacha20':
                        algorithm_items.append("仅ChaCha20")
                    elif alg == 'salsa20':
                        algorithm_items.append("仅Salsa20")
                    elif alg == 'matrix_cipher':
                        algorithm_items.append("仅矩阵变换")
                    elif alg == 'blowfish':
                        algorithm_items.append("仅Blowfish")
                    elif alg == 'twofish':
                        algorithm_items.append("仅Twofish")

                self.gpu_algorithms.clear()
                self.gpu_algorithms.addItems(algorithm_items)

            else:
                status_text = "❌ GPU不可用"
                self.gpu_status_label.setStyleSheet("color: red;")
                self.enable_gpu.setEnabled(False)

            self.gpu_status_label.setText(status_text)

        except Exception as e:
            self.gpu_status_label.setText(f"❌ 检测失败: {str(e)[:30]}")
            self.gpu_status_label.setStyleSheet("color: red;")
            self.enable_gpu.setEnabled(False)

    def update_gpu_status(self, enabled):
        """更新GPU状态显示"""
        if enabled:
            self.gpu_status_label.setStyleSheet("color: blue;")
            current_text = self.gpu_status_label.text()
            if "✅" in current_text:
                self.gpu_status_label.setText(current_text.replace("✅", "🚀"))
        else:
            self.check_gpu_availability()

    def preview_config(self):
        """预览配置"""
        config = self.get_config()

        preview_dialog = QDialog(self)
        preview_dialog.setWindowTitle("配置预览")
        preview_dialog.setGeometry(300, 300, 500, 400)

        layout = QVBoxLayout(preview_dialog)

        preview_text = QTextEdit()
        preview_text.setReadOnly(True)

        # 格式化配置信息
        config_text = "加密配置预览:\n\n"
        config_text += f"主要算法: {config['primary_algorithm']}\n"
        config_text += f"辅助算法: {config['secondary_algorithm']}\n"
        config_text += f"加密模式: {config['encryption_mode']}\n"
        config_text += f"加密层数: {config['layer_count']}\n"
        config_text += f"启用压缩: {'是' if config['enable_compression'] else '否'}\n"

        if config['enable_compression']:
            config_text += f"压缩级别: {config['compression_level']}\n"

        config_text += f"密钥派生: {config['key_derivation']}\n"
        config_text += f"迭代次数: {config['iterations']}\n"

        config_text += f"启用隐写术: {'是' if config['enable_steganography'] else '否'}\n"
        if config['enable_steganography']:
            config_text += f"隐写方法: {config['steganography_method']}\n"

        config_text += f"\n🚀 GPU加速设置:\n"
        config_text += f"启用GPU: {'是' if config['enable_gpu'] else '否'}\n"
        if config['enable_gpu']:
            config_text += f"GPU阈值: {config['gpu_threshold']} MB\n"
            config_text += f"GPU算法: {config['gpu_algorithms']}\n"

        config_text += f"\n⚡ 多线程设置:\n"
        config_text += f"线程数: {config['thread_count']}\n"
        config_text += f"并行阈值: {config['parallel_threshold']} MB\n"

        config_text += f"\n🔒 安全保护: {', '.join([k for k, v in config.items() if k.startswith('anti_') and v])}\n"

        preview_text.setPlainText(config_text)
        layout.addWidget(preview_text)

        close_button = QPushButton("关闭")
        close_button.clicked.connect(preview_dialog.close)
        layout.addWidget(close_button)

        preview_dialog.exec()

    def get_config(self):
        """获取当前配置"""
        return {
            'primary_algorithm': self.primary_algorithm.currentText(),
            'secondary_algorithm': self.secondary_algorithm.currentText(),
            'encryption_mode': self.encryption_mode.currentText(),
            'layer_count': self.layer_count.value(),
            'enable_compression': self.enable_compression.isChecked(),
            'compression_level': self.compression_level.value(),
            'key_derivation': self.key_derivation.currentText(),
            'iterations': self.iterations.value(),
            'enable_steganography': self.enable_steganography.isChecked(),
            'steganography_method': self.steganography_method.currentText(),
            'enable_gpu': self.enable_gpu.isChecked(),
            'gpu_threshold': self.gpu_threshold.value(),
            'gpu_algorithms': self.gpu_algorithms.currentText(),
            'thread_count': self.thread_count.value(),
            'parallel_threshold': self.parallel_threshold.value(),
            'delete_original': self.delete_original.isChecked(),
            'create_backup': self.create_backup.isChecked(),
            'split_large_files': self.split_large_files.isChecked(),
            'max_file_size': self.max_file_size.value(),
            'anti_debug': self.anti_debug.isChecked(),
            'anti_vm': self.anti_vm.isChecked(),
            'code_obfuscation': self.code_obfuscation.isChecked(),
            'enable_checksum': self.enable_checksum.isChecked(),
            'checksum_algorithm': self.checksum_algorithm.currentText(),
            'password_protect': self.password_protect.isChecked(),
            'time_limit': self.time_limit.isChecked(),
            'usage_limit': self.usage_limit.isChecked()
        }

    def set_config(self, config):
        """设置配置"""
        if 'primary_algorithm' in config:
            index = self.primary_algorithm.findText(config['primary_algorithm'])
            if index >= 0:
                self.primary_algorithm.setCurrentIndex(index)

        # 设置其他配置项...
        # 这里可以根据需要添加更多配置项的设置
