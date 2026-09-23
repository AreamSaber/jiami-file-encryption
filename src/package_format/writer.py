"""The single publication path for CLI, GUI, and engine adapters."""
import os
from pathlib import Path
import uuid

from .envelope import encode_frame
from .schema import create_headers
from .publication import make_stage, publish_directory, write_private


def write_package(result, plaintext, destination, *, profile, original_name, kind='file'):
    from src.encryptor.key_injector import KeyInjector
    from src.decryptor.base_decryptor import load_package
    package_id, mac_key = uuid.uuid4().hex, os.urandom(32)
    public, secret = create_headers(result, plaintext, profile, original_name, kind, package_id)
    recovery = encode_frame(secret, b'', mac_key, secret=True)
    data = encode_frame(public, result['encrypted_data'], mac_key)
    stage = make_stage(destination)
    try:
        write_private(stage/'data.jmi', data)
        write_private(stage/'recovery.jmis', recovery)
        KeyInjector().create_python_decryptor(recovery, stage/'recover.py')
        write_private(stage/'PRIVATE-README.txt', (
            'PRIVATE PACKAGE: do not share or zip this folder.\n'
            'Share only data.jmi. recovery.jmis and recover.py contain keys.\n'
            'Recover: python recover.py data.jmi NEW_OUTPUT_PATH\n'
            'Existing output is never overwritten. Legacy pickle is rejected.\n'
        ).encode('utf-8'))
        return publish_directory(stage, destination, lambda path: load_package(path))
    except Exception as exc:
        # Retained staging belongs to this attempt; never clean another attempt.
        if hasattr(exc, 'add_note'):
            exc.add_note('Private staging retained at ' + str(stage))
        raise
