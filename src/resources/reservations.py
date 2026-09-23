"""Shared soft reservations, acquired before reads and cipher pool submission."""
from contextlib import contextmanager
from dataclasses import dataclass
import threading
import time

import psutil

from .admission import MIB
from src.package_format.cancellation import checkpoint


class ResourceRefusal(ValueError):
    error_code = 'ADMISSION_RESOURCE'


@dataclass(frozen=True)
class ResourcePolicy:
    # Provisional, unvalidated defaults for the reference host; not an RSS cap.
    budget_bytes: int = 256 * MIB
    available_reserve_bytes: int = 256 * MIB
    wait_seconds: float = 30.0

    def __post_init__(self):
        if (type(self.budget_bytes) is not int or self.budget_bytes <= 0
                or type(self.available_reserve_bytes) is not int or self.available_reserve_bytes < 0
                or not 0 <= self.wait_seconds <= 300):
            raise ValueError('Invalid resource policy')


class ReservationLedger:
    def __init__(self, policy=None, *, available_memory=None):
        self.policy = policy or ResourcePolicy()
        self._available_memory = available_memory or (lambda: psutil.virtual_memory().available)
        self._condition = threading.Condition()
        self._reserved = 0
        self._peak = 0

    @property
    def reserved_bytes(self):
        with self._condition:
            return self._reserved

    @property
    def peak_reserved_bytes(self):
        with self._condition:
            return self._peak

    @contextmanager
    def reserve(self, estimate, *, extra_bytes=0, cancellation=None):
        checkpoint(cancellation)
        estimate.check_format()
        if type(extra_bytes) is not int or extra_bytes < 0:
            raise ValueError('Extra reservation must be a nonnegative integer')
        if not estimate.guaranteed:
            yield  # Explicitly no guarantee; caller must expose the reason.
            return
        amount = estimate.estimated_peak_bytes + extra_bytes
        if type(amount) is not int or amount <= 0:
            raise ValueError('Estimated reservation must be a positive integer')
        policy = self.policy
        if amount > policy.budget_bytes:
            raise ResourceRefusal(f'Estimated allocation {amount} exceeds reservation budget {policy.budget_bytes}; cannot fit even alone')
        deadline = time.monotonic() + policy.wait_seconds
        with self._condition:
            while True:
                checkpoint(cancellation)
                available = self._available_memory()
                budget_ok = self._reserved + amount <= policy.budget_bytes
                # Conservatively include outstanding reservations. Existing real
                # allocations may already appear in available; over-counting is
                # intentional because queued claims have not allocated yet.
                memory_ok = available - self._reserved - amount >= policy.available_reserve_bytes
                if budget_ok and memory_ok:
                    self._reserved += amount
                    self._peak = max(self._peak, self._reserved)
                    break
                if not self._reserved or time.monotonic() >= deadline:
                    raise ResourceRefusal(f'Soft admission refused: requested={amount}, reserved={self._reserved}, '
                                          f'budget={policy.budget_bytes}, available={available}, '
                                          f'available_reserve={policy.available_reserve_bytes}')
                self._condition.wait(timeout=min(0.1, max(0, deadline - time.monotonic())))
        try:
            checkpoint(cancellation)
            yield
        finally:
            with self._condition:
                self._reserved -= amount
                self._condition.notify_all()


# All default producer instances/batches share claims within this process.
# Callers may explicitly supply an isolated ledger with a different policy.
DEFAULT_LEDGER = ReservationLedger()
