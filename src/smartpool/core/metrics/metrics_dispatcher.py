"""
Asynchronous metrics event dispatcher.

This module provides a bounded-queue dispatcher with a dedicated worker thread
to process metrics events outside hot paths.
"""

import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from smartpool.config import MetricsOverloadPolicy


@dataclass(frozen=True)
class MetricsEvent:
    """Represents a metrics event consumed by the background worker."""

    event_type: str
    payload: Dict[str, Any]
    ack: Optional[threading.Event] = None


class MetricsDispatcher:
    """
    Dispatches metrics events to a worker thread using a bounded queue.

    The dispatcher supports overload policies to control behavior when the queue
    is full and provides best-effort flush/shutdown operations.
    """

    _FLUSH_EVENT = "__flush__"
    _STOP_EVENT = "__stop__"

    def __init__(
        self,
        *,
        maxsize: int,
        overload_policy: MetricsOverloadPolicy,
        handlers: Dict[str, Callable[[Dict[str, Any]], None]],
        on_drop: Optional[Callable[[str], None]] = None,
        on_worker_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self._maxsize = maxsize
        self._queue: queue.Queue[MetricsEvent] = queue.Queue(maxsize=maxsize)
        self._overload_policy = overload_policy
        self._handlers = handlers
        self._on_drop = on_drop
        self._on_worker_error = on_worker_error
        self._worker_stop = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._dropped_events = 0
        self._processed_events = 0
        self._lock = threading.RLock()

    def start(self) -> None:
        """Starts the worker thread if not already running."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._worker_stop.clear()
            self._worker_thread = threading.Thread(
                target=self._run_worker,
                name="smartpool-metrics-dispatcher",
                daemon=True,
            )
            self._worker_thread.start()

    def publish(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Publishes an event according to the configured overload policy.

        Returns:
            bool: True if the event was queued, False if dropped.
        """
        event = MetricsEvent(event_type=event_type, payload=payload or {})

        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            return self._handle_full_queue(event)

    def flush(self, timeout_seconds: float) -> bool:
        """
        Flushes queued events best-effort within the provided timeout.

        Returns:
            bool: True if flush completed before timeout, False otherwise.
        """
        if not self.is_alive():
            return True

        ack = threading.Event()
        flush_event = MetricsEvent(event_type=self._FLUSH_EVENT, payload={}, ack=ack)
        if not self._enqueue_control_event(flush_event, timeout_seconds):
            return False
        return ack.wait(timeout=max(0.0, timeout_seconds))

    def shutdown(self, timeout_seconds: float) -> None:
        """Performs best-effort flush and requests worker termination."""
        self.flush(timeout_seconds)
        self._worker_stop.set()
        stop_event = MetricsEvent(event_type=self._STOP_EVENT, payload={})
        self._enqueue_control_event(stop_event, timeout_seconds)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=max(0.0, timeout_seconds))

    def get_health_metrics(self) -> Dict[str, float]:
        """Returns lightweight dispatcher health metrics."""
        return {
            "queue_depth": float(self._queue.qsize()),
            "worker_alive": 1.0 if self.is_alive() else 0.0,
            "dropped_events": float(self._dropped_events),
            "processed_events": float(self._processed_events),
        }

    def get_queue_depth_ratio(self) -> float:
        """Returns queue fill ratio in [0, 1]."""
        if self._maxsize <= 0:
            return 0.0
        return min(1.0, self._queue.qsize() / float(self._maxsize))

    def is_alive(self) -> bool:
        """Returns whether the worker thread is currently alive."""
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def _handle_full_queue(self, event: MetricsEvent) -> bool:
        if self._overload_policy == MetricsOverloadPolicy.DROP_NEWEST:
            self._record_drop(event.event_type)
            return False

        if self._overload_policy == MetricsOverloadPolicy.DROP_OLDEST:
            try:
                _ = self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                self._record_drop(event.event_type)
                return False
            try:
                self._queue.put_nowait(event)
                self._record_drop("dropped_oldest_for_new_event")
                return True
            except queue.Full:
                self._record_drop(event.event_type)
                return False

        # BACKPRESSURE policy: brief blocking put, then drop if still full.
        try:
            self._queue.put(event, timeout=0.01)
            return True
        except queue.Full:
            self._record_drop(event.event_type)
            return False

    def _record_drop(self, reason: str) -> None:
        self._dropped_events += 1
        if self._on_drop is not None:
            self._on_drop(reason)

    def _enqueue_control_event(self, event: MetricsEvent, timeout_seconds: float) -> bool:
        end_time = time.monotonic() + max(0.0, timeout_seconds)
        while time.monotonic() < end_time:
            try:
                self._queue.put(event, timeout=0.01)
                return True
            except queue.Full:
                continue
        return False

    def _run_worker(self) -> None:
        while not self._worker_stop.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                if event.event_type == self._STOP_EVENT:
                    return
                if event.event_type == self._FLUSH_EVENT:
                    if event.ack is not None:
                        event.ack.set()
                    continue

                handler = self._handlers.get(event.event_type)
                if handler is not None:
                    try:
                        handler(event.payload)
                    except Exception as exc:  # pylint: disable=broad-exception-caught
                        if self._on_worker_error is not None:
                            self._on_worker_error(exc)
                self._processed_events += 1
            finally:
                self._queue.task_done()
