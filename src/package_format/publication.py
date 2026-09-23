"""Private staging and one no-replace publication; no implicit recovery."""
import ctypes
import errno
import os
from pathlib import Path
import sys
import tempfile
from dataclasses import dataclass


class PublicationUnsupportedError(OSError):
    pass


@dataclass(frozen=True)
class PublicationResult:
    path: Path
    durability: str
    warning: str = ''


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def absolute_destination(path):
    # Canonicalize the parent, not the final component: an existing (even
    # dangling) destination symlink must still be treated as a conflict.
    path = Path(path)
    return path.parent.resolve() / path.name


def rename_noreplace(source, destination):
    if os.name == 'nt':
        os.rename(source, destination)
        return
    if not sys.platform.startswith('linux'):
        raise PublicationUnsupportedError('No-replace publication is supported on Linux/Windows only')
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise PublicationUnsupportedError('libc has no renameat2; publication aborted') from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        if code in (errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP):
            raise PublicationUnsupportedError(code, 'No-replace publication unsupported or invalid: ' + os.strerror(code))
        raise OSError(code, os.strerror(code), str(destination))


def make_stage(destination):
    if os.name == 'nt' and sys.version_info < (3, 12, 4):
        raise PublicationUnsupportedError('Windows private staging requires Python 3.12.4 or newer')
    destination = absolute_destination(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.jiami-stage-', dir=destination.parent))
    if stage.stat().st_dev != destination.parent.stat().st_dev:
        raise OSError(errno.EXDEV, 'Staging and destination must share a filesystem', str(stage))
    return stage


def publish_directory(stage, destination, validate):
    stage, destination = Path(stage).resolve(), absolute_destination(destination)
    if stage.parent != destination.parent or stage.stat().st_dev != destination.parent.stat().st_dev:
        raise OSError(errno.EXDEV, 'Staging must be a sibling on the destination filesystem')
    validate(stage)
    if os.name != 'nt':
        # Children names need synchronization as well as their file contents.
        for root, dirs, files in os.walk(stage, topdown=False):
            sync_directory(root)
        sync_directory(stage.parent)
    rename_noreplace(stage, destination)
    if os.name == 'nt':
        return PublicationResult(destination, 'unconfirmed', 'Windows directory durability is not guaranteed')
    try:
        sync_directory(destination.parent)
    except OSError as exc:
        return PublicationResult(destination, 'unconfirmed', 'Published; durability unconfirmed: ' + str(exc))
    return PublicationResult(destination, 'synced')


def publish_file(data, destination):
    """Used for recovered plaintext: content complete before its name appears."""
    destination = absolute_destination(destination)
    stage = make_stage(destination)
    source = stage / 'payload'
    write_private(source, data)
    if os.name != 'nt':
        sync_directory(stage)
    rename_noreplace(source, destination)
    if os.name != 'nt':
        try:
            sync_directory(destination.parent)
        except OSError as exc:
            return PublicationResult(destination, 'unconfirmed', 'Published; durability unconfirmed: ' + str(exc))
    warning = 'Windows directory durability is not guaranteed' if os.name == 'nt' else ''
    try:
        stage.rmdir()
    except OSError as exc:
        warning += ' Published; empty staging cleanup failed: ' + str(exc)
    return PublicationResult(destination, 'unconfirmed' if os.name == 'nt' else 'synced', warning)
