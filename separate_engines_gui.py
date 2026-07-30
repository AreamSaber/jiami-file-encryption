#!/usr/bin/env python3
"""
CPU/GPU分离式加密引擎GUI界面
让用户可以自由选择使用CPU加密或GPU加密，显示对应的算法，创建对应的解密器
"""

import os
import sys
import time
import pickle
import multiprocessing
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 检查GUI库
GUI_AVAILABLE = False
GUI_FRAMEWORK = None

try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                QHBoxLayout, QGridLayout, QFormLayout, QGroupBox,
                                QLabel, QPushButton, QRadioButton, QButtonGroup,
                                QComboBox, QTextEdit, QProgressBar, QFileDialog,
                                QMessageBox, QTabWidget, QCheckBox, QSpinBox,
                                QListWidget, QListWidgetItem, QSplitter)
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
    GUI_AVAILABLE = True
    GUI_FRAMEWORK = "PyQt6"
    print("✅ PyQt6 导入成功")
except ImportError as e:
    print(f"PyQt6 导入失败: {e}")
    try:
        from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                      QHBoxLayout, QGridLayout, QFormLayout, QGroupBox,
                                      QLabel, QPushButton, QRadioButton, QButtonGroup,
                                      QComboBox, QTextEdit, QProgressBar, QFileDialog,
                                      QMessageBox, QTabWidget, QCheckBox, QSpinBox,
                                      QListWidget, QListWidgetItem, QSplitter)
        from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QTimer
        from PySide6.QtGui import QFont, QIcon, QPixmap, QColor
        GUI_AVAILABLE = True
        GUI_FRAMEWORK = "PySide6"
        print("✅ PySide6 导入成功")
    except ImportError as e2:
        GUI_AVAILABLE = False
        print(f"❌ GUI库导入失败:")
        print(f"   PyQt6: {e}")
        print(f"   PySide6: {e2}")
        print("请安装: pip install PyQt6 或 pip install PySide6")

if GUI_AVAILABLE:
    try:
        from src.encryptor.pure_cpu_engine import PureCPUEngine
        from src.encryptor.pure_gpu_only_engine import PureGPUOnlyEngine
        from src.encryptor.key_injector import KeyInjector
        from src.utils.logger import Logger
        print("✅ 项目模块导入成功")
    except ImportError as e:
        print(f"❌ 项目模块导入失败: {e}")
        print("请确保在项目根目录运行此脚本")
        GUI_AVAILABLE = False


class EncryptionWorker(QThread):
    """加密工作线程"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, input_file: str, output_dir: str, engine_type: str,
                 security_level: int, parent=None):
        super().__init__(parent)
        self.input_file = input_file
        self.output_dir = output_dir
        self.engine_type = engine_type
        self.security_level = security_level
        self.logger = Logger("EncryptionWorker")

    def run(self):
        """执行加密"""
        try:
            self.progress.emit(5, "读取文件...")

            # 读取文件
            with open(self.input_file, 'rb') as f:
                file_data = f.read()

            file_size = len(file_data)
            self.progress.emit(10, f"文件读取完成: {file_size:,} 字节")

            # 创建对应的引擎
            if self.engine_type == 'cpu':
                self.progress.emit(15, "初始化CPU引擎...")
                engine = PureCPUEngine(security_level=self.security_level)
                engine_name = "纯CPU引擎"
            else:
                self.progress.emit(15, "初始化GPU引擎...")
                engine = PureGPUOnlyEngine(security_level=self.security_level)
                engine_name = "纯GPU引擎"

            self.progress.emit(20, f"{engine_name}初始化完成")

            # 执行加密
            start_time = time.time()

            def progress_callback(progress, status):
                # 将引擎进度映射到20-90范围
                mapped_progress = 20 + int(progress * 0.7)
                self.progress.emit(mapped_progress, status)

            result = engine.encrypt_with_security_level(file_data, progress_callback)

            encrypt_time = time.time() - start_time
            self.progress.emit(90, "保存加密文件...")

            # 生成文件名
            base_name = Path(self.input_file).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            encrypted_file = os.path.join(self.output_dir,
                                        f"{base_name}_{self.engine_type}_level{self.security_level}_{timestamp}.encrypted")

            # 保存加密文件
            with open(encrypted_file, 'wb') as f:
                pickle.dump(result, f)

            self.progress.emit(95, "创建解密器...")

            # 创建解密器
            decryptor_file = self._create_decryptor(encrypted_file, result)

            self.progress.emit(100, "加密完成！")

            # 返回结果
            result_info = {
                'success': True,
                'engine_type': self.engine_type,
                'security_level': self.security_level,
                'encryption_time': encrypt_time,
                'file_size': file_size,
                'encrypted_size': len(result['encrypted_data']),
                'encrypted_file': encrypted_file,
                'decryptor_file': decryptor_file,
                'engine_info': result.get('metadata', {})
            }

            self.finished.emit(result_info)

        except Exception as e:
            self.logger.error(f"加密失败: {e}")
            self.error.emit(str(e))

    def _create_decryptor(self, encrypted_file: str, encryption_result: dict) -> str:
        """创建对应的专用解密器（仅使用专用模板）"""
        try:
            base_name = os.path.splitext(encrypted_file)[0]

            # 生成解密器文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            decryptor_py_file = base_name + f"_{self.engine_type}_decryptor_{timestamp}.py"
            decryptor_exe_file = base_name + f"_{self.engine_type}_decryptor_{timestamp}.exe"

            # 使用KeyInjector创建专业的解密器
            from src.encryptor.key_injector import KeyInjector

            # 准备解密元数据
            metadata = {
                'engine_type': f'pure_{self.engine_type}',
                'security_level': self.security_level,
                'encryption_time': encryption_result.get('encryption_time', 0),
                'file_size': encryption_result.get('file_size', 0),
                'encrypted_size': encryption_result.get('encrypted_size', 0),
                'layers': encryption_result.get('layers', []),
                'algorithm_info': encryption_result.get('algorithm_info', {}),
                'decryptor_type': self.engine_type,
                'created_time': datetime.now().isoformat(),
                'version': '1.0'
            }

            # 创建KeyInjector实例
            key_injector = KeyInjector()

            # 设置专用模板路径
            if self.engine_type == 'cpu':
                specialized_template = "src/decryptor/cpu_template.py"
                template_name = "CPU专用模板"
            else:
                specialized_template = "src/decryptor/gpu_template.py"
                template_name = "GPU专用模板"

            # 检查专用模板是否存在
            if not os.path.exists(specialized_template):
                self.logger.error(f"{template_name}不存在: {specialized_template}")
                raise FileNotFoundError(f"{template_name}文件不存在")

            # 使用专用模板
            original_template_path = key_injector.template_path
            key_injector.template_path = specialized_template

            self.logger.info(f"使用{template_name}: {specialized_template}")

            try:
                # 创建Python解密器
                self.logger.info(f"创建{self.engine_type.upper()}专用解密器...")

                if not key_injector.create_decryptor(metadata, decryptor_py_file):
                    raise Exception(f"{template_name}Python解密器创建失败")

                self.logger.info(f"Python解密器创建成功: {decryptor_py_file}")

                # 创建可执行解密器
                self.logger.info("正在创建exe解密器...")

                if key_injector.create_executable_decryptor(metadata, decryptor_exe_file):
                    self.logger.info(f"exe解密器创建成功: {decryptor_exe_file}")

                    # 恢复原始模板路径
                    key_injector.template_path = original_template_path

                    # 返回exe文件路径（优先）
                    return decryptor_exe_file
                else:
                    self.logger.warning("exe解密器创建失败，返回Python版本")
                    # 恢复原始模板路径
                    key_injector.template_path = original_template_path
                    return decryptor_py_file

            finally:
                # 确保恢复原始模板路径
                key_injector.template_path = original_template_path

        except Exception as e:
            self.logger.error(f"创建{self.engine_type.upper()}专用解密器失败: {e}")
            raise Exception(f"无法创建{self.engine_type.upper()}专用解密器: {e}")




class SeparateEnginesGUI(QMainWindow):
    """CPU/GPU分离式加密引擎GUI主窗口"""

    def __init__(self):
        super().__init__()
        if not GUI_AVAILABLE:
            raise ImportError("没有可用的GUI库")

        self.logger = Logger("SeparateEnginesGUI")
        self.worker = None
        self.cpu_count = multiprocessing.cpu_count()

        # 引擎信息
        self.cpu_algorithms = {}
        self.gpu_algorithms = {}

        self.init_ui()
        self.setup_connections()
        self.load_engine_info()
        self.check_gpu_availability()

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("CPU/GPU分离式加密引擎 v1.0")
        self.setGeometry(100, 100, 1000, 700)

        # 设置中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QHBoxLayout(central_widget)

        # 创建分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧控制面板
        self.create_control_panel(splitter)

        # 右侧信息面板
        self.create_info_panel(splitter)

        # 设置分割器比例
        splitter.setSizes([400, 600])

    def create_control_panel(self, parent):
        """创建左侧控制面板"""
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)

        # 文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)

        # 输入文件
        input_layout = QHBoxLayout()
        self.input_path_label = QLabel("请选择要加密的文件")
        self.input_path_label.setStyleSheet("QLabel { border: 1px solid gray; padding: 8px; }")
        self.browse_file_btn = QPushButton("选择文件")
        self.browse_file_btn.setFixedWidth(100)
        input_layout.addWidget(self.input_path_label)
        input_layout.addWidget(self.browse_file_btn)
        file_layout.addLayout(input_layout)

        # 输出目录
        output_layout = QHBoxLayout()
        self.output_path_label = QLabel("请选择输出目录")
        self.output_path_label.setStyleSheet("QLabel { border: 1px solid gray; padding: 8px; }")
        self.browse_output_btn = QPushButton("选择目录")
        self.browse_output_btn.setFixedWidth(100)
        output_layout.addWidget(self.output_path_label)
        output_layout.addWidget(self.browse_output_btn)
        file_layout.addLayout(output_layout)

        layout.addWidget(file_group)

        # 引擎选择区域
        engine_group = QGroupBox("加密引擎选择")
        engine_layout = QVBoxLayout(engine_group)

        self.engine_button_group = QButtonGroup()
        self.cpu_engine_radio = QRadioButton("纯CPU引擎")
        self.gpu_engine_radio = QRadioButton("纯GPU引擎")
        self.cpu_engine_radio.setChecked(True)

        self.engine_button_group.addButton(self.cpu_engine_radio, 0)
        self.engine_button_group.addButton(self.gpu_engine_radio, 1)

        engine_layout.addWidget(self.cpu_engine_radio)
        engine_layout.addWidget(self.gpu_engine_radio)

        # 引擎状态显示
        self.engine_status_label = QLabel("CPU引擎: 可用")
        self.engine_status_label.setStyleSheet("color: green; font-weight: bold;")
        engine_layout.addWidget(self.engine_status_label)

        layout.addWidget(engine_group)

        # 安全级别选择
        security_group = QGroupBox("安全级别")
        security_layout = QFormLayout(security_group)

        self.security_level_combo = QComboBox()
        self.security_level_combo.addItems([
            "1 - 基础安全",
            "2 - 标准安全",
            "3 - 高级安全",
            "4 - 专业安全",
            "5 - 极限安全"
        ])
        self.security_level_combo.setCurrentIndex(1)

        security_layout.addRow("安全级别:", self.security_level_combo)

        # 安全级别描述
        self.security_description = QLabel("双层加密，平衡性能和安全性")
        self.security_description.setStyleSheet("color: gray; font-style: italic;")
        security_layout.addRow("描述:", self.security_description)

        layout.addWidget(security_group)

        # 操作按钮
        button_layout = QHBoxLayout()
        self.encrypt_btn = QPushButton("开始加密")
        self.encrypt_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 12px; }")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setEnabled(False)

        button_layout.addWidget(self.encrypt_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # 进度显示
        progress_group = QGroupBox("进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.status_label = QLabel("就绪")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        layout.addWidget(progress_group)

        # 添加弹性空间
        layout.addStretch()

        parent.addWidget(control_widget)

    def create_info_panel(self, parent):
        """创建右侧信息面板"""
        info_widget = QWidget()
        layout = QVBoxLayout(info_widget)

        # 创建标签页
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 算法信息标签页
        self.create_algorithms_tab()

        # 系统信息标签页
        self.create_system_tab()

        # 日志标签页
        self.create_log_tab()

        parent.addWidget(info_widget)

    def create_algorithms_tab(self):
        """创建算法信息标签页"""
        algorithms_widget = QWidget()
        layout = QVBoxLayout(algorithms_widget)

        # 当前选择的引擎信息
        current_group = QGroupBox("当前引擎信息")
        current_layout = QFormLayout(current_group)

        self.current_engine_label = QLabel("纯CPU引擎")
        self.current_engine_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        current_layout.addRow("引擎类型:", self.current_engine_label)

        self.current_security_label = QLabel("标准安全 (级别2)")
        current_layout.addRow("安全级别:", self.current_security_label)

        self.current_algorithms_label = QLabel("ChaCha20, AES-256")
        current_layout.addRow("算法组合:", self.current_algorithms_label)

        self.current_description_label = QLabel("双层加密，平衡性能和安全性")
        self.current_description_label.setWordWrap(True)
        current_layout.addRow("描述:", self.current_description_label)

        layout.addWidget(current_group)

        # 支持的算法列表
        algorithms_group = QGroupBox("支持的算法")
        algorithms_layout = QVBoxLayout(algorithms_group)

        self.algorithms_list = QListWidget()
        self.algorithms_list.setMaximumHeight(200)
        algorithms_layout.addWidget(self.algorithms_list)

        layout.addWidget(algorithms_group)

        # 性能预估
        performance_group = QGroupBox("性能预估")
        performance_layout = QFormLayout(performance_group)

        self.estimated_speed_label = QLabel("~300 MB/s")
        performance_layout.addRow("预估速度:", self.estimated_speed_label)

        self.estimated_layers_label = QLabel("2层")
        performance_layout.addRow("加密层数:", self.estimated_layers_label)

        self.estimated_security_label = QLabel("高")
        performance_layout.addRow("安全强度:", self.estimated_security_label)

        layout.addWidget(performance_group)

        self.tab_widget.addTab(algorithms_widget, "算法信息")

    def create_system_tab(self):
        """创建系统信息标签页"""
        system_widget = QWidget()
        layout = QVBoxLayout(system_widget)

        # CPU信息
        cpu_group = QGroupBox("CPU信息")
        cpu_layout = QFormLayout(cpu_group)

        cpu_layout.addRow("CPU核心数:", QLabel(str(self.cpu_count)))
        cpu_layout.addRow("CPU引擎状态:", QLabel("可用"))

        layout.addWidget(cpu_group)

        # GPU信息
        gpu_group = QGroupBox("GPU信息")
        gpu_layout = QFormLayout(gpu_group)

        self.gpu_status_label = QLabel("检测中...")
        gpu_layout.addRow("GPU状态:", self.gpu_status_label)

        self.gpu_device_label = QLabel("未知")
        gpu_layout.addRow("GPU设备:", self.gpu_device_label)

        self.gpu_memory_label = QLabel("未知")
        gpu_layout.addRow("GPU内存:", self.gpu_memory_label)

        layout.addWidget(gpu_group)

        # 系统信息
        system_group = QGroupBox("系统信息")
        system_layout = QFormLayout(system_group)

        system_layout.addRow("GUI框架:", QLabel(GUI_FRAMEWORK))
        system_layout.addRow("Python版本:", QLabel(f"{sys.version_info.major}.{sys.version_info.minor}"))

        layout.addWidget(system_group)

        # 添加弹性空间
        layout.addStretch()

        self.tab_widget.addTab(system_widget, "系统信息")

    def create_log_tab(self):
        """创建日志标签页"""
        log_widget = QWidget()
        layout = QVBoxLayout(log_widget)

        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)

        # 日志控制
        log_control_layout = QHBoxLayout()

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.setFixedWidth(100)
        log_control_layout.addWidget(self.clear_log_btn)
        log_control_layout.addStretch()

        layout.addLayout(log_control_layout)

        self.tab_widget.addTab(log_widget, "日志")

    def setup_connections(self):
        """设置信号连接"""
        self.browse_file_btn.clicked.connect(self.browse_input_file)
        self.browse_output_btn.clicked.connect(self.browse_output_dir)
        self.encrypt_btn.clicked.connect(self.start_encryption)
        self.cancel_btn.clicked.connect(self.cancel_encryption)

        # 引擎选择变化
        self.engine_button_group.buttonClicked.connect(self.on_engine_changed)

        # 安全级别变化
        self.security_level_combo.currentIndexChanged.connect(self.on_security_level_changed)

        # 日志控制
        self.clear_log_btn.clicked.connect(self.clear_log)

    def load_engine_info(self):
        """加载引擎信息"""
        try:
            # 加载CPU引擎信息
            for level in range(1, 6):
                cpu_engine = PureCPUEngine(security_level=level)
                self.cpu_algorithms[level] = {
                    'name': cpu_engine.encryption_name,
                    'algorithms': cpu_engine.current_algorithms,
                    'description': cpu_engine.encryption_description,
                    'supported_algorithms': cpu_engine.get_supported_algorithms()
                }

            # 加载GPU引擎信息
            try:
                for level in range(1, 6):
                    gpu_engine = PureGPUOnlyEngine(security_level=level)
                    self.gpu_algorithms[level] = {
                        'name': gpu_engine.encryption_name,
                        'algorithms': gpu_engine.algorithm_list,
                        'description': gpu_engine.description,
                        'supported_algorithms': ['aes256', 'chacha20', 'salsa20', 'matrix_cipher', 'blowfish']
                    }
            except Exception as e:
                self.log_message(f"GPU引擎信息加载失败: {e}")

            self.log_message("引擎信息加载完成")

        except Exception as e:
            self.log_message(f"引擎信息加载失败: {e}")

    def check_gpu_availability(self):
        """检查GPU可用性"""
        try:
            import os
            os.environ['PYOPENCL_CTX'] = '0'

            from src.gpu.gpu_manager import gpu_manager

            gpu_info = gpu_manager.get_performance_info()

            if gpu_info['gpu_available']:
                device_name = gpu_info.get('device_name', 'AMD GPU')
                memory_info = gpu_info.get('memory_info', {})
                memory_gb = memory_info.get('total', 0) // 1024 // 1024 // 1024

                self.gpu_status_label.setText("可用")
                self.gpu_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.gpu_device_label.setText(device_name)
                self.gpu_memory_label.setText(f"{memory_gb}GB")

                self.gpu_engine_radio.setEnabled(True)
                self.log_message(f"GPU检测成功: {device_name} ({memory_gb}GB)")

            else:
                self.gpu_status_label.setText("不可用")
                self.gpu_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.gpu_device_label.setText("无")
                self.gpu_memory_label.setText("N/A")

                self.gpu_engine_radio.setEnabled(False)
                self.log_message("GPU不可用，GPU引擎已禁用")

        except Exception as e:
            self.gpu_status_label.setText("检测失败")
            self.gpu_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.gpu_device_label.setText("错误")
            self.gpu_memory_label.setText("N/A")

            self.gpu_engine_radio.setEnabled(False)
            self.log_message(f"GPU检测失败: {e}")

    def on_engine_changed(self):
        """引擎选择变化"""
        if self.cpu_engine_radio.isChecked():
            self.current_engine_label.setText("纯CPU引擎")
            self.engine_status_label.setText("CPU引擎: 可用")
            self.engine_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.current_engine_label.setText("纯GPU引擎")
            if self.gpu_engine_radio.isEnabled():
                self.engine_status_label.setText("GPU引擎: 可用")
                self.engine_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.engine_status_label.setText("GPU引擎: 不可用")
                self.engine_status_label.setStyleSheet("color: red; font-weight: bold;")

        self.update_algorithm_info()

    def on_security_level_changed(self):
        """安全级别变化"""
        self.update_algorithm_info()

    def update_algorithm_info(self):
        """更新算法信息显示"""
        try:
            level = self.security_level_combo.currentIndex() + 1

            if self.cpu_engine_radio.isChecked():
                engine_info = self.cpu_algorithms.get(level, {})
                engine_type = "CPU"
            else:
                engine_info = self.gpu_algorithms.get(level, {})
                engine_type = "GPU"

            if engine_info:
                # 更新当前引擎信息
                self.current_security_label.setText(f"{self.security_level_combo.currentText()}")
                self.current_algorithms_label.setText(", ".join(engine_info.get('algorithms', [])))
                self.current_description_label.setText(engine_info.get('description', ''))

                # 更新算法列表
                self.algorithms_list.clear()
                supported_algorithms = engine_info.get('supported_algorithms', [])
                for algorithm in supported_algorithms:
                    item = QListWidgetItem(f"✓ {algorithm}")
                    if algorithm in engine_info.get('algorithms', []):
                        item.setBackground(Qt.GlobalColor.lightGray)
                    self.algorithms_list.addItem(item)

                # 更新性能预估
                layer_count = len(engine_info.get('algorithms', []))
                self.estimated_layers_label.setText(f"{layer_count}层")

                if engine_type == "CPU":
                    speed = max(100, 500 - layer_count * 50)
                    self.estimated_speed_label.setText(f"~{speed} MB/s")
                else:
                    speed = max(200, 800 - layer_count * 100)
                    self.estimated_speed_label.setText(f"~{speed} MB/s")

                security_levels = ["低", "中", "高", "很高", "极高"]
                self.estimated_security_label.setText(security_levels[min(level-1, 4)])

        except Exception as e:
            self.log_message(f"更新算法信息失败: {e}")

    def browse_input_file(self):
        """浏览输入文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要加密的文件", "", "所有文件 (*.*)"
        )
        if file_path:
            self.input_path_label.setText(file_path)
            file_size = os.path.getsize(file_path)
            self.log_message(f"选择输入文件: {os.path.basename(file_path)} ({file_size:,} 字节)")

    def browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_path_label.setText(dir_path)
            self.log_message(f"选择输出目录: {dir_path}")

    def start_encryption(self):
        """开始加密"""
        # 验证输入
        input_path = self.input_path_label.text()
        output_path = self.output_path_label.text()

        if input_path == "请选择要加密的文件":
            QMessageBox.warning(self, "警告", "请选择要加密的文件")
            return

        if output_path == "请选择输出目录":
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return

        if not os.path.exists(input_path):
            QMessageBox.warning(self, "警告", "输入文件不存在")
            return

        if not os.path.exists(output_path):
            QMessageBox.warning(self, "警告", "输出目录不存在")
            return

        # 检查GPU引擎可用性
        if self.gpu_engine_radio.isChecked() and not self.gpu_engine_radio.isEnabled():
            QMessageBox.warning(self, "警告", "GPU引擎不可用，请选择CPU引擎")
            return

        # 获取配置
        engine_type = 'cpu' if self.cpu_engine_radio.isChecked() else 'gpu'
        security_level = self.security_level_combo.currentIndex() + 1

        # 禁用控件
        self.encrypt_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.browse_file_btn.setEnabled(False)
        self.browse_output_btn.setEnabled(False)
        self.cpu_engine_radio.setEnabled(False)
        self.gpu_engine_radio.setEnabled(False)
        self.security_level_combo.setEnabled(False)

        # 重置进度
        self.progress_bar.setValue(0)
        self.status_label.setText("准备加密...")

        engine_name = "CPU" if engine_type == 'cpu' else "GPU"
        self.log_message(f"开始{engine_name}加密 - 安全级别{security_level}")

        # 启动工作线程
        self.worker = EncryptionWorker(input_path, output_path, engine_type, security_level)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_encryption_finished)
        self.worker.error.connect(self.on_encryption_error)
        self.worker.start()

    def cancel_encryption(self):
        """取消加密"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.reset_ui_state()
        self.status_label.setText("已取消")
        self.log_message("加密已取消")

    def on_progress(self, value: int, status: str):
        """进度更新"""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)

    def on_encryption_finished(self, result: dict):
        """加密完成"""
        self.reset_ui_state()

        if result['success']:
            engine_type = result['engine_type'].upper()
            self.log_message(f"🎉 {engine_type}加密成功！")
            self.log_message(f"   引擎类型: {engine_type}")
            self.log_message(f"   安全级别: {result['security_level']}")
            self.log_message(f"   加密时间: {result['encryption_time']:.3f}秒")
            self.log_message(f"   原始大小: {result['file_size']:,} 字节")
            self.log_message(f"   加密大小: {result['encrypted_size']:,} 字节")
            self.log_message(f"   加密文件: {os.path.basename(result['encrypted_file'])}")

            # 显示解密器信息
            decryptor_file = result['decryptor_file']
            if decryptor_file:
                decryptor_name = os.path.basename(decryptor_file)
                decryptor_type = "exe解密器" if decryptor_file.endswith('.exe') else "Python解密器"
                self.log_message(f"   {decryptor_type}: {decryptor_name}")

                # 检查文件大小
                if os.path.exists(decryptor_file):
                    decryptor_size = os.path.getsize(decryptor_file)
                    self.log_message(f"   解密器大小: {decryptor_size:,} 字节")

            # 显示引擎特定信息
            engine_info = result.get('engine_info', {})
            if engine_info:
                self.log_message(f"   算法层数: {engine_info.get('layers', 'unknown')}")
                if engine_type == 'GPU':
                    self.log_message(f"   GPU专用: {engine_info.get('gpu_only', 'unknown')}")

            # 显示成功对话框
            decryptor_info = ""
            if decryptor_file:
                decryptor_name = os.path.basename(decryptor_file)
                decryptor_type = "exe解密器" if decryptor_file.endswith('.exe') else "Python解密器"
                decryptor_info = f"{decryptor_type}: {decryptor_name}\n"

            QMessageBox.information(
                self, "加密完成",
                f"🎉 {engine_type}加密成功！\n\n"
                f"📁 加密文件: {os.path.basename(result['encrypted_file'])}\n"
                f"🔓 {decryptor_info}"
                f"⏱️ 加密时间: {result['encryption_time']:.3f}秒\n"
                f"🔒 安全级别: {result['security_level']}\n"
                f"📊 压缩比: {(1 - result['encrypted_size']/result['file_size'])*100:.1f}%"
            )
        else:
            self.log_message("❌ 加密失败")

    def on_encryption_error(self, error_msg: str):
        """加密错误"""
        self.reset_ui_state()

        self.status_label.setText("加密失败")
        self.log_message(f"❌ 加密错误: {error_msg}")

        # 检查是否是解密器模板相关错误
        if "专用解密器" in error_msg or "模板" in error_msg:
            error_title = "解密器创建失败"
            error_detail = f"无法创建专用解密器:\n{error_msg}\n\n请检查解密器模板文件是否存在。"
        else:
            error_title = "加密失败"
            error_detail = f"加密过程中发生错误:\n{error_msg}"

        QMessageBox.critical(self, error_title, error_detail)

    def reset_ui_state(self):
        """重置UI状态"""
        self.encrypt_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.browse_file_btn.setEnabled(True)
        self.browse_output_btn.setEnabled(True)
        self.cpu_engine_radio.setEnabled(True)
        if self.gpu_status_label.text() == "可用":
            self.gpu_engine_radio.setEnabled(True)
        self.security_level_combo.setEnabled(True)

    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.log_message("日志已清空")

    def log_message(self, message: str):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    """主函数"""
    if not GUI_AVAILABLE:
        print("错误: 没有可用的GUI库")
        print("请安装: pip install PyQt6 或 pip install PySide6")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("CPU/GPU分离式加密引擎")
    app.setApplicationVersion("1.0.0")

    # 创建主窗口
    try:
        window = SeparateEnginesGUI()
        window.show()

        # 添加欢迎消息
        window.log_message("🚀 CPU/GPU分离式加密引擎启动成功")
        window.log_message("💡 选择CPU引擎使用纯CPU算法，选择GPU引擎使用纯GPU算法")
        window.log_message("🔧 每种引擎都会创建对应的专用解密器")

        # 初始化算法信息显示
        window.update_algorithm_info()

        sys.exit(app.exec())

    except Exception as e:
        print(f"❌ GUI启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
