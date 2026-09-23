"""Explicit backend adapter; format parsing and publication remain shared."""
from .base_decryptor import BaseDecryptor


class GPUDecryptor(BaseDecryptor):
    """Use a supplied, parity-tested backend for its declared algorithm variants.

    Backend contract: supports(algorithm, params) and decrypt(data, algorithm,
    params). GPU selection is explicit; no unverified kernel is selected by name.
    CPU fallback is opt-in and its use is reported in backend_used.
    """

    def __init__(self, recovery_path=None, recovery_bytes=None, *, backend=None, allow_fallback=False):
        super().__init__(recovery_path, recovery_bytes)
        if backend is None and not allow_fallback:
            raise RuntimeError('A validated GPU backend is required; CPU fallback must be requested explicitly')
        self.backend = backend
        self.allow_fallback = allow_fallback
        self.backend_used = set()

    def decrypt_layer(self, data, algorithm, params):
        if self.backend is not None and self.backend.supports(algorithm, params):
            result = self.backend.decrypt(data, algorithm, params)
            if type(result) is not bytes:
                raise TypeError('GPU backend must return bytes')
            self.backend_used.add('gpu')
            return result
        if not self.allow_fallback:
            raise RuntimeError('GPU backend does not support ' + algorithm)
        self.backend_used.add('cpu')
        return super().decrypt_layer(data, algorithm, params)
