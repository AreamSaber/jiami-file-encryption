"""File and data-only folder handling; pickle is never accepted."""
from pathlib import Path
from src.package_format.archive import pack_folder, unpack_folder
from src.package_format.envelope import MAX_BODY
from src.package_format.publication import make_stage, publish_directory


class FileProcessor:
    def read_file(self, file_path, *, expected_size=None):
        path = Path(file_path)
        size = path.stat().st_size
        if size > MAX_BODY:
            raise ValueError('Input exceeds the in-memory engine size limit')
        if expected_size is not None and size != expected_size:
            raise ValueError('Input changed after admission')
        limit = MAX_BODY if expected_size is None else min(MAX_BODY, expected_size)
        with path.open('rb') as stream:
            data = stream.read(limit + 1)
        if len(data) > limit or (expected_size is not None and len(data) != expected_size):
            raise ValueError('Input changed or exceeded the admitted size')
        return data

    def process_folder(self, folder_path, exclude_patterns=None, *, plan=None):
        return pack_folder(folder_path, exclude_patterns or [], plan=plan)

    def load_encrypted_data(self, file_path, recovery_path=None):
        from src.decryptor.base_decryptor import load_package
        public, secret, body = load_package(file_path, recovery_path)
        return {'public_metadata': public, 'secret_metadata': secret, 'encrypted_data': body}

    def save_encrypted_data(self, encryption_result, output_path, original_size=None, *, plaintext=None, profile='custom', original_name='data'):
        if plaintext is None:
            raise ValueError('v1 publication requires the original bytes; use FileEncryptor or write_package')
        from src.package_format.writer import write_package
        return write_package(encryption_result, plaintext, output_path, profile=profile, original_name=original_name)

    def restore_folder(self, folder_package, output_path):
        stage = make_stage(output_path)
        unpack_folder(folder_package, stage)
        return publish_directory(stage, output_path, lambda _: None)

    def get_file_info(self, file_path):
        path = Path(file_path)
        info = path.stat()
        return {'name': path.name, 'path': str(path), 'size': info.st_size,
                'modified_time': info.st_mtime, 'is_file': path.is_file(), 'extension': path.suffix}
