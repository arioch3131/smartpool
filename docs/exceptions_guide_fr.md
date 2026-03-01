# Guide de Gestion des Exceptions SmartPool

## Vue d'ensemble

SmartPool fournit une hiérarchie complète d'exceptions personnalisées conçue pour une gestion d'erreurs granulaire et une observabilité améliorée. Ce système permet une classification précise des erreurs, un contexte de débogage riche, et des politiques de gestion d'erreurs flexibles.

## Hiérarchie des Exceptions

### Exception de Base

#### SmartPoolError
L'exception de base pour toutes les erreurs SmartPool, fournissant un contexte riche pour le débogage et le monitoring.

**Fonctionnalités :**
- Informations contextuelles riches avec timestamp
- Codes d'erreur pour la catégorisation
- Chaînage de cause pour l'analyse de cause racine
- Support de sérialisation pour logging/monitoring

**Utilisation :**
```python
from smartpool.core.exceptions import SmartPoolError

try:
    # Opérations du pool
    pass
except SmartPoolError as e:
    # Accéder aux informations d'erreur riches
    error_dict = e.to_dict()
    print(f"Erreur : {e.message}")
    print(f"Contexte : {e.context}")
    print(f"Timestamp : {e.timestamp}")
```

## Catégories d'Exceptions

### 1. Exceptions de Configuration

#### PoolConfigurationError
Classe de base pour les erreurs liées à la configuration.

#### InvalidPoolSizeError
Levée lorsque les paramètres de taille du pool sont invalides.

```python
from smartpool.config import MemoryConfig
from smartpool.core.exceptions import InvalidPoolSizeError

# Exemple : taille de pool invalide
try:
    config = MemoryConfig(max_objects_per_key=-1)
except InvalidPoolSizeError as e:
    print(f"Erreur de taille de pool : {e.message}")
    print(f"Taille fournie : {e.context['provided_size']}")
```

#### InvalidTTLError
Levée lorsque les valeurs TTL (Time-To-Live) sont invalides.

```python
from smartpool.config import MemoryConfig
from smartpool.core.exceptions import InvalidTTLError

try:
    config = MemoryConfig(ttl_seconds=-1.0)
except InvalidTTLError as e:
    print(f"Erreur TTL : {e.message}")
```

#### InvalidPresetError
Levée lorsqu'un preset de configuration invalide est spécifié.

#### ConfigurationConflictError
Levée lorsque les paramètres de configuration entrent en conflit les uns avec les autres.

### 2. Exceptions de Factory

#### FactoryError
Classe de base pour les erreurs liées aux factories, avec contexte sur la classe factory et la méthode.

#### FactoryCreationError
Levée lorsque la création d'objet échoue dans la factory.

```python
from smartpool.core.exceptions import FactoryCreationError

try:
    obj = factory.create(*args, **kwargs)
except FactoryCreationError as e:
    print(f"Échec de création : {e.message}")
    print(f"Factory : {e.context['factory_class']}")
    print(f"Nombre d'args : {e.context['args_count']}")
```

#### FactoryValidationError
Levée lorsque la validation d'objet échoue.

#### FactoryResetError
Levée lorsque l'opération de reset d'objet échoue.

#### FactoryDestroyError
Levée lorsque la destruction d'objet échoue.

#### FactoryKeyGenerationError
Levée lorsque la génération de clé de pool échoue.

### 3. Exceptions d'Opérations de Pool

#### PoolOperationError
Classe de base pour les erreurs d'opération de pool.

#### ObjectAcquisitionError
Classe de base pour les erreurs d'acquisition d'objet.

#### PoolExhaustedError
Levée lorsque le pool est épuisé et ne peut pas fournir d'objets.

```python
from smartpool.core.exceptions import PoolExhaustedError

try:
    obj_id, key, obj = pool.acquire()
except PoolExhaustedError as e:
    print(f"Pool épuisé : {e.message}")
    print(f"Utilisation : {e.context['utilization_percent']}%")
    print(f"Actuel/Max : {e.context['current_size']}/{e.context['max_objects_per_key']}")
```

#### AcquisitionTimeoutError
Levée lorsque l'acquisition d'objet expire.

#### ObjectCreationFailedError
Levée lorsque la création d'objet échoue pendant l'acquisition.

#### ObjectReleaseError
Classe de base pour les erreurs de libération d'objet.

#### ObjectValidationFailedError
Levée lorsque la validation d'objet échoue pendant la libération.

#### ObjectResetFailedError
Levée lorsque le reset d'objet échoue pendant la libération.

#### ObjectCorruptionError
Levée lorsqu'une corruption d'objet est détectée.

### 4. Exceptions de Cycle de Vie

#### PoolLifecycleError
Classe de base pour les erreurs de cycle de vie de pool.

#### PoolAlreadyShutdownError
Levée lors de tentative d'utilisation d'un pool fermé.

```python
from smartpool.core.exceptions import PoolAlreadyShutdownError

try:
    pool.acquire()
except PoolAlreadyShutdownError as e:
    print(f"Pool fermé : {e.message}")
    print(f"Opération tentée : {e.context['attempted_operation']}")
```

#### PoolInitializationError
Levée lorsque l'initialisation du pool échoue.

#### BackgroundManagerError
Levée lorsque les opérations de tâches en arrière-plan échouent.

#### ManagerSynchronizationError
Levée lorsque la synchronisation entre managers échoue.

### 5. Exceptions de Performance

#### PoolPerformanceError
Classe de base pour les erreurs liées à la performance.

#### HighLatencyError
Levée lorsque la latence d'opération dépasse les seuils.

```python
from smartpool.core.exceptions import HighLatencyError

try:
    # Surveiller la latence
    if latency > threshold:
        raise HighLatencyError(
            operation="acquire",
            actual_latency_ms=latency,
            threshold_ms=threshold
        )
except HighLatencyError as e:
    print(f"Latence élevée détectée : {e.context['latency_ratio']}x seuil")
```

#### LowHitRateError
Levée lorsque le taux de réussite tombe en dessous des niveaux acceptables.

#### ExcessiveObjectCreationError
Levée lorsque le taux de création d'objets est excessif.

### 6. Exceptions de Ressources

#### PoolResourceError
Classe de base pour les erreurs liées aux ressources.

#### MemoryLimitExceededError
Levée lorsque les limites de mémoire sont dépassées.

#### DiskSpaceExhaustedError
Levée lorsque l'espace disque est épuisé.

#### ThreadPoolExhaustedError
Levée lorsque le pool de threads est épuisé.

#### ResourceLeakDetectedError
Levée lorsque des fuites de ressources sont détectées.

## Utilitaires de Gestion des Exceptions

### ExceptionPolicy

Contrôle le comportement des exceptions basé sur l'environnement et la configuration.

```python
from smartpool.core.exceptions import ExceptionPolicy

policy = ExceptionPolicy()
policy.strict_mode = True  # Lever toutes les exceptions en dev/test
policy.log_all_exceptions = True
policy.raise_on_corruption = False

# Vérifier si l'exception doit être levée
if policy.should_raise(exception_type):
    raise exception
else:
    logger.warning(f"Erreur récupérable : {exception}")
```

### ExceptionMetrics

Collecte des métriques sur les exceptions pour le monitoring et l'analyse.

```python
from smartpool.core.exceptions import ExceptionMetrics, SmartPoolError

metrics = ExceptionMetrics()

# Enregistrer les exceptions
error = SmartPoolError("Erreur de test", error_code="TEST_001")
metrics.record_exception(error)

# Accéder aux métriques
print(f"Nombre d'erreurs : {metrics.exception_counters['TEST_001']}")
```

### SmartPoolExceptionFactory

Factory pour créer des exceptions avec un contexte standardisé.

```python
from smartpool.core.exceptions import SmartPoolExceptionFactory

# Créer une exception de factory
factory_error = SmartPoolExceptionFactory.create_factory_error(
    error_type="creation",
    factory_class="BytesIOFactory",
    method_name="create",
    args=(1024,),
    kwargs={"mode": "binary"}
)

# Créer une exception d'opération de pool
pool_error = SmartPoolExceptionFactory.create_pool_operation_error(
    error_type="exhausted",
    pool_key="buffer_pool",
    current_size=50,
    max_objects_per_key=50,
    active_objects_count=45
)
```

## Meilleures Pratiques

### 1. Gestion des Exceptions dans les Factories

```python
from smartpool.core.exceptions import FactoryCreationError, FactoryResetError

class CustomFactory(ObjectFactory[MonObjet]):
    def create(self, *args, **kwargs):
        try:
            return MonObjet(*args, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                factory_class=self.__class__.__name__,
                args=args,
                kwargs_dict=kwargs,
                cause=e
            )
    
    def reset(self, obj):
        try:
            obj.reset()
            return True
        except Exception as e:
            raise FactoryResetError(
                factory_class=self.__class__.__name__,
                object_type=type(obj).__name__,
                cause=e
            )
```

### 2. Gestion d'Erreurs Gracieuse

```python
from smartpool.core.exceptions import (
    SmartPoolError, 
    PoolExhaustedError, 
    AcquisitionTimeoutError
)

def acquisition_securisee_objet(pool, timeout=5.0):
    try:
        return pool.acquire(timeout=timeout)
    except PoolExhaustedError:
        # Gérer l'épuisement du pool
        logger.warning("Pool épuisé, tentative de stratégie alternative")
        return None
    except AcquisitionTimeoutError:
        # Gérer le timeout
        logger.warning("Timeout d'acquisition, nouvelle tentative avec timeout plus long")
        return pool.acquire(timeout=timeout * 2)
    except SmartPoolError as e:
        # Logger toutes les erreurs SmartPool avec contexte
        logger.error(f"Erreur de pool : {e.to_dict()}")
        raise
```

### 3. Intégration avec le Monitoring

```python
from smartpool.core.exceptions import ExceptionPolicy, ExceptionMetrics

class PoolAvecMonitoring:
    def __init__(self):
        self.exception_policy = ExceptionPolicy()
        self.exception_metrics = ExceptionMetrics()
    
    def gerer_exception(self, exception):
        # Enregistrer pour les métriques
        self.exception_metrics.record_exception(exception)
        
        # Appliquer la politique
        if self.exception_policy.should_log(exception):
            logger.error(f"Exception de pool : {exception.to_dict()}")
        
        if self.exception_policy.should_raise(type(exception)):
            raise exception
```

### 4. Enrichissement du Contexte

```python
from smartpool.core.exceptions import SmartPoolError

def enrichir_contexte_exception(exception, contexte_additionnel):
    """Ajouter du contexte additionnel à une exception existante."""
    if isinstance(exception, SmartPoolError):
        exception.context.update(contexte_additionnel)
    return exception

# Utilisation
try:
    pool.acquire()
except SmartPoolError as e:
    e = enrichir_contexte_exception(e, {
        "request_id": "req_123",
        "user_id": "user_456",
        "operation_phase": "initialisation"
    })
    raise e
```

## Exemples de Configuration

### Environnement de Développement

```python
from smartpool.core.exceptions import ExceptionPolicy

# Mode strict pour le développement
policy = ExceptionPolicy()
policy.strict_mode = True
policy.log_all_exceptions = True
policy.raise_on_corruption = True
policy.performance_monitoring = True
```

### Environnement de Production

```python
# Gestion gracieuse pour la production
policy = ExceptionPolicy()
policy.strict_mode = False
policy.log_all_exceptions = True
policy.raise_on_corruption = False
policy.max_error_details = 500  # Limiter la taille du contexte
```

## Intégration avec le Code Existant

### Compatibilité Descendante

Le nouveau système d'exceptions est conçu pour être rétrocompatible. Le code existant qui capture les `Exception` générales continuera de fonctionner :

```python
# Le code existant continue de fonctionner
try:
    pool.acquire()
except Exception as e:
    logger.error(f"Erreur de pool : {e}")

# Le nouveau code peut être plus spécifique
try:
    pool.acquire()
except PoolExhaustedError as e:
    # Gérer l'épuisement de pool spécifiquement
    pass
except SmartPoolError as e:
    # Gérer toutes les erreurs SmartPool
    logger.error(f"Erreur SmartPool : {e.to_dict()}")
except Exception as e:
    # Gérer toute autre erreur
    logger.error(f"Erreur inattendue : {e}")
```

### Migration Graduelle

Migrer vers le nouveau système d'exceptions graduellement :

1. Commencer par capturer `SmartPoolError` pour les exceptions SmartPool générales
2. Ajouter des gestionnaires spécifiques pour les exceptions communes comme `PoolExhaustedError`
3. Implémenter des politiques d'exception pour un comportement spécifique à l'environnement
4. Ajouter la collecte de métriques pour le monitoring

Ce système d'exceptions fournit des capacités de gestion d'erreurs robustes tout en maintenant la flexibilité et la facilité d'utilisation.
