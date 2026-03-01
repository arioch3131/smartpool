"""
Improved client for testing web integration of the memory pool.

This script provides more realistic usage patterns and better failure tracking.
"""

import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

BASE_URL = "http://localhost:8000"

# pylint: disable=R0801


# pylint: disable=R0903
class TestResult:
    """Container for test results with more detailed tracking."""

    def __init__(self):
        self.successful_requests = 0
        self.failed_requests = 0
        self.operation_counts = defaultdict(int)
        self.operation_successes = defaultdict(int)
        self.operation_failures = defaultdict(int)
        self.http_404_count = 0  # Track legitimate 404s separately


def process_data(content: str):
    """Sends a request to the data processing endpoint."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/data/process", json={"content": content}, timeout=10
        )
        response.raise_for_status()
        return True, None
    except requests.exceptions.RequestException as e:
        return False, str(e)


def set_cache(key: str, value: any):
    """Sends a request to set a cache value."""
    try:
        response = requests.post(f"{BASE_URL}/api/cache/{key}", json={"value": value}, timeout=10)
        response.raise_for_status()
        return True, None
    except requests.exceptions.RequestException as e:
        return False, str(e)


def get_cache(key: str):
    """Sends a request to get a cache value. Returns (success, data/error, is_404)."""
    try:
        response = requests.get(f"{BASE_URL}/api/cache/{key}", timeout=10)
        if response.status_code == 404:
            return False, "Key not found", True  # Flag as 404
        response.raise_for_status()
        return True, response.json(), False
    except requests.exceptions.RequestException as e:
        return False, str(e), False


def delete_cache(key: str):
    """Sends a request to delete a cache value. Returns (success, error, is_404)."""
    try:
        response = requests.delete(f"{BASE_URL}/api/cache/{key}", timeout=10)
        if response.status_code == 404:
            return False, "Key not found", True  # Flag as 404
        response.raise_for_status()
        return True, None, False
    except requests.exceptions.RequestException as e:
        return False, str(e), False


def monitor_pools(stop_event):
    """Periodically fetches and prints the pool status."""
    while not stop_event.is_set():
        try:
            response = requests.get(f"{BASE_URL}/admin/pools/status", timeout=5)
            response.raise_for_status()
            print(f"\n--- Pool Status at {time.strftime('%H:%M:%S')} ---")
            print(response.json())
            print("-------------------------------------\n")
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)


# pylint: disable=R0903
class RealisticWorkloadGenerator:
    """Generates more realistic workload patterns."""

    def __init__(self):
        self.cache_keys = set()  # Track which keys exist
        self.key_counter = 0

    def generate_realistic_operations(self, duration_seconds: int):
        """Generates a sequence of realistic operations."""
        operations = []
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            # 40% chance: Process data (always valid)
            if random.random() < 0.4:
                operations.append(("process_data", f"content_{random.randint(0, 1000)}"))

            # 30% chance: Cache operations (realistic flow)
            elif random.random() < 0.7:
                if len(self.cache_keys) == 0 or random.random() < 0.6:
                    # SET operation (create new key or update existing)
                    if random.random() < 0.3 and self.cache_keys:
                        # 30% chance to update existing key
                        key = random.choice(list(self.cache_keys))
                    else:
                        # 70% chance to create new key
                        key = f"realistic_key_{self.key_counter}"
                        self.key_counter += 1
                        self.cache_keys.add(key)

                    operations.append(("set_cache", key, f"value_{time.time()}"))

                # GET or DELETE on existing keys (90% success rate)
                elif random.random() < 0.7:
                    # GET operation
                    key = random.choice(list(self.cache_keys))
                    operations.append(("get_cache", key))
                else:
                    # DELETE operation (remove from tracking)
                    key = random.choice(list(self.cache_keys))
                    self.cache_keys.discard(key)
                    operations.append(("delete_cache", key))

            # 30% chance: Mix of operations with some intentional 404s
            else:
                operation_type = random.choice(["get_cache", "delete_cache"])
                # 20% chance to use non-existent key (intentional 404)
                if random.random() < 0.2:
                    key = f"nonexistent_key_{random.randint(1000, 9999)}"
                else:
                    key = (
                        random.choice(list(self.cache_keys))
                        if self.cache_keys
                        else f"key_{random.randint(0, 20)}"
                    )

                operations.append((operation_type, key))

            time.sleep(0.05)  # Rate limiting

        return operations


# pylint: disable=R0915
def run_realistic_load_test(duration_seconds: int):  # noqa: PLR0915
    """Runs a more realistic load test."""
    print(f"--- Starting Realistic Load Test for {duration_seconds} seconds ---")

    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_pools, args=(stop_event,))
    monitor_thread.start()

    workload_generator = RealisticWorkloadGenerator()
    result = TestResult()

    # pylint: disable=R0912
    def execute_operation(operation_data):  # noqa: PLR0912
        """Execute a single operation and track results."""
        op_type = operation_data[0]
        result.operation_counts[op_type] += 1

        try:
            if op_type == "process_data":
                success, _ = process_data(operation_data[1])
                if success:
                    result.operation_successes[op_type] += 1
                    result.successful_requests += 1
                else:
                    result.operation_failures[op_type] += 1
                    result.failed_requests += 1

            elif op_type == "set_cache":
                success, _ = set_cache(operation_data[1], operation_data[2])
                if success:
                    result.operation_successes[op_type] += 1
                    result.successful_requests += 1
                else:
                    result.operation_failures[op_type] += 1
                    result.failed_requests += 1

            elif op_type in ["get_cache", "delete_cache"]:
                if op_type == "get_cache":
                    success, _, is_404 = get_cache(operation_data[1])
                else:  # delete_cache
                    success, _, is_404 = delete_cache(operation_data[1])

                if success:
                    result.operation_successes[op_type] += 1
                    result.successful_requests += 1
                elif is_404:
                    # Track 404s separately - they're not system failures
                    result.http_404_count += 1
                    result.operation_failures[op_type] += 1
                else:
                    # Real system failure
                    result.operation_failures[op_type] += 1
                    result.failed_requests += 1

        except Exception as e:  # pylint: disable=W0718
            print(f"Unexpected error in {op_type}: {e}")
            result.operation_failures[op_type] += 1
            result.failed_requests += 1

    # Generate realistic operations
    operations = workload_generator.generate_realistic_operations(duration_seconds)

    # Execute operations with controlled concurrency
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(execute_operation, operations)

    print("--- Realistic Load Test Finished ---")
    total_requests = result.successful_requests + result.failed_requests + result.http_404_count
    print(f"Total requests: {total_requests}")
    print(f"Successful requests: {result.successful_requests}")
    print(f"Failed requests (system errors): {result.failed_requests}")
    print(f"HTTP 404 responses (expected): {result.http_404_count}")
    successful_or_failed = result.successful_requests + result.failed_requests
    failure_rate = (
        (result.failed_requests / successful_or_failed * 100) if successful_or_failed else 0.0
    )
    print(f"Actual failure rate: {failure_rate:.1f}%")

    print("\n--- Operation Breakdown ---")
    for op_type in result.operation_counts:
        total = result.operation_counts[op_type]
        successes = result.operation_successes[op_type]
        failures = result.operation_failures[op_type]
        success_rate = (successes / total * 100) if total > 0 else 0
        print(
            f"{op_type}: {total} total,"
            f" {successes} success,"
            f" {failures} failed ({success_rate:.1f}% success)"
        )

    stop_event.set()
    monitor_thread.join()
    return result


def run_mixed_load_test(duration_seconds: int):  # noqa: PLR0915
    """Runs the original random test but with better failure tracking."""
    print(f"--- Starting Mixed Load Test for {duration_seconds} seconds ---")

    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_pools, args=(stop_event,))
    monitor_thread.start()

    result = TestResult()

    # pylint: disable=comparison-with-callable
    def task_wrapper(func, *args):
        op_type = ""
        if func == process_data:
            success, _ = func(*args)
            op_type = "process_data"
        elif func == set_cache:
            success, _ = func(*args)
            op_type = "set_cache"
        elif func == get_cache:
            success, _, is_404 = func(*args)
            op_type = "get_cache"
            if not success and is_404:
                result.http_404_count += 1
        elif func == delete_cache:
            success, _, is_404 = func(*args)
            op_type = "delete_cache"
            if not success and is_404:
                result.http_404_count += 1

        result.operation_counts[op_type] += 1
        if success:
            result.operation_successes[op_type] += 1
            result.successful_requests += 1
        else:
            result.operation_failures[op_type] += 1
            if op_type not in ["get_cache", "delete_cache"] or not locals().get("is_404", False):
                result.failed_requests += 1

    end_time = time.time() + duration_seconds
    with ThreadPoolExecutor(max_workers=10) as executor:
        while time.time() < end_time:
            func = random.choice([process_data, set_cache, get_cache, delete_cache])
            key = f"key_{random.randint(0, 20)}"

            if func is process_data:
                executor.submit(task_wrapper, func, f"content_{random.randint(0, 1000)}")
            elif func is set_cache:
                executor.submit(task_wrapper, func, key, f"value_{time.time()}")
            elif func is get_cache:
                executor.submit(task_wrapper, func, key)
            elif func is delete_cache:
                executor.submit(task_wrapper, func, key)

            time.sleep(0.05)

    print("--- Mixed Load Test Finished ---")
    print(
        f"Total requests: {
            result.successful_requests + result.failed_requests + result.http_404_count
        }"
    )
    print(f"Successful requests: {result.successful_requests}")
    print(f"Failed requests (system errors): {result.failed_requests}")
    print(f"HTTP 404 responses: {result.http_404_count}")

    stop_event.set()
    monitor_thread.join()
    return result


if __name__ == "__main__":
    print(
        "Waiting for the server to start..."
        " (make sure you run 'python examples/example_07_main_web_server.py')"
    )
    time.sleep(3)

    print("\n" + "=" * 60)
    print("RUNNING REALISTIC LOAD TEST")
    print("=" * 60)
    realistic_result = run_realistic_load_test(20)

    print("\n" + "=" * 60)
    print("RUNNING ORIGINAL MIXED LOAD TEST (for comparison)")
    print("=" * 60)
    mixed_result = run_mixed_load_test(20)
