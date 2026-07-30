#!/usr/bin/env python3
"""
GPU文件加密器
集成纯GPU加密算法，支持文件加密和解密
"""

import os
import sys
import time
import pickle
from datetime import datetime
from typing import Dict, Any, Optional, Callable

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.encryptor.pure_gpu_only_engine import PureGPUOnlyEngine
from src.encryptor.key_injector import KeyInjector
from src.utils.logger import Logger


class GPUFileEncryptor:
    """GPU文件加密器（支持自动降级到CPU）"""

    def __init__(self, allow_fallback: bool = True):
        """
        初始化GPU文件加密器
        
        Args:
            allow_fallback: 是否允许在GPU不可用时降级到CPU模式
        """
        self.logger = Logger("GPUFileEncryptor")
        self.logger.info("GPU文件加密器初始化")
        self.allow_fallback = allow_fallback
        self.using_fallback = False

        # 检查GPU可用性
        try:
            from src.gpu.gpu_manager import gpu_manager
            if not gpu_manager.is_gpu_available():
                raise Exception("GPU不可用")
            self.gpu_available = True
            self.gpu_manager = gpu_manager
            self.logger.info("✅ GPU可用")
        except Exception as e:
            self.gpu_available = False
            self.logger.warning(f"⚠️ GPU不可用: {e}")
            
            if allow_fallback:
                self.logger.warning("⚠️ 将使用CPU模式作为降级方案")
                self.using_fallback = True
            else:
                self.logger.error(f"GPU初始化失败且不允许降级: {e}")
                raise Exception(f"GPU文件加密器启动失败: {e}")

    def encrypt_file(self, input_file: str, output_dir: str = ".",
                    security_level: int = 3, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        加密文件

        Args:
            input_file: 输入文件路径
            output_dir: 输出目录
            security_level: 安全级别 (1-5)
            progress_callback: 进度回调函数

        Returns:
            加密结果字典
        """
        try:
            start_time = time.time()

            # 验证输入文件
            if not os.path.exists(input_file):
                raise Exception(f"输入文件不存在: {input_file}")

            file_size = os.path.getsize(input_file)
            self.logger.info(f"开始GPU加密文件: {input_file}")
            self.logger.info(f"文件大小: {file_size:,} 字节 ({file_size/1024/1024:.2f} MB)")
            self.logger.info(f"安全级别: {security_level}")

            if progress_callback:
                progress_callback(0, "读取文件...")

            # 读取文件内容
            with open(input_file, 'rb') as f:
                file_data = f.read()

            self.logger.info(f"文件读取完成: {len(file_data):,} 字节")

            if progress_callback:
                progress_callback(10, "初始化加密引擎...")

            # 根据GPU可用性选择引擎
            if self.gpu_available and not self.using_fallback:
                try:
                    # 创建GPU引擎
                    gpu_engine = PureGPUOnlyEngine(security_level=security_level)
                    engine_type = "GPU"
                    if progress_callback:
                        progress_callback(20, "开始GPU加密...")
                except Exception as e:
                    if self.allow_fallback:
                        self.logger.warning(f"⚠️ GPU引擎初始化失败，降级到CPU: {e}")
                        self.using_fallback = True
                        return self._encrypt_with_cpu_fallback(
                            file_data, input_file, output_dir, 
                            security_level, progress_callback, start_time
                        )
                    else:
                        raise
            else:
                # 使用CPU降级模式
                return self._encrypt_with_cpu_fallback(
                    file_data, input_file, output_dir,
                    security_level, progress_callback, start_time
                )

            if progress_callback:
                progress_callback(20, "开始GPU加密...")

            # 执行GPU加密
            encrypt_start = time.time()
            result = gpu_engine.encrypt_with_security_level(file_data, progress_callback)
            encrypt_time = time.time() - encrypt_start

            self.logger.info(f"GPU加密完成 - 耗时: {encrypt_time:.2f}秒")

            if progress_callback:
                progress_callback(90, "保存加密文件...")

            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)

            # 生成输出文件名
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            encrypted_file = os.path.join(output_dir, f"{base_name}_gpu_encrypted_{timestamp}.encrypted")
            decryptor_file = os.path.join(output_dir, f"gpu_decryptor_{timestamp}.py")

            # 准备加密包 - 确保original_size同时存在于顶层和metadata中
            metadata = result['metadata'].copy()
            metadata['original_size'] = file_size  # 添加到metadata中供解密器使用
            
            encrypted_package = {
                'encrypted_data': result['encrypted_data'],
                'metadata': metadata,
                'original_filename': os.path.basename(input_file),
                'original_size': file_size,  # 保留顶层兼容性
                'encryption_time': encrypt_time,
                'encryption_date': datetime.now().isoformat(),
                'engine_type': 'pure_gpu_only',
                'version': '1.0'
            }

            # 保存加密文件
            with open(encrypted_file, 'wb') as f:
                pickle.dump(encrypted_package, f)

            self.logger.info(f"加密文件已保存: {encrypted_file}")

            # 生成解密器（包含exe文件）- 使用包含original_size的metadata
            exe_file = self._generate_decryptor(decryptor_file, metadata)

            total_time = time.time() - start_time

            if progress_callback:
                progress_callback(100, "加密完成")

            # 计算性能统计
            speed_mbps = file_size / 1024 / 1024 / encrypt_time

            result_info = {
                'success': True,
                'encrypted_file': encrypted_file,
                'decryptor_file': decryptor_file,
                'decryptor_exe': exe_file,
                'original_size': file_size,
                'encrypted_size': len(result['encrypted_data']),
                'encryption_time': encrypt_time,
                'total_time': total_time,
                'speed_mbps': speed_mbps,
                'security_level': security_level,
                'layers': result['metadata']['total_layers'],
                'gpu_only': result['metadata']['gpu_only'],
                'engine_name': result['metadata']['encryption_name']
            }

            self.logger.info(f"GPU文件加密完成:")
            self.logger.info(f"  - 加密速度: {speed_mbps:.2f} MB/s")
            self.logger.info(f"  - 总耗时: {total_time:.2f}秒")
            self.logger.info(f"  - 加密层数: {result['metadata']['total_layers']}")
            self.logger.info(f"  - GPU专用: {result['metadata']['gpu_only']}")

            return result_info

        except Exception as e:
            self.logger.error(f"GPU文件加密失败: {e}")
            
            # 尝试降级到CPU
            if self.allow_fallback and not self.using_fallback:
                self.logger.warning(f"⚠️ GPU加密失败，尝试降级到CPU模式: {e}")
                self.using_fallback = True
                try:
                    return self._encrypt_with_cpu_fallback(
                        file_data, input_file, output_dir,
                        security_level, progress_callback, start_time
                    )
                except Exception as fallback_error:
                    self.logger.error(f"CPU降级也失败: {fallback_error}")
            
            if progress_callback:
                progress_callback(0, f"加密失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _encrypt_with_cpu_fallback(self, file_data: bytes, input_file: str, 
                                   output_dir: str, security_level: int,
                                   progress_callback: Optional[Callable],
                                   start_time: float) -> Dict[str, Any]:
        """
        使用CPU作为降级方案进行加密
        
        Args:
            file_data: 文件数据
            input_file: 输入文件路径
            output_dir: 输出目录
            security_level: 安全级别
            progress_callback: 进度回调
            start_time: 开始时间
            
        Returns:
            加密结果字典
        """
        self.logger.warning("⚠️ 使用CPU降级模式进行加密")
        
        if progress_callback:
            progress_callback(20, "使用CPU降级模式加密...")
        
        try:
            from src.encryptor.main import FileEncryptor
            
            # 创建CPU加密器
            cpu_encryptor = FileEncryptor()
            
            # 根据安全级别选择配置
            profile_map = {
                1: 'basic',
                2: 'standard', 
                3: 'high',
                4: 'paranoid',
                5: 'paranoid'
            }
            profile = profile_map.get(security_level, 'standard')
            
            if progress_callback:
                progress_callback(30, f"CPU加密中 (配置: {profile})...")
            
            # 执行CPU加密
            result = cpu_encryptor.encrypt_file(input_file, output_dir, profile)
            
            if result.get('success'):
                total_time = time.time() - start_time
                file_size = len(file_data)
                encrypt_time = result.get('encryption_time', total_time)
                speed_mbps = file_size / 1024 / 1024 / encrypt_time if encrypt_time > 0 else 0
                
                if progress_callback:
                    progress_callback(100, "CPU降级加密完成")
                
                self.logger.info(f"✅ CPU降级加密完成")
                self.logger.info(f"  - 加密速度: {speed_mbps:.2f} MB/s")
                
                return {
                    'success': True,
                    'encrypted_file': result['encrypted_file'],
                    'decryptor_file': result['decryptor_file'],
                    'decryptor_exe': None,
                    'original_size': file_size,
                    'encrypted_size': result['encrypted_size'],
                    'encryption_time': encrypt_time,
                    'total_time': total_time,
                    'speed_mbps': speed_mbps,
                    'security_level': security_level,
                    'layers': 0,  # CPU模式不返回层数
                    'gpu_only': False,
                    'engine_name': f'CPU降级模式 ({profile})',
                    'fallback_used': True
                }
            else:
                raise Exception(result.get('error', 'CPU加密失败'))
                
        except Exception as e:
            self.logger.error(f"CPU降级加密失败: {e}")
            raise

    def _generate_decryptor(self, decryptor_file: str, metadata: Dict) -> str:
        """
        生成GPU解密器（包含Python脚本和exe文件）

        Args:
            decryptor_file: Python解密器文件路径
            metadata: 加密元数据

        Returns:
            exe文件路径
        """
        try:
            # 1. 生成Python解密器
            self.logger.info("开始生成GPU解密器...")
            decryptor_code = self._create_decryptor_code(metadata)

            with open(decryptor_file, 'w', encoding='utf-8') as f:
                f.write(decryptor_code)

            # 设置可执行权限
            try:
                os.chmod(decryptor_file, 0o755)
            except:
                pass

            self.logger.info(f"✅ GPU Python解密器已生成: {decryptor_file}")

            # 2. 使用KeyInjector生成exe解密器
            try:
                self.logger.info("开始使用KeyInjector生成GPU exe解密器...")

                # 创建KeyInjector实例
                injector = KeyInjector()

                # 生成exe文件路径
                exe_file = decryptor_file.replace('.py', '.exe')

                # 调用KeyInjector生成exe
                success = injector.create_executable_decryptor(metadata, exe_file)

                if success and os.path.exists(exe_file):
                    exe_size = os.path.getsize(exe_file)
                    self.logger.info(f"✅ GPU exe解密器已生成: {exe_file}")
                    self.logger.info(f"   - exe文件大小: {exe_size:,} 字节 ({exe_size/1024/1024:.1f} MB)")

                    # 生成辅助文件信息
                    self._log_auxiliary_files(exe_file)

                    return exe_file
                else:
                    self.logger.warning("KeyInjector生成exe失败，保留Python解密器")
                    return None

            except Exception as e:
                self.logger.warning(f"KeyInjector生成exe失败: {e}")
                self.logger.info("保留Python解密器，用户可手动运行")
                return None

        except Exception as e:
            self.logger.error(f"生成GPU解密器失败: {e}")
            raise

    def _log_auxiliary_files(self, exe_file: str):
        """记录辅助文件信息"""
        try:
            base_path = exe_file.replace('.exe', '')

            # 检查批处理文件
            bat_file = base_path + '.bat'
            if os.path.exists(bat_file):
                self.logger.info(f"   - 批处理文件: {os.path.basename(bat_file)}")

            # 检查说明文件
            readme_file = base_path + '_README.txt'
            if os.path.exists(readme_file):
                self.logger.info(f"   - 使用说明: {os.path.basename(readme_file)}")

            # 检查Python文件
            py_file = base_path + '.py'
            if os.path.exists(py_file):
                py_size = os.path.getsize(py_file)
                self.logger.info(f"   - Python脚本: {os.path.basename(py_file)} ({py_size:,} 字节)")

        except Exception as e:
            self.logger.debug(f"记录辅助文件信息失败: {e}")

    def _create_decryptor_code(self, metadata: Dict) -> str:
        """创建GPU解密器代码"""
        layers = metadata.get('layers', [])
        security_level = metadata.get('security_level', 1)
        engine_name = metadata.get('encryption_name', 'GPU加密')

        decryptor_code = f'''#!/usr/bin/env python3
"""
GPU解密器 - 自动生成
引擎: {engine_name}
安全级别: {security_level}
加密层数: {len(layers)}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

import os
import sys
import pickle
import time
from datetime import datetime


class GPUDecryptor:
    """GPU解密器"""

    def __init__(self):
        """初始化GPU解密器"""
        self.gpu_available = self._check_gpu_availability()
        print(f"GPU状态: {{'可用' if self.gpu_available else '不可用（CPU回退）'}}")

    def _check_gpu_availability(self) -> bool:
        """检查GPU可用性"""
        try:
            # 尝试导入GPU管理器
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from src.gpu.gpu_manager import gpu_manager
            return gpu_manager.is_gpu_available()
        except:
            return False

    def decrypt_file(self, encrypted_file: str, output_file: str = None) -> bool:
        """
        解密文件

        Args:
            encrypted_file: 加密文件路径
            output_file: 输出文件路径

        Returns:
            解密是否成功
        """
        try:
            start_time = time.time()
            print(f"开始GPU解密文件: {{encrypted_file}}")

            # 读取加密文件
            with open(encrypted_file, 'rb') as f:
                encrypted_package = pickle.load(f)

            # 验证文件格式
            if not self._verify_gpu_encryption(encrypted_package):
                print("错误: 此文件不是GPU引擎加密的文件")
                return False

            # 提取数据
            metadata = encrypted_package['metadata']
            encrypted_data = encrypted_package['encrypted_data']
            original_filename = encrypted_package.get('original_filename', 'decrypted_file')

            print(f"检测到加密信息:")
            print(f"   - 引擎: {{metadata.get('encryption_name', 'Unknown')}}")
            print(f"   - 安全级别: {{metadata.get('security_level', 'Unknown')}}")
            print(f"   - 加密层数: {{len(metadata.get('layers', []))}}")
            print(f"   - GPU专用: {{metadata.get('gpu_only', False)}}")
            print(f"   - 原始文件: {{original_filename}}")

            # 逐层解密
            print(f"\\n开始逐层解密...")
            decrypted_data = self._decrypt_layers(encrypted_data, metadata['layers'])

            # 确定输出文件路径
            if output_file is None:
                output_file = self._generate_output_path(encrypted_file, original_filename)

            # 保存解密文件
            with open(output_file, 'wb') as f:
                f.write(decrypted_data)

            decrypt_time = time.time() - start_time
            speed_mbps = len(decrypted_data) / 1024 / 1024 / decrypt_time

            print(f"\\nGPU解密完成!")
            print(f"   - 解密文件: {{output_file}}")
            print(f"   - 文件大小: {{len(decrypted_data):,}} 字节")
            print(f"   - 解密耗时: {{decrypt_time:.2f}}秒")
            print(f"   - 解密速度: {{speed_mbps:.2f}} MB/s")

            return True

        except Exception as e:
            print(f"GPU解密失败: {{e}}")
            import traceback
            traceback.print_exc()
            return False

    def _verify_gpu_encryption(self, encrypted_package: dict) -> bool:
        """验证是否为GPU引擎加密"""
        try:
            required_keys = ['encrypted_data', 'metadata', 'engine_type']
            for key in required_keys:
                if key not in encrypted_package:
                    return False

            return encrypted_package.get('engine_type') == 'pure_gpu_only'
        except:
            return False

    def _decrypt_layers(self, data: bytes, layers: list) -> bytes:
        """逐层解密"""
        current_data = data

        # 反向解密（从最后一层开始）
        for i in reversed(range(len(layers))):
            layer = layers[i]
            algorithm = layer.get('algorithm', 'Unknown')

            print(f"   第{{i+1}}层: {{algorithm}}")

            try:
                if 'AES-256' in algorithm:
                    current_data = self._decrypt_aes256(current_data, layer)
                elif 'ChaCha20' in algorithm:
                    current_data = self._decrypt_chacha20(current_data, layer)
                elif 'Salsa20' in algorithm:
                    current_data = self._decrypt_salsa20(current_data, layer)
                elif 'Matrix_Cipher' in algorithm:
                    current_data = self._decrypt_matrix_cipher(current_data, layer)
                elif 'Blowfish' in algorithm:
                    current_data = self._decrypt_blowfish(current_data, layer)
                else:
                    raise Exception(f"不支持的算法: {{algorithm}}")

                print(f"      解密成功 - 数据大小: {{len(current_data):,}} 字节")

            except Exception as e:
                print(f"      解密失败: {{e}}")
                raise

        return current_data'''

        # 添加各种解密算法的实现
        decryptor_code += '''

    def _decrypt_aes256(self, data: bytes, layer: dict) -> bytes:
        """解密AES-256"""
        try:
            if self.gpu_available:
                return self._decrypt_aes256_gpu(data, layer)
            else:
                return self._decrypt_aes256_cpu(data, layer)
        except Exception as e:
            # GPU失败时回退到CPU
            return self._decrypt_aes256_cpu(data, layer)

    def _decrypt_aes256_gpu(self, data: bytes, layer: dict) -> bytes:
        """GPU解密AES-256（优先使用CPU确保兼容性）"""
        try:
            # 为了确保解密兼容性，直接使用CPU标准实现
            return self._decrypt_aes256_cpu(data, layer)

        except Exception as e:
            # 如果CPU也失败，抛出异常
            raise Exception(f"AES-256解密失败: {e}")

    def _decrypt_aes256_cpu(self, data: bytes, layer: dict) -> bytes:
        """CPU解密AES-256"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding

            key = layer['key']
            iv = layer['iv']
            mode = layer.get('mode', 'CBC')

            if mode == 'CBC':
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            elif mode == 'ECB':
                cipher = Cipher(algorithms.AES(key), modes.ECB())
            else:
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))

            decryptor = cipher.decryptor()
            decrypted_padded = decryptor.update(data) + decryptor.finalize()

            # 移除填充
            unpadder = padding.PKCS7(128).unpadder()
            decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()

            return decrypted_data

        except Exception as e:
            raise Exception(f"AES-256解密失败: {e}")

    def _decrypt_chacha20(self, data: bytes, layer: dict) -> bytes:
        """解密ChaCha20"""
        try:
            if self.gpu_available:
                return self._decrypt_chacha20_gpu(data, layer)
            else:
                return self._decrypt_chacha20_cpu(data, layer)
        except Exception as e:
            return self._decrypt_chacha20_cpu(data, layer)

    def _decrypt_chacha20_gpu(self, data: bytes, layer: dict) -> bytes:
        """GPU解密ChaCha20"""
        try:
            from src.gpu.gpu_manager import gpu_manager

            gpu_result = gpu_manager.decrypt_data(data, 'chacha20', {
                'key': layer['key'],
                'nonce': layer['nonce']
            })

            if gpu_result and 'decrypted_data' in gpu_result:
                return gpu_result['decrypted_data']
            else:
                return self._decrypt_chacha20_cpu(data, layer)

        except Exception as e:
            return self._decrypt_chacha20_cpu(data, layer)

    def _decrypt_chacha20_cpu(self, data: bytes, layer: dict) -> bytes:
        """CPU解密ChaCha20"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

            key = layer['key']
            nonce = layer['nonce']

            algorithm = algorithms.ChaCha20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()

            return decryptor.update(data) + decryptor.finalize()

        except Exception as e:
            raise Exception(f"ChaCha20解密失败: {e}")

    def _decrypt_salsa20(self, data: bytes, layer: dict) -> bytes:
        """解密Salsa20"""
        try:
            if self.gpu_available:
                return self._decrypt_salsa20_gpu(data, layer)
            else:
                return self._decrypt_salsa20_cpu(data, layer)
        except Exception as e:
            return self._decrypt_salsa20_cpu(data, layer)

    def _decrypt_salsa20_gpu(self, data: bytes, layer: dict) -> bytes:
        """GPU解密Salsa20"""
        try:
            from src.gpu.gpu_manager import gpu_manager

            gpu_result = gpu_manager.decrypt_data(data, 'salsa20', {
                'key': layer['key'],
                'nonce': layer['nonce']
            })

            if gpu_result and 'decrypted_data' in gpu_result:
                return gpu_result['decrypted_data']
            else:
                return self._decrypt_salsa20_cpu(data, layer)

        except Exception as e:
            return self._decrypt_salsa20_cpu(data, layer)

    def _decrypt_salsa20_cpu(self, data: bytes, layer: dict) -> bytes:
        """CPU解密Salsa20"""
        try:
            # 简化的Salsa20解密（与加密相同）
            key = layer['key']
            nonce = layer['nonce']

            result = bytearray()
            for i, byte in enumerate(data):
                key_byte = key[i % len(key)]
                nonce_byte = nonce[i % len(nonce)]

                # 简化的Salsa20风格解密
                keystream = key_byte ^ nonce_byte
                for _ in range(10):
                    keystream += key_byte
                    keystream ^= (keystream << 1)
                    keystream += nonce_byte
                    keystream ^= (keystream >> 1)
                    keystream = (keystream << 2) | (keystream >> 6)
                    keystream &= 0xFF

                result.append(byte ^ keystream)

            return bytes(result)

        except Exception as e:
            raise Exception(f"Salsa20解密失败: {e}")

    def _decrypt_matrix_cipher(self, data: bytes, layer: dict) -> bytes:
        """解密矩阵变换"""
        try:
            if self.gpu_available:
                return self._decrypt_matrix_cipher_gpu(data, layer)
            else:
                return self._decrypt_matrix_cipher_cpu(data, layer)
        except Exception as e:
            return self._decrypt_matrix_cipher_cpu(data, layer)

    def _decrypt_matrix_cipher_gpu(self, data: bytes, layer: dict) -> bytes:
        """GPU解密矩阵变换"""
        try:
            from src.gpu.gpu_manager import gpu_manager

            gpu_result = gpu_manager.decrypt_data(data, 'matrix_cipher', layer)

            if gpu_result and 'decrypted_data' in gpu_result:
                return gpu_result['decrypted_data']
            else:
                return self._decrypt_matrix_cipher_cpu(data, layer)

        except Exception as e:
            return self._decrypt_matrix_cipher_cpu(data, layer)

    def _decrypt_matrix_cipher_cpu(self, data: bytes, layer: dict) -> bytes:
        """CPU解密矩阵变换"""
        try:
            # 简化的矩阵逆变换
            import random

            # 使用相同的种子重建矩阵
            seed = layer.get('seed', 12345)
            random.seed(seed)

            # 简化的逆变换
            result = bytearray()
            for i, byte in enumerate(data):
                # 简单的逆变换
                transformed = (byte - (i % 256)) % 256
                result.append(transformed)

            return bytes(result)

        except Exception as e:
            raise Exception(f"矩阵变换解密失败: {e}")

    def _decrypt_blowfish(self, data: bytes, layer: dict) -> bytes:
        """解密Blowfish"""
        try:
            if self.gpu_available:
                return self._decrypt_blowfish_gpu(data, layer)
            else:
                return self._decrypt_blowfish_cpu(data, layer)
        except Exception as e:
            return self._decrypt_blowfish_cpu(data, layer)

    def _decrypt_blowfish_gpu(self, data: bytes, layer: dict) -> bytes:
        """GPU解密Blowfish（优先使用CPU确保兼容性）"""
        try:
            # 为了确保解密兼容性，直接使用CPU标准实现
            return self._decrypt_blowfish_cpu(data, layer)

        except Exception as e:
            raise Exception(f"Blowfish解密失败: {e}")

    def _decrypt_blowfish_cpu(self, data: bytes, layer: dict) -> bytes:
        """CPU解密Blowfish"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding

            key = layer['key']
            iv = layer['iv']
            mode = layer.get('mode', 'CBC')

            if mode == 'CBC':
                cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
            else:
                cipher = Cipher(algorithms.Blowfish(key), modes.ECB())

            decryptor = cipher.decryptor()
            decrypted_padded = decryptor.update(data) + decryptor.finalize()

            # 移除填充
            unpadder = padding.PKCS7(64).unpadder()
            decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()

            return decrypted_data

        except Exception as e:
            raise Exception(f"Blowfish解密失败: {e}")

    def _generate_output_path(self, encrypted_file: str, original_filename: str) -> str:
        """生成输出文件路径"""
        # 创建解密文件夹
        decrypt_dir = "decrypted_files"
        os.makedirs(decrypt_dir, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%H%M%S")
        name, ext = os.path.splitext(original_filename)
        output_file = os.path.join(decrypt_dir, f"{name}_decrypted_{timestamp}{ext}")

        return output_file


def main():
    """主函数"""
    import sys

    if len(sys.argv) < 2:
        print("使用方法: python gpu_decryptor.py <加密文件> [输出文件]")
        return

    encrypted_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    decryptor = GPUDecryptor()
    success = decryptor.decrypt_file(encrypted_file, output_file)

    if success:
        print("\\n解密成功!")
    else:
        print("\\n解密失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
'''

        return decryptor_code


def main():
    """测试GPU文件加密器"""
    print("🚀 GPU文件加密器测试")
    print("=" * 50)

    try:
        # 创建测试文件
        test_file = "test_gpu_file.txt"
        test_content = "这是一个GPU加密测试文件。\n" * 1000

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)

        print(f"📁 创建测试文件: {test_file}")
        print(f"   文件大小: {len(test_content.encode('utf-8')):,} 字节")

        # 创建GPU文件加密器
        encryptor = GPUFileEncryptor()

        # 加密文件
        print(f"\n🔐 开始GPU文件加密...")
        result = encryptor.encrypt_file(test_file, ".", security_level=3)

        if result['success']:
            print(f"✅ GPU文件加密成功!")
            print(f"   加密文件: {result['encrypted_file']}")
            print(f"   解密器: {result['decryptor_file']}")
            print(f"   加密速度: {result['speed_mbps']:.2f} MB/s")
            print(f"   加密层数: {result['layers']}")
            print(f"   GPU专用: {result['gpu_only']}")
        else:
            print(f"❌ GPU文件加密失败: {result['error']}")

        # 清理测试文件
        try:
            os.remove(test_file)
        except:
            pass

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
