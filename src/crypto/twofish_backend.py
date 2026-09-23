"""Python 3.12+ binding to twofish 0.3.0's unchanged native implementation.

The upstream Python loader imports removed stdlib imp. Locate its installed
native library with importlib instead; no imp shim or substitute cipher.
ABI: Keybase python-twofish / Niels Ferguson Twofish, BSD-3-Clause.
See TWOFISH-LICENSE.txt for the upstream binding license.
"""
import ctypes as C
import importlib.util
from pathlib import Path
import sys


class _Schedule(C.Structure):
    _fields_ = [('sboxes', C.c_uint32 * 1024), ('round_keys', C.c_uint32 * 40)]


def _load():
    spec = importlib.util.find_spec('_twofish')
    origin = spec.origin if spec else None
    if origin is None and getattr(sys, 'frozen', False):
        candidates = list(Path(sys._MEIPASS).glob('_twofish*.pyd'))
        if len(candidates) == 1:
            origin = str(candidates[0])
    if origin is None:
        raise ImportError('twofish==0.3.0 and its native library are required')
    native = C.CDLL(origin)
    for name, args in (
        ('initialise', []),
        ('prepare_key', [C.c_char_p, C.c_int, C.POINTER(_Schedule)]),
        ('encrypt', [C.POINTER(_Schedule), C.c_char_p, C.c_void_p]),
        ('decrypt', [C.POINTER(_Schedule), C.c_char_p, C.c_void_p]),
    ):
        function = getattr(native, 'exp_Twofish_' + name)
        function.argtypes, function.restype = args, None
    native.exp_Twofish_initialise()
    return native


_NATIVE = _load()


class Twofish:
    def __init__(self, key):
        if type(key) is not bytes or len(key) not in (16, 24, 32):
            raise ValueError('Twofish requires a 128/192/256-bit key')
        self._schedule = _Schedule()
        _NATIVE.exp_Twofish_prepare_key(key, len(key), C.byref(self._schedule))

    def _block(self, data, decrypt):
        if type(data) is not bytes or len(data) != 16:
            raise ValueError('Twofish requires a 16-byte block')
        output = C.create_string_buffer(16)
        operation = _NATIVE.exp_Twofish_decrypt if decrypt else _NATIVE.exp_Twofish_encrypt
        operation(C.byref(self._schedule), data, output)
        return output.raw

    def encrypt(self, data):
        return self._block(data, False)

    def decrypt(self, data):
        return self._block(data, True)
