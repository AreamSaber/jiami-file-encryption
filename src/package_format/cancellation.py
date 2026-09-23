"""Operation-owned cooperative cancellation and atomic publication ordering."""
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from contextvars import ContextVar
import signal
import threading


class OperationCancelled(Exception):
    error_code = 'CANCELLED'

    def __init__(self, message='Operation cancelled before publication'):
        super().__init__(message)


class PublicationGate:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = 'pending'
        self._late_request = False

    def request_cancel(self) -> bool:
        with self._lock:
            if self._state == 'publishing':
                self._late_request = True
                return False
            self._state = 'cancelled'
            return True

    def enter_publishing(self) -> bool:
        with self._lock:
            if self._state != 'pending':
                return False
            self._state = 'publishing'
            return True

    def checkpoint(self):
        with self._lock:
            if self._state == 'cancelled':
                raise OperationCancelled()

    def late_request(self):
        with self._lock:
            return self._late_request


class CancellationToken:
    """One token per attempted output; never reuse it for another publication."""
    def __init__(self):
        self.gate = PublicationGate()

    def request_cancel(self):
        return self.gate.request_cancel()

    def checkpoint(self):
        self.gate.checkpoint()

    def enter_publishing(self):
        if not self.gate.enter_publishing():
            self.checkpoint()
            raise RuntimeError('Publication already entered; cancellation tokens are single-use')

    def completion_warning(self):
        return ('Cancellation requested too late: the operation had already committed.'
                if self.gate.late_request() else '')


class CancellationGroup:
    """Stop queued admissions and request cancellation of active batch attempts."""
    def __init__(self):
        self._lock = threading.Lock()
        self._requested = False
        self._active = set()

    def request_cancel(self):
        with self._lock:
            self._requested = True
            for token in self._active:
                token.request_cancel()
        return True

    def completion_warning(self):
        with self._lock:
            return ('Cancellation requested too late: all batch operations had completed.'
                    if self._requested else '')

    @contextmanager
    def operation(self):
        token = CancellationToken()
        with self._lock:
            self._active.add(token)
            if self._requested:
                token.request_cancel()
        try:
            token.checkpoint()
            yield token
        finally:
            with self._lock:
                self._active.remove(token)


_current = ContextVar('jiami_cancellation', default=None)


@contextmanager
def cancellation_scope(token):
    marker = _current.set(token)
    try:
        checkpoint(token)
        yield
        checkpoint(token)
    finally:
        _current.reset(marker)


def checkpoint(token=None):
    token = token if token is not None else _current.get()
    if token is not None:
        token.checkpoint()


def iter_checked(iterable, token=None):
    token = token if token is not None else _current.get()
    if token is None:
        yield from iterable
        return
    for index, item in enumerate(iterable):
        if index % 4096 == 0:
            token.checkpoint()
        yield item
    token.checkpoint()


def retain_stage(exc, stage, contents):
    # Also retain the note on Python 3.10, where BaseException.add_note is absent.
    note = f'Private staging retained at {stage}; may contain {contents}.'
    notes = list(getattr(exc, '__notes__', []))
    if note not in notes:
        notes.append(note)
    exc.__notes__ = notes


def error_text(exc):
    return '\n'.join([str(exc), *getattr(exc, '__notes__', [])])


def exit_code(result):
    """Errors outrank cancellation; a completed late request still exits zero."""
    if result.get('failed', 0) or (not result.get('success') and not result.get('cancelled', 0)):
        return 1
    return 130 if result.get('cancelled', 0) else 0


def run_with_sigint(operation, controller):
    """Keep SIGINT on the main thread, away from operation locks and rename.

    The signal handler only requests cooperative cancellation. Repeated Ctrl+C
    never forcibly interrupts native work or the final publication step.
    """
    if threading.current_thread() is not threading.main_thread():
        return operation()
    previous = signal.getsignal(signal.SIGINT)
    requested = False

    def request_once(*_):
        # A second SIGINT can interrupt this handler while it owns a lock.
        # Mark the request before acquiring any controller/gate locks.
        nonlocal requested
        if not requested:
            requested = True
            controller.request_cancel()

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='jiami-cli') as pool:
        signal.signal(signal.SIGINT, request_once)
        try:
            future = pool.submit(operation)
            # Windows locks before Python 3.14 do not interrupt an indefinite
            # Condition.wait for SIGINT. Return to Python periodically so the
            # main thread can execute its handler while the worker is active.
            while not future.done():
                wait((future,), timeout=0.1)
            result = future.result()
        finally:
            signal.signal(signal.SIGINT, previous)
    # Include a signal delivered after the worker formed its successful result
    # but before the main thread restored the handler.
    if isinstance(result, dict) and result.get('success'):
        warning = controller.completion_warning()
        if warning and warning not in result.get('warning', ''):
            result['warning'] = '\n'.join(filter(None, (result.get('warning'), warning)))
    return result
