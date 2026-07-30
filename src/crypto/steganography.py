"""
隐写术实现
"""

import os
import random
from typing import Tuple, Dict, Any, Optional
try:
    from PIL import Image
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..utils.logger import Logger


class Steganography:
    """隐写术类"""
    
    def __init__(self):
        """初始化隐写术"""
        self.logger = Logger("Steganography")
    
    def lsb_hide_in_image(self, data: bytes, cover_image_path: str = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        在图像中使用LSB隐写术隐藏数据
        
        Args:
            data: 要隐藏的数据
            cover_image_path: 载体图像路径
            
        Returns:
            (含隐藏数据的图像字节, 元数据)
        """
        try:
            if not PIL_AVAILABLE:
                # 如果PIL不可用，使用简单隐写
                return self._simple_hide(data)

            if cover_image_path and os.path.exists(cover_image_path):
                # 使用提供的图像
                image = Image.open(cover_image_path)
            else:
                # 生成随机图像作为载体
                image = self._generate_cover_image(len(data))
            
            # 转换为RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 转换为numpy数组
            img_array = np.array(image)
            height, width, channels = img_array.shape
            
            # 检查容量
            max_capacity = height * width * channels  # 每个颜色通道可以隐藏1位
            data_bits = len(data) * 8
            
            if data_bits > max_capacity:
                raise ValueError(f"数据太大，无法隐藏在图像中。需要{data_bits}位，但只有{max_capacity}位可用")
            
            # 将数据转换为二进制字符串
            data_bits_str = ''.join(format(byte, '08b') for byte in data)
            
            # 添加结束标记
            end_marker = '1111111111111110'  # 16位结束标记
            data_bits_str += end_marker
            
            # 隐藏数据
            bit_index = 0
            for i in range(height):
                for j in range(width):
                    for k in range(channels):
                        if bit_index < len(data_bits_str):
                            # 修改最低位
                            pixel_value = img_array[i, j, k]
                            bit = int(data_bits_str[bit_index])
                            img_array[i, j, k] = (pixel_value & 0xFE) | bit
                            bit_index += 1
                        else:
                            break
                    if bit_index >= len(data_bits_str):
                        break
                if bit_index >= len(data_bits_str):
                    break
            
            # 转换回图像
            stego_image = Image.fromarray(img_array)
            
            # 保存为字节
            import io
            img_bytes = io.BytesIO()
            stego_image.save(img_bytes, format='PNG')
            stego_data = img_bytes.getvalue()
            
            metadata = {
                'algorithm': 'LSB_Steganography',
                'cover_type': 'image',
                'image_size': (width, height),
                'data_size': len(data),
                'format': 'PNG'
            }
            
            self.logger.debug(f"LSB隐写完成，隐藏了{len(data)}字节数据")
            return stego_data, metadata
            
        except ImportError:
            self.logger.error("PIL库未安装，无法进行图像隐写")
            # 回退到简单隐写
            return self._simple_hide(data)
        except Exception as e:
            self.logger.error(f"LSB隐写失败: {e}")
            raise
    
    def lsb_extract_from_image(self, stego_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        从图像中提取LSB隐写的数据
        
        Args:
            stego_data: 含隐藏数据的图像字节
            metadata: 隐写元数据
            
        Returns:
            提取的数据
        """
        try:
            import io
            
            # 从字节加载图像
            img_bytes = io.BytesIO(stego_data)
            image = Image.open(img_bytes)
            
            # 转换为numpy数组
            img_array = np.array(image)
            height, width, channels = img_array.shape
            
            # 提取位
            extracted_bits = []
            end_marker = '1111111111111110'
            
            for i in range(height):
                for j in range(width):
                    for k in range(channels):
                        bit = img_array[i, j, k] & 1
                        extracted_bits.append(str(bit))
                        
                        # 检查是否到达结束标记
                        if len(extracted_bits) >= 16:
                            current_bits = ''.join(extracted_bits[-16:])
                            if current_bits == end_marker:
                                # 找到结束标记，移除它
                                extracted_bits = extracted_bits[:-16]
                                break
                    else:
                        continue
                    break
                else:
                    continue
                break
            
            # 转换为字节
            extracted_data = bytearray()
            for i in range(0, len(extracted_bits), 8):
                if i + 8 <= len(extracted_bits):
                    byte_bits = ''.join(extracted_bits[i:i+8])
                    byte_value = int(byte_bits, 2)
                    extracted_data.append(byte_value)
            
            self.logger.debug(f"LSB提取完成，提取了{len(extracted_data)}字节数据")
            return bytes(extracted_data)
            
        except ImportError:
            return self._simple_extract(stego_data, metadata)
        except Exception as e:
            self.logger.error(f"LSB提取失败: {e}")
            raise
    
    def _generate_cover_image(self, data_size: int):
        """生成随机载体图像"""
        # 计算所需的图像大小
        bits_needed = data_size * 8 + 16  # 数据位 + 结束标记
        pixels_needed = (bits_needed + 2) // 3  # 每个像素3个通道
        
        # 计算图像尺寸
        width = int(np.sqrt(pixels_needed)) + 1
        height = (pixels_needed + width - 1) // width
        
        if PIL_AVAILABLE:
            # 生成随机图像
            random_data = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
            return Image.fromarray(random_data)
        else:
            # 如果PIL不可用，返回None
            return None
    
    def _simple_hide(self, data: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """简单隐写（回退方法）"""
        # 生成随机载体数据
        cover_size = len(data) * 8  # 8倍大小的载体
        cover_data = os.urandom(cover_size)
        
        # 简单的LSB隐写
        hidden_data = bytearray(cover_data)
        data_bits = ''.join(format(byte, '08b') for byte in data)
        
        for i, bit in enumerate(data_bits):
            if i < len(hidden_data):
                hidden_data[i] = (hidden_data[i] & 0xFE) | int(bit)
        
        metadata = {
            'algorithm': 'LSB_Steganography',
            'cover_type': 'random',
            'cover_size': cover_size,
            'data_size': len(data)
        }
        
        return bytes(hidden_data), metadata
    
    def _simple_extract(self, stego_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """简单提取（回退方法）"""
        data_size = metadata['data_size']
        
        # 从LSB中提取数据
        extracted_bits = []
        for i in range(data_size * 8):
            if i < len(stego_data):
                bit = stego_data[i] & 1
                extracted_bits.append(str(bit))
        
        # 转换为字节
        extracted_data = bytearray()
        for i in range(0, len(extracted_bits), 8):
            if i + 8 <= len(extracted_bits):
                byte_bits = ''.join(extracted_bits[i:i+8])
                byte_value = int(byte_bits, 2)
                extracted_data.append(byte_value)
        
        return bytes(extracted_data)
    
    def text_hide_in_text(self, data: bytes, cover_text: str = None) -> Tuple[str, Dict[str, Any]]:
        """
        在文本中隐藏数据（使用空白字符）
        
        Args:
            data: 要隐藏的数据
            cover_text: 载体文本
            
        Returns:
            (含隐藏数据的文本, 元数据)
        """
        if cover_text is None:
            cover_text = self._generate_cover_text(len(data))
        
        # 将数据转换为二进制
        data_bits = ''.join(format(byte, '08b') for byte in data)
        
        # 在单词之间插入隐藏的空白字符
        words = cover_text.split()
        stego_text = []
        bit_index = 0
        
        for word in words:
            stego_text.append(word)
            
            if bit_index < len(data_bits):
                # 根据位值添加不同的空白字符
                if data_bits[bit_index] == '1':
                    stego_text.append('\u00A0')  # 不间断空格
                else:
                    stego_text.append(' ')  # 普通空格
                bit_index += 1
            else:
                stego_text.append(' ')
        
        result_text = ''.join(stego_text)
        
        metadata = {
            'algorithm': 'Text_Steganography',
            'method': 'whitespace',
            'data_size': len(data),
            'original_text_length': len(cover_text)
        }
        
        self.logger.debug(f"文本隐写完成，隐藏了{len(data)}字节数据")
        return result_text, metadata
    
    def text_extract_from_text(self, stego_text: str, metadata: Dict[str, Any]) -> bytes:
        """从文本中提取隐藏的数据"""
        data_size = metadata['data_size']
        
        # 分析空白字符
        extracted_bits = []
        i = 0
        while i < len(stego_text) and len(extracted_bits) < data_size * 8:
            char = stego_text[i]
            if char == '\u00A0':  # 不间断空格 = 1
                extracted_bits.append('1')
            elif char == ' ':  # 普通空格 = 0
                extracted_bits.append('0')
            i += 1
        
        # 转换为字节
        extracted_data = bytearray()
        for i in range(0, len(extracted_bits), 8):
            if i + 8 <= len(extracted_bits):
                byte_bits = ''.join(extracted_bits[i:i+8])
                byte_value = int(byte_bits, 2)
                extracted_data.append(byte_value)
        
        self.logger.debug(f"文本提取完成，提取了{len(extracted_data)}字节数据")
        return bytes(extracted_data)
    
    def _generate_cover_text(self, data_size: int) -> str:
        """生成载体文本"""
        words = [
            "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
            "this", "is", "sample", "text", "for", "steganography", "testing",
            "purpose", "only", "and", "should", "not", "be", "used", "in",
            "production", "environment", "without", "proper", "validation"
        ]
        
        # 生成足够长的文本
        needed_words = data_size * 8 + 10  # 确保有足够的空间
        cover_words = []
        
        for i in range(needed_words):
            cover_words.append(words[i % len(words)])
        
        return ' '.join(cover_words)
    
    def get_supported_methods(self) -> list:
        """获取支持的隐写方法"""
        return ['lsb_image', 'text_whitespace']
    
    def hide_data(self, data: bytes, method: str = 'lsb_image', **kwargs) -> Tuple[bytes, Dict[str, Any]]:
        """
        通用隐藏接口
        
        Args:
            data: 要隐藏的数据
            method: 隐写方法
            **kwargs: 方法参数
            
        Returns:
            (隐写载体, 元数据)
        """
        if method == 'lsb_image':
            return self.lsb_hide_in_image(data, kwargs.get('cover_image_path'))
        elif method == 'text_whitespace':
            result_text, metadata = self.text_hide_in_text(data, kwargs.get('cover_text'))
            return result_text.encode('utf-8'), metadata
        else:
            raise ValueError(f"不支持的隐写方法: {method}")
    
    def extract_data(self, stego_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        通用提取接口
        
        Args:
            stego_data: 隐写载体
            metadata: 隐写元数据
            
        Returns:
            提取的数据
        """
        algorithm = metadata['algorithm']
        
        if algorithm == 'LSB_Steganography':
            return self.lsb_extract_from_image(stego_data, metadata)
        elif algorithm == 'Text_Steganography':
            stego_text = stego_data.decode('utf-8')
            return self.text_extract_from_text(stego_text, metadata)
        else:
            raise ValueError(f"不支持的隐写算法: {algorithm}")
