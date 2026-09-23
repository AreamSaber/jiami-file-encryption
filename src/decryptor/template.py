"""Compatibility entry point for the shared v1 reader; no template cipher copy."""
from .cpu_decryptor import CPUDecryptor


class FileDecryptor(CPUDecryptor):
    def _decrypt_layered(self, encrypted_data, layers):
        # Trusted in-process engine compatibility; file inputs use authenticated frames.
        from src.package_format.schema import split_node, validate_node
        data = encrypted_data
        for index in reversed(range(len(layers))):
            public, secret = split_node(layers[index], index)
            validate_node(public, secret, index)
            data = self._node(data, public, secret)
        return data


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Recover a v1 package; legacy pickle is rejected')
    parser.add_argument('input')
    parser.add_argument('output', nargs='?')
    parser.add_argument('--recovery')
    args = parser.parse_args()
    print(FileDecryptor(recovery_path=args.recovery).decrypt_file(args.input, args.output))


if __name__ == '__main__':
    main()
