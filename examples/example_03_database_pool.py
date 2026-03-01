"""
Example 03: Advanced Usage of SmartObjectManager for Database Sessions.

# To run this example, first install the required dependencies:
# pip install -e ".[database]"

This script provides a comprehensive demonstration of using SmartObjectManager
to manage a pool of SQLAlchemy database sessions. It covers basic operations,
performance under concurrent load, error handling, and advanced monitoring.

Key Concepts Illustrated:
- Configuring the pool for database connections using presets and custom configs.
- Acquiring and releasing sessions safely within a context.
- Simulating high-concurrency workloads to measure performance.
- Handling database errors gracefully without crashing the pool.
- Using advanced features like performance metrics, reporting, and auto-tuning.
- Comparing different performance presets.
"""

import datetime
import threading
import time

from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from examples.factories import SQLAlchemySessionFactory
from smartpool import MemoryConfig, MemoryPreset, ObjectCreationCost, SmartObjectManager

# --- 1. Database Model Setup ---
Base = declarative_base()


class User(Base):  # pylint: disable=R0903
    """Database model for example users."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class DatabaseService:  # pylint: disable=R0903
    """
    A service class to manage the database engine and session creation.
    Each time this class is instantiated, it cleans and rebuilds the database schema.
    """

    def __init__(self, database_url="sqlite:///example.db"):
        # `check_same_thread=False` is important for SQLite when used across multiple threads.
        self.engine = create_engine(
            database_url, echo=False, connect_args={"check_same_thread": False}
        )
        # Clear and create schema for a clean run for each example
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)  # Renamed from self.SessionClass


# --- 2. Example Functions ---


def basic_database_pool_example():
    """Demonstrates the basic usage of the pool for CRUD operations."""
    print("\n=== Database Session Pool - Basic Usage ===\n")
    db_service = DatabaseService()

    factory = SQLAlchemySessionFactory(db_service)
    config = MemoryConfig(
        max_objects_per_key=10,
        ttl_seconds=1800.0,
        enable_logging=True,
        enable_performance_metrics=True,
        max_expected_concurrency=20,
        object_creation_cost=ObjectCreationCost.HIGH,
    )
    pool = SmartObjectManager(factory, default_config=config)

    try:
        print("--- Basic Database Operations ---")
        with pool.acquire_context() as session:
            new_user = User(username="john_doe", email="john@example.com")
            session.add(new_user)
            session.commit()
            print(f"User created: {new_user.username}")

        with pool.acquire_context() as session:
            users = session.query(User).all()
            print(f"Number of users: {len(users)}")

        stats = pool.get_basic_stats()
        print("\n--- Pool Statistics ---")
        print(f"Sessions created: {stats['counters'].get('total_objects_created', 0)}")
        print(f"Sessions reused (hits): {stats['counters'].get('hits', 0)}")
    finally:
        pool.shutdown()
        print("Basic example finished and pool shut down.")


def concurrent_load_example():
    """Simulates a concurrent load to test pool performance."""
    print("\n=== Concurrent Load Simulation ===\n")
    db_service = DatabaseService()

    factory = SQLAlchemySessionFactory(db_service)
    pool = SmartObjectManager(factory, preset=MemoryPreset.DATABASE_CONNECTIONS)

    def worker(worker_id):  # pylint: disable=W0613
        with pool.acquire_context() as session:
            _ = session.query(User).limit(5).all()

    try:
        print("Simulating 100 concurrent requests...")
        start_time = time.time()
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        end_time = time.time()

        print(
            f"Total time for 100 requests: {(end_time - start_time) * 1000:.2f}ms"
        )  # Line too long fix
        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()
            print("\n--- Performance Metrics ---")
            print(f"Hit Rate: {snapshot.hit_rate:.2%}")
            print(f"Average Acquisition Time: {snapshot.avg_acquisition_time_ms:.2f}ms")
            print(f"Throughput: {snapshot.acquisitions_per_second:.1f} sessions/sec")
    finally:
        pool.shutdown()
        print("Concurrent load example finished and pool shut down.")


def error_handling_example():
    """Demonstrates the pool's resilience to errors."""
    print("\n=== Error Handling Demonstration ===\n")
    db_service = DatabaseService()

    factory = SQLAlchemySessionFactory(db_service)
    pool = SmartObjectManager(
        factory, default_config=MemoryConfig(max_objects_per_key=5, enable_logging=True)
    )

    try:
        print("--- Testing Error Recovery ---")
        with pool.acquire_context() as session:
            session.add(User(username="another_user", email="another@test.com"))
            session.commit()
            print("Normal operation successful.")

        try:
            with pool.acquire_context() as session:
                session.add(User(username="another_user", email="duplicate@test.com"))
                session.commit()
        except Exception as e:  # pylint: disable=W0718
            print(f"Caught expected error: {type(e).__name__}")
            print("Session was automatically rolled back by the factory.")

        with pool.acquire_context() as session:
            count = session.query(User).count()
            print(f"Number of users after error: {count}")
            print("Pool is still functional.")
    finally:
        pool.shutdown()
        print("Error handling example finished and pool shut down.")


def advanced_monitoring_example():
    """Example of advanced monitoring and auto-tuning."""
    print("\n=== Advanced Monitoring ===\n")
    db_service = DatabaseService()

    factory = SQLAlchemySessionFactory(db_service)
    config = MemoryConfig(
        max_objects_per_key=8, enable_performance_metrics=True, enable_acquisition_tracking=True
    )
    pool = SmartObjectManager(factory, default_config=config)

    try:
        pool.enable_auto_tuning(interval_seconds=5.0)
        print("Collecting performance data with auto-tuning enabled...")
        for i in range(50):
            with pool.acquire_context() as session:
                time.sleep(0.01 if i < 10 else 0)
                session.query(User).count()

        perf_report = pool.get_performance_report(detailed=True)
        print("\n--- Detailed Performance Report ---")
        current_metrics = perf_report["performance"]["current_metrics"]
        print(f"Hit Rate: {current_metrics['hit_rate']:.2%}")
        print(f"Average Time: {current_metrics['avg_acquisition_time_ms']:.2f}ms")
        print(f"P95 Time: {current_metrics['p95_acquisition_time_ms']:.2f}ms")
    finally:
        pool.shutdown()
        print("Advanced monitoring example finished and pool shut down.")


def presets_comparison_example():
    """Example comparing different performance presets."""
    print("\n=== Preset Comparison ===\n")
    db_service = DatabaseService()

    factory = SQLAlchemySessionFactory(db_service)
    pool = SmartObjectManager(factory, preset=MemoryPreset.DATABASE_CONNECTIONS)

    try:
        start_time = time.time()
        for _ in range(20):
            with pool.acquire_context() as session:
                session.query(User).count()
        end_time = time.time()
        stats = pool.get_basic_stats()
        hits = stats["counters"].get("hits", 0)
        misses = stats["counters"].get("misses", 0)
        total = hits + misses
        hit_rate = hits / total if total > 0 else 0
        print(f"  Time: {(end_time - start_time) * 1000:.2f}ms")
        print(f"  Max size: {pool.default_config.max_objects_per_key}")
        print(f"  Hit rate: {hit_rate:.2%}")
    finally:
        pool.shutdown()
    print()


if __name__ == "__main__":
    basic_database_pool_example()
    concurrent_load_example()
    error_handling_example()
    advanced_monitoring_example()
    presets_comparison_example()
    print("\nAll examples completed successfully.")
