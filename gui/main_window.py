"""
主窗口界面

文件加密系统的主要GUI界面。
"""

import sys
import os
from pathlib import Path

# 尝试导入GUI库
try:
    from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QPushButton, QFileDialog, QTextEdit,
                                QProgressBar, QMenuBar, QStatusBar, QGroupBox,
                                QComboBox, QCheckBox, QMessageBox, QTabWidget,
                                QListWidget, QSplitter, QSpinBox, QSlider,
                                QFormLayout, QFrame)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QIcon, QFont, QPixmap, QAction
    GUI_AVAILABLE = True
    GUI_FRAMEWORK = "PyQt6"
except ImportError:
    try:
        from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                      QLabel, QPushButton, QFileDialog, QTextEdit,
                                      QProgressBar, QMenuBar, QStatusBar, QGroupBox,
                                      QComboBox, QCheckBox, QMessageBox, QTabWidget,
                                      QListWidget, QSplitter, QSpinBox, QSlider,
                                      QFormLayout, QFrame)
        from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QTimer
        from PySide6.QtGui import QIcon, QFont, QPixmap, QAction
        GUI_AVAILABLE = True
        GUI_FRAMEWORK = "PySide6"
    except ImportError:
        GUI_AVAILABLE = False
        GUI_FRAMEWORK = None

if GUI_AVAILABLE:
    # 添加项目根目录到路径
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from src.encryptor.main import FileEncryptor
    from src.utils.logger import Logger
    from src.thread_pool.thread_manager import thread_manager, ThreadPriority
    import multiprocessing

class EncryptionWorker(QThread):
    """加密工作线程"""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, input_path, output_path, profile, threading_config=None, gpu_config=None):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.profile = profile
        self.threading_config = threading_config or {}
        self.gpu_config = gpu_config or {}
        self.encryptor = FileEncryptor(max_threads=self.threading_config.get('max_threads'))

    def run(self):
            try:
                import os  # 确保os在整个方法作用域内可用

                self.status.emit("正在初始化加密...")
                self.progress.emit(10)

                # 应用GPU配置
                if self.gpu_config.get('enable_gpu', False):
                    try:
                        os.environ['PYOPENCL_CTX'] = '0'

                        from src.gpu.gpu_manager import gpu_manager

                        # 启用GPU并设置阈值
                        gpu_manager.force_cpu_mode = False  # 确保GPU模式启用
                        gpu_threshold_mb = self.gpu_config.get('gpu_threshold_mb', 10)
                        gpu_manager.set_threshold(gpu_threshold_mb * 1024 * 1024)  # 转换为字节

                        gpu_info = gpu_manager.get_performance_info()
                        if gpu_info['gpu_available']:
                            self.status.emit(f"🚀 GPU加速已启用 (阈值: {gpu_threshold_mb}MB)")
                        else:
                            self.status.emit("⚠️ GPU不可用，使用CPU模式")

                    except Exception as e:
                        self.status.emit(f"⚠️ GPU初始化失败: {str(e)[:30]}")
                else:
                    # GPU禁用时，明确禁用GPU管理器
                    try:
                        from src.gpu.gpu_manager import gpu_manager
                        gpu_manager.force_cpu_mode = True  # 强制CPU模式
                        self.status.emit("💻 CPU模式已启用")
                    except Exception as e:
                        self.status.emit("💻 使用CPU模式")

                # 应用多线程配置（通过全局线程管理器，GUI优先级最高）
                if self.threading_config:
                    thread_manager.set_gui_config(
                        max_threads=self.threading_config.get('max_threads'),
                        enable_threading=self.threading_config.get('enable_threading', True),
                        parallel_threshold_mb=self.threading_config.get('parallel_threshold_mb')
                    )

                    config = thread_manager.get_config()
                    self.status.emit(f"多线程配置: {config.get('max_threads')}线程 (来源: {config.get('source')})")

                self.progress.emit(20)
                self.status.emit("正在读取文件...")
                self.progress.emit(30)

                if os.path.isfile(self.input_path):
                    result = self.encryptor.encrypt_file(self.input_path, self.output_path, self.profile)
                else:
                    result = self.encryptor.encrypt_folder(self.input_path, self.output_path, self.profile)

                self.progress.emit(90)
                self.status.emit("加密完成")
                self.progress.emit(100)

                self.finished.emit(result)

            except Exception as e:
                self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()
        if not GUI_AVAILABLE:
            raise ImportError("没有可用的GUI库")

        self.logger = Logger("GUI")
        self.encryptor = FileEncryptor()
        self.worker = None

        # 获取系统CPU信息
        self.cpu_count = multiprocessing.cpu_count()

        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("文件加密系统 v1.0.0")
        self.setGeometry(100, 100, 1000, 700)

        # 设置中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # 加密标签页
        self.create_encryption_tab()

        # 解密标签页
        self.create_decryption_tab()

        # 设置标签页
        self.create_settings_tab()

        # 创建菜单栏
        self.create_menu_bar()

        # 创建状态栏
        self.create_status_bar()

    def create_encryption_tab(self):
        """创建加密标签页"""
        encrypt_widget = QWidget()
        layout = QVBoxLayout(encrypt_widget)

        # 文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)

        # 输入文件选择
        input_layout = QHBoxLayout()
        self.input_label = QLabel("选择要加密的文件或文件夹:")
        self.input_path_label = QLabel("未选择文件或文件夹")
        self.input_path_label.setStyleSheet("color: gray; font-style: italic;")
        self.browse_file_btn = QPushButton("选择文件")
        self.browse_folder_btn = QPushButton("选择文件夹")

        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_path_label, 1)
        input_layout.addWidget(self.browse_file_btn)
        input_layout.addWidget(self.browse_folder_btn)
        file_layout.addLayout(input_layout)

        # 输出目录选择
        output_layout = QHBoxLayout()
        self.output_label = QLabel("输出目录:")
        self.output_path_label = QLabel("未选择目录")
        self.output_path_label.setStyleSheet("color: gray; font-style: italic;")
        self.browse_output_btn = QPushButton("浏览...")

        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_path_label, 1)
        output_layout.addWidget(self.browse_output_btn)
        file_layout.addLayout(output_layout)

        layout.addWidget(file_group)

        # 加密设置区域
        settings_group = QGroupBox("加密设置")
        settings_layout = QVBoxLayout(settings_group)

        # 加密配置选择
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("加密配置:"))
        self.profile_combo = QComboBox()
        self.load_profiles()
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        settings_layout.addLayout(profile_layout)

        # 多线程配置
        threading_layout = QHBoxLayout()
        threading_layout.addWidget(QLabel("CPU线程数:"))

        self.threading_combo = QComboBox()
        self.threading_combo.addItem("自动选择", 0)
        for i in range(1, self.cpu_count + 1):
            self.threading_combo.addItem(f"{i} 线程", i)
        # 默认选择全部CPU核心数
        default_index = self.cpu_count if self.cpu_count <= len(range(1, self.cpu_count + 1)) else 0
        self.threading_combo.setCurrentIndex(default_index)
        threading_layout.addWidget(self.threading_combo)

        # CPU信息标签
        cpu_info_label = QLabel(f"(检测到 {self.cpu_count} 个CPU核心)")
        cpu_info_label.setStyleSheet("color: gray; font-size: 10px;")
        threading_layout.addWidget(cpu_info_label)
        threading_layout.addStretch()
        settings_layout.addLayout(threading_layout)

        # 性能设置
        perf_layout = QHBoxLayout()
        perf_layout.addWidget(QLabel("并行阈值:"))

        self.threshold_combo = QComboBox()
        self.threshold_combo.addItem("512KB", 0.5)
        self.threshold_combo.addItem("1MB", 1)
        self.threshold_combo.addItem("5MB", 5)
        self.threshold_combo.addItem("10MB", 10)
        self.threshold_combo.addItem("50MB", 50)
        self.threshold_combo.setCurrentIndex(0)  # 默认512KB，更积极使用多线程
        perf_layout.addWidget(self.threshold_combo)

        threshold_info_label = QLabel("(大于此大小的文件使用多线程)")
        threshold_info_label.setStyleSheet("color: gray; font-size: 10px;")
        perf_layout.addWidget(threshold_info_label)
        perf_layout.addStretch()
        settings_layout.addLayout(perf_layout)

        # 高级选项
        self.advanced_checkbox = QCheckBox("显示高级选项")
        self.advanced_checkbox.toggled.connect(self.toggle_advanced_options)
        settings_layout.addWidget(self.advanced_checkbox)

        # 高级选项组（默认隐藏）
        self.advanced_group = QGroupBox("高级设置")
        self.advanced_group.setVisible(False)
        advanced_layout = QFormLayout(self.advanced_group)

        # GPU加速设置
        self.enable_gpu_checkbox = QCheckBox("启用GPU加速")
        self.enable_gpu_checkbox.setChecked(False)
        advanced_layout.addRow("GPU加速:", self.enable_gpu_checkbox)

        # GPU状态显示
        self.gpu_status_label = QLabel("检测中...")
        advanced_layout.addRow("GPU状态:", self.gpu_status_label)

        # GPU阈值设置
        self.gpu_threshold_combo = QComboBox()
        self.gpu_threshold_combo.addItem("5MB", 5)
        self.gpu_threshold_combo.addItem("10MB", 10)
        self.gpu_threshold_combo.addItem("20MB", 20)
        self.gpu_threshold_combo.addItem("50MB", 50)
        self.gpu_threshold_combo.setCurrentIndex(1)  # 默认10MB
        self.gpu_threshold_combo.setEnabled(False)
        advanced_layout.addRow("GPU阈值:", self.gpu_threshold_combo)

        # 启用多线程复选框
        self.enable_threading_checkbox = QCheckBox("启用多线程加速")
        self.enable_threading_checkbox.setChecked(True)
        advanced_layout.addRow("多线程:", self.enable_threading_checkbox)

        # 性能监控
        self.show_performance_checkbox = QCheckBox("显示性能统计")
        self.show_performance_checkbox.setChecked(False)
        advanced_layout.addRow("监控:", self.show_performance_checkbox)

        # 连接GPU复选框
        self.enable_gpu_checkbox.toggled.connect(self.gpu_threshold_combo.setEnabled)
        self.enable_gpu_checkbox.toggled.connect(self.update_gpu_status)

        settings_layout.addWidget(self.advanced_group)

        # 初始化GPU状态检测
        self.check_gpu_availability()

        layout.addWidget(settings_group)

        # 操作按钮
        button_layout = QHBoxLayout()
        self.encrypt_btn = QPushButton("开始加密")
        self.encrypt_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)

        button_layout.addStretch()
        button_layout.addWidget(self.encrypt_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # 进度区域
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        layout.addWidget(progress_group)

        # 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        self.tab_widget.addTab(encrypt_widget, "文件加密")

    def create_decryption_tab(self):
        """创建解密标签页"""
        decrypt_widget = QWidget()
        layout = QVBoxLayout(decrypt_widget)

        # 解密说明
        info_label = QLabel("解密功能:")
        info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(info_label)

        instruction_text = QTextEdit()
        instruction_text.setMaximumHeight(100)
        instruction_text.setReadOnly(True)
        instruction_text.setPlainText(
            "1. 使用生成的解密器程序进行解密\n"
            "2. 解密器位于加密输出目录中\n"
            "3. 双击解密器或使用命令行运行"
        )
        layout.addWidget(instruction_text)

        # 解密器列表
        decryptor_group = QGroupBox("可用的解密器")
        decryptor_layout = QVBoxLayout(decryptor_group)

        self.decryptor_list = QListWidget()
        self.refresh_decryptors()
        decryptor_layout.addWidget(self.decryptor_list)

        refresh_btn = QPushButton("刷新列表")
        refresh_btn.clicked.connect(self.refresh_decryptors)
        decryptor_layout.addWidget(refresh_btn)

        layout.addWidget(decryptor_group)
        layout.addStretch()

        self.tab_widget.addTab(decrypt_widget, "文件解密")

    def create_settings_tab(self):
        """创建设置标签页"""
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)

        # 系统信息
        info_group = QGroupBox("系统信息")
        info_layout = QVBoxLayout(info_group)

        info_text = QTextEdit()
        info_text.setMaximumHeight(200)
        info_text.setReadOnly(True)

        system_info = f"""
文件加密系统 v1.0.0 (多线程优化版)
GUI框架: {GUI_FRAMEWORK}
Python版本: {sys.version}
操作系统: {os.name}

多线程支持:
CPU核心数: {self.cpu_count}
最大线程数: {min(self.cpu_count, 8)}
支持策略: layered, threaded_layered, parallel
        """.strip()

        info_text.setPlainText(system_info)
        info_layout.addWidget(info_text)
        layout.addWidget(info_group)

        # 设置选项
        options_group = QGroupBox("选项")
        options_layout = QVBoxLayout(options_group)

        self.auto_open_checkbox = QCheckBox("加密完成后自动打开输出目录")
        self.auto_open_checkbox.setChecked(True)
        options_layout.addWidget(self.auto_open_checkbox)

        self.confirm_delete_checkbox = QCheckBox("删除原文件前确认")
        self.confirm_delete_checkbox.setChecked(True)
        options_layout.addWidget(self.confirm_delete_checkbox)

        layout.addWidget(options_group)
        layout.addStretch()

        self.tab_widget.addTab(settings_widget, "设置")

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        open_file_action = QAction("打开文件", self)
        open_file_action.triggered.connect(self.browse_input_file)
        file_menu.addAction(open_file_action)

        open_folder_action = QAction("打开文件夹", self)
        open_folder_action.triggered.connect(self.browse_input_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 工具菜单
        tools_menu = menubar.addMenu("工具")

        profiles_action = QAction("管理配置文件", self)
        tools_menu.addAction(profiles_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")

    def setup_connections(self):
        """设置信号连接"""
        self.browse_file_btn.clicked.connect(self.browse_input_file)
        self.browse_folder_btn.clicked.connect(self.browse_input_folder)
        self.browse_output_btn.clicked.connect(self.browse_output_dir)
        self.encrypt_btn.clicked.connect(self.start_encryption)
        self.cancel_btn.clicked.connect(self.cancel_encryption)
        self.threading_combo.currentTextChanged.connect(self.update_threading_info)

    def load_profiles(self):
        """加载加密配置文件"""
        try:
            profiles = self.encryptor.list_profiles()
            self.profile_combo.clear()
            for profile in profiles:
                info = self.encryptor.get_profile_info(profile)
                display_name = f"{profile} - {info.get('name', '无名称')}"
                self.profile_combo.addItem(display_name, profile)
        except Exception as e:
            self.log_message(f"加载配置文件失败: {e}")

    def toggle_advanced_options(self, checked):
        """切换高级选项显示"""
        self.advanced_group.setVisible(checked)
        if checked:
            self.resize(self.width(), self.height() + 100)
        else:
            self.resize(self.width(), self.height() - 100)

    def update_threading_info(self):
        """更新线程信息"""
        current_threads = self.threading_combo.currentData()
        if current_threads == 0:
            self.log_message("已选择自动线程数配置")
        else:
            self.log_message(f"已选择 {current_threads} 个线程")

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

                # 启用GPU选项
                self.enable_gpu_checkbox.setEnabled(True)

            else:
                status_text = "❌ GPU不可用"
                self.gpu_status_label.setStyleSheet("color: red;")
                self.enable_gpu_checkbox.setEnabled(False)

            self.gpu_status_label.setText(status_text)

        except Exception as e:
            self.gpu_status_label.setText(f"❌ 检测失败")
            self.gpu_status_label.setStyleSheet("color: red;")
            self.enable_gpu_checkbox.setEnabled(False)
            self.log_message(f"GPU检测失败: {str(e)[:50]}")

    def update_gpu_status(self, enabled):
        """更新GPU状态显示"""
        if enabled:
            self.gpu_status_label.setStyleSheet("color: blue;")
            current_text = self.gpu_status_label.text()
            if "✅" in current_text:
                self.gpu_status_label.setText(current_text.replace("✅", "🚀"))
            self.log_message("GPU加速已启用")
        else:
            self.check_gpu_availability()
            self.log_message("GPU加速已禁用")

    def get_threading_config(self):
        """获取当前多线程配置"""
        max_threads = self.threading_combo.currentData()
        if max_threads == 0:
            max_threads = None  # 自动选择

        parallel_threshold_mb = self.threshold_combo.currentData()
        enable_threading = self.enable_threading_checkbox.isChecked()

        return {
            'max_threads': max_threads,
            'enable_threading': enable_threading,
            'parallel_threshold_mb': parallel_threshold_mb,
            'show_performance': self.show_performance_checkbox.isChecked()
        }

    def get_gpu_config(self):
        """获取GPU配置"""
        return {
            'enable_gpu': self.enable_gpu_checkbox.isChecked(),
            'gpu_threshold_mb': self.gpu_threshold_combo.currentData()
        }

    def browse_input_file(self):
        """浏览输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要加密的文件", "", "所有文件 (*.*)"
        )
        if file_path:
            self.input_path_label.setText(file_path)
            self.input_path_label.setStyleSheet("color: black;")

    def browse_input_folder(self):
        """浏览输入文件夹"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择要加密的文件夹"
        )
        if folder_path:
            self.input_path_label.setText(folder_path)
            self.input_path_label.setStyleSheet("color: black;")

    def browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录"
        )
        if dir_path:
            self.output_path_label.setText(dir_path)
            self.output_path_label.setStyleSheet("color: black;")

    def start_encryption(self):
        """开始加密"""
        input_path = self.input_path_label.text()
        output_path = self.output_path_label.text()

        if input_path == "未选择文件或文件夹":
            QMessageBox.warning(self, "警告", "请选择要加密的文件或文件夹")
            return

        if output_path == "未选择目录":
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return

        profile = self.profile_combo.currentData()
        threading_config = self.get_threading_config()
        gpu_config = self.get_gpu_config()

        # 显示配置信息
        if threading_config['show_performance']:
            config_info = f"多线程配置: {threading_config['max_threads'] or 'auto'}线程, " \
                         f"阈值: {threading_config['parallel_threshold_mb']}MB"
            if gpu_config['enable_gpu']:
                config_info += f", GPU阈值: {gpu_config['gpu_threshold_mb']}MB"
            self.log_message(config_info)

        # 禁用按钮
        self.encrypt_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # 重置进度
        self.progress_bar.setValue(0)

        # 启动工作线程
        self.worker = EncryptionWorker(input_path, output_path, profile, threading_config, gpu_config)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.status_label.setText)
        self.worker.finished.connect(self.encryption_finished)
        self.worker.error.connect(self.encryption_error)
        self.worker.start()

    def cancel_encryption(self):
        """取消加密"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.encrypt_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("已取消")

    def encryption_finished(self, result):
        """加密完成"""
        self.encrypt_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if result['success']:
            # 基础信息
            message = (f"加密完成！\n\n"
                      f"加密文件: {result['encrypted_file']}\n"
                      f"解密器: {result['decryptor_file']}\n"
                      f"耗时: {result['encryption_time']:.2f} 秒")

            # 如果启用了性能监控，显示详细信息
            if self.show_performance_checkbox.isChecked():
                try:
                    perf_info = self.worker.encryptor.get_performance_info()
                    message += (f"\n\n性能统计:\n"
                               f"CPU核心: {perf_info['cpu_cores']}\n"
                               f"使用线程: {perf_info['max_threads']}\n"
                               f"并行阈值: {perf_info['parallel_threshold_mb']:.1f}MB")

                    # 计算吞吐量
                    if result['encryption_time'] > 0:
                        throughput = result['original_size'] / result['encryption_time'] / (1024 * 1024)
                        message += f"\n吞吐量: {throughput:.1f} MB/s"

                except Exception as e:
                    self.log_message(f"获取性能信息失败: {e}")

            QMessageBox.information(self, "成功", message)

            if self.auto_open_checkbox.isChecked():
                import subprocess
                subprocess.Popen(f'explorer "{os.path.dirname(result["encrypted_file"])}"')
        else:
            QMessageBox.critical(self, "错误", f"加密失败: {result['error']}")

    def encryption_error(self, error_msg):
        """加密错误"""
        self.encrypt_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.critical(self, "错误", f"加密过程中发生错误: {error_msg}")

    def refresh_decryptors(self):
        """刷新解密器列表"""
        self.decryptor_list.clear()
        # 这里可以扫描常见目录查找解密器
        self.decryptor_list.addItem("暂无可用的解密器")

    def log_message(self, message):
        """添加日志消息"""
        self.log_text.append(f"[{QTimer().remainingTime()}] {message}")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "文件加密系统 v1.0.0\n\n"
            "企业级数据保护解决方案\n"
            "支持多种加密算法和安全保护机制"
        )


if __name__ == "__main__":
    if not GUI_AVAILABLE:
        print("错误: 没有可用的GUI库")
        print("请安装: pip install PyQt6 或 pip install PySide6")
        sys.exit(1)

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("文件加密系统")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
