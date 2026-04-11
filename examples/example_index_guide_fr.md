# Guide d'utilisation du système de pool de mémoire

## Vue d'ensemble

Le système de pool de mémoire (`smartpool`) est une solution avancée pour optimiser la gestion de la mémoire et améliorer les performances des applications Python. Il offre une réutilisation intelligente d'objets coûteux à créer, avec monitoring, auto-optimisation et gestion robuste des erreurs.

## Architecture principale

```
SmartObjectManager (Pool principal)
├── ObjectFactory (Interface pour créer/valider/détruire les objets)
├── MemoryConfig (Configuration du pool)
├── Managers spécialisés:
│   ├── PoolOperationsManager (Opérations de base)
│   ├── ActiveObjectsManager (Suivi des objets actifs)
│   ├── BackgroundManager (Nettoyage en arrière-plan)
│   ├── MemoryManager (Interface haut niveau)
│   └── MemoryOptimizer (Auto-optimisation)
└── Métriques et monitoring
```

## Guide de démarrage rapide

### 1. Utilisation basique

```python
from smartpool.core.smartpool_manager import SmartObjectManager
from smartpool.factories import BytesIOFactory
from smartpool.config import MemoryPreset

# Créer un pool simple
factory = BytesIOFactory()
pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

# Utiliser le pool
with pool.acquire_context(1024) as buffer:
    buffer.write(b"Hello, World!")
    # Le buffer est automatiquement libéré

# Fermer proprement
pool.shutdown()
```

### 2. Configuration avancée

```python
from smartpool.config import MemoryConfig

# Configuration personnalisée
config = MemoryConfig(
    max_size=50,                    # 50 objets max par clé
    ttl_seconds=1800.0,             # 30 minutes de vie
    enable_performance_metrics=True, # Activer les métriques
    max_expected_concurrency=100        # 100 threads concurrents attendus
)

pool = SmartObjectManager(factory, default_config=config)
```

### 3. Monitoring

```python
# Statistiques de base
stats = pool.get_basic_stats()
if (stats['hits'] + stats['misses']) > 0:
    print(f"Hit rate: {stats['hits']/(stats['hits']+stats['misses']):.2%}")

# Statut de santé
health = pool.get_health_status()
print(f"Statut: {health['status']}")

# Rapport complet
report = pool.get_performance_report(detailed=True)
```

## Index des exemples

### Exemples de base

| Fichier | Description | Niveau | Concepts clés |
|---------|-------------|--------|---------------|
| `example_01_basic_bytesio.py` | Utilisation fondamentale du pool avec `BytesIOFactory`. | Débutant | Création de pool, `acquire`/`release`, context managers, statistiques de base. |
| `example_02_pil_images.py` | Gestion d'un pool d'images PIL pour le traitement par lots. | Intermédiaire | Objets lourds, gestion de formats multiples, monitoring de la mémoire. |
| `example_03_database_pool.py` | Pool de sessions de base de données SQLAlchemy. | Intermédiaire | Connexions DB, gestion des transactions, gestion d'erreurs, tests de charge. |
| `example_04_numpy_arrays.py` | Pool de tableaux NumPy pour le calcul scientifique. | Intermédiaire | Calcul scientifique, simulation ML, gestion de grands tableaux, types de données. |

### Exemples avancés

| Fichier | Description | Niveau | Concepts clés |
|---------|-------------|--------|---------------|
| `example_05_advanced_features.py` | Exploration des fonctionnalités avancées du pool. | Avancé | Presets de configuration, auto-optimisation, monitoring temps réel, rapports détaillés. |
| `example_06_custom_factory.py` | Création de factories personnalisées pour des objets complexes. | Avancé | Héritage de `ObjectFactory`, implémentation de `create`/`reset`/`validate`, clés personnalisées. |
| `example_07_*.py` | Intégration web complète avec Flask et FastAPI. | Avancé | APIs REST, gestion du cycle de vie dans une app web, concurrence, client de test de charge. |
| `example_08_advanced_patterns.py` | Implémentation de patrons de conception avancés. | Expert | Hiérarchies de pools, décorateurs, pattern Builder, Adapters, lazy loading, Observability. |

### Outils et intégration complète

| Fichier | Description | Niveau | Concepts clés |
|---------|-------------|--------|---------------|
| `example_09_debugging_troubleshooting.py` | Outils et techniques pour le débogage et le diagnostic. | Avancé | Diagnostic de performance, détection de fuites mémoire, analyse de contention. |
| `example_10_complete_integration.py` | Projet complet d'application de traitement d'images. | Expert | Architecture réelle, combinaison de tous les concepts, API REST complète, gestion de jobs. |
| `example_11_metrics_modes.py` | Compare les modes de métriques `off/sync/async/sampled` sur la même charge. | Intermédiaire | Surcharge d'exécution, comparaison p95/p99, visibilité des événements rejetés. |

## Choix de la factory appropriée

### Factories disponibles

| Factory | Usage recommandé | Objets gérés | Performance |
|---------|------------------|--------------|-------------|
| `BytesIOFactory` | Buffers I/O, données temporaires | `io.BytesIO` | Élevée |
| `PILImageFactory` | Traitement d'images | `PIL.Image` | Bonne |
| `NumpyArrayFactory` | Calculs scientifiques, ML | `numpy.ndarray` | Élevée |
| `SQLAlchemySessionFactory` | Sessions de base de données | Sessions SQLAlchemy | Moyenne |
| `MetadataFactory` | Cache de métadonnées, configurations | Dictionnaires | Élevée |

### Critères de choix

- **Coût de création** : Plus l'objet est coûteux à créer, plus le pool est bénéfique.
- **Taille des objets** : Les objets volumineux bénéficient grandement de la réutilisation pour éviter les allocations mémoire.
- **Pattern d'utilisation** : Une réutilisation fréquente des mêmes types d'objets maximise le taux de "hit".
- **Concurrence** : Un grand nombre de threads accédant aux mêmes ressources bénéficiera de la gestion centralisée du pool.

## Presets de configuration

### Presets disponibles

| Preset | Cas d'usage | Max Size | TTL | Concurrence attendue |
|--------|-------------|----------|-----|----------------------|
| `HIGH_THROUGHPUT` | Applications web à forte charge | 100 | 30min | 50 |
| `LOW_MEMORY` | Environnements contraints en mémoire | 5 | 1min | 5 |
| `IMAGE_PROCESSING` | Traitement d'images | 30 | 10min | 15 |
| `DATABASE_CONNECTIONS` | Pools de connexions DB | 20 | 1h | 25 |
| `DEVELOPMENT` | Développement et débogage | 10 | 30s | 3 |

### Sélection du preset

```python
# Pour une API web
pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

# Pour un service de traitement d'images
pool = SmartObjectManager(factory, preset=MemoryPreset.IMAGE_PROCESSING)
```

## Patterns d'utilisation

### 1. Context Manager (Recommandé)

La méthode la plus sûre et recommandée pour garantir que les objets sont toujours retournés au pool.

```python
# Libération automatique et sécurisée
try:
    with pool.acquire_context(*args) as obj:
        # utiliser obj
        pass # obj est automatiquement libéré, même en cas d'exception
except Exception as e:
    handle_error(e)
```

### 2. Acquisition manuelle (À utiliser avec précaution)

Nécessaire uniquement dans des cas spécifiques où le cycle de vie de l'objet ne correspond pas à un bloc `with`.

```python
# Risque de fuite si la libération n'est pas garantie
obj_id, key, obj = pool.acquire(*args)
try:
    # utiliser obj
finally:
    pool.release(obj_id, key, obj)  # OBLIGATOIRE dans un bloc finally
```

### 3. Décorateurs (Pour la simplicité)

Simplifie l'injection de ressources du pool dans des fonctions. Voir `example_08_advanced_patterns.py`.

```python
@with_buffer_pool(pool, 1024)
def process_data(buffer, data):
    buffer.write(data)
    return buffer.getvalue()

result = process_data(b"test data")
```

## Monitoring et Observabilité

### Métriques essentielles

1.  **Taux de "Hit" (Hit Rate)** : Idéalement > 60%. Un taux faible indique que le pool n'est pas efficace.
2.  **Temps d'acquisition moyen** : Idéalement < 20ms. Un temps élevé peut indiquer une contention ou une création d'objet coûteuse.
3.  **Taux de contention des verrous** : Idéalement < 20%. Un taux élevé indique des goulots d'étranglement dans un environnement concurrent.
4.  **Ratio objets actifs / objets dans le pool** : Un ratio élevé peut signaler des fuites d'objets (objets non retournés).

### Alertes recommandées

Mettez en place des alertes pour :
- Un taux de "hit" inférieur à un seuil (ex: 50%).
- Un statut de santé (`health_status`) qui n'est pas `healthy`.
- Une augmentation constante de la mémoire utilisée par le pool.

## Optimisation des performances

### Auto-optimisation

Pour une gestion "mains libres", activez l'auto-tuning. Le pool ajustera ses propres paramètres en fonction de la charge observée.

```python
# Activer l'auto-tuning (vérification toutes les 5 minutes)
pool.enable_auto_tuning(interval_seconds=300)
```

### Optimisation manuelle

Utilisez les recommandations pour guider les ajustements manuels.

```python
# Obtenir des recommandations
recommendations = pool.manager.get_optimization_recommendations()

for rec in recommendations['recommendations']:
    print(f"Action: {rec['reason']} -> Changer {rec['parameter']} de {rec['current']} à {rec['recommended']}")
```

## Dépannage

### Problèmes fréquents

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| Taux de "hit" faible | Pool trop petit ou TTL trop court. | Augmenter `max_size` ou `ttl_seconds`. |
| Acquisition lente | Validation des objets trop coûteuse. | Réduire `max_validation_attempts` ou optimiser `factory.validate()`. |
| Contention élevée | Nettoyage en arrière-plan trop fréquent. | Augmenter `cleanup_interval`. |
| Mémoire qui augmente | Objets non retournés au pool. | Assurer l'utilisation de `with pool.acquire_context(...)` partout. |
| Objets corrompus | Logique incorrecte dans la factory. | Vérifier les méthodes `validate()` et `reset()` de la factory. |

### Outils de diagnostic

L'exemple `example_09_debugging_troubleshooting.py` fournit une classe `PoolDiagnostic` pour générer des rapports complets.

```python
from examples.example_09_debugging_troubleshooting import PoolDiagnostic

# Diagnostic automatique
diagnostic = PoolDiagnostic(pool)
report = diagnostic.generate_comprehensive_report()

print(f"Sévérité du problème: {report.issue_severity}")
for issue in report.issues_found:
    print(f"- {issue}")
```
