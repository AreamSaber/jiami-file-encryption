"""File and data-only folder handling; pickle is never accepted."""
from pathlib import Path
from src.package_format.archive import pack_folder, unpack_folder
from src.package_format.envelope import MAX_BODY
from src.package_format.publication import make_stage, publish_directory


class FileProcessor:
    def read_file(self, file_path):
        path = Path(file_path)
        if path.stat().st_size > MAX_BODY:
            raise ValueError('Input exceeds the in-memory engine size limit')
        with path.open('rb') as stream:
            data = stream.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise ValueError('Input exceeds the in-memory engine size limit')
        return data

    def process_folder(self, folder_path, exclude_patterns=None):
        return pack_folder(folder_path, exclude_patterns or [])

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
