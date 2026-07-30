"""
Blowfish加密算法实现
"""

import os
from typing import Tuple, Dict, Any

from ..utils.logger import Logger


class BlowfishEncryption:
    """Blowfish加密算法类"""
    
    def __init__(self):
        """初始化Blowfish加密"""
        self.logger = Logger("BlowfishEncryption")
    
    def encrypt(self, data: bytes, key_size: int = 256, mode: str = 'CBC') -> Tuple[bytes, Dict[str, Any]]:
        """
        Blowfish加密
        
        Args:
            data: 要加密的数据
            key_size: 密钥大小（位）
            mode: 加密模式
            
        Returns:
            (加密数据, 元数据)
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            
            # 生成密钥和IV
            key = os.urandom(key_size // 8)
            iv = os.urandom(8)  # Blowfish块大小为64位
            
            # 创建加密器
            if mode == 'CBC':
                cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
                
                # 填充数据
                padder = padding.PKCS7(64).padder()  # Blowfish块大小为64位
                padded_data = padder.update(data) + padder.finalize()
                
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
                
            elif mode == 'ECB':
                cipher = Cipher(algorithms.Blowfish(key), modes.ECB())
                
                # 填充数据
                padder = padding.PKCS7(64).padder()
                padded_data = padder.update(data) + padder.finalize()
                
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
                
            else:
                raise ValueError(f"不支持的Blowfish模式: {mode}")
            
            metadata = {
                'algorithm': 'Blowfish',
                'key_size': key_size,
                'mode': mode,
                'key': key,
                'iv': iv if mode == 'CBC' else None
            }
            
            self.logger.debug(f"Blowfish-{key_size}-{mode}加密完成，数据大小: {len(encrypted_data)}")
            return encrypted_data, metadata
            
        except ImportError:
            self.logger.error("cryptography库未安装，无法使用Blowfish加密")
            # 回退到简单加密
            return self._fallback_encrypt(data)
        except Exception as e:
            self.logger.error(f"Blowfish加密失败: {e}")
            raise
    
    def decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        Blowfish解密
        
        Args:
            encrypted_data: 加密的数据
            metadata: 加密元数据
            
        Returns:
            解密后的数据
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            
            key = metadata['key']
            mode = metadata['mode']
            iv = metadata.get('iv')
            
            # 创建解密器
            if mode == 'CBC':
                cipher = Cipher(algorithms.Blowfish(key), modes.CBC(iv))
            elif mode == 'ECB':
                cipher = Cipher(algorithms.Blowfish(key), modes.ECB())
            else:
                raise ValueError(f"不支持的Blowfish模式: {mode}")
            
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # 移除填充
            unpadder = padding.PKCS7(64).unpadder()
            decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
            
            self.logger.debug(f"Blowfish解密完成，数据大小: {len(decrypted_data)}")
            return decrypted_data
            
        except ImportError:
            return self._fallback_decrypt(encrypted_data, metadata)
        except Exception as e:
            self.logger.error(f"Blowfish解密失败: {e}")
            raise
    
    def _fallback_encrypt(self, data: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """回退加密方法"""
        key = os.urandom(len(data))
        encrypted_data = bytes(a ^ b for a, b in zip(data, key))
        
        metadata = {
            'algorithm': 'Blowfish_Fallback',
            'key': key
        }
        
        return encrypted_data, metadata
    
    def _fallback_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """回退解密方法"""
        key = metadata['key']
        return bytes(a ^ b for a, b in zip(encrypted_data, key))
    
    def generate_key(self, key_size: int = 256) -> bytes:
        """生成Blowfish密钥"""
        if key_size < 32 or key_size > 448:
            raise ValueError("Blowfish密钥大小必须在32-448位之间")
        
        return os.urandom(key_size // 8)
    
    def get_supported_key_sizes(self) -> list:
        """获取支持的密钥大小"""
        return list(range(32, 449, 8))  # 32-448位，8位递增
    
    def get_supported_modes(self) -> list:
        """获取支持的加密模式"""
        return ['CBC', 'ECB']
    
    def get_recommended_config(self) -> Dict[str, Any]:
        """获取推荐配置"""
        return {
            'key_size': 256,
            'mode': 'CBC',
            'description': 'Blowfish-256-CBC提供良好的安全性和性能'
        }
