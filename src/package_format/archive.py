"""Data-only folder archives with closed, portable path validation."""
import fnmatch
import io
from pathlib import Path, PurePosixPath
import stat
import zipfile

from .schema import safe_name, require
from .envelope import MAX_BODY
from .publication import write_private


def pack_folder(folder, exclude_patterns=()):
    root = Path(folder).resolve()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        total = 0
        for path in sorted(root.rglob('*')):
            relative = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(relative, pat) for pat in exclude_patterns):
                continue
            require(not path.is_symlink(), 'Folder symlinks are unsupported')
            for part in PurePosixPath(relative).parts:
                safe_name(part)
            if path.is_dir():
                archive.writestr(relative + '/', b'')
            elif path.is_file():
                total += path.stat().st_size
                require(total <= MAX_BODY, 'Folder exceeds supported size')
                archive.write(path, relative)
            else:
                raise ValueError('Unsupported special file in folder')
    require(len(buffer.getvalue()) <= MAX_BODY, 'Folder archive exceeds supported size')
    return buffer.getvalue()


def unpack_folder(data, stage):
    with zipfile.ZipFile(io.BytesIO(data), 'r') as archive:
        infos = archive.infolist()
        require(len(infos) <= 100000, 'Too many archived files')
        total, seen = 0, set()
        spellings, types = {}, {}
        validated = []
        for info in infos:
            require(info.orig_filename == info.filename, 'Archive filename was normalized or truncated')
            name = info.filename.rstrip('/')
            parts = name.split('/')
            require(name and all(parts) and '\\' not in name, 'Unsafe archive path')
            for part in parts:
                safe_name(part)
            normalized = '/'.join(parts).casefold()
            require(normalized not in seen, 'Duplicate or case-colliding archive path')
            seen.add(normalized)
            for i in range(1, len(parts) + 1):
                spelling = '/'.join(parts[:i])
                key = spelling.casefold()
                kind = 'directory' if i < len(parts) or info.is_dir() else 'file'
                require(key not in spellings or spellings[key] == spelling, 'Case-colliding ancestor')
                require(key not in types or types[key] == kind, 'File/directory path collision')
                spellings[key], types[key] = spelling, kind
            mode = (info.external_attr >> 16) & 0xffff
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR)
                    and info.compress_type == zipfile.ZIP_STORED and not (info.flag_bits & 1), 'Unsupported archive member')
            total += info.file_size
            require(total <= MAX_BODY, 'Archive exceeds supported size')
            validated.append((info, Path(stage).joinpath(*parts)))
        for info, path in validated:
            if info.is_dir():
                path.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                write_private(path, archive.read(info))
