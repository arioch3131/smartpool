"""Export Exceptions."""

from .base_error import SmartPoolError
from .configuration_error import (
    ConfigurationConflictError,
    InvalidPoolSizeError,
    InvalidPresetError,
    InvalidTTLError,
    PoolConfigurationError,
)
from .factory_creating_exceptions_context import SmartPoolExceptionFactory
from .factory_error import (
    FactoryCreationError,
    FactoryDestroyError,
    FactoryError,
    FactoryKeyGenerationError,
    FactoryResetError,
    FactoryValidationError,
)
from .lifecycle_error import (
    BackgroundManagerError,
    ManagerSynchronizationError,
    PoolAlreadyShutdownError,
    PoolInitializationError,
    PoolLifecycleError,
)
from .management_utils import ExceptionMetrics, ExceptionPolicy
from .operation_error import (
    AcquisitionTimeoutError,
    CorruptionThresholdExceededError,
    ObjectAcquisitionError,
    ObjectCorruptionError,
    ObjectCreationFailedError,
    ObjectReleaseError,
    ObjectResetFailedError,
    ObjectStateCorruptedError,
    ObjectValidationFailedError,
    PoolExhaustedError,
    PoolOperationError,
)
from .performance_error import (
    ExcessiveObjectCreationError,
    HighLatencyError,
    LowHitRateError,
    PoolPerformanceError,
)
from .resource_error import (
    DiskSpaceExhaustedError,
    MemoryLimitExceededError,
    PoolResourceError,
    ResourceLeakDetectedError,
    ThreadPoolExhaustedError,
)

__all__ = [
    "SmartPoolError",
    # Configuration
    "PoolConfigurationError",
    "InvalidPoolSizeError",
    "InvalidTTLError",
    "InvalidPresetError",
    "ConfigurationConflictError",
    # Factory
    "FactoryError",
    "FactoryCreationError",
    "FactoryDestroyError",
    "FactoryKeyGenerationError",
    "FactoryResetError",
    "FactoryValidationError",
    # Pool Operations
    "PoolOperationError",
    "ObjectAcquisitionError",
    "ObjectReleaseError",
    "AcquisitionTimeoutError",
    "ObjectCreationFailedError",
    "ObjectValidationFailedError",
    "ObjectResetFailedError",
    "PoolExhaustedError",
    "ObjectCorruptionError",
    "ObjectStateCorruptedError",
    "CorruptionThresholdExceededError",
    # Lifecycle
    "PoolLifecycleError",
    "BackgroundManagerError",
    "PoolInitializationError",
    "PoolAlreadyShutdownError",
    "ManagerSynchronizationError",
    # Performance
    "PoolPerformanceError",
    "LowHitRateError",
    "HighLatencyError",
    "ExcessiveObjectCreationError",
    # Resources
    "PoolResourceError",
    "DiskSpaceExhaustedError",
    "ThreadPoolExhaustedError",
    "MemoryLimitExceededError",
    "ResourceLeakDetectedError",
    # Management Utils
    "ExceptionMetrics",
    "ExceptionPolicy",
    # Factory Creating Exception Context
    "SmartPoolExceptionFactory",
]
