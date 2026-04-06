"""
Example of integrating the memory pool system with web applications.

This file shows how to:
- Integrate the pool with Flask and FastAPI.
- Manage the pool's lifecycle in a web application.
- Optimize performance for HTTP requests.
- Monitor the pool via admin endpoints.
- Handle concurrency and user sessions.
"""

import asyncio
import atexit
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

# Imports for Flask
try:
    from flask import Flask, jsonify, request

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Imports for FastAPI
try:
    from fastapi import Depends, FastAPI, HTTPException

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from smartpool import MemoryConfig, MemoryPreset, SmartObjectManager

from .factories import BytesIOFactory, MetadataFactory

LOGGER = logging.getLogger(__name__)

# === Singleton Pattern for the Global Pool ===


class PoolManager:
    """Singleton manager for memory pools."""

    _instance = None
    _pools: Dict[str, SmartObjectManager] = {}
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # Ensure shutdown is called when the application exits
                atexit.register(cls._instance.shutdown_all)
        return cls._instance

    def get_pool(self, pool_name: str) -> Optional[SmartObjectManager]:
        """Gets a pool by name."""
        return self._pools.get(pool_name)

    def create_pool(
        self, pool_name: str, factory, config: MemoryConfig = None, preset: MemoryPreset = None
    ) -> SmartObjectManager:
        """Creates and registers a new pool."""
        with self._lock:
            if pool_name in self._pools:
                # In a web context with hot-reloading, it might be better to
                # return the existing pool
                return self._pools[pool_name]

            pool = SmartObjectManager(factory, default_config=config, preset=preset)
            self._pools[pool_name] = pool
            return pool

    def shutdown_all(self):
        """Shuts down all pools."""
        with self._lock:
            print("Shutting down all pools...")
            for pool_name, pool in self._pools.items():
                try:
                    print(f"Shutting down pool: {pool_name}")
                    pool.shutdown()
                except Exception as e:  # pylint: disable=W0718
                    print(f"Error shutting down pool {pool_name}: {e}")
            self._pools.clear()


# === Flask Integration ===

if FLASK_AVAILABLE:

    def init_flask_pools():
        """Initializes pools for the Flask application."""
        pool_manager = PoolManager()
        print("Initializing pools for Flask...")

        # Pool for data buffers
        buffer_factory = BytesIOFactory()
        buffer_config = MemoryConfig(
            max_objects_per_key=50,
            ttl_seconds=1800.0,
            enable_performance_metrics=True,
            max_expected_concurrency=100,  # Web app with many users
        )
        pool_manager.create_pool("flask_buffers", buffer_factory, buffer_config)

        # Pool for cache sessions
        cache_factory = MetadataFactory()
        pool_manager.create_pool("flask_cache", cache_factory, preset=MemoryPreset.HIGH_THROUGHPUT)
        print("Flask pools initialized.")

    def create_flask_app():  # noqa: PLR0915
        """Creates a Flask application with pool integration."""
        # pylint: disable=R0915 # Too many statements, but acceptable for example clarity

        app = Flask(__name__)
        pool_manager = PoolManager()

        # API Routes
        @app.route("/api/data/process", methods=["POST"])
        def process_data():
            """Processes data using the buffer pool."""
            data = request.get_json()
            if not data or "content" not in data:
                return jsonify({"error": "No content provided"}), 400

            buffer_pool = pool_manager.get_pool("flask_buffers")
            if not buffer_pool:
                return jsonify({"error": "Buffer pool not available"}), 500

            try:
                content = data["content"].encode("utf-8")
                buffer_size = max(len(content) * 2, 1024)  # At least 1KB

                with buffer_pool.acquire_context(buffer_size) as buffer:
                    buffer.write(content)
                    buffer.write(b"\n--- PROCESSED ---\n")
                    buffer.write(f"Processed at: {time.time()}".encode())
                    buffer.seek(0)
                    result = buffer.read().decode("utf-8")

                return jsonify(
                    {"status": "success", "processed_content": result, "buffer_size": buffer_size}
                )
            except Exception:  # pylint: disable=W0718
                LOGGER.exception("Unhandled error in /api/data/process")
                return jsonify({"error": "Internal server error"}), 500

        @app.route("/api/cache/<key>", methods=["GET", "POST", "DELETE"])
        def cache_operations(key):
            """Cache operations using the pool."""
            cache_pool = pool_manager.get_pool("flask_cache")
            if not cache_pool:
                return jsonify({"error": "Cache pool not available"}), 500

            response_data = {}
            status_code = 200

            try:
                with cache_pool.acquire_context(
                    file_path=f"cache_ns_{key.split('_')[0]}"
                ) as cache_dict:
                    if request.method == "GET":
                        value = cache_dict.get(key)
                        if value is None:
                            response_data = {"error": "Key not found"}
                            status_code = 404
                        else:
                            response_data = {"key": key, "value": value}
                    elif request.method == "POST":
                        data = request.get_json()
                        if not data or "value" not in data:
                            response_data = {"error": "No value provided"}
                            status_code = 400
                        else:
                            cache_dict[key] = data["value"]
                            cache_dict["last_updated"] = time.time()
                            response_data = {"status": "stored", "key": key}
                    elif request.method == "DELETE":
                        if key in cache_dict:
                            del cache_dict[key]
                            response_data = {"status": "deleted", "key": key}
                        else:
                            response_data = {"error": "Key not found"}
                            status_code = 404
                    else:
                        response_data = {"error": "Method not allowed"}
                        status_code = 405
            except Exception:  # pylint: disable=W0718
                LOGGER.exception("Unhandled error in /api/cache/%s", key)
                response_data = {"error": "Internal server error"}
                status_code = 500

            return jsonify(response_data), status_code

        # Admin and monitoring routes
        @app.route("/admin/pools/status")
        def pools_status():
            """Status of all pools."""
            status = {}
            for pool_name in ["flask_buffers", "flask_cache"]:
                pool = pool_manager.get_pool(pool_name)
                if pool:
                    stats = pool.get_basic_stats()
                    health = pool.get_health_status()
                    status[pool_name] = {
                        "health": health["status"],
                        "hit_rate": health["hit_rate"],
                        "total_pooled_objects": stats.get("total_pooled_objects", 0),
                        "active_objects_count": stats.get("active_objects_count", 0),
                        "total_requests": health["total_requests"],
                    }
                else:
                    status[pool_name] = {"status": "not_available"}
            return jsonify(status)

        @app.route("/admin/pools/<pool_name>/metrics")
        def pool_metrics(pool_name):
            """Detailed metrics of a pool."""
            pool = pool_manager.get_pool(pool_name)
            if not pool:
                return jsonify({"error": "Pool not found"}), 404
            try:
                report = pool.get_performance_report(detailed=True)
                return jsonify(report)
            except Exception:  # pylint: disable=W0718
                LOGGER.exception("Unhandled error in /admin/pools/%s/metrics", pool_name)
                return jsonify({"error": "Internal server error"}), 500

        return app


# === FastAPI Integration ===

if FASTAPI_AVAILABLE:

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # pylint: disable=unused-argument
        """Lifecycle manager for FastAPI."""
        # Startup
        pool_manager = PoolManager()
        print("Initializing pools for FastAPI...")

        buffer_factory = BytesIOFactory()
        buffer_config = MemoryConfig(
            max_objects_per_key=100,
            ttl_seconds=900.0,
            enable_performance_metrics=True,
            max_expected_concurrency=200,
        )
        pool_manager.create_pool("fastapi_buffers", buffer_factory, buffer_config)

        cache_factory = MetadataFactory()
        pool_manager.create_pool(
            "fastapi_cache", cache_factory, preset=MemoryPreset.HIGH_THROUGHPUT
        )
        print("FastAPI pools initialized.")

        yield

        # Shutdown is handled by atexit hook in PoolManager

    def create_fastapi_app():
        """Creates a FastAPI application with pool integration."""
        app = FastAPI(title="Memory Pool API (FastAPI)", lifespan=lifespan)
        pool_manager = PoolManager()

        def get_buffer_pool():
            pool = pool_manager.get_pool("fastapi_buffers")
            if not pool:
                raise HTTPException(status_code=500, detail="Buffer pool not available")
            return pool

        def get_cache_pool():
            pool = pool_manager.get_pool("fastapi_cache")
            if not pool:
                raise HTTPException(status_code=500, detail="Cache pool not available")
            return pool

        @app.post("/api/data/process")
        async def process_data_async(
            data: Dict[str, Any], buffer_pool: SmartObjectManager = Depends(get_buffer_pool)
        ):
            content = data["content"].encode("utf-8")
            buffer_size = max(len(content) * 2, 1024)
            with buffer_pool.acquire_context(buffer_size) as buffer:
                buffer.write(content)
                await asyncio.sleep(0.01)  # Simulate async I/O
                buffer.seek(0)
                result = buffer.read().decode("utf-8")
            return {"processed_content": result}

        @app.get("/api/cache/{key}")
        async def get_cache(key: str, cache_pool: SmartObjectManager = Depends(get_cache_pool)):
            with cache_pool.acquire_context(
                file_path=f"cache_ns_{key.split('_', maxsplit=1)[0]}"
            ) as cache_dict:
                value = cache_dict.get(key)
                if value is None:
                    raise HTTPException(status_code=404, detail="Key not found")
                return {"key": key, "value": value}

        @app.post("/api/cache/{key}")
        async def set_cache(
            key: str,
            data: Dict[str, Any],
            cache_pool: SmartObjectManager = Depends(get_cache_pool),
        ):
            if "value" not in data:
                raise HTTPException(status_code=400, detail="No value provided")
            with cache_pool.acquire_context(
                file_path=f"cache_ns_{key.split('_', maxsplit=1)[0]}"
            ) as cache_dict:
                cache_dict[key] = data["value"]
                cache_dict["last_updated"] = time.time()
                return {"status": "stored", "key": key}

        @app.delete("/api/cache/{key}")
        async def delete_cache(key: str, cache_pool: SmartObjectManager = Depends(get_cache_pool)):
            with cache_pool.acquire_context(
                file_path=f"cache_ns_{key.split('_', maxsplit=1)[0]}"
            ) as cache_dict:
                if key in cache_dict:
                    del cache_dict[key]
                    return {"status": "deleted", "key": key}
                raise HTTPException(status_code=404, detail="Key not found")  # Refactored

        @app.get("/admin/pools/status")
        async def pools_status_async():
            status = {}
            for pool_name in ["fastapi_buffers", "fastapi_cache"]:
                pool = pool_manager.get_pool(pool_name)
                if pool:
                    stats = pool.get_basic_stats()
                    health = pool.get_health_status()
                    status[pool_name] = {
                        "health": health["status"],
                        "hit_rate": health["hit_rate"],
                        "total_pooled_objects": stats.get("total_pooled_objects", 0),
                        "active_objects_count": stats.get("active_objects_count", 0),
                        "total_requests": health["total_requests"],
                    }
                else:
                    status[pool_name] = {"status": "not_available"}
            return status

        return app
