"""Closed per-variant metadata schemas and explicit public/secret projection."""
import base64
import binascii
import hashlib
import re

from src.exceptions.decryption_errors import InvalidMetadataError, KeyMismatchError
from .envelope import MAX_BODY, json_bytes

# algorithm: (method, public parameter fields, secret parameter fields)
SCHEMAS = {
    'AES-256': ('aes256', {'mode'}, {'key', 'iv'}),
    'ChaCha20-CPU': ('chacha20', set(), {'key', 'nonce'}),
    'Salsa20_PyNaCl': ('salsa20', {'encrypted_with_nonce'}, {'key'}),
    'Blowfish': ('blowfish', {'key_size', 'mode'}, {'key', 'iv'}),
    'Twofish': ('twofish', {'key_size', 'original_length'}, {'key'}),
    'RSA': ('rsa', {'key_size'}, {'private_key_pem'}),
    'RSA-Hybrid': ('rsa', {'key_size'}, {'private_key_pem', 'encrypted_aes_key', 'aes_metadata'}),
    'LSB_Steganography': ('steganography', {'cover_size', 'data_size'}, set()),
    'Simple_XOR': ('custom', set(), {'key'}),
    'Bit_Shuffle': ('custom', set(), {'seed', 'bit_positions'}),
    'Rotate_Cipher': ('custom', set(), {'rotation'}),
    'Matrix_Cipher-CPU': ('custom', {'matrix_size', 'key_schedule', 'original_length'}, {'seed', 'transform_matrix'}),
    'Pre_Scramble': ('custom', {'scramble_rounds'}, {'seed', 'operations'}),
    'Final_Obfuscation': ('custom', {'obfuscation_level', 'operations_count', 'original_length'}, {'obfuscation_key', 'applied_operations'}),
}
BYTES_FIELDS = {'key', 'iv', 'nonce', 'tag', 'encrypted_aes_key', 'obfuscation_key'}
DIAGNOSTICS = {'thread_count', 'gpu_accelerated'}
NODE_FIELDS = {'layer_index', 'method', 'algorithm', 'input_size', 'output_size', 'params'}


def require(condition, message):
    if not condition:
        raise InvalidMetadataError(message)


def exact(obj, fields):
    require(type(obj) is dict and set(obj) == set(fields), 'Missing or unknown metadata field')


def integer(value, low=0, high=MAX_BODY):
    require(type(value) is int and low <= value <= high, 'Invalid bounded integer')
    return value


def safe_name(value):
    require(type(value) is str and 0 < len(value) <= 255 and value not in ('.', '..')
            and not any(c in value for c in '/\\\x00:<>"|?*')
            and all(ord(c) >= 32 for c in value) and not value.endswith((' ', '.')),
            'Invalid original filename')
    require(value.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
            *('COM'+str(i) for i in range(1, 10)), *('LPT'+str(i) for i in range(1, 10))},
            'Reserved original filename')
    return value


def _wire(params, encode):
    result = {}
    for field, value in params.items():
        if field == 'aes_metadata':
            result[field] = _wire(value, encode)
        elif field in BYTES_FIELDS and value is not None:
            if encode:
                require(type(value) is bytes, 'Expected bytes for ' + field)
                result[field] = base64.b64encode(value).decode('ascii')
            else:
                require(type(value) is str, 'Expected base64 for ' + field)
                try:
                    result[field] = base64.b64decode(value, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise InvalidMetadataError('Invalid base64 field') from exc
        else:
            # Operation tuples have a defined list representation in the protocol.
            result[field] = [list(op) for op in value] if field in ('operations', 'applied_operations') else value
    return result


def fields_for(algorithm, params):
    require(type(algorithm) is str and algorithm in SCHEMAS, 'Unsupported algorithm variant')
    require(type(params) is dict, 'Expected parameter object')
    method, public, secret = SCHEMAS[algorithm]
    secret = secret | ({'tag'} if algorithm == 'AES-256' and params.get('mode') == 'GCM' else set())
    return method, public, secret


def validate_params(algorithm, params, input_size, output_size):
    method, public, secret = fields_for(algorithm, params)
    exact(params, public | secret)
    for k in BYTES_FIELDS & params.keys():
        require(type(params[k]) is bytes or (algorithm == 'Blowfish' and k == 'iv' and params['mode'] == 'ECB' and params[k] is None), 'Invalid bytes field')
    if 'key' in params:
        require(0 < len(params['key']) <= 56, 'Invalid cipher key size')
    if algorithm == 'AES-256':
        require(len(params['key']) == 32 and params['mode'] in ('CBC', 'GCM', 'CTR'), 'Invalid AES parameters')
        require(len(params['iv']) == (12 if params['mode'] == 'GCM' else 16), 'Invalid AES IV/counter')
        if params['mode'] == 'GCM':
            require(len(params['tag']) == 16, 'Invalid GCM tag')
        require(output_size == ((input_size // 16 + 1) * 16 if params['mode'] == 'CBC' else input_size), 'AES length mismatch')
    elif algorithm == 'ChaCha20-CPU':
        require(len(params['key']) == 32 and len(params['nonce']) == 16 and input_size == output_size, 'Invalid ChaCha20 parameters')
    elif algorithm == 'Salsa20_PyNaCl':
        require(len(params['key']) == 32 and params['encrypted_with_nonce'] is True and output_size == input_size + 40, 'Invalid SecretBox parameters')
    elif algorithm in ('Blowfish', 'Twofish'):
        require(params['key_size'] == len(params['key']) * 8, 'Key size mismatch')
        block = 8 if algorithm == 'Blowfish' else 16
        require(output_size == (input_size // block + 1) * block, 'Block cipher length mismatch')
        if algorithm == 'Blowfish':
            require(4 <= len(params['key']) <= 56 and params['mode'] in ('CBC', 'ECB'), 'Invalid Blowfish parameters')
            require(params['iv'] is None if params['mode'] == 'ECB' else len(params['iv']) == 8, 'Invalid Blowfish IV')
        else:
            require(len(params['key']) in (16, 24, 32) and params['original_length'] == input_size, 'Invalid Twofish parameters')
    elif algorithm.startswith('RSA'):
        require(type(params['private_key_pem']) is str and len(params['private_key_pem']) <= 16384 and
                params['private_key_pem'].startswith('-----BEGIN PRIVATE KEY-----'), 'Invalid RSA private key encoding')
        require(type(params['key_size']) is int and params['key_size'] in (2048, 3072, 4096), 'Invalid RSA key size')
        if algorithm == 'RSA':
            require(output_size == params['key_size']//8, 'Invalid RSA ciphertext length')
        else:
            require(len(params['encrypted_aes_key']) == params['key_size']//8, 'Invalid wrapped key length')
            aes = dict(params['aes_metadata'])
            require(aes.pop('algorithm', None) == 'AES-256' and aes.get('mode') == 'GCM', 'Invalid RSA hybrid cipher')
            validate_params('AES-256', aes, input_size, output_size)
    elif algorithm == 'LSB_Steganography':
        require(params['data_size'] == input_size and params['cover_size'] == output_size == input_size * 8, 'Invalid steganography size')
    elif algorithm == 'Simple_XOR':
        require(input_size == output_size, 'XOR length mismatch')
    elif algorithm == 'Bit_Shuffle':
        integer(params['seed'], 0, 2**64-1)
        positions = params['bit_positions']
        require(type(positions) is list and all(type(x) is int for x in positions)
                and sorted(positions) == list(range(8)) and input_size == output_size, 'Invalid bit permutation')
    elif algorithm == 'Rotate_Cipher':
        integer(params['rotation'], 0, 255)
        require(input_size == output_size, 'Rotate length mismatch')
    elif algorithm == 'Matrix_Cipher-CPU':
        n = integer(params['matrix_size'], 1, 16)
        integer(params['seed'], 0, 2**64-1)
        require(params['key_schedule'] in ('dynamic', 'complex', 'static', 'simple') and params['original_length'] == input_size, 'Invalid matrix parameters')
        matrix = params['transform_matrix']
        require(type(matrix) is list and len(matrix) == n and all(type(row) is list and len(row) == n for row in matrix), 'Invalid matrix dimensions')
        require(all(type(x) is int and x in (0, 1) for row in matrix for x in row)
                and all(sum(row) == 1 for row in matrix) and all(sum(col) == 1 for col in zip(*matrix)), 'Matrix must be a permutation')
        require(output_size == ((input_size + n*n-1)//(n*n))*(n*n), 'Matrix length mismatch')
    elif algorithm == 'Pre_Scramble':
        rounds = integer(params['scramble_rounds'], 0, 100)
        integer(params['seed'], 0, 2**64-1)
        ops = params['operations']
        require(type(ops) is list and len(ops) <= rounds and input_size == output_size, 'Invalid scramble operations')
        for op in ops:
            require(type(op) is list and len(op) >= 2, 'Invalid operation')
            name, *args = op
            require(name in ('swap', 'reverse', 'rotate', 'xor') and len(args) == (2 if name in ('swap', 'reverse') else 1), 'Unknown operation/arity')
            for arg in args:
                integer(arg, 0, 255 if name == 'xor' else input_size)
            if name == 'swap':
                require(all(a < input_size for a in args), 'Swap outside input')
            if name == 'reverse':
                require(args[0] <= args[1], 'Invalid reverse interval')
    elif algorithm == 'Final_Obfuscation':
        require(len(params['obfuscation_key']) == 32 and params['original_length'] == input_size, 'Invalid obfuscation parameters')
        require(params['obfuscation_level'] in ('low', 'medium', 'high', 'maximum'), 'Invalid obfuscation level')
        ops = params['applied_operations']
        require(type(ops) is list and len(ops) == integer(params['operations_count'], 0, 100), 'Invalid operation count')
        size = output_size
        for op in reversed(ops):
            require(type(op) is list and len(op) == 2, 'Invalid obfuscation operation')
            name, arg = op
            if name == 'frequency_analysis_resistance':
                require(type(arg) is list and arg == sorted(set(arg)), 'Invalid insertion positions')
                for pos in arg:
                    integer(pos, 0, size - 1)
                    size -= 1
            elif name == 'byte_substitution':
                require(type(arg) is list and sorted(arg) == list(range(256)), 'Invalid substitution permutation')
            elif name in ('bit_permutation', 'block_cipher'):
                integer(arg, 0, 255)
            elif name == 'entropy_increase':
                require(arg is None, 'Unexpected entropy parameter')
            else:
                raise InvalidMetadataError('Unknown obfuscation operation')
        require(size == input_size, 'Obfuscation length mismatch')
    return method


def split_node(meta, index):
    algorithm, method = meta['algorithm'], meta['method']
    input_size, output_size = meta['input_size'], meta['output_size']
    public = dict(layer_index=index, method=method, algorithm=algorithm,
                  input_size=input_size, output_size=output_size, params={})
    secret = dict(layer_index=index, method=method, params={})
    structural = {'algorithm', 'method', 'input_size', 'output_size', 'layer_index'} | DIAGNOSTICS
    if 'chunks' in meta:
        require(not (set(meta) - structural - {'chunks'}), 'Unknown chunk metadata')
        chunks = meta['chunks']
        require(type(chunks) is dict and set(chunks) == set(range(len(chunks))), 'Non-contiguous producer chunk indexes')
        pairs = [split_node(chunks[i], i) for i in range(len(chunks))]
        public['algorithm'] = 'chunked'
        public['chunks'] = [p for p, s in pairs]
        secret['chunks'] = [s for p, s in pairs]
    else:
        _, pub_fields, secret_fields = fields_for(algorithm, meta)
        require(not (set(meta) - structural - pub_fields - secret_fields), 'Unknown producer metadata field')
        require(pub_fields | secret_fields <= set(meta), 'Missing producer recovery field')
        params = {k: meta[k] for k in pub_fields | secret_fields}
        wire = _wire(params, True)
        validate_params(algorithm, _wire(wire, False), input_size, output_size)
        public['params'] = {k: wire[k] for k in pub_fields}
        secret['params'] = {k: wire[k] for k in secret_fields}
    return public, secret


def validate_node(public, secret, index, depth=0):
    require(depth <= 1, 'Nested chunking is unsupported')
    chunked = public.get('algorithm') == 'chunked' if type(public) is dict else False
    exact(public, NODE_FIELDS | ({'chunks'} if chunked else set()))
    exact(secret, {'layer_index', 'method', 'params'} | ({'chunks'} if chunked else set()))
    require(type(public['layer_index']) is int and type(secret['layer_index']) is int
            and public['layer_index'] == secret['layer_index'] == index
            and public['method'] == secret['method'], 'Layer identity mismatch')
    integer(public['input_size']); integer(public['output_size'])
    if chunked:
        exact(public['params'], set()); exact(secret['params'], set())
        children, secrets = public['chunks'], secret['chunks']
        require(type(children) is list and type(secrets) is list and 1 <= len(children) == len(secrets) <= 1024, 'Invalid chunk count')
        for i, (child, key) in enumerate(zip(children, secrets)):
            require(child['method'] == public['method'], 'Chunk method mismatch')
            validate_node(child, key, i, depth+1)
        require(sum(c['input_size'] for c in children) == public['input_size'] and
                sum(c['output_size'] for c in children) == public['output_size'], 'Chunk boundary mismatch')
    else:
        method, pf, sf = fields_for(public['algorithm'], public['params'])
        exact(public['params'], pf); exact(secret['params'], sf)
        require(method == public['method'], 'Algorithm/method mismatch')
        params = _wire({**public['params'], **secret['params']}, False)
        validate_params(public['algorithm'], params, public['input_size'], public['output_size'])


def create_headers(result, plaintext, profile, original_name, kind, package_id):
    require(type(result) is dict and {'metadata', 'encrypted_data'} <= result.keys()
            and not (result.keys() - {'metadata', 'encrypted_data', 'duration', 'strategy_used', 'cpu_engine_info'}),
            'Unknown or missing producer result field')
    metadata = result['metadata']
    require(type(metadata) is dict and 'type' in metadata, 'Invalid producer metadata')
    topology = 'parallel_chunks' if metadata['type'] == 'parallel' else 'sequential'
    if topology == 'parallel_chunks':
        exact(metadata, {'type', 'chunks', 'chunk_count', 'original_size', 'thread_count'})
        chunks = metadata['chunks']
        require(type(chunks) is dict and set(chunks) == set(range(len(chunks)))
                and metadata['chunk_count'] == len(chunks), 'Invalid producer chunk indexes')
        for i, chunk in chunks.items():
            exact(chunk, {'index', 'data', 'metadata', 'original_size', 'method'})
            require(chunk['index'] == i and chunk['original_size'] == chunk['metadata']['input_size']
                    and len(chunk['data']) == chunk['metadata']['output_size']
                    and chunk['method'] == chunk['metadata']['method'], 'Invalid producer chunk')
        require(b''.join(chunks[i]['data'] for i in range(len(chunks))) == result['encrypted_data'],
                'Producer chunk assembly mismatch')
        layers = [chunks[i]['metadata'] for i in range(len(chunks))]
    else:
        require(metadata['type'] in ('layered', 'threaded_layered'), 'Unsupported producer topology')
        exact(metadata, {'type', 'layers', 'original_size', 'encrypted_size'})
        require(metadata['encrypted_size'] == len(result['encrypted_data']), 'Producer output size mismatch')
        layers = metadata['layers']
    require(metadata['original_size'] == len(plaintext), 'Producer input size mismatch')
    pairs = [split_node(layer, i) for i, layer in enumerate(layers)]
    field = 'chunk_layers' if topology == 'parallel_chunks' else 'layers'
    public = dict(version=1, package_id=package_id, profile=profile, topology=topology,
                  original_size=len(plaintext), encrypted_size=len(result['encrypted_data']),
                  original_name=original_name, kind=kind)
    public[field] = [p for p, s in pairs]
    secret = dict(version=1, package_id=package_id, plaintext_sha256=hashlib.sha256(plaintext).hexdigest())
    secret[field] = [s for p, s in pairs]
    validate_headers(public, secret, len(result['encrypted_data']))
    json_bytes(public); json_bytes(secret)
    return public, secret


def validate_headers(public, secret, body_size):
    try:
        return _validate_headers(public, secret, body_size)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as exc:
        raise InvalidMetadataError('Malformed metadata structure') from exc


def _validate_headers(public, secret, body_size):
    require(type(public) is dict and public.get('topology') in ('sequential', 'parallel_chunks'), 'Invalid topology')
    field = 'layers' if public['topology'] == 'sequential' else 'chunk_layers'
    exact(public, {'version', 'package_id', 'profile', 'topology', 'original_size', 'encrypted_size', 'original_name', 'kind', field})
    exact(secret, {'version', 'package_id', 'plaintext_sha256', field})
    require(type(public['version']) is int and type(secret['version']) is int and public['version'] == secret['version'] == 1, 'Invalid metadata version')
    require(type(public['package_id']) is str and re.fullmatch('[0-9a-f]{32}', public['package_id']), 'Invalid package ID')
    if public['package_id'] != secret['package_id']:
        raise KeyMismatchError('Recovery file belongs to a different package')
    require(type(secret['plaintext_sha256']) is str and re.fullmatch('[0-9a-f]{64}', secret['plaintext_sha256']), 'Invalid plaintext digest')
    require(type(public['profile']) is str and len(public['profile']) <= 128 and public['kind'] in ('file', 'folder'), 'Invalid package properties')
    safe_name(public['original_name'])
    integer(public['original_size']); integer(public['encrypted_size'])
    require(public['encrypted_size'] == body_size, 'Ciphertext size mismatch')
    nodes, secrets = public[field], secret[field]
    require(type(nodes) is list and type(secrets) is list and 1 <= len(nodes) == len(secrets) <= (32 if field == 'layers' else 1024), 'Invalid layer count')
    for i, (node, recovery) in enumerate(zip(nodes, secrets)):
        validate_node(node, recovery, i)
    if field == 'layers':
        size = public['original_size']
        for node in nodes:
            require(node['input_size'] == size, 'Sequential layer length mismatch')
            size = node['output_size']
        require(size == body_size, 'Final layer size mismatch')
    else:
        require(sum(n['input_size'] for n in nodes) == public['original_size'] and sum(n['output_size'] for n in nodes) == body_size, 'Parallel chunk lengths mismatch')
    return field
