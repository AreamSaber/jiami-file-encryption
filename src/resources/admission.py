"""Exact shipped-profile size predictions and provisional allocation estimates."""
from dataclasses import dataclass
import hashlib
import json

from src.package_format.envelope import MAX_BODY, MAX_COLLECTION, MAX_HEADER
from src.package_format.schema import predicted_collection_sizes, predicted_output_size, rsa_variant

MIB = 1024 * 1024
# Canonical JSON fingerprints pin the reviewed profile definitions, not merely
# their names or a mutable config file. Profile edits need explicit revalidation.
SHIPPED = {
    'basic': '82f7b0c3620c18fb832b0b6fc4d8fd2e8f0cb14a8603c5c0b1ed9f05d2430995',
    'standard': '4e6cf050672778f5e30c2818da636db7c46d5535e6a3fec041dc34236e8cbf99',
    'high': '1c92c4053a7ff3c2bd261c6aff11a963e7f0dfee8746c69a5c73c9b3efe785a4',
    'stealth': 'c5fdbe54f0bae8441c246e44cf7d53e13cd9a1b7176db20ebe99929db1694ecf',
    'paranoid': '198ee8bb3978fb80052a5dd122e36880143d125325f4d0217f583f956d63672f',
    'parallel_fast': '34d0b2ec55cfbf4bfcd01e3ee86ef31f1e9f5d50fd1f0e8299f30824f3c2544e',
    'blowfish_secure': '188fa9e4e5947e04921813439da57a664cfc6459431256d465ef575e86fc4f1d',
    'salsa20_stream': '40d386905ea7b2ac9dcc153eafc58b18e906467668bf1f2a87dc82279bcef4b3',
    'twofish_strong': '43933eae5210ef77ce6895a3bec78997387a0880a996cc38b4059e9d7601bdbb',
    'multi_algorithm': 'd628a5c206e8070f52c3b05e7c348debd2b8e5c59771ae672fa4ca2ba83876d2',
    'paranoid_gpu': '9110e207c78139b8422c3526eefc2662189840f8b8769043229143870c6c479f',
}


class AdmissionError(ValueError):
    error_code = 'ADMISSION_FORMAT'


def _known_profile(config, profile, custom):
    if custom or (profile is not None and profile not in SHIPPED):
        return False
    try:
        encoded = json.dumps(config, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    except (TypeError, ValueError):
        return False
    digest = hashlib.sha256(encoded).hexdigest()
    return digest == SHIPPED[profile] if profile is not None else digest in SHIPPED.values()


@dataclass(frozen=True)
class LayerSize:
    algorithm: str
    input_size: int
    output_size: int
    insertion_count: int
    header_upper: int
    working_bytes: int


@dataclass(frozen=True)
class AdmissionEstimate:
    guaranteed: bool
    reason: str
    input_size: int
    output_size: int = 0
    strategy: str = ''
    # Each tuple is one sequential stage or one independent parallel chunk.
    stages: tuple = ()
    estimated_peak_bytes: int = 0
    header_upper_bytes: int = 0
    violations: tuple = ()

    def check_format(self):
        if self.violations:
            raise AdmissionError('; '.join(self.violations))

    def summary(self):
        return {'status': 'exact_sizes_soft_memory' if self.guaranteed else 'no_guarantee',
                'reason': self.reason, 'estimated_peak_bytes': self.estimated_peak_bytes,
                'predicted_output_bytes': self.output_size if self.guaranteed else None}


def _variant(layer, size):
    params = {**layer, **layer.get('params', {})}
    method = layer['method']
    if method == 'rsa':
        params.setdefault('key_size', 2048)
        return rsa_variant(size, params['key_size']), params
    algorithms = {'aes256': 'AES-256', 'chacha20': 'ChaCha20-CPU', 'salsa20': 'Salsa20_PyNaCl',
                  'blowfish': 'Blowfish', 'twofish': 'Twofish', 'steganography': 'LSB_Steganography'}
    if method == 'custom':
        algorithms = {'bit_shuffle': 'Bit_Shuffle', 'rotate_cipher': 'Rotate_Cipher',
                      'matrix_cipher': 'Matrix_Cipher-CPU', 'pre_scramble': 'Pre_Scramble',
                      'final_obfuscation': 'Final_Obfuscation'}
        return algorithms[params['algorithm']], params
    return algorithms[method], params


def _layer_size(layer, size):
    algorithm, params = _variant(layer, size)
    output = predicted_output_size(algorithm, params, size)
    inserted = predicted_collection_sizes(algorithm, params, size).get('insertion_positions', 0)
    # Upper estimates, not exact JSON lengths: random operation choices, RSA PEM,
    # integer widths and key values vary. No recovery values are materialized.
    header = 20000 if algorithm.startswith('RSA') else 4096
    if algorithm == 'Final_Obfuscation':
        header = 16384 + inserted * (len(str(max(0, size - 1))) + 1)
    work = 2 * size + 2 * output
    if algorithm == 'LSB_Steganography':
        # Includes the current producer's temporary per-byte bit strings/list.
        work += 80 * size
    if algorithm == 'Final_Obfuscation':
        # Python integer/list/set temporaries plus metadata validation copies.
        work += 128 * inserted
    return LayerSize(algorithm, size, output, inserted, header, work)


def _position_list_minimum(count):
    """Minimum JSON length of count distinct nonnegative integer positions."""
    digits, start, width = 1, 1, 1  # zero contributes one digit
    if not count:
        return 2
    while start < count:
        stop = min(count, start * 10)
        digits += (stop - start) * width
        start *= 10
        width += 1
    return 2 + digits + count - 1


def estimate_admission(engine, size, config, *, profile=None, custom=False):
    """Predict without reading plaintext or creating a cipher/thread pool.

    Only exact bundled configurations qualify. Explicit custom_config, modified
    configurations and unrecognized variants retain post-hoc validation.
    """
    if type(size) is not int or size < 0:
        raise ValueError('Input size must be a nonnegative integer')
    if not _known_profile(config, profile, custom):
        return AdmissionEstimate(False, 'No admission guarantee for custom or unrecognized configuration', size)
    layers = config['layers']
    strategy = engine.choose_strategy_for_size(size, config)
    stages, violations = [], []
    if size > MAX_BODY:
        violations.append(f'Input size {size} exceeds MAX_BODY={MAX_BODY}')
    try:
        if strategy == 'parallel':
            for i, (start, end) in enumerate(engine.parallel_chunk_ranges(size, config)):
                stages.append((_layer_size(layers[i % len(layers)], end - start),))
            output = sum(stage[0].output_size for stage in stages)
            if len(stages) > 1024:
                violations.append('Parallel chunk count exceeds 1024')
        else:
            output = size
            for layer in layers:
                chunk_size = None
                if strategy == 'threaded_layered':
                    _, chunk_size = engine.threaded_layer_shape(output, layer['method'])
                if chunk_size is None:
                    stage = (_layer_size(layer, output),)
                else:
                    count = (output + chunk_size - 1) // chunk_size
                    if count > 1024:
                        violations.append(f'Layer chunk count {count} exceeds 1024')
                        # Bound the estimator itself for adversarial stat sizes.
                        return AdmissionEstimate(True, 'Exact topology exceeds supported limits', size,
                                                 strategy=strategy, violations=tuple(violations))
                    stage = tuple(_layer_size(layer, min(chunk_size, output - offset))
                                  for offset in range(0, output, chunk_size))
                stages.append(stage)
                output = sum(node.output_size for node in stage)
                if output > MAX_BODY:
                    violations.append(f'Layer output {output} exceeds MAX_BODY={MAX_BODY}')
    except (KeyError, ValueError, TypeError) as exc:
        return AdmissionEstimate(False, 'No admission guarantee for algorithm variant: ' + str(exc), size)
    nodes = [node for stage in stages for node in stage]
    for node in nodes:
        if node.output_size > MAX_BODY:
            violations.append(f'{node.algorithm} output {node.output_size} exceeds MAX_BODY={MAX_BODY}')
        if node.insertion_count > MAX_COLLECTION:
            violations.append(f'{node.algorithm} insertion_positions={node.insertion_count} exceeds MAX_COLLECTION={MAX_COLLECTION}')
    if output > MAX_BODY:
        violations.append(f'Ciphertext size {output} exceeds MAX_BODY={MAX_BODY}')
    if sum(_position_list_minimum(n.insertion_count) for n in nodes) > MAX_HEADER:
        violations.append(f'Minimum insertion-list JSON size exceeds MAX_HEADER={MAX_HEADER}')
    header = 8192 + sum(n.header_upper for n in nodes)  # both frame structures/filename
    # Allocation model, not a peak-RSS theorem: profile/topology-sensitive working
    # buffers, retained input/output, JSON/metadata copies and fixed runtime slack.
    work = (sum(n.working_bytes for n in nodes) if strategy == 'parallel'
            else max(sum(n.working_bytes for n in stage) for stage in stages))
    peak = 8 * MIB + 2 * size + max(4 * output, work) + 8 * header
    return AdmissionEstimate(True, 'Exact ciphertext/collection sizes; provisional memory and JSON bounds',
                             size, output, strategy, tuple(stages), peak, header, tuple(violations))
