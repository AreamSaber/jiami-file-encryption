"""Exercise the primary Qt widgets, real workers, ciphers and publication."""
import os
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PyQt6', reason='Optional Qt desktop dependency absent in CPU-only environment')
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from gui.main_window import MainWindow
from src.decryptor.cpu_decryptor import CPUDecryptor
from src.encryptor.main import FileEncryptor
from src.thread_pool.thread_manager import thread_manager


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def wait_for(app, predicate):
    deadline = time.monotonic() + 15
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert predicate(), 'Qt worker did not finish within 15 seconds'


@pytest.fixture
def window(app, monkeypatch):
    messages = []
    for name in ('warning', 'critical', 'information'):
        monkeypatch.setattr(QMessageBox, name, lambda _w, title, body, *a, kind=name:
                            messages.append((kind, title, body)))
    # A desktop window must not leak its global GUI override into other tests.
    saved = thread_manager.snapshot()
    win = MainWindow()
    win.auto_open_checkbox.setChecked(False)
    win.tab_widget.setCurrentIndex(1)
    win.show()
    app.processEvents()
    yield win, messages
    wait_for(app, lambda: not win._operation_running())
    win.close()
    win.deleteLater()
    app.processEvents()
    thread_manager.thread_configs = saved.thread_configs
    thread_manager.active_config = saved.active_config


def package(tmp_path, folder=False, name='original'):
    source = tmp_path / name
    content = bytes(range(256)) * 17
    if folder:
        source.mkdir()
        (source / 'empty').mkdir()
        (source / 'nested').mkdir()
        (source / 'nested' / 'sample.bin').write_bytes(content)
    else:
        source.write_bytes(content)
    engine = FileEncryptor(thread_settings=thread_manager.snapshot())
    try:
        encrypt = engine.encrypt_folder if folder else engine.encrypt_file
        result = encrypt(source, tmp_path / 'encrypted', 'basic')
        assert result['success'], result
        return Path(result['encrypted_file']), content
    finally:
        engine.hybrid_engine.shutdown()


@pytest.mark.parametrize('folder', [False, True])
def test_widget_roundtrip(app, window, tmp_path, monkeypatch, folder):
    win, messages = window
    data, content = package(tmp_path, folder)
    if folder:
        monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a: str(data.parent))
        QTest.mouseClick(win.select_package_btn, Qt.MouseButton.LeftButton)
    else:
        monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: (str(data), ''))
        QTest.mouseClick(win.select_cipher_btn, Qt.MouseButton.LeftButton)
    assert Path(win.decryption_recovery.text()) == data.with_name('recovery.jmis')
    win.decryption_recovery.clear()  # Exercise adjacent recovery discovery.
    target = tmp_path / 'restored'
    win.decryption_output.setText(str(target))
    QTest.mouseClick(win.decrypt_btn, Qt.MouseButton.LeftButton)
    wait_for(app, lambda: win.decryption_worker is None)
    recovered = target / 'nested' / 'sample.bin' if folder else target
    assert recovered.read_bytes() == content
    if folder:
        assert (target / 'empty').is_dir()
    assert win.decryption_progress.value() == 100
    assert str(target) in win.decryption_status.text()
    assert win.encrypt_btn.isEnabled() and win.decrypt_btn.isEnabled()
    assert not messages


@pytest.mark.parametrize('failure', ['wrong_recovery', 'corrupt_ciphertext'])
def test_authentication_failure_then_retry(app, window, tmp_path, failure):
    win, messages = window
    data, content = package(tmp_path)
    other, _ = package(tmp_path, name='other')
    original = data.read_bytes()
    win._select_ciphertext(str(data))
    target = tmp_path / 'recovered'
    win.decryption_output.setText(str(target))
    if failure == 'wrong_recovery':
        win.decryption_recovery.setText(str(other.with_name('recovery.jmis')))
    else:
        data.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    QTest.mouseClick(win.decrypt_btn, Qt.MouseButton.LeftButton)
    wait_for(app, lambda: win.decryption_worker is None)
    assert messages[-1][0] == 'critical'
    assert not target.exists() and win.decryption_progress.value() == 0
    assert win.decrypt_btn.isEnabled() and win.decryption_data.isEnabled()
    data.write_bytes(original)
    win.decryption_recovery.clear()
    QTest.mouseClick(win.decrypt_btn, Qt.MouseButton.LeftButton)
    wait_for(app, lambda: win.decryption_worker is None)
    assert target.read_bytes() == content


def test_existing_output_is_preserved(window, tmp_path):
    win, messages = window
    data, _ = package(tmp_path)
    target = tmp_path / 'keep'
    target.write_bytes(b'keep existing data')
    win._select_ciphertext(str(data))
    win.decryption_output.setText(str(target))
    QTest.mouseClick(win.decrypt_btn, Qt.MouseButton.LeftButton)
    assert win.decryption_worker is None and messages[-1][0] == 'warning'
    assert target.read_bytes() == b'keep existing data'


def test_close_waits_for_real_worker(app, window, tmp_path, monkeypatch):
    win, messages = window
    data, content = package(tmp_path)
    entered, release = threading.Event(), threading.Event()
    actual = CPUDecryptor.decrypt_file

    def held(reader, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        return actual(reader, *args, **kwargs)

    monkeypatch.setattr(CPUDecryptor, 'decrypt_file', held)
    win._select_ciphertext(str(data))
    target = tmp_path / 'restored'
    win.decryption_output.setText(str(target))
    QTest.mouseClick(win.decrypt_btn, Qt.MouseButton.LeftButton)
    try:
        wait_for(app, entered.is_set)
        worker = win.decryption_worker
        win.start_decryption()  # No second worker, even through direct invocation.
        assert win.decryption_worker is worker
        assert not win.close() and win.isVisible()
        assert messages[-1][0] == 'warning'
        assert not win.encrypt_btn.isEnabled()
        assert win.decryption_progress.maximum() == 0
    finally:
        release.set()
        wait_for(app, lambda: win.decryption_worker is None)
    assert target.read_bytes() == content


def test_encryption_worker_and_decryption_lifecycle(app, window, tmp_path):
    win, messages = window
    source = tmp_path / 'input.txt'
    source.write_bytes(b'Qt encryption and decryption integration')
    output = tmp_path / 'packages'
    win.tab_widget.setCurrentIndex(0)
    win.input_path_label.setText(str(source))
    win.output_path_label.setText(str(output))
    win.profile_combo.setCurrentIndex(win.profile_combo.findData('basic'))
    QTest.mouseClick(win.encrypt_btn, Qt.MouseButton.LeftButton)
    wait_for(app, lambda: win.worker is None)
    assert messages[-1][0] == 'information'
    assert win.encrypt_btn.isEnabled() and win.decrypt_btn.isEnabled()
    win.tab_widget.setCurrentIndex(1)
    win._select_ciphertext(str(output / 'input.txt.jiami'))
    target = tmp_path / 'restored.txt'
    win.decryption_output.setText(str(target))
    QTest.mouseClick(win.decrypt_btn, Qt.MouseButton.LeftButton)
    wait_for(app, lambda: win.decryption_worker is None)
    assert target.read_bytes() == source.read_bytes()
