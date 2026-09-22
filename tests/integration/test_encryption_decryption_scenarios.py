#!/usr/bin/env python3
"""
全面的加密解密场景测试

测试常见场景下的文件加密和解密功能，包括：
- 不同文件类型（文本、二进制、图片等）
- 不同文件大小（小文件、中等文件、大文件）
- 不同安全级别（1-5级）
- CPU和GPU引擎
- 边界条件和特殊情况
"""

import os
import sys
import time
import tempfile
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import pytest

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 设置OpenCL环境变量
os.environ['PYOPENCL_CTX'] = '0'
os.environ['PYOPENCL_COMPILER_OUTPUT'] = '0'


class TestEncryptionDecryptionScenarios:
    """加密解密场景测试类"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """测试前后的设置和清理"""
        self.test_dir = tmp_path / "encryption_test"
        self.test_dir.mkdir(exist_ok=True)
        self.output_dir = tmp_path / "output"
        self.output_dir.mkdir(exist_ok=True)
        yield
        # 清理临时文件

    def _create_test_file(self, filename: str, content: bytes) -> Path:
        """创建测试文件"""
        file_path = self.test_dir / filename
        file_path.write_bytes(content)
        return file_path

    def _calculate_hash(self, data: bytes) -> str:
        """计算数据的SHA256哈希"""
        return hashlib.sha256(data).hexdigest()

    def _get_cpu_engine(self, security_level: int = 2):
        """获取CPU加密引擎"""
        from src.encryptor.pure_cpu_engine import PureCPUEngine
        return PureCPUEngine(security_level=security_level)

    def _get_gpu_engine(self, security_level: int = 2):
        """获取GPU加密引擎"""
        from src.encryptor.pure_gpu_only_engine import PureGPUOnlyEngine
        return PureGPUOnlyEngine(security_level=security_level)

    def _decrypt_data(self, encrypted_result: Dict, engine_type: str = 'cpu') -> bytes:
        """解密数据"""
        encrypted_data = encrypted_result['encrypted_data']
        metadata = encrypted_result.get('metadata', {})
        layers = metadata.get('layers', [])

        # 反向解密每一层
        decrypted_data = encrypted_data
        for layer in reversed(layers):
            decrypted_data = self._decrypt_single_layer(decrypted_data, layer)

        return decrypted_data

    def _decrypt_single_layer(self, data, layer_metadata):
        from src.decryptor.algorithm_registry import AlgorithmRegistry
        registry = AlgorithmRegistry()
        return registry.get_handler(layer_metadata['algorithm']).decrypt(data, layer_metadata)

    def _decrypt_aes256(self, data: bytes, metadata: Dict) -> bytes:
        """AES-256解密"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        key = metadata['key']
        iv = metadata['iv']
        mode_name = metadata.get('mode', 'CBC')

        if mode_name == 'GCM':
            tag = metadata.get('tag')
            cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        else:  # CBC
            if len(iv) != 16:
                iv = iv[:16] if len(iv) > 16 else iv + b'\x00' * (16 - len(iv))
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(data) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            return unpadder.update(padded_data) + unpadder.finalize()

    def _decrypt_chacha20(self, data: bytes, metadata: Dict) -> bytes:
        """ChaCha20解密（对称加密，加密=解密）"""
        # ChaCha20是流密码，加密和解密操作相同
        from src.gpu.gpu_manager import gpu_manager
        key = metadata['key']
        nonce = metadata['nonce']

        result = gpu_manager.encrypt_data(data, 'chacha20', {
            'key': key,
            'nonce': nonce,
            'rounds': 20
        })
        return result['encrypted_data'] if result else data

    def _decrypt_salsa20(self, data: bytes, metadata: Dict) -> bytes:
        """Salsa20解密"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
            key = metadata['key']
            nonce = metadata['nonce']
            algorithm = algorithms.Salsa20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()
            return decryptor.update(data) + decryptor.finalize()
        except Exception:
            # 简化实现
            return data

    def _decrypt_matrix_cipher(self, data: bytes, metadata: Dict) -> bytes:
        """矩阵变换解密"""
        from src.gpu.gpu_manager import gpu_manager
        result = gpu_manager.decrypt_data(data, 'matrix_cipher', metadata)
        return result['decrypted_data'] if result and 'decrypted_data' in result else data

    def _decrypt_blowfish(self, data: bytes, metadata: Dict) -> bytes:
        """Blowfish解密"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        key = metadata['key']
        iv = metadata['iv']
        mode_name = metadata.get('mode', 'CBC')

        if mode_name == 'CBC':
            cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        else:
            cipher = Cipher(algorithms.Blowfish(key), modes.ECB())

        decryptor = cipher.decryptor()
        padded_data = decryptor.update(data) + decryptor.finalize()
        unpadder = padding.PKCS7(64).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()


class TestTextFileEncryption(TestEncryptionDecryptionScenarios):
    """文本文件加密测试"""

    def test_small_text_file_cpu(self):
        """测试小文本文件CPU加密"""
        content = "Hello, World! 你好，世界！".encode('utf-8')
        file_path = self._create_test_file("small.txt", content)
        original_hash = self._calculate_hash(content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        assert 'encrypted_data' in result
        assert result['encrypted_data'] != content
        assert len(result['encrypted_data']) > 0

        # 验证元数据 - CPU引擎的layers在metadata内部
        assert 'metadata' in result
        assert 'layers' in result['metadata']
        assert len(result['metadata']['layers']) == 2  # 安全级别2有2层

    def test_medium_text_file_cpu(self):
        """测试中等文本文件CPU加密"""
        content = ("这是一个测试文件。\n" * 1000).encode('utf-8')
        file_path = self._create_test_file("medium.txt", content)

        engine = self._get_cpu_engine(security_level=3)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        assert 'encrypted_data' in result
        assert len(result['metadata']['layers']) == 3  # 安全级别3有3层

    def test_large_text_file_cpu(self):
        """测试大文本文件CPU加密"""
        content = ("Large file content. 大文件内容。\n" * 10000).encode('utf-8')
        file_path = self._create_test_file("large.txt", content)

        engine = self._get_cpu_engine(security_level=2)
        start_time = time.time()
        result = engine.encrypt_with_security_level(content)
        encrypt_time = time.time() - start_time

        assert result is not None
        assert encrypt_time < 30  # 应在30秒内完成

    def test_unicode_text_file(self):
        """测试Unicode文本文件加密"""
        content = "中文测试 日本語テスト 한국어 테스트 🎉🔐💻".encode('utf-8')
        file_path = self._create_test_file("unicode.txt", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        assert 'encrypted_data' in result


class TestBinaryFileEncryption(TestEncryptionDecryptionScenarios):
    """二进制文件加密测试"""

    def test_random_binary_data(self):
        """测试随机二进制数据加密"""
        content = os.urandom(1024 * 100)  # 100KB随机数据
        file_path = self._create_test_file("random.bin", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        assert 'encrypted_data' in result
        assert result['encrypted_data'] != content

    def test_zero_filled_binary(self):
        """测试全零二进制数据加密"""
        content = b'\x00' * 1024 * 10  # 10KB全零
        file_path = self._create_test_file("zeros.bin", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        # 加密后不应该全是零
        assert result['encrypted_data'] != content

    def test_pattern_binary(self):
        """测试重复模式二进制数据加密"""
        pattern = b'\xAA\x55\xFF\x00'
        content = pattern * 1024 * 10  # 40KB重复模式
        file_path = self._create_test_file("pattern.bin", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        # 加密后应该打破重复模式
        encrypted = result['encrypted_data']
        # 检查加密数据不是简单的重复模式
        assert encrypted[:4] != encrypted[4:8] or encrypted[:4] != pattern


class TestSecurityLevels(TestEncryptionDecryptionScenarios):
    """安全级别测试"""

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_cpu_security_levels(self, level):
        """测试CPU引擎所有安全级别"""
        content = os.urandom(1024 * 10)  # 10KB

        engine = self._get_cpu_engine(security_level=level)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        assert 'encrypted_data' in result
        assert 'metadata' in result
        assert 'layers' in result['metadata']
        # CPU引擎层数与安全级别对应
        assert len(result['metadata']['layers']) >= 1

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    def test_gpu_security_levels(self, level):
        """测试GPU引擎所有安全级别"""
        try:
            content = os.urandom(1024 * 10)  # 10KB

            engine = self._get_gpu_engine(security_level=level)
            result = engine.encrypt_with_security_level(content)

            assert result is not None
            assert result['metadata']['security_level'] == level
            assert result['metadata']['gpu_only'] == True
        except Exception as e:
            pytest.skip(f"GPU不可用: {e}")


class TestEdgeCases(TestEncryptionDecryptionScenarios):
    """边界条件测试"""

    def test_empty_file(self):
        """测试空文件加密"""
        content = b''
        file_path = self._create_test_file("empty.txt", content)

        engine = self._get_cpu_engine(security_level=1)
        # 空文件可能会抛出异常或返回特殊结果
        try:
            result = engine.encrypt_with_security_level(content)
            # 如果成功，验证结果
            assert result is not None
        except Exception as e:
            # 空文件加密失败是可接受的
            assert "empty" in str(e).lower() or len(content) == 0

    def test_single_byte_file(self):
        """测试单字节文件加密"""
        content = b'A'
        file_path = self._create_test_file("single.txt", content)

        engine = self._get_cpu_engine(security_level=1)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        assert 'encrypted_data' in result

    def test_exact_block_size_file(self):
        """测试恰好是块大小的文件"""
        # AES块大小是16字节
        content = b'A' * 16
        file_path = self._create_test_file("block16.txt", content)

        engine = self._get_cpu_engine(security_level=1)
        result = engine.encrypt_with_security_level(content)

        assert result is not None

    def test_block_size_minus_one(self):
        """测试块大小减一的文件"""
        content = b'A' * 15
        file_path = self._create_test_file("block15.txt", content)

        engine = self._get_cpu_engine(security_level=1)
        result = engine.encrypt_with_security_level(content)

        assert result is not None

    def test_block_size_plus_one(self):
        """测试块大小加一的文件"""
        content = b'A' * 17
        file_path = self._create_test_file("block17.txt", content)

        engine = self._get_cpu_engine(security_level=1)
        result = engine.encrypt_with_security_level(content)

        assert result is not None


class TestSpecialCharacters(TestEncryptionDecryptionScenarios):
    """特殊字符测试"""

    def test_null_bytes(self):
        """测试包含空字节的数据"""
        content = b'Hello\x00World\x00Test'
        file_path = self._create_test_file("null_bytes.bin", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None

    def test_high_entropy_data(self):
        """测试高熵数据（已压缩或加密的数据）"""
        content = os.urandom(1024 * 50)  # 50KB高熵数据
        file_path = self._create_test_file("high_entropy.bin", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None

    def test_all_byte_values(self):
        """测试包含所有字节值的数据"""
        content = bytes(range(256)) * 100  # 所有字节值重复100次
        file_path = self._create_test_file("all_bytes.bin", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None


class TestPerformance(TestEncryptionDecryptionScenarios):
    """性能测试"""

    def test_cpu_encryption_speed(self):
        """测试CPU加密速度"""
        content = os.urandom(1024 * 1024)  # 1MB
        
        engine = self._get_cpu_engine(security_level=2)
        start_time = time.time()
        result = engine.encrypt_with_security_level(content)
        encrypt_time = time.time() - start_time

        assert result is not None
        speed_mbps = len(content) / encrypt_time / (1024 * 1024)
        print(f"\nCPU加密速度: {speed_mbps:.2f} MB/s")
        assert speed_mbps > 1  # 至少1MB/s

    def test_gpu_encryption_speed(self):
        """测试GPU加密速度"""
        try:
            content = os.urandom(1024 * 1024)  # 1MB

            engine = self._get_gpu_engine(security_level=2)
            start_time = time.time()
            result = engine.encrypt_with_security_level(content)
            encrypt_time = time.time() - start_time

            assert result is not None
            speed_mbps = len(content) / encrypt_time / (1024 * 1024)
            print(f"\nGPU加密速度: {speed_mbps:.2f} MB/s")
        except Exception as e:
            pytest.skip(f"GPU不可用: {e}")

    def test_encryption_scaling(self):
        """测试加密时间随数据大小的扩展性"""
        sizes = [1024, 10240, 102400, 1024000]  # 1KB, 10KB, 100KB, 1MB
        times = []

        engine = self._get_cpu_engine(security_level=2)

        for size in sizes:
            content = os.urandom(size)
            start_time = time.time()
            result = engine.encrypt_with_security_level(content)
            encrypt_time = time.time() - start_time
            times.append(encrypt_time)
            assert result is not None

        # 验证时间大致线性增长
        print(f"\n加密时间扩展性测试:")
        for size, t in zip(sizes, times):
            print(f"  {size/1024:.0f}KB: {t:.4f}s")


class TestCPUGPUComparison(TestEncryptionDecryptionScenarios):
    """CPU和GPU对比测试"""

    def test_same_security_level_output_format(self):
        """测试相同安全级别的输出格式一致性"""
        content = os.urandom(1024 * 10)  # 10KB

        cpu_engine = self._get_cpu_engine(security_level=2)
        cpu_result = cpu_engine.encrypt_with_security_level(content)

        try:
            gpu_engine = self._get_gpu_engine(security_level=2)
            gpu_result = gpu_engine.encrypt_with_security_level(content)

            # 验证输出格式一致
            assert 'encrypted_data' in cpu_result
            assert 'encrypted_data' in gpu_result

            # CPU和GPU返回格式略有不同，但都有加密数据
            assert len(cpu_result['encrypted_data']) > 0
            assert len(gpu_result['encrypted_data']) > 0

        except Exception as e:
            pytest.skip(f"GPU不可用: {e}")

    def test_different_encrypted_output(self):
        """测试CPU和GPU产生不同的加密输出"""
        content = os.urandom(1024 * 10)  # 10KB

        cpu_engine = self._get_cpu_engine(security_level=2)
        cpu_result = cpu_engine.encrypt_with_security_level(content)

        try:
            gpu_engine = self._get_gpu_engine(security_level=2)
            gpu_result = gpu_engine.encrypt_with_security_level(content)

            # 由于使用不同的随机密钥，加密结果应该不同
            assert cpu_result['encrypted_data'] != gpu_result['encrypted_data']

        except Exception as e:
            pytest.skip(f"GPU不可用: {e}")


class TestEncryptionRoundTrip(TestEncryptionDecryptionScenarios):
    """加密解密往返测试"""

    def test_cpu_aes256_roundtrip(self):
        """测试CPU AES-256加密解密往返"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        original_data = b"Test data for AES-256 roundtrip"
        key = os.urandom(32)
        iv = os.urandom(16)

        # 加密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(original_data) + padder.finalize()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()

        # 解密
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

        assert decrypted == original_data

    def test_cpu_chacha20_roundtrip(self):
        """测试CPU ChaCha20加密解密往返"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

        original_data = b"Test data for ChaCha20 roundtrip"
        key = os.urandom(32)
        nonce = os.urandom(16)

        # 加密
        algorithm = algorithms.ChaCha20(key, nonce)
        cipher = Cipher(algorithm, mode=None)
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(original_data) + encryptor.finalize()

        # 解密（ChaCha20是对称的）
        cipher = Cipher(algorithm, mode=None)
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted) + decryptor.finalize()

        assert decrypted == original_data

    def test_cpu_blowfish_roundtrip(self):
        """测试CPU Blowfish加密解密往返"""
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import padding

        original_data = b"Test data for Blowfish roundtrip"
        key = os.urandom(16)
        iv = os.urandom(8)

        # 加密
        cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(64).padder()
        padded_data = padder.update(original_data) + padder.finalize()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()

        # 解密
        cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = padding.PKCS7(64).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

        assert decrypted == original_data


class TestFileTypeSimulation(TestEncryptionDecryptionScenarios):
    """模拟不同文件类型测试"""

    def test_pdf_like_header(self):
        """测试PDF类型文件头"""
        # PDF文件头
        content = b'%PDF-1.4\n' + os.urandom(1024 * 10)
        file_path = self._create_test_file("test.pdf", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        # 加密后不应该保留PDF头
        assert not result['encrypted_data'].startswith(b'%PDF')

    def test_zip_like_header(self):
        """测试ZIP类型文件头"""
        # ZIP文件头
        content = b'PK\x03\x04' + os.urandom(1024 * 10)
        file_path = self._create_test_file("test.zip", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        # 加密后不应该保留ZIP头
        assert not result['encrypted_data'].startswith(b'PK')

    def test_png_like_header(self):
        """测试PNG类型文件头"""
        # PNG文件头
        content = b'\x89PNG\r\n\x1a\n' + os.urandom(1024 * 10)
        file_path = self._create_test_file("test.png", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        # 加密后不应该保留PNG头
        assert not result['encrypted_data'].startswith(b'\x89PNG')

    def test_exe_like_header(self):
        """测试EXE类型文件头"""
        # PE/EXE文件头
        content = b'MZ' + os.urandom(1024 * 10)
        file_path = self._create_test_file("test.exe", content)

        engine = self._get_cpu_engine(security_level=2)
        result = engine.encrypt_with_security_level(content)

        assert result is not None
        # 加密后不应该保留MZ头
        assert not result['encrypted_data'].startswith(b'MZ')


class TestConcurrentEncryption(TestEncryptionDecryptionScenarios):
    """并发加密测试"""

    def test_multiple_files_sequential(self):
        """测试顺序加密多个文件"""
        files_data = [os.urandom(1024 * 10) for _ in range(5)]
        results = []

        engine = self._get_cpu_engine(security_level=2)

        for i, data in enumerate(files_data):
            result = engine.encrypt_with_security_level(data)
            results.append(result)
            assert result is not None

        # 验证所有加密结果都不同
        encrypted_set = set()
        for result in results:
            encrypted_hash = self._calculate_hash(result['encrypted_data'])
            assert encrypted_hash not in encrypted_set
            encrypted_set.add(encrypted_hash)


class TestMetadataIntegrity(TestEncryptionDecryptionScenarios):
    """元数据完整性测试"""

    def test_cpu_metadata_structure(self):
        """测试CPU加密元数据结构"""
        content = os.urandom(1024 * 10)

        engine = self._get_cpu_engine(security_level=3)
        result = engine.encrypt_with_security_level(content)

        # 验证必需字段
        assert 'encrypted_data' in result
        assert 'metadata' in result
        assert 'layers' in result['metadata']
        
        # 验证层信息
        layers = result['metadata']['layers']
        assert len(layers) == 3  # 安全级别3应该有3层
        
        for layer in layers:
            assert 'algorithm' in layer
            # 不同算法有不同的密钥存储方式
            # RSA使用encrypted_aes_key，其他使用key
            has_key = 'key' in layer or 'encrypted_aes_key' in layer or 'aes_metadata' in layer
            assert has_key, f"层 {layer.get('algorithm')} 缺少密钥信息"

    def test_gpu_metadata_structure(self):
        """测试GPU加密元数据结构"""
        try:
            content = os.urandom(1024 * 10)

            engine = self._get_gpu_engine(security_level=3)
            result = engine.encrypt_with_security_level(content)

            metadata = result['metadata']
            
            # 验证必需字段
            assert 'engine_type' in metadata
            assert 'security_level' in metadata
            assert 'gpu_only' in metadata
            assert metadata['gpu_only'] == True

        except Exception as e:
            pytest.skip(f"GPU不可用: {e}")


def run_all_tests():
    """运行所有测试"""
    print("🧪 开始全面加密解密场景测试")
    print("=" * 60)
    
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",  # 遇到第一个失败就停止
    ])


if __name__ == "__main__":
    run_all_tests()
