"""Tests for the MetricsDispatcher."""

import queue
import threading
import time

import pytest

from smartpool.config import MetricsOverloadPolicy
from smartpool.core.metrics.metrics_dispatcher import MetricsDispatcher, MetricsEvent


class TestMetricsDispatcher:
    """Unit tests for async metrics dispatch behavior."""

    def test_publish_and_flush_processes_events(self):
        processed = []

        dispatcher = MetricsDispatcher(
            maxsize=16,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={"evt": lambda payload: processed.append(payload["value"])},
        )
        dispatcher.start()

        dispatcher.publish("evt", {"value": 1})
        assert dispatcher.flush(1.0)
        dispatcher.shutdown(1.0)

        assert processed == [1]

    def test_drop_newest_policy_records_drops(self):
        drop_count = 0
        block_event = threading.Event()

        def handler(_: dict) -> None:
            block_event.wait(timeout=0.4)

        def on_drop(_: str) -> None:
            nonlocal drop_count
            drop_count += 1

        dispatcher = MetricsDispatcher(
            maxsize=2,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={"evt": handler},
            on_drop=on_drop,
        )
        assert dispatcher.publish("evt", {})
        assert dispatcher.publish("evt", {})
        # Queue saturation reached; this event should be dropped with DROP_NEWEST.
        assert not dispatcher.publish("evt", {})

        dispatcher.start()
        block_event.set()
        dispatcher.shutdown(1.0)

        assert drop_count >= 1

    def test_drop_oldest_policy_keeps_new_event(self):
        processed = []
        gate = threading.Event()

        def slow_handler(payload: dict) -> None:
            if payload["id"] == 1:
                gate.wait(timeout=0.5)
            processed.append(payload["id"])

        dispatcher = MetricsDispatcher(
            maxsize=1,
            overload_policy=MetricsOverloadPolicy.DROP_OLDEST,
            handlers={"evt": slow_handler},
        )
        dispatcher.start()

        assert dispatcher.publish("evt", {"id": 1})
        # Wait until first event is likely consumed by worker and blocked in handler.
        time.sleep(0.02)
        assert dispatcher.publish("evt", {"id": 2})
        # Queue is full with id=2; id=3 should replace oldest queued event (id=2).
        assert dispatcher.publish("evt", {"id": 3})

        gate.set()
        assert dispatcher.flush(1.0)
        dispatcher.shutdown(1.0)

        assert 1 in processed
        assert 3 in processed

    def test_worker_error_callback_is_called_and_worker_survives(self):
        errors = []
        processed = []

        def failing_handler(_: dict) -> None:
            raise RuntimeError("boom")

        dispatcher = MetricsDispatcher(
            maxsize=8,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={
                "bad": failing_handler,
                "ok": lambda payload: processed.append(payload["value"]),
            },
            on_worker_error=lambda exc: errors.append(str(exc)),
        )
        dispatcher.start()

        assert dispatcher.publish("bad", {})
        assert dispatcher.publish("ok", {"value": 7})
        assert dispatcher.flush(1.0)
        dispatcher.shutdown(1.0)

        assert errors
        assert "boom" in errors[0]
        assert processed == [7]

    def test_start_is_idempotent_and_flush_shutdown_without_worker(self):
        dispatcher_no_worker = MetricsDispatcher(
            maxsize=4,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )
        # No worker started: flush should be a no-op success and shutdown should not fail.
        assert dispatcher_no_worker.flush(0.01)
        dispatcher_no_worker.shutdown(0.01)

        dispatcher = MetricsDispatcher(
            maxsize=4,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )
        dispatcher.start()
        first_thread = dispatcher._worker_thread
        dispatcher.start()
        assert dispatcher._worker_thread is first_thread
        dispatcher.shutdown(1.0)

    def test_queue_depth_ratio_with_unbounded_queue(self):
        dispatcher = MetricsDispatcher(
            maxsize=0,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )
        assert dispatcher.get_queue_depth_ratio() == 0.0

        bounded = MetricsDispatcher(
            maxsize=4,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )
        bounded.publish("evt", {})
        assert bounded.get_queue_depth_ratio() == 0.25

    def test_publish_defaults_to_empty_payload_and_health_metrics(self):
        payloads = []

        def record_payload(payload: dict) -> None:
            payloads.append(payload)

        dispatcher = MetricsDispatcher(
            maxsize=8,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={"evt": record_payload},
        )
        dispatcher.start()
        assert dispatcher.publish("evt")
        assert dispatcher.flush(1.0)
        health = dispatcher.get_health_metrics()
        dispatcher.shutdown(1.0)

        assert payloads == [{}]
        assert health["processed_events"] >= 1.0
        assert health["worker_alive"] in (0.0, 1.0)

    def test_flush_returns_false_when_control_event_cannot_be_enqueued(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        dispatcher = MetricsDispatcher(
            maxsize=1,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )
        dispatcher.start()
        monkeypatch.setattr(dispatcher, "_enqueue_control_event", lambda *_args, **_kwargs: False)
        assert not dispatcher.flush(0.01)
        dispatcher.shutdown(1.0)

    def test_drop_oldest_handles_empty_and_requeue_full_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        drops = []

        def on_drop(reason: str) -> None:
            drops.append(reason)

        dispatcher = MetricsDispatcher(
            maxsize=1,
            overload_policy=MetricsOverloadPolicy.DROP_OLDEST,
            handlers={},
            on_drop=on_drop,
        )

        # Force "queue empty" branch after entering DROP_OLDEST path.
        event = MetricsEvent(event_type="evt", payload={})
        assert not dispatcher._handle_full_queue(event)
        assert drops[-1] == "evt"

        # Force "requeue full" branch by raising queue.Full on put_nowait.
        dispatcher._queue.put_nowait(MetricsEvent(event_type="occupied", payload={}))
        monkeypatch.setattr(
            dispatcher._queue,
            "put_nowait",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(queue.Full()),
        )
        assert not dispatcher._handle_full_queue(event)
        assert drops[-1] == "evt"

    def test_backpressure_policy_drop_and_success_paths(self, monkeypatch: pytest.MonkeyPatch):
        drops = []

        def on_drop(reason: str) -> None:
            drops.append(reason)

        dispatcher = MetricsDispatcher(
            maxsize=1,
            overload_policy=MetricsOverloadPolicy.BACKPRESSURE,
            handlers={},
            on_drop=on_drop,
        )

        event = MetricsEvent(event_type="evt", payload={})
        dispatcher._queue.put_nowait(MetricsEvent(event_type="occupied", payload={}))

        # First force timeout/drop in backpressure branch.
        monkeypatch.setattr(
            dispatcher._queue, "put", lambda *_args, **_kwargs: (_ for _ in ()).throw(queue.Full())
        )
        assert not dispatcher._handle_full_queue(event)
        assert drops[-1] == "evt"

        # Then force success path.
        monkeypatch.setattr(dispatcher._queue, "put", lambda *_args, **_kwargs: None)
        assert dispatcher._handle_full_queue(event)

    def test_enqueue_control_event_timeout_path(self):
        dispatcher = MetricsDispatcher(
            maxsize=1,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )
        dispatcher._queue.put_nowait(MetricsEvent(event_type="occupied", payload={}))
        assert not dispatcher._enqueue_control_event(
            MetricsEvent(event_type="ctrl", payload={}), 0.0
        )

    def test_enqueue_control_event_retries_on_full_then_times_out(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        dispatcher = MetricsDispatcher(
            maxsize=1,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={},
        )

        monkeypatch.setattr(
            dispatcher._queue,
            "put",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(queue.Full()),
        )
        assert not dispatcher._enqueue_control_event(
            MetricsEvent(event_type="ctrl", payload={}), 0.02
        )

    def test_run_worker_edge_paths_without_thread(self, monkeypatch: pytest.MonkeyPatch):
        errors = []
        handled = []

        dispatcher = MetricsDispatcher(
            maxsize=8,
            overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            handlers={
                "fail": lambda _payload: (_ for _ in ()).throw(RuntimeError("boom-no-callback")),
                "ok": lambda payload: handled.append(payload.get("v", -1)),
            },
            on_worker_error=None,
        )

        # Cover while-not-entered path.
        dispatcher._worker_stop.set()
        dispatcher._run_worker()
        dispatcher._worker_stop.clear()

        # Preload events to hit worker branches:
        # flush(no ack), unknown handler, failing handler(no callback), stop.
        dispatcher._queue.put_nowait(
            MetricsEvent(event_type=dispatcher._FLUSH_EVENT, payload={}, ack=None)
        )
        dispatcher._queue.put_nowait(MetricsEvent(event_type="unknown", payload={}))
        dispatcher._queue.put_nowait(MetricsEvent(event_type="fail", payload={}))
        dispatcher._queue.put_nowait(MetricsEvent(event_type="ok", payload={"v": 1}))
        dispatcher._queue.put_nowait(MetricsEvent(event_type=dispatcher._STOP_EVENT, payload={}))

        # Also cover queue.Empty continue path once before consuming real queue.
        original_get = dispatcher._queue.get
        state = {"first": True}

        def flaky_get(*args, **kwargs):
            if state["first"]:
                state["first"] = False
                raise queue.Empty()
            return original_get(*args, **kwargs)

        monkeypatch.setattr(dispatcher._queue, "get", flaky_get)
        dispatcher._run_worker()

        assert handled == [1]
        assert not errors
