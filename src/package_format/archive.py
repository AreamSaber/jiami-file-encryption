"""Data-only folder archives with closed, portable path validation."""
import fnmatch
import io
from pathlib import Path, PurePosixPath
import stat
import zipfile
from dataclasses import dataclass

from .schema import safe_name, require
from .cancellation import checkpoint, iter_checked
from .envelope import MAX_BODY
from .publication import write_private


@dataclass(frozen=True)
class FolderEntry:
    path: Path
    name: str
    size: int
    directory: bool


@dataclass(frozen=True)
class FolderPlan:
    entries: tuple
    archive_size: int


def plan_folder(folder, exclude_patterns=(), *, cancellation=None):
    """Stat-only ZIP_STORED plan; no member contents are read."""
    root = Path(folder).resolve()
    entries, size = [], 22  # EOCD, no comment
    for path in iter_checked(root.rglob('*'), cancellation):
        relative = path.relative_to(root).as_posix()
        if any(fnmatch.fnmatch(relative, pat) for pat in exclude_patterns):
            continue
        require(len(entries) < 100000, 'Too many archived files')
        require(not path.is_symlink(), 'Folder symlinks are unsupported')
        for part in PurePosixPath(relative).parts:
            safe_name(part)
        info = path.stat()
        directory = stat.S_ISDIR(info.st_mode)
        require(directory or stat.S_ISREG(info.st_mode), 'Unsupported special file in folder')
        name = relative + ('/' if directory else '')
        member_size = 0 if directory else info.st_size
        # ZipInfo uses ASCII where possible, UTF-8 otherwise. ASCII bytes are
        # identical in UTF-8. These entries have no extras/comments/descriptors.
        size += 30 + 46 + 2 * len(name.encode('utf-8')) + member_size
        require(size <= MAX_BODY, 'Folder archive exceeds supported size')
        entries.append(FolderEntry(path, name, member_size, directory))
    if len(entries) > zipfile.ZIP_FILECOUNT_LIMIT:
        size += zipfile.sizeEndCentDir64 + zipfile.sizeEndCentDir64Locator
    require(size <= MAX_BODY, 'Folder archive exceeds supported size')
    return FolderPlan(tuple(sorted(entries, key=lambda entry: entry.path)), size)


class _BoundedArchiveBuffer(io.BytesIO):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def write(self, data):
        require(self.tell() + len(data) <= self.limit, 'Folder changed or archive exceeded admission bound')
        return super().write(data)


def pack_folder(folder, exclude_patterns=(), *, plan=None, cancellation=None):
    checkpoint(cancellation)
    plan = plan if plan is not None else plan_folder(folder, exclude_patterns, cancellation=cancellation)
    buffer = _BoundedArchiveBuffer(plan.archive_size)
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as archive:
        for entry in plan.entries:
            checkpoint(cancellation)
            require(not entry.path.is_symlink(), 'Folder symlinks are unsupported')
            if entry.directory:
                require(entry.path.is_dir(), 'Folder changed after admission')
                archive.writestr(entry.name, b'')
            else:
                info = zipfile.ZipInfo.from_file(entry.path, entry.name)
                require(entry.path.is_file() and info.file_size == entry.size, 'Folder changed after admission')
                with entry.path.open('rb') as source, archive.open(info, 'w') as target:
                    count = 0
                    while True:
                        checkpoint(cancellation)
                        chunk = source.read(min(65536, entry.size - count + 1))
                        if not chunk:
                            break
                        count += len(chunk)
                        require(count <= entry.size, 'Folder member grew after admission')
                        target.write(chunk)
                    require(count == entry.size, 'Folder member shrank after admission')
    # Catch added/deleted/resized entries as well as per-member growth while read.
    require(plan_folder(folder, exclude_patterns, cancellation=cancellation) == plan, 'Folder changed after admission')
    require(len(buffer.getvalue()) == plan.archive_size, 'Archive size prediction mismatch')
    return buffer.getvalue()


def unpack_folder(data, stage, *, cancellation=None):
    checkpoint(cancellation)
    with zipfile.ZipFile(io.BytesIO(data), 'r') as archive:
        infos = archive.infolist()
        require(len(infos) <= 100000, 'Too many archived files')
        total, seen = 0, set()
        spellings, types = {}, {}
        validated = []
        for info in infos:
            checkpoint(cancellation)
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
            checkpoint(cancellation)
            if info.is_dir():
                path.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                write_private(path, archive.read(info), cancellation=cancellation)
