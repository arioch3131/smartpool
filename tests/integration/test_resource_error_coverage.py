from smartpool.core.exceptions.resource_error import (
    DiskSpaceExhaustedError,
    MemoryLimitExceededError,
    ResourceLeakDetectedError,
    ThreadPoolExhaustedError,
)


class TestResourceErrors:
    def test_memory_limit_exceeded_error(self):
        err = MemoryLimitExceededError(current_usage=1000, limit=500, component="cache")
        assert "Memory limit exceeded for cache" in str(err)
        assert err.context["current_usage_bytes"] == 1000
        assert err.context["limit_bytes"] == 500
        assert err.context["component"] == "cache"
        assert err.message == "Memory limit exceeded for cache: 0.0MB/0.0MB"

        err_zero_limit = MemoryLimitExceededError(current_usage=1000, limit=0)
        assert "Memory limit exceeded for pool: 0.0MB/0.0MB" in str(err_zero_limit)
        assert err_zero_limit.context["usage_percent"] == 0.0

    def test_thread_pool_exhausted_error(self):
        err = ThreadPoolExhaustedError(active_threads=10, max_threads=10, waiting_tasks=5)
        assert "Thread pool exhausted" in str(err)
        assert err.context["active_threads"] == 10
        assert err.context["max_threads"] == 10
        assert err.context["waiting_tasks"] == 5
        assert err.message == "Thread pool exhausted: 10/10 active threads, 5 waiting tasks"

        err_zero_max_threads = ThreadPoolExhaustedError(active_threads=10, max_threads=0)
        assert "Thread pool exhausted: 10/0 active threads, 0 waiting tasks" in str(
            err_zero_max_threads
        )
        assert err_zero_max_threads.context["utilization_percent"] == 0.0

    def test_resource_leak_detected_error(self):
        err = ResourceLeakDetectedError(
            resource_type="connection", leaked_count=3, expected_count=1
        )
        assert "Resource leak detected for connection" in str(err)
        assert err.context["resource_type"] == "connection"
        assert err.context["leaked_count"] == 3
        assert err.context["expected_count"] == 1
        assert (
            err.message
            == "Resource leak detected for connection: 3 unreleased resources (expected: 1)"
        )

        err_zero_expected = ResourceLeakDetectedError(
            resource_type="socket", leaked_count=5, expected_count=0
        )
        assert "Resource leak detected for socket: 5 unreleased resources (expected: 0)" in str(
            err_zero_expected
        )
        assert err_zero_expected.context["leak_ratio"] == 5.0  # 5 / 1 (max(1,0))

    def test_disk_space_exhausted_error(self):
        err = DiskSpaceExhaustedError(available_bytes=1000, required_bytes=5000, path="/data")
        assert "Insufficient disk space on /data" in str(err)
        assert err.context["available_bytes"] == 1000
        assert err.context["required_bytes"] == 5000
        assert err.context["path"] == "/data"
        assert err.message == "Insufficient disk space on /data: 0.0MB available, 0.0MB required"

        err_zero_required = DiskSpaceExhaustedError(available_bytes=1000, required_bytes=0)
        assert "Insufficient disk space on /tmp: 0.0MB available, 0.0MB required" in str(
            err_zero_required
        )
