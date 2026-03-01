"""
Client for testing web integration of the memory pool.

This script simulates load on the web application by sending various
HTTP requests (POST, GET, DELETE) to the API endpoints.
It also monitors the memory pool status periodically.
"""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

# pylint: disable=R0801

BASE_URL = "http://localhost:8000"


def process_data(content: str):
    """Sends a request to the data processing endpoint."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/data/process", json={"content": content}, timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def set_cache(key: str, value: any):
    """Sends a request to set a cache value."""
    try:
        response = requests.post(f"{BASE_URL}/api/cache/{key}", json={"value": value}, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


def get_cache(key: str):
    """Sends a request to get a cache value."""
    try:
        response = requests.get(f"{BASE_URL}/api/cache/{key}", timeout=10)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def delete_cache(key: str):
    """Sends a request to delete a cache value."""
    try:
        response = requests.delete(f"{BASE_URL}/api/cache/{key}", timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException:
        return False


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


def run_load_test(duration_seconds: int):
    """Runs a load test for a given duration."""
    print(f"--- Starting Load Test for {duration_seconds} seconds ---")
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_pools, args=(stop_event,))
    monitor_thread.start()

    successful_requests = 0
    failed_requests = 0

    def task_wrapper(func, *args):
        nonlocal successful_requests, failed_requests
        if func(*args):
            successful_requests += 1
        else:
            failed_requests += 1

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

    print("--- Load Test Finished ---")
    print(f"Successful requests: {successful_requests}")
    print(f"Failed requests: {failed_requests}")
    stop_event.set()
    monitor_thread.join()


if __name__ == "__main__":
    print(
        "Waiting for the server to start..."
        " (make sure you run 'python examples/example_07_main_web_server.py')"
    )
    time.sleep(3)
    run_load_test(20)
