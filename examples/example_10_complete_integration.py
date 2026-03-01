"""
Complete integration example of the memory pool system in a real project.

# To run this example, first install the required dependencies:
# pip install -e ".[examples]"

This file demonstrates a complete implementation of an image processing application
using all aspects of the pool system:
- Multiple pools (images, buffers, cache, DB sessions)
- Real-time monitoring
- Auto-optimization
- Robust error handling
- Complete REST API
- Flexible configuration
"""

import asyncio
import logging
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Imports for web application
try:
    from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Imports for image processing
try:
    from PIL import Image, ImageEnhance, ImageFilter

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


from examples.factories import BytesIOFactory, MetadataFactory, PILImageFactory

# Imports from the pool system
from smartpool import (
    MemoryConfig,
    MemoryPreset,
    MemoryPressure,
    ObjectCreationCost,
    PoolConfiguration,
    SmartObjectManager,
)

# === Data Models ===


@dataclass
class ImageProcessingJob:  # pylint: disable=R0902
    """Represents an image processing job."""

    job_id: str
    input_path: str
    output_path: str
    operations: List[str]
    status: str  # 'pending', 'processing', 'completed', 'failed'
    created_at: float
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """To convert to dict"""
        return asdict(self)


@dataclass
class AppConfig:
    """Application configuration."""

    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_formats: List[str] = None
    enable_monitoring: bool = True
    enable_auto_optimization: bool = True
    log_level: str = "INFO"

    def __post_init__(self):
        if self.allowed_formats is None:
            self.allowed_formats = ["JPEG", "PNG", "WEBP", "BMP"]


# === Pool Manager ===


class PoolManager:
    """Centralized manager for all application pools."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.pools: Dict[str, SmartObjectManager] = {}
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def _setup_logging(self):
        """Configures the logging for the application."""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def initialize_pools(self):
        """Initializes all necessary pools."""
        self.logger.info("Initializing memory pools...")

        # Pool for PIL images
        image_factory = PILImageFactory(enable_reset=True)
        image_config = MemoryConfig(
            max_objects_per_key=50,
            ttl_seconds=1800.0,  # 30 minutes
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            max_expected_concurrency=20,
            object_creation_cost=ObjectCreationCost.HIGH,
            memory_pressure=MemoryPressure.NORMAL,
        )

        self.pools["images"] = SmartObjectManager(
            image_factory,
            default_config=image_config,
            pool_config=PoolConfiguration(max_total_objects=150, enable_monitoring=True),
        )

        # Pool for I/O buffers
        buffer_factory = BytesIOFactory()
        self.pools["buffers"] = SmartObjectManager(
            buffer_factory, preset=MemoryPreset.HIGH_THROUGHPUT
        )

        # Pool for metadata cache
        metadata_factory = MetadataFactory()
        cache_config = MemoryConfig(
            max_objects_per_key=200,
            ttl_seconds=3600.0,
            enable_performance_metrics=True,  # 1 hour
        )

        self.pools["cache"] = SmartObjectManager(metadata_factory, default_config=cache_config)

        # Enable auto-optimization if configured
        if self.config.enable_auto_optimization:
            for pool_name, pool in self.pools.items():
                pool.enable_auto_tuning(interval_seconds=300.0)  # 5 minutes
                self.logger.info("Auto-tuning enabled for pool '%s'", pool_name)

        self.logger.info("Initialized %d memory pools", len(self.pools))

    def get_pool(self, pool_name: str) -> Optional[SmartObjectManager]:
        """Retrieves a pool by name."""
        return self.pools.get(pool_name)

    def get_health_status(self) -> Dict[str, Any]:
        """Health status of all pools."""
        status = {"timestamp": time.time(), "overall_status": "healthy", "pools": {}}

        unhealthy_count = 0

        for pool_name, pool in self.pools.items():
            try:
                pool_health = pool.get_health_status()
                status["pools"][pool_name] = pool_health

                if pool_health["status"] != "healthy":
                    unhealthy_count += 1

            except Exception as e:  # pylint: disable=W0718
                status["pools"][pool_name] = {"status": "error", "error": str(e)}
                unhealthy_count += 1

        if unhealthy_count > 0:
            status["overall_status"] = (
                "degraded" if unhealthy_count < len(self.pools) else "critical"
            )

        return status

    def get_performance_summary(self) -> Dict[str, Any]:
        """Performance summary of all pools."""
        summary = {"timestamp": time.time(), "pools": {}}

        for pool_name, pool in self.pools.items():
            try:
                if pool.performance_metrics:
                    snapshot = pool.performance_metrics.create_snapshot()
                    summary["pools"][pool_name] = {
                        "hit_rate": snapshot.hit_rate,
                        "avg_acquisition_time_ms": snapshot.avg_acquisition_time_ms,
                        "acquisitions_per_second": snapshot.acquisitions_per_second,
                        "active_objects_count": pool.get_basic_stats().get(
                            "active_objects_count", 0
                        ),
                    }
                else:
                    stats = pool.get_basic_stats()
                    total_requests = stats.get("hits", 0) + stats.get("misses", 0)
                    hit_rate = stats.get("hits", 0) / total_requests if total_requests > 0 else 0

                    summary["pools"][pool_name] = {
                        "hit_rate": hit_rate,
                        "active_objects_count": stats.get("active_objects_count", 0),
                    }

            except Exception as e:  # pylint: disable=W0718
                summary["pools"][pool_name] = {"error": str(e)}

        return summary

    def shutdown_all(self):
        """Shuts down all pools."""
        self.logger.info("Shutting down all pools...")

        for pool_name, pool in self.pools.items():
            try:
                pool.shutdown()
                self.logger.info("Pool '%s' shutdown successfully", pool_name)
            except Exception as e:  # pylint: disable=W0718
                self.logger.error("Error shutting down pool '%s': %s'", pool_name, e)

        self.pools.clear()


# === Image Processing Service ===


class ImageProcessingService:
    """Image processing service using pools."""

    def __init__(self, pool_manager: PoolManager):
        self.pool_manager = pool_manager
        self.logger = logging.getLogger(__name__)
        self.jobs: Dict[str, ImageProcessingJob] = {}

    def create_job(self, input_path: str, operations: List[str]) -> ImageProcessingJob:
        """Creates a new processing job."""
        job_id = str(uuid.uuid4())
        output_path = f"outputs/{job_id}.jpg"

        job = ImageProcessingJob(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            operations=operations,
            status="pending",
            created_at=time.time(),
        )

        self.jobs[job_id] = job
        return job

    async def process_image(self, job: ImageProcessingJob) -> bool:
        """Processes an image according to the specified operations."""
        try:
            job.status = "processing"
            self.logger.info("Starting processing job %s", job.job_id)

            # Load the image from cache or create a new one
            original_image = await self._load_image_cached(job.input_path)

            # Determine the working image size
            work_size = original_image.size

            # Acquire a working image from the pool
            image_pool = self.pool_manager.get_pool("images")

            with image_pool.acquire_context(*work_size, original_image.mode) as work_image:
                # Copy the original image into the working image
                work_image.paste(original_image)

                # Apply operations
                processed_image = await self._apply_operations(work_image, job.operations)

                # Save the result
                await self._save_image_with_buffer(processed_image, job.output_path)

            job.status = "completed"
            job.completed_at = time.time()

            # Update metadata in cache
            await self._update_job_metadata(job)

            self.logger.info("Job %s completed successfully", job.job_id)
            return True

        except Exception as e:  # pylint: disable=W0718
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = time.time()

            self.logger.error("Job %d failed: %s", job.job_id, e)
            return False

    async def _load_image_cached(self, image_path: str) -> Image.Image:
        """Loads an image with caching."""
        cache_pool = self.pool_manager.get_pool("cache")

        with cache_pool.acquire_context(file_path=image_path) as cache_dict:
            cache_key = f"image_{Path(image_path).name}"

            # Check if image is in cache
            if cache_key in cache_dict:
                cached_data = cache_dict[cache_key]

                # Check if file has not changed
                file_stat = Path(image_path).stat()
                if cached_data.get("mtime") == file_stat.st_mtime:
                    # Recreate image from cached data
                    image_pool = self.pool_manager.get_pool("images")
                    with image_pool.acquire_context(
                        *cached_data["size"], cached_data["mode"]
                    ) as img:
                        # In reality, we should save/restore image data
                        # Here we load from file for simplicity
                        original = Image.open(image_path)
                        img.paste(original)
                        return img.copy()

            # Load from file and cache
            original = Image.open(image_path)

            # Cache metadata
            file_stat = Path(image_path).stat()
            cache_dict[cache_key] = {
                "size": original.size,
                "mode": original.mode,
                "format": original.format,
                "mtime": file_stat.st_mtime,
                "cached_at": time.time(),
            }

            return original

    async def _apply_operations(self, image: Image.Image, operations: List[str]) -> Image.Image:
        """Applies a series of operations to an image."""
        result_image = image

        for operation in operations:
            if operation == "blur":
                result_image = result_image.filter(ImageFilter.BLUR)
            elif operation == "sharpen":
                result_image = result_image.filter(ImageFilter.SHARPEN)
            elif operation == "enhance_contrast":
                enhancer = ImageEnhance.Contrast(result_image)
                result_image = enhancer.enhance(1.5)
            elif operation == "enhance_brightness":
                enhancer = ImageEnhance.Brightness(result_image)
                result_image = enhancer.enhance(1.2)
            elif operation == "resize_50":
                new_size = (result_image.width // 2, result_image.height // 2)
                result_image = result_image.resize(new_size, Image.Resampling.LANCZOS)
            elif operation == "grayscale":
                result_image = result_image.convert("L").convert("RGB")

            # Simulate asynchronous processing
            await asyncio.sleep(0.01)

        return result_image

    async def _save_image_with_buffer(self, image: Image.Image, output_path: str):
        """Saves an image using a buffer from the pool."""
        buffer_pool = self.pool_manager.get_pool("buffers")

        # Estimate necessary buffer size
        estimated_size = image.width * image.height * 3  # RGB approximation
        buffer_size = max(estimated_size, 64 * 1024)  # At least 64KB

        with buffer_pool.acquire_context(buffer_size) as buffer:
            # Save image to buffer
            image.save(buffer, format="JPEG", quality=85)

            # Write buffer to file
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                buffer.seek(0)
                f.write(buffer.read())

    async def _update_job_metadata(self, job: ImageProcessingJob):
        """Updates job metadata in cache."""
        cache_pool = self.pool_manager.get_pool("cache")

        with cache_pool.acquire_context(file_path=f"job_{job.job_id}") as cache_dict:
            cache_dict.update(
                {
                    "job_data": job.to_dict(),
                    "processed_at": time.time(),
                    "operations_count": len(job.operations),
                }
            )

    def get_job(self, job_id: str) -> Optional[ImageProcessingJob]:
        """Retrieves a job by its ID."""
        return self.jobs.get(job_id)

    def list_jobs(self, status: Optional[str] = None) -> List[ImageProcessingJob]:
        """Lists jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())

        if status:
            jobs = [job for job in jobs if job.status == status]

        return sorted(jobs, key=lambda x: x.created_at, reverse=True)


# === FastAPI Application ===
if FASTAPI_AVAILABLE and PIL_AVAILABLE:
    # pylint: disable=R0903
    class ImageProcessingApp:
        """Complete image processing application."""

        def __init__(self, config: AppConfig):
            self.config = config
            self.pool_manager = PoolManager(config)
            self.image_service = ImageProcessingService(self.pool_manager)
            self.executor = ThreadPoolExecutor(max_workers=4)
            self.app = self._create_app()

        def _create_app(self) -> FastAPI:
            """Creates the FastAPI application."""

            @asynccontextmanager
            async def lifespan(_app: FastAPI):
                # Startup
                self.pool_manager.initialize_pools()

                # Create necessary directories
                Path(self.config.upload_dir).mkdir(exist_ok=True)
                Path(self.config.output_dir).mkdir(exist_ok=True)

                yield

                # Shutdown
                self.pool_manager.shutdown_all()
                self.executor.shutdown(wait=True)

            app = FastAPI(
                title="Image Processing Service",
                description="Image processing service with optimized memory pools",
                version="1.0.0",
                lifespan=lifespan,
            )

            # CORS
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

            # Routes
            self._setup_routes(app)

            return app

        def _setup_routes(self, app: FastAPI):  # noqa: PLR0915
            """Configures the API routes."""

            @app.post("/upload")
            async def upload_image(
                file: UploadFile = File(...), operations: str = "blur,enhance_contrast"
            ):
                """Upload and process an image."""

                # Basic checks
                if file.size > self.config.max_file_size:
                    raise HTTPException(400, "File too large")

                # Save the uploaded file
                file_path = Path(self.config.upload_dir) / file.filename

                buffer_pool = self.pool_manager.get_pool("buffers")
                with buffer_pool.acquire_context(file.size) as buffer:
                    content = await file.read()
                    buffer.write(content)

                    with open(file_path, "wb") as f:
                        buffer.seek(0)
                        f.write(buffer.read())

                # Create the job
                ops_list = operations.split(",")
                job = self.image_service.create_job(str(file_path), ops_list)

                return {"job_id": job.job_id, "status": job.status, "operations": job.operations}

            @app.post("/process/{job_id}")
            async def process_job(job_id: str, background_tasks: BackgroundTasks):
                """Triggers job processing."""

                job = self.image_service.get_job(job_id)
                if not job:
                    raise HTTPException(404, "Job not found")

                if job.status != "pending":
                    raise HTTPException(400, f"Job is {job.status}")

                # Start processing in the background
                background_tasks.add_task(self.image_service.process_image, job)

                return {"message": "Processing started", "job_id": job_id}

            @app.get("/jobs/{job_id}")
            async def get_job_status(job_id: str):
                """Retrieves job status."""

                job = self.image_service.get_job(job_id)
                if not job:
                    raise HTTPException(404, "Job not found")

                return job.to_dict()

            @app.get("/jobs")
            async def list_jobs(status: Optional[str] = None):
                """Lists all jobs."""

                jobs = list(self.image_service.jobs.values())

                if status:
                    jobs = [job for job in jobs if job.status == status]

                return [job.to_dict() for job in jobs]

            @app.get("/download/{job_id}")
            async def download_result(job_id: str):
                """Downloads job result."""

                job = self.image_service.get_job(job_id)
                if not job:
                    raise HTTPException(404, "Job not found")

                if job.status != "completed":
                    raise HTTPException(400, f"Job is {job.status}")

                if not Path(job.output_path).exists():
                    raise HTTPException(404, "Output file not found")

                return FileResponse(job.output_path, filename=f"processed_{job.job_id}.jpg")

            # Monitoring routes
            @app.get("/health")
            async def health_check():
                """Application health check."""

                health = self.pool_manager.get_health_status()

                if health["overall_status"] != "healthy":
                    return JSONResponse(content=health, status_code=503)

                return health

            @app.get("/metrics")
            async def get_metrics():
                """Performance metrics."""

                performance = self.pool_manager.get_performance_summary()

                # Add application metrics
                app_metrics = {
                    "jobs": {
                        "total": len(self.image_service.jobs),
                        "pending": len(self.image_service.list_jobs("pending")),
                        "processing": len(self.image_service.list_jobs("processing")),
                        "completed": len(self.image_service.list_jobs("completed")),
                        "failed": len(self.image_service.list_jobs("failed")),
                    }
                }

                return {"pools": performance, "application": app_metrics}

            @app.get("/pools/{pool_name}/status")
            async def get_pool_status(pool_name: str):
                """Detailed pool status."""

                pool = self.pool_manager.get_pool(pool_name)
                if not pool:
                    raise HTTPException(404, "Pool not found")

                return {
                    "health": pool.get_health_status(),
                    "stats": pool.get_basic_stats(),
                    "dashboard": pool.manager.get_dashboard_summary(),
                }

            @app.post("/pools/{pool_name}/optimize")
            async def optimize_pool(pool_name: str):
                """Triggers pool optimization."""

                pool = self.pool_manager.get_pool(pool_name)
                if not pool:
                    raise HTTPException(404, "Pool not found")

                if pool.optimizer:
                    success = pool.optimizer.perform_auto_tuning()
                    return {
                        "success": success,
                        "message": (
                            "Optimization completed" if success else "No optimization needed"
                        ),
                    }
                raise HTTPException(400, "Pool optimizer not available")


# === Usage Examples ===
# pylint: disable=R0914,R0912,R0915
async def demo_complete_application():  # noqa: PLR0912,PLR0915
    """Complete application demonstration."""

    if not (FASTAPI_AVAILABLE and PIL_AVAILABLE):
        print("FastAPI or PIL not available, demo skipped")
        return

    print("=== Complete Application Demonstration ===\n")

    # Configuration
    config = AppConfig(
        upload_dir="demo_uploads",
        output_dir="demo_outputs",
        enable_monitoring=True,
        enable_auto_optimization=True,
        log_level="INFO",
    )

    # Create the application
    app_instance = ImageProcessingApp(config)

    # Simulate operations without web server
    pool_manager = app_instance.pool_manager
    image_service = app_instance.image_service

    # Initialize pools explicitly for the demo, as FastAPI app is not run
    pool_manager.initialize_pools()

    try:
        # Create a test image
        print("1. Creating a test image...")

        # Use the image pool to create a test image
        image_pool = pool_manager.get_pool("images")

        with image_pool.acquire_context(400, 300, "RGB") as test_image:
            # Fill with a color gradient
            for x in range(400):
                for y in range(300):
                    r = int(255 * x / 400)
                    g = int(255 * y / 300)
                    b = 128
                    test_image.putpixel((x, y), (r, g, b))

            # Save the test image
            test_path = Path(config.upload_dir) / "test_image.jpg"
            test_path.parent.mkdir(exist_ok=True)
            test_image.save(test_path)

        print(f"Test image created: {test_path}")

        # Create and process a job
        print("\n2. Creating and processing a job...")

        operations = ["blur", "enhance_contrast", "resize_50"]
        job = image_service.create_job(str(test_path), operations)

        print(f"Job created: {job.job_id}")
        print(f"Operations: {job.operations}")

        # Process the job
        success = await image_service.process_image(job)

        if success:
            print("Job processed successfully!")
            print(f"Result: {job.output_path}")
        else:
            print(f"Processing failed: {job.error_message}")

        # Pool statistics
        print("\n3. Pool statistics...")

        health = pool_manager.get_health_status()
        print(f"Overall status: {health['overall_status']}")

        for pool_name, pool_health in health["pools"].items():
            print(
                f"  {pool_name}: {pool_health['status']}, "
                f"hit_rate: {pool_health.get('hit_rate', 0):.1%}"
            )

        performance = pool_manager.get_performance_summary()
        # Performance metrics
        print("\n4. Pool performance...")

        for pool_name, metrics in performance["pools"].items():
            if "error" not in metrics:
                print(f"  {pool_name}:")
                print(f"    Hit rate: {metrics.get('hit_rate', 0):.1%}")
                print(f"    Active objects: {metrics.get('active_objects_count', 0)}")
                if "avg_acquisition_time_ms" in metrics:
                    print(f"    Average time: {metrics['avg_acquisition_time_ms']:.1f}ms")

        # Load test
        print("\n5. Load test with multiple jobs...")

        jobs = []
        for i in range(10):
            ops = ["blur"] if i % 2 == 0 else ["enhance_brightness", "sharpen"]
            job = image_service.create_job(str(test_path), ops)
            jobs.append(job)

        start_time = time.time()

        # Process jobs in parallel (simulation)
        tasks = [image_service.process_image(job) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()

        successful = sum(1 for r in results if r is True)
        failed = len(results) - successful

        print(f"Processed {len(jobs)} jobs in {(end_time - start_time):.2f}s")
        print(f"Successful: {successful}, Failed: {failed}")

        # Final performance
        final_performance = pool_manager.get_performance_summary()
        print("\n6. Final performance...")

        for pool_name, metrics in final_performance["pools"].items():
            if "error" not in metrics:
                print(f"  {pool_name}: hit_rate {metrics.get('hit_rate', 0):.1%}")

    finally:
        # Cleanup
        pool_manager.shutdown_all()

        # Clean up test files

        for dir_path in [config.upload_dir, config.output_dir]:
            if Path(dir_path).exists():
                shutil.rmtree(dir_path)


def demo_api_usage():
    """Demonstration of API usage."""

    if not (FASTAPI_AVAILABLE and PIL_AVAILABLE):
        print("FastAPI or PIL not available, demo skipped")
        return

    print("\n=== REST API Demonstration ===\n")

    config = AppConfig()
    _ = ImageProcessingApp(config)

    print("FastAPI application created with the following endpoints:")
    print()
    print("Main routes:")
    print("  POST /upload - Upload and job creation")
    print("  POST /process/{job_id} - Start processing")
    print("  GET /jobs/{job_id} - Job status")
    print("  GET /jobs - List all jobs")
    print("  GET /download/{job_id} - Download result")
    print()
    print("Monitoring routes:")
    print("  GET /health - Global health check")
    print("  GET /metrics - Performance metrics")
    print("  GET /pools/{pool_name}/status - Pool status")
    print("  POST /pools/{pool_name}/optimize - Manual optimization")
    print()
    print("To start the server:")
    print("  uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("Example usage with curl:")
    print("  # Upload an image")
    print(
        "  curl -X POST -F 'file=@image.jpg' -F "
        "'operations=blur,enhance_contrast' http://localhost:8000/upload"
    )
    print()
    print("  # Process a job")
    print("  curl -X POST http://localhost:8000/process/{job_id}")
    print()
    print("  # Check status")
    print("  curl http://localhost:8000/jobs/{job_id}")
    print()
    print("  # Download result")
    print("  curl -O http://localhost:8000/download/{job_id}")


if __name__ == "__main__":
    print("=== Complete Integration in a Real Project ===")
    print("This demonstration shows a complete image processing application")
    print("using all aspects of the memory pool system.")
    print()

    # Run demonstrations
    asyncio.run(demo_complete_application())
    demo_api_usage()

    print("\n=== Demonstrated Features ===")
    print("✓ Multiple pools (images, buffers, cache)")
    print("✓ Business service with integrated pools")
    print("✓ Complete REST API with FastAPI")
    print("✓ Asynchronous background processing")
    print("✓ Intelligent metadata caching")
    print("✓ Real-time monitoring and metrics")
    print("✓ Auto-optimization of pools")
    print("✓ Robust error handling")
    print("✓ Flexible configuration by environment")
    print("✓ Health checks and observability")
    print()
    print("This architecture can serve as a basis for:")
    print("- Image processing applications")
    print("- Document processing services")
    print("- Data transformation APIs")
    print("- High-performance microservices")
    print("- Applications requiring optimized memory management")
