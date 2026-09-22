"""Standard Twofish only; an unavailable native library is an explicit error."""
import os


class TwofishEncryption:
    def encrypt(self, data, key_size=256):
        from src.crypto.twofish_backend import Twofish
        from cryptography.hazmat.primitives import padding
        if key_size not in (128, 192, 256):
            raise ValueError('Invalid Twofish key size')
        key = os.urandom(key_size//8)
        cipher = Twofish(key)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(data)+padder.finalize()
        encrypted = b''.join(cipher.encrypt(padded[i:i+16]) for i in range(0,len(padded),16))
        return encrypted, {'algorithm':'Twofish','key_size':key_size,'key':key,'original_length':len(data)}

    def decrypt(self, data, metadata):
        from src.decryptor.algorithm_registry import TwofishHandler
        return TwofishHandler().decrypt(data, metadata)
