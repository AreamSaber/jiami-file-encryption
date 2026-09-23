"""Dependency notices must distinguish missing profile support from optional UI."""
import builtins

import pytest

import main as launcher
from cli.enhanced_cli import EnhancedCLI
from tools import diagnose


def block_import(monkeypatch, unavailable):
    actual_import = builtins.__import__

    def checked_import(name, *args, **kwargs):
        if name == unavailable or name.startswith(unavailable + '.'):
            raise ImportError('deliberately unavailable: ' + name)
        return actual_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', checked_import)


@pytest.mark.parametrize('entry', ['launcher', 'diagnose', 'enhanced'])
@pytest.mark.parametrize('missing', [False, True])
def test_pynacl_detection_and_profile_availability(entry, missing, monkeypatch, capsys):
    # Installed packages are real; only simulate absence for the failure case.
    import nacl.secret
    import PIL

    if missing:
        block_import(monkeypatch, 'nacl')
    if entry == 'launcher':
        assert launcher.check_dependencies() is True  # Other profiles may run.
    elif entry == 'diagnose':
        assert diagnose.check_dependencies() is (not missing)
    else:
        EnhancedCLI._check_dependencies(EnhancedCLI.__new__(EnhancedCLI))

    output = capsys.readouterr().out
    assert 'pycryptodome' not in output.lower()
    if missing:
        assert 'PyNaCl' in output
        assert 'salsa20_stream' in output
        assert '不可用' in output
        assert '核心功能可用' not in output
    elif entry == 'launcher':
        assert 'PyNaCl' not in output  # No missing-dependency warning.
    else:
        assert '✅ PyNaCl' in output
        assert '✅ Pillow' in output


@pytest.mark.parametrize('check', [launcher.check_dependencies, diagnose.check_dependencies])
def test_missing_core_dependency_still_fails(check, monkeypatch, capsys):
    block_import(monkeypatch, 'cryptography')
    assert check() is False
    assert 'cryptography' in capsys.readouterr().out
