"""CPU recovery through the shared, authenticated package reader."""
from .base_decryptor import BaseDecryptor


class CPUDecryptor(BaseDecryptor):
    backend = 'cpu'
