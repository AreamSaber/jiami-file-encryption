"""
AES加密算法实现
"""

import os
from typing import Tuple, Dict, Any

from ..utils.logger import Logger


class AESEncryption:
    """AES加密算法类"""
    
    def __init__(self):
        """初始化AES加密"""
        self.logger = Logger("AESEncryption")
    
    def encrypt(self, data: bytes, key_size: int = 256, mode: str = 'GCM') -> Tuple[bytes, Dict[str, Any]]:
        """
        AES加密
        
        Args:
            data: 要加密的数据
            key_size: 密钥大小（128, 192, 256）
            mode: 加密模式（CBC, GCM, CTR）
            
        Returns:
            (加密数据, 元数据)
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding
            
            # 生成密钥和IV
            key = os.urandom(key_size // 8)
            
            if mode == 'GCM':
                iv = os.urandom(12)  # GCM推荐96位IV
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(data) + encryptor.finalize()
                
                metadata = {
                    'algorithm': 'AES',
                    'key_size': key_size,
                    'mode': mode,
                    'key': key,
                    'iv': iv,
                    'tag': encryptor.tag
                }
                
            elif mode == 'CBC':
                iv = os.urandom(16)  # CBC需要128位IV
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                
                # 填充数据
                padder = padding.PKCS7(128).padder()
                padded_data = padder.update(data) + padder.finalize()
                
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
                
                metadata = {
                    'algorithm': 'AES',
                    'key_size': key_size,
                    'mode': mode,
                    'key': key,
                    'iv': iv
                }
                
            elif mode == 'CTR':
                iv = os.urandom(16)
                cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
                encryptor = cipher.encryptor()
                encrypted_data = encryptor.update(data) + encryptor.finalize()
                
                metadata = {
                    'algorithm': 'AES',
                    'key_size': key_size,
                    'mode': mode,
                    'key': key,
                    'iv': iv
                }
                
            else:
                raise ValueError(f"不支持的AES模式: {mode}")
            
            self.logger.debug(f"AES-{key_size}-{mode} 加密完成，数据大小: {len(encrypted_data)}")
            return encrypted_data, metadata
            
        except ImportError:
            self.logger.error("cryptography库未安装，无法使用AES加密")
            raise
        except Exception as e:
            self.logger.error(f"AES加密失败: {e}")
            raise
    
    def decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        AES解密
        
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
            iv = metadata['iv']
            mode = metadata['mode']
            
            if mode == 'GCM':
                tag = metadata['tag']
                cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
                
            elif mode == 'CBC':
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
                decryptor = cipher.decryptor()
                padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
                
                # 移除填充
                unpadder = padding.PKCS7(128).unpadder()
                decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
                
            elif mode == 'CTR':
                cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
                
            else:
                raise ValueError(f"不支持的AES模式: {mode}")
            
            self.logger.debug(f"AES解密完成，数据大小: {len(decrypted_data)}")
            return decrypted_data
            
        except Exception as e:
            self.logger.error(f"AES解密失败: {e}")
            raise
    
    def generate_key(self, key_size: int = 256) -> bytes:
        """
        生成AES密钥
        
        Args:
            key_size: 密钥大小（位）
            
        Returns:
            AES密钥
        """
        if key_size not in [128, 192, 256]:
            raise ValueError("AES密钥大小必须是128、192或256位")
        
        return os.urandom(key_size // 8)
    
    def get_supported_modes(self) -> list:
        """获取支持的加密模式"""
        return ['GCM', 'CBC', 'CTR']
    
    def get_recommended_config(self) -> Dict[str, Any]:
        """获取推荐配置"""
        return {
            'key_size': 256,
            'mode': 'GCM',
            'description': 'AES-256-GCM提供最佳的安全性和性能平衡'
        }
