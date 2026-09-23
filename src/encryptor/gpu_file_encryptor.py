"""Engine adapter using the same authenticated writer as FileEncryptor.

Unverified legacy GPU-only kernels are not automatically selected for v1.
A supplied backend must produce the v1 producer contract. CPU fallback is
explicitly reported and never changes the configured algorithms after failure.
"""
from pathlib import Path
import time

from src.encryptor.file_processor import FileProcessor
from src.encryptor.pure_cpu_engine import PureCPUEngine
from src.package_format.writer import write_package


class GPUFileEncryptor:
    def __init__(self, allow_fallback=True, *, backend=None):
        self.allow_fallback = allow_fallback
        self.backend = backend
        self.gpu_available = backend is not None
        self.using_fallback = backend is None
        if self.using_fallback and not allow_fallback:
            raise RuntimeError('No validated v1 GPU backend is configured')

    def encrypt_file(self, input_file, output_dir='.', security_level=3, progress_callback=None):
        engine = None
        try:
            started = time.monotonic()
            source = Path(input_file)
            plaintext = FileProcessor().read_file(source)
            if self.backend is None:
                engine = PureCPUEngine(security_level=security_level)
                result = engine.encrypt_with_security_level(plaintext, progress_callback)
            else:
                result = self.backend.encrypt_with_security_level(plaintext, security_level, progress_callback)
            publication = write_package(result, plaintext, Path(output_dir)/(source.name+'.jiami'),
                                        profile='level-'+str(security_level), original_name=source.name)
            duration = time.monotonic()-started
            warning = publication.warning
            if self.using_fallback:
                warning = 'Using CPU: v1 GPU parity is not yet verified. ' + warning
            return {'success':True, 'package_dir':str(publication.path),
                    'encrypted_file':str(publication.path/'data.jmi'),
                    'recovery_file':str(publication.path/'recovery.jmis'),
                    'decryptor_file':str(publication.path/'recover.py'), 'decryptor_exe':None,
                    'original_size':len(plaintext), 'encrypted_size':len(result['encrypted_data']),
                    'encryption_time':duration, 'total_time':duration,
                    'speed_mbps':len(plaintext)/(1024*1024*max(duration,1e-9)),
                    'security_level':security_level, 'layers':len(result['metadata'].get('layers',[])),
                    'gpu_only':not self.using_fallback, 'using_fallback':self.using_fallback,
                    'engine_name':'CPU' if self.using_fallback else 'explicit GPU backend',
                    'publication_state':'published', 'durability':publication.durability, 'warning':warning}
        except Exception as exc:
            return {'success':False, 'error':str(exc), 'details':getattr(exc,'__notes__',[])}
        finally:
            if engine is not None:
                engine.shutdown()
