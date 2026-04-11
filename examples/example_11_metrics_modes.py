"""
SmartPool metrics modes example.

This example runs the same deterministic workload across four modes:
- off
- sync
- async
- sampled

It prints elapsed runtime plus p95/p99 acquisition times (when available).
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

from examples.factories import BytesIOFactory
from smartpool import MemoryConfig, MetricsMode, PoolConfiguration, SmartObjectManager


@dataclass(frozen=True)
class ModeSetup:
    """Configuration payload for one run mode."""

    name: str
    metrics_enabled: bool
    metrics_mode: MetricsMode
    sample_rate: int


MODES: Tuple[ModeSetup, ...] = (
    ModeSetup("off", False, MetricsMode.SYNC, 1),
    ModeSetup("sync", True, MetricsMode.SYNC, 1),
    ModeSetup("async", True, MetricsMode.ASYNC, 1),
    ModeSetup("sampled", True, MetricsMode.SAMPLED, 10),
)


def build_dataset(iterations: int, seed: int) -> List[Tuple[int, bytes]]:
    """Build a deterministic workload dataset."""
    rng = random.Random(seed)
    buffer_sizes = (256, 512, 1024, 2048, 4096)
    dataset: List[Tuple[int, bytes]] = []

    for i in range(iterations):
        size = buffer_sizes[rng.randrange(len(buffer_sizes))]
        payload_len = rng.randint(16, 160)
        payload = f"idx={i}|seed={seed}|{'x' * payload_len}".encode()
        dataset.append((size, payload))

    return dataset


def run_mode(
    mode: ModeSetup,
    dataset: List[Tuple[int, bytes]],
    history_size: int,
    queue_maxsize: int,
) -> Dict[str, float]:
    """Run one mode and collect summary metrics."""
    config = MemoryConfig(
        enable_performance_metrics=mode.metrics_enabled,
        enable_acquisition_tracking=mode.metrics_enabled,
        enable_lock_contention_tracking=False,
        max_performance_history_size=history_size,
        metrics_mode=mode.metrics_mode,
        metrics_sample_rate=mode.sample_rate,
        metrics_queue_maxsize=queue_maxsize,
        metrics_flush_timeout_seconds=2.0,
    )

    pool = SmartObjectManager(
        BytesIOFactory(),
        default_config=config,
        pool_config=PoolConfiguration(enable_monitoring=mode.metrics_enabled),
    )

    p95_ms = 0.0
    p99_ms = 0.0
    dropped = 0.0
    elapsed_ms = 0.0

    try:
        start = time.perf_counter()
        for buffer_size, payload in dataset:
            with pool.acquire_context(buffer_size) as buffer:
                buffer.write(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if pool.metrics_dispatcher is not None:
            pool.metrics_dispatcher.flush(config.metrics_flush_timeout_seconds)

        if pool.performance_metrics is not None:
            snapshot = pool.performance_metrics.create_snapshot()
            p95_ms = snapshot.p95_acquisition_time_ms
            p99_ms = snapshot.p99_acquisition_time_ms

        stats = pool.get_basic_stats()
        dropped = float(stats.get("counters", {}).get("metrics_events_dropped", 0))
    finally:
        pool.shutdown()

    return {
        "elapsed_ms": elapsed_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "dropped_events": dropped,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare SmartPool metrics modes on one workload")
    parser.add_argument("--iterations", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--history-size", type=int, default=1000)
    parser.add_argument("--queue-maxsize", type=int, default=20_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.iterations <= 0:
        raise ValueError("--iterations must be > 0")

    dataset = build_dataset(args.iterations, args.seed)
    results: Dict[str, Dict[str, float]] = {}

    for mode in MODES:
        results[mode.name] = run_mode(
            mode=mode,
            dataset=dataset,
            history_size=args.history_size,
            queue_maxsize=args.queue_maxsize,
        )

    print("=== SmartPool Metrics Modes Example ===")
    print(f"iterations: {args.iterations}")
    print(f"history_size: {args.history_size}")
    print(f"queue_maxsize: {args.queue_maxsize}")

    off_elapsed = results["off"]["elapsed_ms"]
    for mode_name in ("off", "sync", "async", "sampled"):
        mode_res = results[mode_name]
        overhead_pct = (
            0.0
            if off_elapsed == 0
            else ((mode_res["elapsed_ms"] - off_elapsed) / off_elapsed) * 100
        )
        print(
            f"\n[{mode_name}] "
            f"elapsed={mode_res['elapsed_ms']:.2f}ms "
            f"overhead_vs_off={overhead_pct:+.1f}% "
            f"p95={mode_res['p95_ms']:.4f}ms "
            f"p99={mode_res['p99_ms']:.4f}ms "
            f"dropped={int(mode_res['dropped_events'])}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
