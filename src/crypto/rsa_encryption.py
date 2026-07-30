"""
RSA加密算法实现
"""

import os
from typing import Tuple, Dict, Any

from ..utils.logger import Logger


class RSAEncryption:
    """RSA加密算法类"""
    
    def __init__(self):
        """初始化RSA加密"""
        self.logger = Logger("RSAEncryption")
    
    def encrypt(self, data: bytes, key_size: int = 2048) -> Tuple[bytes, Dict[str, Any]]:
        """
        RSA加密
        
        Args:
            data: 要加密的数据
            key_size: RSA密钥大小
            
        Returns:
            (加密数据, 元数据)
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.hazmat.primitives import hashes
            
            # 生成RSA密钥对
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            public_key = private_key.public_key()
            
            # RSA加密限制
            max_data_size = key_size // 8 - 42  # OAEP填充的限制
            
            if len(data) > max_data_size:
                # 对于大数据，使用混合加密
                return self._hybrid_encrypt(data, public_key, private_key, key_size)
            else:
                # 直接RSA加密
                encrypted_data = public_key.encrypt(
                    data,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                metadata = {
                    'algorithm': 'RSA',
                    'key_size': key_size,
                    'private_key': private_key,
                    'public_key': public_key
                }
                
                self.logger.debug(f"RSA-{key_size}加密完成，数据大小: {len(encrypted_data)}")
                return encrypted_data, metadata
                
        except ImportError:
            self.logger.error("cryptography库未安装，无法使用RSA加密")
            # 回退到简单加密
            return self._fallback_encrypt(data)
        except Exception as e:
            self.logger.error(f"RSA加密失败: {e}")
            raise
    
    def _hybrid_encrypt(self, data: bytes, public_key, private_key, key_size: int) -> Tuple[bytes, Dict[str, Any]]:
        """混合RSA加密（RSA + AES）"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives import hashes
            
            # 生成AES密钥
            aes_key = os.urandom(32)  # 256位AES密钥
            iv = os.urandom(16)  # 128位IV
            
            # 用AES加密数据
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            
            # 填充数据
            from cryptography.hazmat.primitives import padding as sym_padding
            padder = sym_padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()
            
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # 用RSA加密AES密钥
            encrypted_aes_key = public_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            metadata = {
                'algorithm': 'RSA-Hybrid',
                'key_size': key_size,
                'private_key': private_key,
                'public_key': public_key,
                'encrypted_aes_key': encrypted_aes_key,
                'iv': iv
            }
            
            self.logger.debug(f"RSA混合加密完成，数据大小: {len(encrypted_data)}")
            return encrypted_data, metadata
            
        except Exception as e:
            self.logger.error(f"RSA混合加密失败: {e}")
            raise
    
    def decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """
        RSA解密
        
        Args:
            encrypted_data: 加密的数据
            metadata: 加密元数据
            
        Returns:
            解密后的数据
        """
        try:
            algorithm = metadata['algorithm']
            private_key = metadata['private_key']
            
            if algorithm == 'RSA-Hybrid':
                return self._hybrid_decrypt(encrypted_data, metadata)
            else:
                # 直接RSA解密
                from cryptography.hazmat.primitives.asymmetric import padding
                from cryptography.hazmat.primitives import hashes
                
                decrypted_data = private_key.decrypt(
                    encrypted_data,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                self.logger.debug(f"RSA解密完成，数据大小: {len(decrypted_data)}")
                return decrypted_data
                
        except ImportError:
            return self._fallback_decrypt(encrypted_data, metadata)
        except Exception as e:
            self.logger.error(f"RSA解密失败: {e}")
            raise
    
    def _hybrid_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """混合RSA解密"""
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.primitives import hashes
            
            private_key = metadata['private_key']
            encrypted_aes_key = metadata['encrypted_aes_key']
            iv = metadata['iv']
            
            # 用RSA解密AES密钥
            aes_key = private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            # 用AES解密数据
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # 移除填充
            from cryptography.hazmat.primitives import padding as sym_padding
            unpadder = sym_padding.PKCS7(128).unpadder()
            decrypted_data = unpadder.update(padded_data) + unpadder.finalize()
            
            self.logger.debug(f"RSA混合解密完成，数据大小: {len(decrypted_data)}")
            return decrypted_data
            
        except Exception as e:
            self.logger.error(f"RSA混合解密失败: {e}")
            raise
    
    def _fallback_encrypt(self, data: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """回退加密方法"""
        key = os.urandom(len(data))
        encrypted_data = bytes(a ^ b for a, b in zip(data, key))
        
        metadata = {
            'algorithm': 'RSA_Fallback',
            'key': key
        }
        
        return encrypted_data, metadata
    
    def _fallback_decrypt(self, encrypted_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """回退解密方法"""
        key = metadata['key']
        return bytes(a ^ b for a, b in zip(encrypted_data, key))
    
    def generate_key_pair(self, key_size: int = 2048):
        """生成RSA密钥对"""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            public_key = private_key.public_key()
            
            return private_key, public_key
            
        except ImportError:
            self.logger.error("cryptography库未安装，无法生成RSA密钥对")
            return None, None
    
    def get_supported_key_sizes(self) -> list:
        """获取支持的密钥大小"""
        return [1024, 2048, 3072, 4096]
    
    def get_recommended_config(self) -> Dict[str, Any]:
        """获取推荐配置"""
        return {
            'key_size': 2048,
            'description': 'RSA-2048提供良好的安全性，适合密钥交换和数字签名'
        }
