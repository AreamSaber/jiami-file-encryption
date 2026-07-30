#!/usr/bin/env python3
"""
解密器程序模板

这是一个自包含的解密器程序，包含解密所需的所有信息。
"""

import base64
import json
import os
import pickle
from pathlib import Path

# 加密元数据占位符 - 将被实际数据替换
ENCRYPTION_METADATA = "__METADATA_PLACEHOLDER__"

class FileDecryptor:
    """文件解密器"""

    def __init__(self):
        self.metadata = self._load_metadata()

    def _load_metadata(self):
        """加载加密元数据"""
        try:
            # 动态获取全局变量ENCRYPTION_METADATA
            # 使用globals()来获取当前模块的全局变量
            encryption_metadata = globals().get('ENCRYPTION_METADATA', None)

            # 检查是否为占位符（使用分离的字符串避免被替换）
            placeholder_check = "__METADATA_" + "PLACEHOLDER__"
            if encryption_metadata == placeholder_check:
                # 这是模板文件，返回空元数据用于测试
                print("WARNING: 这是解密器模板文件，未注入实际元数据")
                return None

            # 检查是否为空或无效数据
            if not encryption_metadata or len(encryption_metadata) < 10:
                print("WARNING: 无效的加密元数据")
                return None

            # ENCRYPTION_METADATA现在直接是base64编码的字符串
            # 解码元数据
            decoded_data = base64.b64decode(encryption_metadata)
            metadata = json.loads(decoded_data.decode('utf-8'))

            # 递归处理所有base64编码的bytes数据
            metadata = self._decode_bytes_in_metadata(metadata)
            return metadata
        except Exception as e:
            print(f"ERROR: 加载元数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _decode_bytes_in_metadata(self, obj):
        """递归解码元数据中的base64编码的bytes数据"""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in ['key', 'iv', 'nonce', 'tag', 'encrypted_aes_key', 'data', 'obfuscation_key'] and isinstance(value, str):
                    # 这些字段应该是bytes类型，从base64解码
                    try:
                        result[key] = base64.b64decode(value)
                    except:
                        result[key] = value
                elif key == 'private_key' and isinstance(value, str):
                    # RSA私钥需要特殊处理
                    try:
                        from cryptography.hazmat.primitives import serialization
                        private_key_bytes = base64.b64decode(value)
                        result[key] = serialization.load_pem_private_key(
                            private_key_bytes,
                            password=None
                        )
                    except Exception as e:
                        print(f"WARNING:  解码RSA私钥失败: {e}")
                        result[key] = value
                elif key == 'public_key' and isinstance(value, str):
                    # RSA公钥需要特殊处理
                    try:
                        from cryptography.hazmat.primitives import serialization
                        public_key_bytes = base64.b64decode(value)
                        result[key] = serialization.load_pem_public_key(public_key_bytes)
                    except Exception as e:
                        print(f"WARNING:  解码RSA公钥失败: {e}")
                        result[key] = value
                else:
                    result[key] = self._decode_bytes_in_metadata(value)
            return result
        elif isinstance(obj, list):
            return [self._decode_bytes_in_metadata(item) for item in obj]
        else:
            return obj

    def decrypt_file(self, encrypted_file_path, output_path):
        """解密文件"""
        try:
            print(f"开始解密: {encrypted_file_path}")

            if not self.metadata:
                print("ERROR: 无效的解密元数据")
                return None

            # 读取加密文件
            with open(encrypted_file_path, 'rb') as f:
                encrypted_package = pickle.load(f)

            encrypted_data = encrypted_package['encrypted_data']

            # 根据加密类型解密
            if self.metadata['type'] == 'layered':
                decrypted_data = self._decrypt_layered(encrypted_data, self.metadata['layers'])
            elif self.metadata['type'] == 'parallel':
                decrypted_data = self._decrypt_parallel(encrypted_data, self.metadata)
            elif self.metadata['type'] == 'threaded_layered':
                # threaded_layered 是分层加密的多线程版本，需要特殊处理chunks结构
                decrypted_data = self._decrypt_threaded_layered(encrypted_data, self.metadata)
            else:
                print(f"ERROR: 不支持的加密类型: {self.metadata['type']}")
                return None

            # 关键修复：截断到原始大小 - 优先从metadata，然后从加密包顶层获取
            original_size = self.metadata.get('original_size') or encrypted_package.get('original_size')
            if original_size:
                print(f"INFO: 原始文件大小: {original_size:,} 字节")
                if len(decrypted_data) > original_size:
                    print(f"INFO: 截断数据到原始大小: {len(decrypted_data):,} -> {original_size:,} 字节")
                    decrypted_data = decrypted_data[:original_size]
                elif len(decrypted_data) < original_size:
                    print(f"WARNING: 解密数据小于原始大小: {len(decrypted_data):,} < {original_size:,} 字节")
                else:
                    print(f"INFO: 数据大小验证通过: {len(decrypted_data):,} 字节")

            # 保存解密数据到专用文件夹
            actual_output_path = self._save_decrypted_data(decrypted_data, output_path)

            print(f"SUCCESS: 解密完成: {actual_output_path}")
            return actual_output_path  # 返回实际的输出路径

        except Exception as e:
            print(f"ERROR: 解密失败: {e}")
            return None  # 返回None表示失败

    def _decrypt_layered(self, encrypted_data, layers):
        """解密分层加密的数据"""
        data = encrypted_data

        # 逆序解密
        for layer in reversed(layers):
            # 获取算法名称 - 支持threaded_layered策略
            algorithm = layer.get('algorithm')

            # 如果直接没有algorithm字段，检查chunks结构（threaded_layered策略）
            if algorithm is None and 'chunks' in layer:
                # 尝试两种解密方式：
                # 1. 先尝试整体解密（可能数据是连续的）
                # 2. 如果失败，再尝试分chunk解密
                data = self._decrypt_threaded_layer_unified(data, layer)
                continue

            # 如果仍然没有算法信息，尝试从method推断
            if algorithm is None:
                method = layer.get('method')
                if method == 'chacha20':
                    algorithm = 'ChaCha20-CPU'  # 默认假设CPU版本
                elif method == 'aes256':
                    algorithm = 'AES-256-CPU'  # 默认假设CPU版本
                elif method:
                    print(f"WARNING: 从method推断算法: {method} -> {algorithm}")

            if algorithm == 'Simple_XOR':
                key = layer['key']
                # 处理密钥长度与数据长度不匹配的情况
                if len(key) >= len(data):
                    data = bytes(a ^ b for a, b in zip(data, key))
                else:
                    # 密钥循环使用
                    data = bytes(a ^ key[i % len(key)] for i, a in enumerate(data))
            elif algorithm == 'Bit_Shuffle':
                data = self._decrypt_bit_shuffle(data, layer)
            elif algorithm == 'Rotate_Cipher':
                rotation = layer['rotation']
                data = bytes((byte - rotation) % 256 for byte in data)
            elif algorithm == 'AES-256' or algorithm == 'AES-256-GPU' or algorithm == 'AES-256-CPU':
                data = self._decrypt_aes256(data, layer)
            elif algorithm == 'ChaCha20' or algorithm == 'ChaCha20-GPU' or algorithm == 'ChaCha20-CPU':
                data = self._decrypt_chacha20(data, layer)
            elif algorithm == 'Salsa20' or algorithm == 'Salsa20-GPU' or algorithm == 'Salsa20-CPU' or algorithm == 'Salsa20_PyNaCl':
                data = self._decrypt_salsa20(data, layer)
            elif algorithm == 'Blowfish' or algorithm == 'Blowfish-GPU' or algorithm == 'Blowfish-CPU':
                data = self._decrypt_blowfish(data, layer)
            elif algorithm == 'Twofish' or algorithm == 'Twofish-GPU' or algorithm == 'Twofish-CPU':
                data = self._decrypt_twofish(data, layer)
            elif algorithm == 'Twofish_Simple':
                data = self._decrypt_twofish_simple(data, layer)
            elif algorithm == 'RSA' or algorithm == 'RSA-Hybrid':
                data = self._decrypt_rsa(data, layer)
            elif algorithm == 'LSB_Steganography':
                data = self._decrypt_steganography(data, layer)
            elif algorithm == 'Matrix_Cipher-CPU' or algorithm == 'Matrix_Cipher-GPU':
                data = self._decrypt_matrix_cipher(data, layer)
            elif algorithm == 'Pre_Scramble':
                data = self._decrypt_pre_scramble(data, layer)
            elif algorithm == 'Final_Obfuscation':
                data = self._decrypt_final_obfuscation(data, layer)
            else:
                print(f"WARNING: 不支持的算法: {algorithm}")

        return data

    def _decrypt_threaded_layered(self, encrypted_data, metadata):
        """解密threaded_layered数据 - 完美版本，正确处理分块独立填充"""
        try:
            layers = metadata.get('layers', [])
            data = encrypted_data
            original_size = metadata.get('original_size')

            print(f"INFO: threaded_layered解密 - {len(layers)} 层 (原始大小: {original_size:,} 字节)")

            # 逆序解密每一层
            for i, layer in enumerate(reversed(layers)):
                layer_index = len(layers) - 1 - i
                method = layer.get('method')
                thread_count = layer.get('thread_count', 1)

                print(f"INFO: 解密第 {layer_index + 1} 层 - {method} (线程数: {thread_count})")

                # 检查是否有chunks（多线程层）
                if 'chunks' in layer and thread_count > 1:
                    # 使用完美的分块解密，正确处理每个chunk的独立填充
                    data = self._decrypt_threaded_chunks_perfect(data, layer, original_size)
                else:
                    # 单线程层，使用标准解密
                    if 'chunks' in layer:
                        chunks = layer['chunks']
                        first_chunk_key = list(chunks.keys())[0]
                        first_chunk = chunks[first_chunk_key]

                        # 创建统一的层配置
                        unified_layer = {
                            'method': method,
                            'algorithm': layer.get('algorithm'),
                            'mode': layer.get('mode', 'CBC')
                        }
                        unified_layer.update(first_chunk)

                        print(f"INFO: 使用chunk {first_chunk_key} 的密钥进行整体解密")
                        data = self._decrypt_single_layer_enhanced(data, unified_layer)
                    else:
                        # 标准单层解密
                        algorithm = layer.get('algorithm')
                        if algorithm is None:
                            # 从method推断algorithm
                            if method == 'chacha20':
                                algorithm = 'ChaCha20-CPU'
                            elif method == 'aes256':
                                algorithm = 'AES-256-CPU'
                            layer['algorithm'] = algorithm

                        data = self._decrypt_single_layer_enhanced(data, layer)

                if data is None:
                    print(f"ERROR: 第 {layer_index + 1} 层解密失败")
                    return None

                print(f"INFO: 第 {layer_index + 1} 层解密完成: {len(data):,} 字节")

            return data

        except Exception as e:
            print(f"ERROR: threaded_layered解密失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _decrypt_threaded_chunks_perfect(self, data, layer, original_size):
        """完美的分块解密 - 正确处理每个chunk的独立填充"""
        try:
            chunks_meta = layer.get('chunks', {})
            method = layer.get('method')

            print(f"     完美分块解密: {len(chunks_meta)} 个chunks")

            # 获取chunk偏移量并排序
            chunk_offsets = []
            for chunk_key in chunks_meta.keys():
                try:
                    offset = int(chunk_key)
                    chunk_offsets.append(offset)
                except:
                    pass

            chunk_offsets.sort()

            # 计算每个chunk的实际大小（基于原始数据）
            chunk_sizes = []
            for i, offset in enumerate(chunk_offsets):
                if i < len(chunk_offsets) - 1:
                    chunk_size = chunk_offsets[i + 1] - offset
                else:
                    chunk_size = original_size - offset
                chunk_sizes.append(chunk_size)

            print(f"     chunk大小: {chunk_sizes[:3]}... (显示前3个)")

            # 计算每个chunk加密后的大小（包含独立填充）
            encrypted_chunk_sizes = []
            for chunk_size in chunk_sizes:
                if method == 'aes256':
                    # 每个chunk独立填充到16字节边界
                    padding = 16 - (chunk_size % 16)
                    if padding == 16:
                        padding = 0
                    encrypted_size = chunk_size + padding
                else:
                    encrypted_size = chunk_size

                encrypted_chunk_sizes.append(encrypted_size)

            print(f"     加密chunk大小: {encrypted_chunk_sizes[:3]}... (显示前3个)")

            # 分块解密
            decrypted_parts = []
            current_pos = 0

            for i, (offset, chunk_size, encrypted_size) in enumerate(zip(chunk_offsets, chunk_sizes, encrypted_chunk_sizes)):
                # 提取这个chunk的加密数据
                chunk_encrypted_data = data[current_pos:current_pos + encrypted_size]
                current_pos += encrypted_size

                print(f"       解密chunk{i}: {len(chunk_encrypted_data)} -> ", end="")

                # 获取这个chunk的密钥信息
                chunk_key = str(offset)
                if chunk_key not in chunks_meta:
                    # 尝试找到匹配的chunk
                    for key in chunks_meta.keys():
                        try:
                            if int(key) == offset:
                                chunk_key = key
                                break
                        except:
                            continue

                if chunk_key not in chunks_meta:
                    print(f"失败 (未找到密钥)")
                    return None

                chunk_info = chunks_meta[chunk_key]

                # 解密这个chunk
                if method == 'chacha20':
                    decrypted_chunk = self._decrypt_chacha20_perfect(chunk_encrypted_data, chunk_info)
                elif method == 'aes256':
                    decrypted_chunk = self._decrypt_aes256_perfect(chunk_encrypted_data, chunk_info, chunk_size)
                elif method == 'custom':
                    # 自定义算法 - 根据chunk中的algorithm字段选择解密方法
                    chunk_algorithm = chunk_info.get('algorithm', '')
                    if chunk_algorithm == 'Pre_Scramble':
                        decrypted_chunk = self._decrypt_pre_scramble(chunk_encrypted_data, chunk_info)
                    elif chunk_algorithm == 'Bit_Shuffle':
                        decrypted_chunk = self._decrypt_bit_shuffle(chunk_encrypted_data, chunk_info)
                    elif chunk_algorithm == 'Final_Obfuscation':
                        decrypted_chunk = self._decrypt_final_obfuscation(chunk_encrypted_data, chunk_info)
                    else:
                        print(f"未知自定义算法: {chunk_algorithm}")
                        return None
                else:
                    print(f"未知方法: {method}")
                    return None

                if decrypted_chunk is None:
                    print(f"失败")
                    return None

                print(f"{len(decrypted_chunk)} 字节")
                decrypted_parts.append(decrypted_chunk)

            # 合并所有解密的部分
            result = b''.join(decrypted_parts)
            print(f"     ✅ 分块解密完成: {len(result):,} 字节")

            return result

        except Exception as e:
            print(f"     ❌ 分块解密失败: {e}")
            return None

    def _decrypt_aes256_perfect(self, data, layer, expected_size):
        """AES256解密并完美处理填充"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            key = layer['key']
            iv = layer['iv']
            mode = layer.get('mode', 'CBC')

            if mode == 'CBC':
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                decryptor = cipher.decryptor()

                # 解密
                padded_data = decryptor.update(data) + decryptor.finalize()

                # 移除填充 - 关键：截断到期望大小
                if len(padded_data) > expected_size:
                    # 直接截断到期望大小，这样可以移除独立填充
                    unpadded_data = padded_data[:expected_size]
                    return unpadded_data
                else:
                    return padded_data

            elif mode == 'GCM':
                tag = layer.get('tag')
                if not tag:
                    return None

                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(data) + decryptor.finalize()
                return decrypted_data

            return None

        except Exception as e:
            return None

    def _decrypt_chacha20_perfect(self, data, layer):
        """ChaCha20解密"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

            key = layer['key']
            nonce = layer['nonce']

            # 确保nonce长度正确
            if len(nonce) != 16:
                if len(nonce) < 16:
                    nonce = nonce + b'\x00' * (16 - len(nonce))
                elif len(nonce) > 16:
                    nonce = nonce[:16]

            algorithm = algorithms.ChaCha20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()

            decrypted_data = decryptor.update(data) + decryptor.finalize()
            return decrypted_data

        except Exception as e:
            return None

    def _decrypt_threaded_layer_enhanced(self, data, layer):
        """增强的threaded层解密 - 支持强制截断策略"""
        try:
            chunks_meta = layer.get('chunks', {})
            method = layer.get('method', 'unknown')
            thread_count = layer.get('thread_count', 1)

            print(f"  增强解密: {method}, 线程数: {thread_count}, chunks: {len(chunks_meta)}")

            if not chunks_meta:
                print("  WARNING: 无chunks信息，尝试标准解密")
                return self._decrypt_single_layer_enhanced(data, layer)

            # 检查第一个chunk的模式
            first_chunk = list(chunks_meta.values())[0]
            mode = first_chunk.get('mode', 'CBC')
            algorithm = first_chunk.get('algorithm', 'Unknown')

            print(f"  检测到模式: {mode}, 算法: {algorithm}")

            # 优先尝试统一解密（适用于流密码和某些情况）
            if 'ChaCha20' in algorithm or mode == 'GCM':
                result = self._decrypt_threaded_unified(data, layer)
                if result is not None and len(result) != len(data):
                    print(f"  SUCCESS: 统一解密成功: {len(data)} -> {len(result)} 字节")
                    return result
                elif 'ChaCha20' in algorithm and result is not None:
                    # ChaCha20是流密码，解密后大小不变是正常的
                    print(f"  SUCCESS: ChaCha20统一解密成功: {len(result)} 字节")
                    return result

            # 回退到分chunk解密（适用于CBC模式）
            print(f"  使用分chunk解密策略")
            return self._decrypt_threaded_chunks(data, layer)

        except Exception as e:
            print(f"  ERROR: 增强解密异常: {e}")
            return data

    def _decrypt_threaded_unified(self, data, layer):
        """统一解密threaded层"""
        try:
            chunks_meta = layer.get('chunks', {})

            # 使用第一个chunk的参数对整个数据解密
            first_chunk = list(chunks_meta.values())[0]

            # 准备解密参数
            chunk_layer = self._prepare_chunk_layer(first_chunk, layer.get('method'))

            # 解密
            algorithm = chunk_layer.get('algorithm', '')
            if 'ChaCha20' in algorithm:
                return self._decrypt_chacha20(data, chunk_layer)
            elif 'AES' in algorithm:
                return self._decrypt_aes256_enhanced(data, chunk_layer)
            else:
                print(f"  WARNING: 不支持的统一算法: {algorithm}")
                return None

        except Exception as e:
            print(f"  ERROR: 统一解密异常: {e}")
            return None

    def _decrypt_threaded_chunks(self, data, layer):
        """分chunk解密threaded层"""
        try:
            chunks_meta = layer.get('chunks', {})

            # 获取所有chunk偏移量并排序
            chunk_offsets = []
            for key in chunks_meta.keys():
                if isinstance(key, int):
                    chunk_offsets.append(key)
                elif isinstance(key, str) and key.isdigit():
                    chunk_offsets.append(int(key))

            chunk_offsets.sort()
            print(f"  分chunk解密: {len(chunk_offsets)} 个chunks")

            # 分别解密每个chunk
            decrypted_chunks = {}
            success_count = 0

            for i, offset in enumerate(chunk_offsets):
                chunk_key = offset if offset in chunks_meta else str(offset)
                if chunk_key not in chunks_meta:
                    continue

                chunk_meta = chunks_meta[chunk_key]

                # 计算chunk的数据范围
                start_pos = offset
                if i == len(chunk_offsets) - 1:
                    end_pos = len(data)
                else:
                    end_pos = chunk_offsets[i + 1]

                chunk_data = data[start_pos:end_pos]

                # 准备chunk解密参数
                chunk_layer = self._prepare_chunk_layer(chunk_meta, layer.get('method'))

                # 解密chunk
                decrypted_chunk = self._decrypt_chunk_enhanced(chunk_data, chunk_layer)

                if decrypted_chunk is not None:
                    decrypted_chunks[offset] = decrypted_chunk
                    success_count += 1
                else:
                    # 解密失败，使用原始数据
                    decrypted_chunks[offset] = chunk_data

            print(f"  成功解密 {success_count}/{len(chunk_offsets)} 个chunks")

            # 重组数据
            combined_data = b''
            for offset in chunk_offsets:
                if offset in decrypted_chunks:
                    combined_data += decrypted_chunks[offset]

            return combined_data

        except Exception as e:
            print(f"  ERROR: 分chunk解密异常: {e}")
            return data

    def _prepare_chunk_layer(self, chunk_meta, method):
        """准备chunk的解密参数"""
        algorithm = chunk_meta.get('algorithm', 'Unknown')

        chunk_layer = {
            'algorithm': algorithm,
            'method': method
        }

        # 复制所有加密参数，确保bytes类型
        for key in ['key', 'iv', 'nonce', 'mode', 'tag']:
            if key in chunk_meta:
                value = chunk_meta[key]
                # 如果是列表，转换为bytes
                if isinstance(value, list):
                    value = bytes(value)
                # 如果是字符串，尝试base64解码
                elif isinstance(value, str) and key != 'mode':
                    try:
                        import base64
                        value = base64.b64decode(value)
                    except:
                        value = value.encode('utf-8')
                chunk_layer[key] = value

        # 复制自定义算法的参数（不需要bytes转换）
        custom_keys = [
            'operations', 'scramble_operations', 'scramble_rounds', 'seed',
            'applied_operations', 'obfuscation_operations', 'obfuscation_key', 'obfuscation_level',
            'bit_positions', 'rotation', 'original_length'
        ]
        for key in custom_keys:
            if key in chunk_meta:
                chunk_layer[key] = chunk_meta[key]

        return chunk_layer

    def _decrypt_chunk_enhanced(self, chunk_data, chunk_layer):
        """增强的chunk解密"""
        try:
            algorithm = chunk_layer.get('algorithm', '')

            if 'ChaCha20' in algorithm:
                return self._decrypt_chacha20(chunk_data, chunk_layer)
            elif 'AES' in algorithm:
                return self._decrypt_aes256_enhanced(chunk_data, chunk_layer)
            elif algorithm == 'Pre_Scramble':
                return self._decrypt_pre_scramble(chunk_data, chunk_layer)
            elif algorithm == 'Bit_Shuffle':
                return self._decrypt_bit_shuffle(chunk_data, chunk_layer)
            elif algorithm == 'Final_Obfuscation':
                return self._decrypt_final_obfuscation(chunk_data, chunk_layer)
            elif algorithm == 'Simple_XOR':
                key = chunk_layer['key']
                if len(key) >= len(chunk_data):
                    return bytes(a ^ b for a, b in zip(chunk_data, key))
                else:
                    return bytes(a ^ key[i % len(key)] for i, a in enumerate(chunk_data))
            elif algorithm == 'Rotate_Cipher':
                rotation = chunk_layer['rotation']
                return bytes((byte - rotation) % 256 for byte in chunk_data)
            else:
                print(f"      WARNING: 不支持的chunk算法: {algorithm}")
                return None

        except Exception as e:
            print(f"      ERROR: chunk解密失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _decrypt_single_layer_enhanced(self, data, layer):
        """增强的单层解密"""
        try:
            algorithm = layer.get('algorithm')
            method = layer.get('method')

            if not algorithm and method:
                # 从method推断algorithm
                if method == 'chacha20':
                    algorithm = 'ChaCha20-CPU'
                elif method == 'aes256':
                    algorithm = 'AES-256-CPU'

            print(f"  单层解密: {algorithm}")

            if algorithm and 'ChaCha20' in algorithm:
                return self._decrypt_chacha20(data, layer)
            elif algorithm and 'AES' in algorithm:
                return self._decrypt_aes256_enhanced(data, layer)
            elif algorithm == 'Pre_Scramble':
                return self._decrypt_pre_scramble(data, layer)
            elif algorithm == 'Bit_Shuffle':
                return self._decrypt_bit_shuffle(data, layer)
            elif algorithm == 'Final_Obfuscation':
                return self._decrypt_final_obfuscation(data, layer)
            elif algorithm == 'Simple_XOR':
                key = layer['key']
                if len(key) >= len(data):
                    return bytes(a ^ b for a, b in zip(data, key))
                else:
                    return bytes(a ^ key[i % len(key)] for i, a in enumerate(data))
            elif algorithm == 'Rotate_Cipher':
                rotation = layer['rotation']
                return bytes((byte - rotation) % 256 for byte in data)
            elif algorithm == 'RSA' or algorithm == 'RSA-Hybrid':
                return self._decrypt_rsa(data, layer)
            elif algorithm == 'Salsa20' or algorithm == 'Salsa20_PyNaCl':
                return self._decrypt_salsa20(data, layer)
            elif algorithm == 'Blowfish':
                return self._decrypt_blowfish(data, layer)
            elif algorithm == 'Twofish' or algorithm == 'Twofish_Simple':
                return self._decrypt_twofish(data, layer)
            elif algorithm == 'LSB_Steganography':
                return self._decrypt_steganography(data, layer)
            else:
                print(f"  WARNING: 不支持的算法: {algorithm}")
                return data

        except Exception as e:
            print(f"  ERROR: 单层解密失败: {e}")
            import traceback
            traceback.print_exc()
            return data

    def _decrypt_threaded_layer_unified(self, data, layer):
        """统一解密threaded_layered策略的单层 - 修复版本"""
        try:
            chunks = layer.get('chunks', {})
            thread_count = layer.get('thread_count', 1)
            method = layer.get('method', 'unknown')

            print(f"INFO: 尝试统一解密threaded层 - 方法: {method}, 线程数: {thread_count}, 块数: {len(chunks)}")

            if not chunks:
                print("WARNING: threaded层缺少chunks信息，尝试单层解密")
                return self._decrypt_single_layer_enhanced(data, layer)

            # 关键修复：threaded_layered可能是整体加密，不是分块加密
            # 先尝试整体解密
            try:
                print("INFO: 尝试整体解密threaded层...")
                # 使用第一个chunk的参数进行整体解密
                first_chunk = list(chunks.values())[0]
                unified_layer = layer.copy()
                unified_layer.update(first_chunk)

                result = self._decrypt_single_layer_enhanced(data, unified_layer)
                if result is not None:
                    print("INFO: 整体解密成功")
                    return result
            except Exception as e:
                print(f"WARNING: 整体解密失败: {e}")

            # 如果整体解密失败，尝试分块解密
            print("INFO: 尝试分块解密...")
            return self._decrypt_chunks_separately(data, chunks, method)

        except Exception as e:
            print(f"WARNING: 统一解密失败: {e}")
            import traceback
            traceback.print_exc()
            # 回退到分chunk解密
            return self._decrypt_threaded_layer(data, layer)

    def _decrypt_chunks_separately(self, data, chunks, method):
        """分块解密 - 每个chunk独立解密后重组"""
        try:
            # 获取所有chunk偏移量并排序
            chunk_offsets = []
            for key in chunks.keys():
                if isinstance(key, int):
                    chunk_offsets.append(key)
                elif isinstance(key, str) and key.isdigit():
                    chunk_offsets.append(int(key))
            
            chunk_offsets.sort()
            print(f"  分块解密: {len(chunk_offsets)} 个chunks")
            
            # 分别解密每个chunk
            decrypted_chunks = {}
            success_count = 0
            
            for i, offset in enumerate(chunk_offsets):
                chunk_key = offset if offset in chunks else str(offset)
                if chunk_key not in chunks:
                    continue
                
                chunk_meta = chunks[chunk_key]
                
                # 计算chunk的数据范围
                start_pos = offset
                if i == len(chunk_offsets) - 1:
                    end_pos = len(data)
                else:
                    end_pos = chunk_offsets[i + 1]
                
                chunk_data = data[start_pos:end_pos]
                
                # 准备chunk解密参数
                chunk_layer = self._prepare_chunk_layer(chunk_meta, method)
                
                # 解密chunk
                decrypted_chunk = self._decrypt_chunk_enhanced(chunk_data, chunk_layer)
                
                if decrypted_chunk is not None:
                    decrypted_chunks[offset] = decrypted_chunk
                    success_count += 1
                else:
                    # 解密失败，使用原始数据
                    decrypted_chunks[offset] = chunk_data
            
            print(f"  成功解密 {success_count}/{len(chunk_offsets)} 个chunks")
            
            # 重组数据
            combined_data = b''
            for offset in chunk_offsets:
                if offset in decrypted_chunks:
                    combined_data += decrypted_chunks[offset]
            
            return combined_data
            
        except Exception as e:
            print(f"  ERROR: 分块解密异常: {e}")
            import traceback
            traceback.print_exc()
            return data

    def _decrypt_threaded_layer_unified_legacy(self, data, layer):
        """统一解密threaded_layered策略的单层 - 旧版本（保留兼容）"""
        try:
            chunks = layer.get('chunks', {})
            thread_count = layer.get('thread_count', 1)
            method = layer.get('method', 'unknown')

            # 获取第一个chunk的加密参数（假设所有chunks使用相同参数）
            first_chunk_key = list(chunks.keys())[0]
            first_chunk = chunks[first_chunk_key]

            # 构造统一的解密参数
            algorithm = first_chunk.get('algorithm')
            key = first_chunk.get('key')
            mode = first_chunk.get('mode')
            iv = first_chunk.get('iv')
            nonce = first_chunk.get('nonce')
            tag = first_chunk.get('tag')

            print(f"  尝试整体解密: 算法={algorithm}, 模式={mode}, 数据大小={len(data)}")

            # 构造layer信息
            unified_layer = {
                'algorithm': algorithm,
                'key': key,
                'mode': mode
            }

            if iv:
                unified_layer['iv'] = iv
            if nonce:
                unified_layer['nonce'] = nonce
            if tag:
                unified_layer['tag'] = tag

            # 尝试对整个数据进行解密
            if algorithm and 'ChaCha20' in algorithm:
                decrypted_data = self._decrypt_chacha20(data, unified_layer)
            elif algorithm and 'AES' in algorithm:
                decrypted_data = self._decrypt_aes256(data, unified_layer)
            else:
                print(f"WARNING: 不支持的算法: {algorithm}")
                decrypted_data = None

            if decrypted_data and len(decrypted_data) > 0:
                print(f"  ✓ 整体解密成功: {len(decrypted_data)} 字节")
                return decrypted_data
            else:
                print(f"  ✗ 整体解密失败，尝试分chunk解密")
                return self._decrypt_threaded_layer(data, layer)

        except Exception as e:
            print(f"WARNING: 统一解密失败: {e}")
            # 回退到分chunk解密
            return self._decrypt_threaded_layer(data, layer)

    def _decrypt_threaded_layer(self, data, layer):
        """解密threaded_layered策略的单层"""
        try:
            chunks = layer.get('chunks', {})
            thread_count = layer.get('thread_count', 1)
            method = layer.get('method', 'unknown')

            print(f"INFO: 解密threaded层 - 方法: {method}, 线程数: {thread_count}, 块数: {len(chunks)}")

            # threaded_layered的正确理解：
            # 1. 数据被分成多个chunk，每个chunk独立加密
            # 2. 每个chunk都有自己的填充和认证标签
            # 3. 需要分别解密每个chunk，然后重组

            if not chunks:
                print("WARNING: threaded层缺少chunks信息")
                return data

            # chunks的键是数据偏移量，不是简单的索引
            # 需要按偏移量排序来确定chunk的顺序和大小
            chunk_offsets = []
            for key in chunks.keys():
                if isinstance(key, int):
                    chunk_offsets.append(key)
                elif isinstance(key, str) and key.isdigit():
                    chunk_offsets.append(int(key))

            chunk_offsets.sort()
            total_chunks = len(chunk_offsets)

            print(f"  数据总大小: {len(data)} 字节")
            print(f"  chunk偏移量: {chunk_offsets}")

            # 分别解密每个chunk
            decrypted_chunks = {}

            for i, offset in enumerate(chunk_offsets):
                chunk_key = offset if offset in chunks else str(offset)
                if chunk_key in chunks:
                    chunk_info = chunks[chunk_key]

                    # 计算这个chunk的实际大小
                    start_pos = offset
                    if i == total_chunks - 1:
                        # 最后一个chunk到数据末尾
                        end_pos = len(data)
                    else:
                        # 下一个chunk的开始位置就是当前chunk的结束位置
                        end_pos = chunk_offsets[i + 1]

                    chunk_data = data[start_pos:end_pos]

                    print(f"  解密chunk {i}: 偏移 {start_pos}-{end_pos}, 大小 {len(chunk_data)} 字节")

                    # 构造chunk的解密参数
                    algorithm = chunk_info.get('algorithm')
                    key = chunk_info.get('key')
                    mode = chunk_info.get('mode')
                    iv = chunk_info.get('iv')
                    nonce = chunk_info.get('nonce')
                    tag = chunk_info.get('tag')

                    chunk_layer = {
                        'algorithm': algorithm,
                        'key': key,
                        'mode': mode
                    }

                    if iv:
                        chunk_layer['iv'] = iv
                    if nonce:
                        chunk_layer['nonce'] = nonce
                    if tag:
                        chunk_layer['tag'] = tag

                    # 解密这个chunk
                    if algorithm and 'ChaCha20' in algorithm:
                        decrypted_chunk = self._decrypt_chacha20(chunk_data, chunk_layer)
                    elif algorithm and 'AES' in algorithm:
                        decrypted_chunk = self._decrypt_aes256(chunk_data, chunk_layer)
                    else:
                        print(f"WARNING: 不支持的chunk算法: {algorithm}")
                        decrypted_chunk = chunk_data

                    if decrypted_chunk:
                        decrypted_chunks[offset] = decrypted_chunk
                        print(f"    OK chunk {i} 解密成功: {len(decrypted_chunk)} 字节")
                    else:
                        print(f"    ERROR chunk {i} 解密失败")
                        decrypted_chunks[offset] = chunk_data  # 使用原始数据
                else:
                    print(f"WARNING: 缺少chunk偏移 {offset}")
                    # 使用对应位置的原始数据
                    start_pos = offset
                    if i == total_chunks - 1:
                        end_pos = len(data)
                    else:
                        end_pos = chunk_offsets[i + 1]
                    chunk_data = data[start_pos:end_pos]
                    decrypted_chunks[offset] = chunk_data

            # 按偏移量顺序重组解密后的数据
            combined_data = b''
            for offset in chunk_offsets:
                if offset in decrypted_chunks:
                    combined_data += decrypted_chunks[offset]

            print(f"  重组完成: {len(combined_data)} 字节")
            return combined_data

        except Exception as e:
            print(f"WARNING: threaded层解密失败: {e}")
            import traceback
            traceback.print_exc()
            return data

    def _decrypt_parallel(self, encrypted_data, metadata):
        """解密并行加密的数据"""
        try:
            # 并行加密使用chunks结构
            if 'chunks' in metadata:
                # 重组并行加密的数据块
                chunks = metadata['chunks']
                chunk_count = metadata.get('chunk_count', len(chunks))

                # 按顺序解密并重组数据
                combined_data = b''
                for i in range(chunk_count):
                    # 尝试整数和字符串键
                    chunk_key = i if i in chunks else str(i)
                    if chunk_key in chunks:
                        chunk_info = chunks[chunk_key]
                        chunk_data = chunk_info.get('data', b'')
                        chunk_metadata = chunk_info.get('metadata', {})
                        chunk_method = chunk_info.get('method', 'aes256')

                        # 解密每个chunk
                        if chunk_method == 'aes256':
                            decrypted_chunk = self._decrypt_aes256(chunk_data, chunk_metadata)
                        elif chunk_method == 'chacha20':
                            decrypted_chunk = self._decrypt_chacha20(chunk_data, chunk_metadata)
                        elif chunk_method == 'salsa20':
                            decrypted_chunk = self._decrypt_salsa20(chunk_data, chunk_metadata)
                        elif chunk_method == 'blowfish':
                            decrypted_chunk = self._decrypt_blowfish(chunk_data, chunk_metadata)
                        elif chunk_method == 'twofish':
                            decrypted_chunk = self._decrypt_twofish(chunk_data, chunk_metadata)
                        elif chunk_method == 'rsa':
                            decrypted_chunk = self._decrypt_rsa(chunk_data, chunk_metadata)
                        else:
                            print(f"WARNING: 不支持的chunk加密方法: {chunk_method}")
                            decrypted_chunk = chunk_data

                        combined_data += decrypted_chunk if decrypted_chunk else b''
                return combined_data
            elif 'layers' in metadata:
                # 回退到分层解密
                return self._decrypt_layered(encrypted_data, metadata['layers'])
            else:
                print("WARNING: 并行加密缺少chunks或layers信息")
                return encrypted_data
        except Exception as e:
            print(f"WARNING: 并行解密失败: {e}")
            import traceback
            traceback.print_exc()
            return encrypted_data

    def _decrypt_bit_shuffle(self, data, layer):
        """解密位混洗"""
        bit_positions = layer['bit_positions']

        # 创建逆映射
        reverse_positions = [0] * 8
        for i, pos in enumerate(bit_positions):
            reverse_positions[pos] = i

        decrypted_data = bytearray()
        for byte in data:
            new_byte = 0
            for i, pos in enumerate(reverse_positions):
                if byte & (1 << i):
                    new_byte |= (1 << pos)
            decrypted_data.append(new_byte)

        return bytes(decrypted_data)

    def _decrypt_aes256_enhanced(self, data, layer):
        """增强的AES-256解密 - 支持强制截断策略"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding

            key = layer['key']
            iv = layer['iv']
            mode = layer.get('mode', 'CBC')

            # 确保key和iv是bytes类型
            if isinstance(key, str):
                import base64
                key = base64.b64decode(key)
            if isinstance(iv, str):
                import base64
                iv = base64.b64decode(iv)

            print(f"      增强AES-{mode}: 数据 {len(data)} 字节, key类型: {type(key).__name__}, iv类型: {type(iv).__name__}")

            if mode == 'GCM':
                tag = layer.get('tag')
                if not tag:
                    print("      ERROR: GCM缺少tag")
                    return None

                # 确保tag是bytes类型
                if isinstance(tag, str):
                    import base64
                    tag = base64.b64decode(tag)

                print(f"      GCM参数: key长度={len(key)}, iv长度={len(iv)}, tag长度={len(tag)}")

                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
                decryptor = cipher.decryptor()

                try:
                    decrypted_data = decryptor.update(data) + decryptor.finalize()
                    print(f"      SUCCESS: AES-GCM解密成功: {len(decrypted_data)} 字节")
                    return decrypted_data
                except Exception as e:
                    print(f"      FAILED: AES-GCM解密失败: {e}")
                    import traceback
                    traceback.print_exc()
                    return None

            elif mode == 'CBC':
                # 检查数据长度并应用强制截断策略
                if len(data) % 16 != 0:
                    print(f"      WARNING: CBC数据长度不是16的倍数: {len(data) % 16}")
                    # 强制截断到16字节边界
                    aligned_length = (len(data) // 16) * 16
                    if aligned_length > 0:
                        aligned_data = data[:aligned_length]
                        print(f"      应用强制截断: {len(data)} -> {aligned_length} 字节")
                        data = aligned_data
                    else:
                        print(f"      ERROR: 截断后数据为空")
                        return None

                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                decryptor = cipher.decryptor()

                try:
                    # 解密
                    padded_data = decryptor.update(data) + decryptor.finalize()

                    # 尝试移除填充
                    try:
                        unpadder = padding.PKCS7(128).unpadder()
                        decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
                        print(f"      SUCCESS: AES-CBC解密成功: {len(decrypted_data)} 字节")
                        return decrypted_data
                    except Exception as padding_error:
                        # 填充移除失败，尝试手动移除填充
                        print(f"      WARNING: 填充移除失败: {padding_error}")
                        if len(padded_data) > 0:
                            padding_length = padded_data[-1]
                            if 1 <= padding_length <= 16:
                                # 验证填充是否有效
                                if all(b == padding_length for b in padded_data[-padding_length:]):
                                    manual_unpadded = padded_data[:-padding_length]
                                    print(f"      SUCCESS: 手动移除填充成功: {len(manual_unpadded)} 字节")
                                    return manual_unpadded
                                else:
                                    print(f"      WARNING: 填充验证失败，填充值不一致")
                            else:
                                print(f"      WARNING: 填充长度无效: {padding_length}")

                        # 强制移除可能的填充（最后16字节内查找）
                        for possible_padding in range(1, min(17, len(padded_data) + 1)):
                            if len(padded_data) >= possible_padding:
                                if all(b == possible_padding for b in padded_data[-possible_padding:]):
                                    forced_unpadded = padded_data[:-possible_padding]
                                    print(f"      SUCCESS: 强制移除填充成功: {possible_padding} 字节 -> {len(forced_unpadded)} 字节")
                                    return forced_unpadded

                        print(f"      ERROR: 无法移除填充，返回原始数据: {len(padded_data)} 字节")
                        return padded_data

                except Exception as e:
                    print(f"      FAILED: AES-CBC解密失败: {e}")
                    return None

            return None

        except ImportError:
            print("      ERROR: cryptography库未安装")
            return None

    def _decrypt_aes256(self, data, layer):
        """解密AES-256"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding

            key = layer['key']
            iv = layer['iv']
            mode = layer.get('mode', 'CBC')

            if mode == 'CBC':
                # 对于threaded_layered，每个chunk可能有不同的填充
                # 不要截断数据，而是尝试直接解密
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                decryptor = cipher.decryptor()

                try:
                    # 检查数据长度
                    if len(data) % 16 != 0:
                        print(f"WARNING: AES-CBC数据长度不是16的倍数: {len(data)} 字节")
                        print(f"  数据长度模16余数: {len(data) % 16}")
                        print("  这可能是threaded_layered的正常情况，尝试直接解密")

                    # 尝试直接解密（可能会失败）
                    padded_data = decryptor.update(data) + decryptor.finalize()

                    # 移除填充
                    unpadder = padding.PKCS7(128).unpadder()
                    decrypted_data = unpadder.update(padded_data) + unpadder.finalize()

                except Exception as decrypt_error:
                    print(f"WARNING: AES-CBC解密失败: {decrypt_error}")
                    print("  可能是chunk边界问题，返回原始数据")
                    # 对于threaded_layered，解密失败可能是正常的
                    # 返回原始数据，让上层处理
                    return data

            elif mode == 'GCM':
                tag = layer.get('tag')
                if not tag:
                    print("ERROR: GCM模式缺少认证标签")
                    return data

                # GCM模式正确的解密方式
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
                decryptor = cipher.decryptor()

                try:
                    # 解密数据并验证认证标签
                    decrypted_data = decryptor.update(data) + decryptor.finalize()
                except Exception as e:
                    print(f"ERROR: GCM认证失败: {e}")
                    return data

            return decrypted_data

        except ImportError:
            print("WARNING:  cryptography库未安装，无法解密AES")
            return data

    def _decrypt_chacha20(self, data, layer):
        """解密ChaCha20 - 修复版本"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

            key = layer['key']
            nonce = layer['nonce']

            # 验证nonce长度
            if len(nonce) != 16:
                print(f"WARNING: ChaCha20 nonce长度异常: {len(nonce)} 字节，期望16字节")
                # 尝试修复nonce长度
                if len(nonce) < 16:
                    nonce = nonce + b'\x00' * (16 - len(nonce))
                    print(f"INFO: 已填充nonce到16字节")
                elif len(nonce) > 16:
                    nonce = nonce[:16]
                    print(f"INFO: 已截断nonce到16字节")

            algorithm = algorithms.ChaCha20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()

            decrypted_data = decryptor.update(data) + decryptor.finalize()
            print(f"INFO: ChaCha20解密成功: {len(decrypted_data)} 字节")
            return decrypted_data

        except Exception as e:
            print(f"ERROR: ChaCha20解密失败: {e}")
            return None
        except ImportError:
            print("WARNING: cryptography库未安装，无法解密ChaCha20")
            return data

    def _decrypt_salsa20(self, data, layer):
        """解密Salsa20"""
        algorithm = layer.get('algorithm', 'Salsa20')

        if algorithm == 'Salsa20_PyNaCl':
            # PyNaCl格式的Salsa20解密
            try:
                from nacl.secret import SecretBox

                key = layer['key']
                encrypted_with_nonce = layer.get('encrypted_with_nonce', True)

                if encrypted_with_nonce:
                    # PyNaCl自动处理nonce，数据中包含nonce
                    box = SecretBox(key)
                    decrypted_data = box.decrypt(data)
                    return decrypted_data
                else:
                    # 手动处理nonce
                    nonce = layer['nonce']
                    box = SecretBox(key)
                    decrypted_data = box.decrypt(data, nonce)
                    return decrypted_data

            except ImportError:
                print("WARNING: PyNaCl库未安装，回退到标准Salsa20解密")
                # 回退到标准解密
                pass

        # 标准Salsa20解密
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

            key = layer['key']
            nonce = layer['nonce']

            algorithm = algorithms.Salsa20(key, nonce)
            cipher = Cipher(algorithm, mode=None)
            decryptor = cipher.decryptor()

            decrypted_data = decryptor.update(data) + decryptor.finalize()
            return decrypted_data

        except ImportError:
            print("WARNING: cryptography库未安装，无法解密Salsa20")
            return data

    def _decrypt_blowfish(self, data, layer):
        """解密Blowfish"""
        try:
            # 使用新的decrepit模块避免弃用警告
            from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish
            from cryptography.hazmat.primitives.ciphers import Cipher, modes
            from cryptography.hazmat.primitives import padding

            key = layer['key']
            iv = layer.get('iv')
            mode = layer.get('mode', 'CBC')

            if mode == 'CBC' and iv:
                cipher = Cipher(Blowfish(key), modes.CBC(iv))
                decryptor = cipher.decryptor()
                padded_data = decryptor.update(data) + decryptor.finalize()

                # 移除填充
                try:
                    unpadder = padding.PKCS7(64).unpadder()  # Blowfish块大小为64位
                    decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
                except Exception:
                    # 如果填充验证失败，返回原始数据
                    decrypted_data = padded_data

            elif mode == 'ECB':
                cipher = Cipher(Blowfish(key), modes.ECB())
                decryptor = cipher.decryptor()
                padded_data = decryptor.update(data) + decryptor.finalize()

                # 移除填充
                try:
                    unpadder = padding.PKCS7(64).unpadder()
                    decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
                except Exception:
                    # 如果填充验证失败，返回原始数据
                    decrypted_data = padded_data

            else:
                print(f"WARNING:  不支持的Blowfish模式: {mode}")
                return data

            return decrypted_data

        except ImportError:
            print("WARNING:  cryptography库未安装，无法解密Blowfish")
            return data

    def _decrypt_twofish(self, data, layer):
        """解密Twofish"""
        try:
            import twofish

            key = layer['key']
            original_length = layer.get('original_length', len(data))

            # 创建Twofish实例
            tf = twofish.Twofish(key)

            # 分块解密
            decrypted_data = bytearray()
            for i in range(0, len(data), 16):
                block = data[i:i+16]
                if len(block) == 16:
                    decrypted_block = tf.decrypt(block)
                    decrypted_data.extend(decrypted_block)

            # 移除填充并截取到原始长度
            return bytes(decrypted_data[:original_length])

        except ImportError:
            # 回退到简化解密
            return self._decrypt_twofish_simple(data, layer)

    def _decrypt_twofish_simple(self, data, layer):
        """简化的Twofish解密"""
        try:
            key = layer['key']
            rounds = layer.get('rounds', 16)

            # 逆向多轮解密
            decrypted_data = bytearray(data)

            for round_num in reversed(range(rounds)):
                round_key = self._derive_round_key(key, round_num)

                for i in range(len(decrypted_data)):
                    # 逆向轮函数
                    decrypted_data[i] = ((decrypted_data[i] >> 1) | (decrypted_data[i] << 7)) & 0xFF
                    decrypted_data[i] = self._inverse_s_box_substitute(decrypted_data[i])
                    decrypted_data[i] ^= round_key[i % len(round_key)]

            return bytes(decrypted_data)

        except Exception as e:
            print(f"WARNING:  Twofish解密失败: {e}")
            return data

    def _derive_round_key(self, key, round_num):
        """派生轮密钥"""
        import hashlib
        round_data = key + round_num.to_bytes(4, 'big')
        return hashlib.sha256(round_data).digest()[:len(key)]

    def _inverse_s_box_substitute(self, byte_val):
        """逆S盒替换"""
        # 简化的逆S盒
        inverse_s_box = [
            0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
            0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
            0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
            0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
            0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
            0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
            0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
            0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
            0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
            0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
            0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
            0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
            0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
            0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
            0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
            0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d
        ]
        return inverse_s_box[byte_val]

    def _decrypt_rsa(self, data, layer):
        """解密RSA"""
        try:
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives import hashes, serialization

            # 检查是否使用PEM格式的私钥
            if 'private_key_pem' in layer:
                private_key_pem = layer['private_key_pem']
                if isinstance(private_key_pem, str):
                    private_key_pem = private_key_pem.encode()

                # 从PEM格式加载私钥
                private_key = serialization.load_pem_private_key(
                    private_key_pem,
                    password=None
                )
            else:
                # 兼容旧格式
                private_key = layer['private_key']

            algorithm = layer['algorithm']

            if algorithm == 'RSA-Hybrid':
                # 混合RSA加密
                encrypted_aes_key = layer['encrypted_aes_key']
                aes_metadata = layer['aes_metadata']

                # 解密AES密钥
                aes_key = private_key.decrypt(
                    encrypted_aes_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )

                # 使用AES密钥解密数据
                aes_layer = aes_metadata.copy()
                aes_layer['key'] = aes_key
                return self._decrypt_aes256(data, aes_layer)
            else:
                # 直接RSA解密
                decrypted_data = private_key.decrypt(
                    data,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                return decrypted_data

        except ImportError:
            print("WARNING: cryptography库未安装，无法解密RSA")
            return data
        except Exception as e:
            print(f"WARNING: RSA解密失败: {e}")
            return data

    def _decrypt_steganography(self, data, layer):
        """解密隐写术"""
        data_size = layer['data_size']

        # 从LSB中提取数据
        extracted_bits = []
        for i in range(data_size * 8):
            if i < len(data):
                bit = data[i] & 1
                extracted_bits.append(str(bit))

        # 转换为字节
        extracted_data = bytearray()
        for i in range(0, len(extracted_bits), 8):
            if i + 8 <= len(extracted_bits):
                byte_bits = ''.join(extracted_bits[i:i+8])
                byte_value = int(byte_bits, 2)
                extracted_data.append(byte_value)

        return bytes(extracted_data)

    def _decrypt_matrix_cipher(self, data, layer):
        """解密矩阵变换"""
        try:
            matrix_size = layer.get('matrix_size', 8)
            transform_matrix = layer.get('transform_matrix')
            original_length = layer.get('original_length', len(data))

            if not transform_matrix:
                print("WARNING:  缺少变换矩阵信息")
                return data

            # 创建逆变换矩阵
            inverse_matrix = self._create_inverse_matrix(transform_matrix)

            # 分块解密
            block_size = matrix_size * matrix_size
            decrypted_data = bytearray()

            for i in range(0, len(data), block_size):
                block = data[i:i+block_size]
                if len(block) < block_size:
                    block = block + b'\x00' * (block_size - len(block))

                # 将块重塑为矩阵
                matrix = [list(block[j:j+matrix_size]) for j in range(0, len(block), matrix_size)]

                # 应用逆变换矩阵
                decrypted_matrix = self._apply_matrix_transform(matrix, inverse_matrix)

                # 将矩阵展平
                for row in decrypted_matrix:
                    decrypted_data.extend(row)

            # 截取到原始长度
            return bytes(decrypted_data[:original_length])

        except Exception as e:
            print(f"WARNING:  矩阵变换解密失败: {e}")
            return data

    def _decrypt_pre_scramble(self, data, layer):
        """解密预处理混淆"""
        try:
            # 兼容两种字段名：operations 和 scramble_operations
            scramble_operations = layer.get('operations', layer.get('scramble_operations', []))

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

        except Exception as e:
            print(f"WARNING:  预处理混淆解密失败: {e}")
            return data

    def _decrypt_final_obfuscation(self, data, layer):
        """解密最终混淆"""
        try:
            import hashlib
            
            # 兼容两种字段名：applied_operations 和 obfuscation_operations
            obfuscation_operations = layer.get('applied_operations', layer.get('obfuscation_operations', []))
            obfuscation_key = layer.get('obfuscation_key', b'')
            
            # 如果obfuscation_key是字符串，尝试base64解码
            if isinstance(obfuscation_key, str):
                import base64
                try:
                    obfuscation_key = base64.b64decode(obfuscation_key)
                except:
                    obfuscation_key = obfuscation_key.encode('utf-8')
            
            # 计算密钥哈希（用于entropy_increase和block_cipher）
            if obfuscation_key:
                key_hash = hashlib.sha256(obfuscation_key).digest()
            else:
                key_hash = b'\x00' * 32

            # 逆序执行混淆操作
            deobfuscated_data = bytearray(data)

            for op_idx, operation in enumerate(reversed(obfuscation_operations)):
                op_type = operation[0]
                # 计算原始操作的索引（用于bit_permutation）
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
                    # 逆向字节替换
                    substitution_table = operation[1]
                    # 创建逆替换表
                    inverse_table = [0] * 256
                    for i, val in enumerate(substitution_table):
                        inverse_table[val] = i
                    for j in range(len(deobfuscated_data)):
                        deobfuscated_data[j] = inverse_table[deobfuscated_data[j]]

                elif op_type == 'bit_permutation':
                    # 逆向位排列
                    i = operation[1]
                    for j in range(len(deobfuscated_data)):
                        byte_val = deobfuscated_data[j]
                        new_byte = 0
                        for bit_pos in range(8):
                            # 逆向计算原始位置
                            new_pos = (bit_pos * 3 + i) % 8
                            if byte_val & (1 << new_pos):
                                new_byte |= (1 << bit_pos)
                        deobfuscated_data[j] = new_byte

                elif op_type == 'block_cipher':
                    # 逆向分组密码
                    round_key = operation[1]
                    block_size = 16
                    for j in range(0, len(deobfuscated_data), block_size):
                        block_end = min(j + block_size, len(deobfuscated_data))
                        for k in range(j, block_end):
                            # 逆向操作：先逆向旋转，再XOR
                            deobfuscated_data[k] = ((deobfuscated_data[k] >> 1) | (deobfuscated_data[k] << 7)) & 0xFF
                            deobfuscated_data[k] ^= round_key

                elif op_type == 'entropy_increase':
                    # 逆向熵增加
                    for j in range(len(deobfuscated_data)):
                        entropy_factor = key_hash[j % len(key_hash)]
                        # 逆向操作：先减去entropy_factor，再XOR
                        deobfuscated_data[j] = (deobfuscated_data[j] - entropy_factor) % 256
                        deobfuscated_data[j] ^= entropy_factor

                elif op_type == 'pattern_disruption':
                    # 逆向模式破坏
                    pattern_map = operation[1]
                    for i in range(len(deobfuscated_data)):
                        if deobfuscated_data[i] in pattern_map:
                            deobfuscated_data[i] = pattern_map[deobfuscated_data[i]]

            return bytes(deobfuscated_data)

        except Exception as e:
            print(f"WARNING:  最终混淆解密失败: {e}")
            import traceback
            traceback.print_exc()
            return data

    def _create_inverse_matrix(self, matrix):
        """创建逆变换矩阵（简化实现）"""
        # 对于简单的变换矩阵，逆矩阵就是转置
        size = len(matrix)
        inverse = [[0] * size for _ in range(size)]

        for i in range(size):
            for j in range(size):
                inverse[j][i] = matrix[i][j]

        return inverse

    def _apply_matrix_transform(self, matrix, transform_matrix):
        """应用矩阵变换"""
        size = len(matrix)
        result = [[0] * size for _ in range(size)]

        # 简化的矩阵乘法
        for i in range(size):
            for j in range(size):
                for k in range(size):
                    result[i][j] = (result[i][j] + matrix[i][k] * transform_matrix[k][j]) % 256

        return result

    def _save_decrypted_data(self, data, output_path):
        """保存解密数据到专门的文件夹"""
        try:
            # 创建解密文件专用文件夹
            decrypted_folder = self._create_decrypted_folder(output_path)

            # 调整输出路径到专用文件夹
            final_output_path = os.path.join(decrypted_folder, os.path.basename(output_path))

            # 尝试解析为文件夹包
            folder_package = pickle.loads(data)

            if isinstance(folder_package, dict) and folder_package.get('type') == 'folder':
                # 恢复文件夹到专用文件夹
                self._restore_folder(folder_package, final_output_path)
                print(f"INFO: 文件夹已恢复到: {decrypted_folder}")
            else:
                # 保存为单个文件到专用文件夹
                with open(final_output_path, 'wb') as f:
                    f.write(data)
                print(f"INFO: 文件已保存到: {final_output_path}")

            # 更新输出路径为实际保存的路径
            return final_output_path

        except:
            # 如果不是pickle数据，直接保存到专用文件夹
            try:
                decrypted_folder = self._create_decrypted_folder(output_path)
                final_output_path = os.path.join(decrypted_folder, os.path.basename(output_path))

                with open(final_output_path, 'wb') as f:
                    f.write(data)
                print(f"INFO: 文件已保存到: {final_output_path}")
                return final_output_path
            except Exception as e:
                # 最后的回退：保存到原始路径
                print(f"WARNING: 无法创建专用文件夹，保存到原始路径: {e}")
                with open(output_path, 'wb') as f:
                    f.write(data)
                return output_path

    def _create_decrypted_folder(self, output_path):
        """创建解密文件专用文件夹 - 在加密文件所在目录"""
        try:
            from datetime import datetime

            # 获取输出文件所在目录（即加密文件所在目录）
            output_dir = os.path.dirname(os.path.abspath(output_path))

            # 创建基于时间戳的文件夹名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 从输出文件名提取基础名称
            base_name = os.path.splitext(os.path.basename(output_path))[0]

            # 创建文件夹名：解密_文件名_时间戳
            folder_name = f"解密_{base_name}_{timestamp}"

            # 完整的文件夹路径 - 在加密文件所在目录
            decrypted_folder = os.path.join(output_dir, folder_name)

            # 创建文件夹
            os.makedirs(decrypted_folder, exist_ok=True)

            print(f"INFO: 在加密文件目录创建解密文件夹: {folder_name}")
            print(f"INFO: 文件夹路径: {decrypted_folder}")
            return decrypted_folder

        except Exception as e:
            print(f"WARNING: 创建解密文件夹失败: {e}")
            # 回退到输出文件所在目录
            try:
                fallback_dir = os.path.dirname(os.path.abspath(output_path))
                return fallback_dir
            except:
                # 最后回退到解密器同目录
                return os.path.dirname(os.path.abspath(__file__))

    def _restore_folder(self, folder_package, output_path):
        """恢复文件夹"""
        root_dir = Path(output_path) / folder_package['name']
        root_dir.mkdir(parents=True, exist_ok=True)

        for file_data in folder_package['files']:
            target_path = root_dir / file_data['relative_path']

            if file_data['is_file']:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, 'wb') as f:
                    f.write(file_data['content'])
                os.utime(target_path, (file_data['modified_time'], file_data['modified_time']))
            else:
                target_path.mkdir(parents=True, exist_ok=True)
                os.utime(target_path, (file_data['modified_time'], file_data['modified_time']))

def detect_file_extension(encrypted_file_path):
    """检测原始文件的扩展名"""
    try:
        # 首先尝试从文件名推断
        name_based_ext = detect_file_type_by_name(encrypted_file_path)
        if name_based_ext:
            print(f"📝 通过文件名检测到类型: {name_based_ext}")
            return name_based_ext

        # 如果文件名推断失败，尝试通过完整解密来检测文件签名
        try:
            # 创建临时解密器实例
            temp_decryptor = FileDecryptor()

            # 完整解密文件
            with open(encrypted_file_path, 'rb') as f:
                encrypted_package = pickle.load(f)

            encrypted_data = encrypted_package['encrypted_data']

            # 根据加密类型解密
            if temp_decryptor.metadata['type'] == 'layered':
                decrypted_data = temp_decryptor._decrypt_layered(encrypted_data, temp_decryptor.metadata['layers'])
            elif temp_decryptor.metadata['type'] == 'parallel':
                decrypted_data = temp_decryptor._decrypt_parallel(encrypted_data, temp_decryptor.metadata)
            elif temp_decryptor.metadata['type'] == 'threaded_layered':
                # threaded_layered 实际上是分层加密的多线程版本，解密时按分层处理
                decrypted_data = temp_decryptor._decrypt_layered(encrypted_data, temp_decryptor.metadata['layers'])
            else:
                print("WARNING:  不支持的加密类型")
                return 'bin'

            # 检测文件签名（只检查前512字节）
            sample_data = decrypted_data[:min(512, len(decrypted_data))]
            detected_ext = detect_file_type_by_signature(sample_data)

            if detected_ext:
                print(f"🔍 通过文件签名检测到类型: {detected_ext}")
                return detected_ext
            else:
                print("WARNING:  无法识别文件签名，使用默认扩展名")
                return 'bin'

        except Exception as e:
            print(f"WARNING:  文件签名检测失败: {e}")
            return 'bin'

    except Exception as e:
        print(f"WARNING:  文件类型检测失败: {e}")
        return 'bin'

def detect_file_type_by_signature(data):
    """通过文件签名检测文件类型"""
    if not data or len(data) < 4:
        return None

    # 常见文件签名
    signatures = {
        b'PK\x03\x04': 'zip',
        b'PK\x05\x06': 'zip',
        b'PK\x07\x08': 'zip',
        b'\x50\x4B\x03\x04': 'zip',
        b'\x1f\x8b\x08': 'gz',
        b'BZh': 'bz2',
        b'\x37\x7A\xBC\xAF\x27\x1C': '7z',
        b'Rar!': 'rar',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'\xff\xd8\xff': 'jpg',
        b'GIF87a': 'gif',
        b'GIF89a': 'gif',
        b'%PDF': 'pdf',
        b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': 'doc',
        b'PK\x03\x04\x14\x00\x06\x00': 'docx',
        b'\x00\x00\x01\x00': 'ico',
        b'RIFF': 'wav',
        b'ID3': 'mp3',
        b'\x00\x00\x00\x18ftypmp4': 'mp4',
        b'\x00\x00\x00\x20ftypM4A': 'm4a',
    }

    # 检查前几个字节
    for signature, extension in signatures.items():
        if data.startswith(signature):
            return extension

    # 检查ZIP文件的其他变体
    if data.startswith(b'PK'):
        return 'zip'

    # 如果是文本文件，尝试检测编码
    try:
        data.decode('utf-8')
        return 'txt'
    except:
        try:
            data.decode('gbk')
            return 'txt'
        except:
            pass

    return None

def detect_file_type_by_name(encrypted_file_path):
    """通过文件名推断原始文件类型"""
    base_name = os.path.splitext(os.path.basename(encrypted_file_path))[0]

    # 常见的文件名模式
    patterns = {
        'zip': ['压缩', '打包', 'archive', 'backup', '备份', '自动备', 'beifeng', '北风'],
        'txt': ['文本', 'text', 'readme', '说明', 'log', '日志'],
        'doc': ['文档', 'document', 'word', 'docx'],
        'pdf': ['pdf', 'document'],
        'jpg': ['图片', 'image', 'photo', '照片', 'jpeg'],
        'png': ['png', 'screenshot', '截图'],
        'mp4': ['视频', 'video', 'movie', 'avi', 'mkv'],
        'mp3': ['音频', 'audio', 'music', '音乐', 'wav'],
        'exe': ['程序', 'program', 'software', '软件', 'app'],
        'rar': ['rar', 'winrar'],
        '7z': ['7z', '7zip'],
    }

    base_name_lower = base_name.lower()

    print(f"🔍 分析文件名: {base_name}")

    for ext, keywords in patterns.items():
        for keyword in keywords:
            if keyword in base_name_lower:
                print(f"SUCCESS: 匹配关键词 '{keyword}' -> 推断类型: {ext}")
                return ext

    # 特殊处理：如果文件名包含日期格式，很可能是备份文件
    import re
    if re.search(r'\d{8}|\d{4}_?\d{2}_?\d{2}', base_name):
        print("📅 检测到日期格式，推断为压缩备份文件")
        return 'zip'

    print("❓ 无法从文件名推断类型")
    return None

def auto_find_files():
    """自动查找加密文件"""
    import glob
    import sys

    # 获取解密器所在的目录
    if getattr(sys, 'frozen', False):
        # 如果是打包的exe文件
        current_dir = os.path.dirname(sys.executable)
    else:
        # 如果是Python脚本
        current_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"🔍 在目录中查找加密文件: {current_dir}")

    # 查找.encrypted文件
    encrypted_files = glob.glob(os.path.join(current_dir, "*.encrypted"))

    if not encrypted_files:
        print("ERROR: 在当前目录未找到 .encrypted 文件")
        return None, None

    if len(encrypted_files) == 1:
        # 只有一个加密文件，自动选择
        encrypted_file = encrypted_files[0]
        base_name = os.path.splitext(os.path.basename(encrypted_file))[0]

        # 尝试推断原始文件扩展名
        if base_name.endswith('_encrypted'):
            base_name = base_name[:-10]  # 移除 '_encrypted'

        # 智能推断文件扩展名
        original_extension = detect_file_extension(encrypted_file)

        # 生成输出文件名
        if original_extension:
            output_file = os.path.join(current_dir, f"{base_name}.{original_extension}")
        else:
            output_file = os.path.join(current_dir, f"{base_name}_decrypted.bin")

        print(f"📁 自动选择加密文件: {os.path.basename(encrypted_file)}")
        print(f"📁 输出文件: {os.path.basename(output_file)}")

        return encrypted_file, output_file
    else:
        # 多个加密文件，让用户选择
        print(f"📋 找到 {len(encrypted_files)} 个加密文件:")
        for i, file in enumerate(encrypted_files, 1):
            print(f"  {i}. {os.path.basename(file)}")

        try:
            choice = input("\n请选择要解密的文件编号 (1-{}): ".format(len(encrypted_files)))
            index = int(choice) - 1

            if 0 <= index < len(encrypted_files):
                encrypted_file = encrypted_files[index]
                base_name = os.path.splitext(os.path.basename(encrypted_file))[0]

                if base_name.endswith('_encrypted'):
                    base_name = base_name[:-10]

                # 智能推断文件扩展名
                original_extension = detect_file_extension(encrypted_file)

                if original_extension:
                    output_file = os.path.join(current_dir, f"{base_name}.{original_extension}")
                else:
                    output_file = os.path.join(current_dir, f"{base_name}_decrypted.bin")

                return encrypted_file, output_file
            else:
                print("ERROR: 无效的选择")
                return None, None

        except (ValueError, KeyboardInterrupt):
            print("ERROR: 无效的输入")
            return None, None

def check_gui_available():
    """检查GUI是否可用"""
    try:
        from PyQt6.QtWidgets import QApplication
        return True, "PyQt6"
    except ImportError:
        try:
            from PySide6.QtWidgets import QApplication
            return True, "PySide6"
        except ImportError:
            return False, None

def run_gui_mode():
    """运行GUI模式"""
    try:
        gui_available, framework = check_gui_available()
        if not gui_available:
            print("ERROR: GUI库不可用，切换到命令行模式")
            return False

        print(f"启动GUI模式 ({framework})")

        # 导入GUI组件
        if framework == "PyQt6":
            from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                        QHBoxLayout, QLabel, QPushButton, QFileDialog,
                                        QTextEdit, QProgressBar, QGroupBox, QComboBox,
                                        QMessageBox, QRadioButton, QButtonGroup, QFrame,
                                        QGridLayout, QSpacerItem, QSizePolicy)
            from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
            from PyQt6.QtGui import QIcon, QFont, QPixmap
        else:
            from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                          QHBoxLayout, QLabel, QPushButton, QFileDialog,
                                          QTextEdit, QProgressBar, QGroupBox, QComboBox,
                                          QMessageBox, QRadioButton, QButtonGroup, QFrame,
                                          QGridLayout, QSpacerItem, QSizePolicy)
            from PySide6.QtCore import Qt, QThread, Signal as pyqtSignal, QTimer
            from PySide6.QtGui import QIcon, QFont, QPixmap

        # 创建简化的GUI解密器
        class SimpleDecryptorGUI(QMainWindow):
            def __init__(self):
                super().__init__()
                self.init_ui()
                self.setup_connections()

            def init_ui(self):
                self.setWindowTitle("🔐 文件解密器 v1.0")
                self.setGeometry(300, 300, 500, 400)

                central_widget = QWidget()
                self.setCentralWidget(central_widget)
                layout = QVBoxLayout(central_widget)

                # 标题
                title = QLabel("🔐 文件解密器")
                title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(title)

                # 文件选择
                file_group = QGroupBox("📁 选择加密文件")
                file_layout = QVBoxLayout(file_group)

                file_select_layout = QHBoxLayout()
                self.file_label = QLabel("未选择文件")
                self.file_label.setStyleSheet("padding: 5px; border: 1px solid #ccc;")
                self.browse_btn = QPushButton("浏览...")

                file_select_layout.addWidget(self.file_label, 1)
                file_select_layout.addWidget(self.browse_btn)
                file_layout.addLayout(file_select_layout)
                layout.addWidget(file_group)

                # 文件类型选择
                type_group = QGroupBox("📋 文件类型")
                type_layout = QVBoxLayout(type_group)

                self.type_combo = QComboBox()
                self.type_combo.addItems([
                    "🔍 自动检测",
                    "📦 压缩包",
                    "📁 文件夹",
                    "📄 文档",
                    "🖼️ 图片",
                    "🎬 视频",
                    "📋 其他"
                ])
                type_layout.addWidget(self.type_combo)
                layout.addWidget(type_group)

                # 操作按钮
                button_layout = QHBoxLayout()
                self.decrypt_btn = QPushButton(" 开始解密")
                self.decrypt_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        font-weight: bold;
                        padding: 10px;
                        border: none;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                """)

                self.exit_btn = QPushButton("🚪 退出")
                self.exit_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2196F3;
                        color: white;
                        font-weight: bold;
                        padding: 10px;
                        border: none;
                        border-radius: 5px;
                    }
                """)

                button_layout.addWidget(self.decrypt_btn)
                button_layout.addWidget(self.exit_btn)
                layout.addLayout(button_layout)

                # 进度和日志
                self.progress = QProgressBar()
                layout.addWidget(self.progress)

                self.log = QTextEdit()
                self.log.setMaximumHeight(100)
                self.log.setReadOnly(True)
                layout.addWidget(self.log)

            def setup_connections(self):
                self.browse_btn.clicked.connect(self.browse_file)
                self.decrypt_btn.clicked.connect(self.start_decrypt)
                self.exit_btn.clicked.connect(self.close)

            def browse_file(self):
                file_path, _ = QFileDialog.getOpenFileName(
                    self, "选择加密文件", "", "加密文件 (*.encrypted);;所有文件 (*.*)"
                )
                if file_path:
                    self.file_label.setText(file_path)
                    self.log_message(f"选择文件: {os.path.basename(file_path)}")

            def start_decrypt(self):
                file_path = self.file_label.text()
                if file_path == "未选择文件":
                    QMessageBox.warning(self, "警告", "请先选择加密文件")
                    return

                if not os.path.exists(file_path):
                    QMessageBox.warning(self, "警告", "文件不存在")
                    return

                try:
                    self.decrypt_btn.setEnabled(False)
                    self.progress.setValue(0)
                    self.log_message("开始解密...")

                    # 生成输出文件名
                    input_path = Path(file_path)
                    base_name = input_path.stem.replace('.encrypted', '')

                    # 根据选择的类型确定扩展名
                    type_text = self.type_combo.currentText()
                    if "压缩包" in type_text:
                        output_file = input_path.parent / f"{base_name}.zip"
                    elif "文件夹" in type_text:
                        output_file = input_path.parent / f"{base_name}_folder"
                    elif "文档" in type_text:
                        output_file = input_path.parent / f"{base_name}.pdf"
                    elif "图片" in type_text:
                        output_file = input_path.parent / f"{base_name}.jpg"
                    elif "视频" in type_text:
                        output_file = input_path.parent / f"{base_name}.mp4"
                    else:
                        # 自动检测或其他
                        original_extension = detect_file_extension(file_path)
                        if original_extension:
                            output_file = input_path.parent / f"{base_name}.{original_extension}"
                        else:
                            output_file = input_path.parent / f"{base_name}_decrypted.bin"

                    self.progress.setValue(30)
                    self.log_message(f"输出文件: {output_file.name}")

                    # 执行解密
                    decryptor = FileDecryptor()
                    self.progress.setValue(50)

                    actual_output_path = decryptor.decrypt_file(file_path, str(output_file))
                    self.progress.setValue(100)

                    if actual_output_path:
                        self.log_message("SUCCESS: 解密成功!")
                        self.log_message(f"文件已保存到专用文件夹")

                        # 显示成功对话框
                        msg = QMessageBox(self)
                        msg.setIcon(QMessageBox.Icon.Information)
                        msg.setWindowTitle("解密成功")
                        msg.setText("文件解密成功!")

                        # 获取文件夹路径
                        output_folder = os.path.dirname(actual_output_path)
                        msg.setDetailedText(f"解密文件: {os.path.basename(actual_output_path)}\n解密文件夹: {output_folder}")

                        open_btn = msg.addButton("打开文件", QMessageBox.ButtonRole.ActionRole)
                        show_btn = msg.addButton("打开文件夹", QMessageBox.ButtonRole.ActionRole)
                        ok_btn = msg.addButton("确定", QMessageBox.ButtonRole.AcceptRole)

                        msg.exec()

                        if msg.clickedButton() == open_btn:
                            self.open_file(actual_output_path)
                        elif msg.clickedButton() == show_btn:
                            self.show_location(output_folder)
                    else:
                        self.log_message("ERROR: 解密失败")
                        QMessageBox.critical(self, "错误", "解密失败，请检查文件是否正确")

                except Exception as e:
                    self.log_message(f"ERROR: 错误: {e}")
                    QMessageBox.critical(self, "错误", f"解密过程中发生错误:\n{e}")
                finally:
                    self.decrypt_btn.setEnabled(True)

            def open_file(self, file_path):
                try:
                    import subprocess
                    import platform

                    if platform.system() == "Windows":
                        os.startfile(file_path)
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", file_path])
                    else:
                        subprocess.run(["xdg-open", file_path])
                except Exception as e:
                    self.log_message(f"打开文件失败: {e}")

            def show_location(self, file_path):
                try:
                    import subprocess
                    import platform

                    if platform.system() == "Windows":
                        subprocess.run(f'explorer /select,"{file_path}"')
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", "-R", file_path])
                    else:
                        subprocess.run(["xdg-open", os.path.dirname(file_path)])
                except Exception as e:
                    self.log_message(f"显示位置失败: {e}")

            def log_message(self, message):
                from datetime import datetime
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.log.append(f"[{timestamp}] {message}")

        # 启动GUI应用
        import sys
        app = QApplication(sys.argv)
        window = SimpleDecryptorGUI()
        window.show()

        # 自动查找加密文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        encrypted_files = [f for f in os.listdir(current_dir) if f.endswith('.encrypted')]

        if encrypted_files:
            if len(encrypted_files) == 1:
                auto_file = os.path.join(current_dir, encrypted_files[0])
                window.file_label.setText(auto_file)
                window.log_message(f"自动选择: {encrypted_files[0]}")
            else:
                window.log_message(f"找到 {len(encrypted_files)} 个加密文件，请手动选择")
        else:
            window.log_message("请选择要解密的加密文件")

        sys.exit(app.exec())

    except Exception as e:
        print(f"ERROR: GUI模式启动失败: {e}")
        return False

def main():
    """主函数"""
    import sys

    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        # 强制命令行模式
        run_cli_mode()
        return

    # 尝试启动GUI模式
    gui_available, framework = check_gui_available()
    if gui_available:
        try:
            run_gui_mode()
            return
        except Exception as e:
            print(f"GUI模式失败: {e}")
            print("切换到命令行模式...")

    # 回退到命令行模式
    run_cli_mode()

def run_cli_mode():
    """运行命令行模式"""
    import sys

    print("🔐 文件解密器 v1.0")
    print("=" * 40)

    try:
        # 检查命令行参数
        if len(sys.argv) >= 3:
            # 传统命令行模式
            encrypted_file = sys.argv[1]
            output_path = sys.argv[2]

            if not os.path.exists(encrypted_file):
                print(f"ERROR: 加密文件不存在: {encrypted_file}")
                input("\n按回车键退出...")
                return
        else:
            # 自动模式：在当前目录查找加密文件
            print("🔍 自动模式：正在查找加密文件...")
            encrypted_file, output_path = auto_find_files()

            if not encrypted_file:
                print("\n💡 使用说明:")
                print("1. 将解密器放在与加密文件相同的目录")
                print("2. 双击运行解密器")
                print("3. 或使用命令行: python decryptor.py <加密文件> <输出路径>")
                print("4. 或使用命令行: python decryptor.py --cli 强制命令行模式")
                input("\n按回车键退出...")
                return

        print(f"\n 开始解密: {os.path.basename(encrypted_file)}")

        decryptor = FileDecryptor()
        actual_output_path = decryptor.decrypt_file(encrypted_file, output_path)

        if actual_output_path:
            print(f"SUCCESS: 解密完成: {os.path.basename(actual_output_path)}")
            print(f"SUCCESS: 文件已保存到专用文件夹: {os.path.dirname(actual_output_path)}")
            print("SUCCESS: 解密成功完成！")
        else:
            print("ERROR: 解密失败")

        input("\n按回车键退出...")

    except KeyboardInterrupt:
        print("\nWARNING:  用户中断操作")
    except Exception as e:
        print(f"ERROR: 解密过程发生错误: {e}")
        input("\n按回车键退出...")

if __name__ == "__main__":
    main()
