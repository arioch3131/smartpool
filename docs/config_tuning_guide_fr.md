# Guide de Configuration & Tuning de Performance

## Vue d'ensemble

Le système de SmartPool - Pool de Mémoire Intelligent fournit des options de configuration étendues et des capacités de tuning automatique pour optimiser les performances selon différents cas d'usage. Ce guide couvre les presets de configuration, les paramètres de tuning manuel, les métriques de performance et les stratégies d'optimisation.

## Presets de Configuration Mémoire

### Presets Disponibles

Le système inclut six presets pré-configurés optimisés pour des scénarios courants,
plus un mode `CUSTOM` pour les configurations manuelles :

#### HIGH_THROUGHPUT
**Cas d'usage :** Applications à haute charge nécessitant des temps de réponse rapides
**Caractéristiques :**
- Taille max du pool : 100 objets par clé
- TTL : 30 minutes (1800 secondes)
- Concurrence attendue : 50 threads
- Métriques de performance : Activées
- Nettoyage d'arrière-plan : Toutes les 2 minutes

```python
from smartpool.config import MemoryPreset
from smartpool.core.smartpool_manager import SmartObjectManager

pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)
```

#### LOW_MEMORY
**Cas d'usage :** Environnements avec contraintes mémoire strictes
**Caractéristiques :**
- Taille max du pool : 5 objets par clé
- TTL : 1 minute (60 secondes)
- Concurrence attendue : 5 threads
- Métriques de performance : Désactivées pour moins d'overhead
- Nettoyage agressif : Toutes les 15 secondes

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.LOW_MEMORY)
```

#### IMAGE_PROCESSING
**Cas d'usage :** Traitement d'images ou gestion d'objets volumineux
**Caractéristiques :**
- Taille max du pool : 30 objets par clé
- TTL : 10 minutes (600 secondes)
- Coût de création d'objet : Élevé
- Pression mémoire : Élevée
- Validation renforcée : 3 tentatives

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.IMAGE_PROCESSING)
```

#### DATABASE_CONNECTIONS
**Cas d'usage :** Pools de connexions base de données ou ressources réseau
**Caractéristiques :**
- Taille max du pool : 20 connexions par clé
- TTL : 1 heure (3600 secondes)
- Validation stricte : 3 tentatives
- Focus sur la stabilité long-terme
- Logging complet activé

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.DATABASE_CONNECTIONS)
```

#### BATCH_PROCESSING
**Cas d'usage :** Traitement par lots ou tâches long-terme
**Caractéristiques :**
- Taille max du pool : 50 objets par clé
- TTL : 2 heures (7200 secondes)
- Contrôle de nettoyage manuel
- Optimisé pour la stabilité sur de longues périodes

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.BATCH_PROCESSING)
```

#### DEVELOPMENT
**Cas d'usage :** Environnements de développement et test
**Caractéristiques :**
- Taille max du pool : 10 objets par clé
- TTL : 30 secondes
- Logging et debugging complets activés
- Détection de corruption stricte (seuil : 1)
- Suivi de performance complet

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.DEVELOPMENT)
```

## Paramètres de Configuration

### Paramètres Principaux du Pool

#### max_objects_per_key
**Objectif :** Nombre maximum d'objets à pooler par clé
**Impact :** Des valeurs plus élevées améliorent les taux de hit mais consomment plus de mémoire
**Directives de Tuning :**
- Commencer avec l'usage concurrent pic attendu
- Surveiller les taux de hit et ajuster en conséquence
- Considérer les contraintes mémoire

```python
# Configuration personnalisée
config = MemoryConfig(max_objects_per_key=75)  # 75 objets par clé
```

#### ttl_seconds
**Objectif :** Durée de vie des objets poolés
**Impact :** Un TTL plus long améliore la réutilisation mais peut retenir des objets obsolètes
**Directives de Tuning :**
- Correspondre au coût de création d'objet
- Considérer les exigences de fraîcheur des données
- Équilibrer usage mémoire vs. performance

```python
config = MemoryConfig(ttl_seconds=900.0)  # 15 minutes
```

#### cleanup_interval_seconds
**Objectif :** Fréquence des opérations de nettoyage d'arrière-plan
**Impact :** Un nettoyage plus fréquent utilise le CPU mais libère la mémoire plus rapidement
**Directives de Tuning :**
- Intervalles plus courts pour environnements contraints en mémoire
- Intervalles plus longs pour applications stables et long-terme

```python
config = MemoryConfig(cleanup_interval_seconds=60.0)  # Toutes les minutes
```

### Paramètres de Concurrence

#### max_expected_concurrency
**Objectif :** Nombre attendu de threads concurrents accédant au pool
**Impact :** Affecte le dimensionnement interne et les stratégies de contention de verrous
**Directives de Tuning :**
- Définir au nombre réaliste de threads concurrents pic
- La sur-estimation vaut mieux que la sous-estimation
- Surveiller les métriques de contention de verrous

```python
config = MemoryConfig(max_expected_concurrency=25)
```

#### enable_lock_contention_tracking
**Objectif :** Activer la surveillance des goulots d'étranglement de threading
**Impact :** Petit overhead de performance mais fournit des données de debugging précieuses
**Directives de Tuning :**
- Activer pendant les phases de tuning de performance
- Considérer désactiver en production si l'overhead est significatif

```python
config = MemoryConfig(enable_lock_contention_tracking=True)
```

### Validation et Gestion d'Erreurs

#### max_validation_attempts
**Objectif :** Nombre de tentatives de retry pour la validation d'objet
**Impact :** Des valeurs plus élevées améliorent la fiabilité mais augmentent la latence
**Directives de Tuning :**
- Augmenter pour objets non-fiables ou ressources réseau
- Diminuer pour objets simples et fiables
- Surveiller les taux d'échec de validation

```python
config = MemoryConfig(max_validation_attempts=2)
```

#### max_corrupted_objects
**Objectif :** Nombre maximum d'objets corrompus avant action
**Impact :** Des valeurs plus faibles fournissent une détection d'erreur plus rapide
**Directives de Tuning :**
- Définir à 1 pour développement/test
- Utiliser des valeurs plus élevées pour la stabilité production
- Surveiller les taux de corruption

```python
config = MemoryConfig(max_corrupted_objects=5)
```

### Monitoring de Performance

#### enable_performance_metrics
**Objectif :** Activer le suivi de performance détaillé
**Impact :** Fournit des données d'optimisation avec un overhead minimal
**Directives de Tuning :**
- Toujours activer pour les systèmes de production
- Essentiel pour la fonctionnalité d'auto-tuning

```python
config = MemoryConfig(enable_performance_metrics=True)
```

#### max_performance_history_size
**Objectif :** Nombre d'échantillons de performance historiques à conserver
**Impact :** Un historique plus large fournit une meilleure analyse de tendances
**Directives de Tuning :**
- 1000-2000 pour systèmes de production
- 100-500 pour développement/test

```python
config = MemoryConfig(max_performance_history_size=1500)
```

## Système d'Auto-Tuning

### Activation de l'Auto-Tuning

Le système inclut une optimisation automatique de configuration basée sur les métriques de performance observées :

```python
from smartpool.core.smartpool_manager import SmartObjectManager

# L'auto-tuning nécessite que les métriques de performance soient activées
config = MemoryConfig(enable_performance_metrics=True)
pool = SmartObjectManager(factory, default_config=config)

# L'auto-tuning est effectué par le MemoryOptimizer (activé par défaut)
if pool.optimizer:
    tuning_applied = pool.optimizer.perform_auto_tuning()
    print(f"Auto-tuning appliqué : {tuning_applied}")
```

### Logique d'Auto-Tuning

Le système ajuste automatiquement la configuration basé sur les métriques observées :

#### Taux de Hit Faible (< 50%)
**Action :** Augmenter la taille du pool
**Raisonnement :** Plus d'objets poolés améliorent les taux de réutilisation
```python
# Avant auto-tuning
hit_rate = 0.35  # 35% de taux de hit

# Le système augmente automatiquement max_objects_per_key
# La nouvelle configuration aura des pools plus larges
```

#### Temps d'Acquisition Élevé (> 15ms en moyenne)
**Action :** Réduire les tentatives de validation
**Raisonnement :** Moins de tentatives de validation réduit la latence
```python
# Le système détecte une latence élevée
avg_acquisition_time = 22.5  # ms

# Réduit max_validation_attempts pour accélérer les acquisitions
```

#### Contention de Verrous Élevée (> 30%)
**Action :** Augmenter l'intervalle de nettoyage
**Raisonnement :** Un nettoyage moins fréquent réduit la pression sur les verrous
```python
# Le système détecte une contention de verrous
lock_contention_rate = 0.45  # 45%

# Augmente cleanup_interval_seconds pour réduire la compétition de verrous
```

### Auto-Tuning Manuel

Vous pouvez déclencher l'auto-tuning manuellement avec des métriques personnalisées :

```python
# Obtenir les métriques de performance actuelles
current_metrics = {
    'hit_rate': 0.65,
    'avg_acquisition_time_ms': 12.0,
    'lock_contention_rate': 0.15
}

# Appliquer l'auto-tuning
from smartpool.config import MemoryConfigFactory
base_config = pool.default_config
optimized_config = MemoryConfigFactory.auto_tune_config(base_config, current_metrics)

# Appliquer la configuration optimisée
pool.default_config = optimized_config
```

## Métriques de Performance et Monitoring

### Indicateurs Clés de Performance

#### Taux de Hit
**Définition :** Pourcentage de requêtes servies depuis le pool vs. création de nouveaux objets
**Cible :** > 60% pour la plupart des applications, > 80% pour scenarios haute performance
**Calcul :** `reuses / (creates + reuses)`

```python
stats = pool.get_basic_stats()
hit_rate = stats['counters']['reuses'] / (stats['counters']['creates'] + stats['counters']['reuses'])
print(f"Taux de hit actuel : {hit_rate:.2%}")
```

#### Temps d'Acquisition Moyen
**Définition :** Temps moyen pour acquérir un objet depuis le pool
**Cible :** < 20ms pour la plupart des applications, < 5ms pour scenarios haute performance
**Monitoring :** Suivre les tendances et pics

```python
# Obtenir le rapport de performance détaillé
report = pool.manager.get_performance_report(detailed=True)
avg_time = report['performance']['avg_acquisition_time_ms']
print(f"Temps d'acquisition moyen : {avg_time:.2f}ms")
```

#### Taux de Contention de Verrous
**Définition :** Pourcentage d'acquisitions qui subissent une contention de verrous
**Cible :** < 20% pour systèmes sains, < 10% pour performance optimale
**Monitoring :** Des valeurs élevées indiquent des goulots d'étranglement de threading

```python
contention_rate = report['performance']['lock_contention_rate']
print(f"Taux de contention de verrous : {contention_rate:.2%}")
```

#### Efficacité Mémoire
**Définition :** Mémoire totale utilisée par les objets poolés
**Cible :** Usage mémoire stable ou croissance lente
**Monitoring :** Surveiller les fuites mémoire ou croissance excessive

```python
# Obtenir les statistiques d'usage mémoire
stats = pool.get_basic_stats()
total_objects = stats['total_pooled_objects']
print(f"Total objets poolés : {total_objects}")
```

### Rapport de Performance Complet

```python
# Générer un rapport de performance détaillé
report = pool.manager.get_performance_report(detailed=True)

print("=== Rapport de Performance ===")
print(f"Taux de Hit : {report['performance']['hit_rate']:.2%}")
print(f"Temps d'Acquisition Moyen : {report['performance']['avg_acquisition_time_ms']:.2f}ms")
print(f"Contention de Verrous : {report['performance']['lock_contention_rate']:.2%}")
print(f"Total Requêtes : {report['performance']['total_requests']}")

# Statistiques par clé
for key, stats in report['key_statistics'].items():
    print(f"Clé '{key}' : {stats['hit_rate']:.2%} taux hit, {stats['avg_time']:.2f}ms moy")
```

## Stratégies de Tuning par Cas d'Usage

### Applications Web Haute Performance

**Objectifs :** Performance maximale, usage mémoire acceptable
**Stratégie de Configuration :**
```python
config = MemoryConfig(
    max_objects_per_key=100,                    # Pools larges pour haute réutilisation
    ttl_seconds=1800.0,             # TTL 30 minutes
    max_expected_concurrency=50,         # Support haute concurrence
    enable_performance_metrics=True, # Surveiller performance
    enable_acquisition_tracking=True,    # Suivre latence
    cleanup_interval_seconds=120.0          # Fréquence nettoyage modérée
)
```

**Focus Monitoring :**
- Taux de hit doivent dépasser 80%
- Temps d'acquisition sous 10ms
- Contention de verrous sous 15%

### Environnements Contraints en Mémoire

**Objectifs :** Empreinte mémoire minimale, performance acceptable
**Stratégie de Configuration :**
```python
config = MemoryConfig(
    max_objects_per_key=5,                     # Pools petits
    ttl_seconds=60.0,               # TTL court pour nettoyage rapide
    max_expected_concurrency=10,        # Concurrence limitée
    enable_performance_metrics=False, # Réduire overhead
    cleanup_interval_seconds=15.0           # Nettoyage fréquent
)
```

**Focus Monitoring :**
- Stabilité usage mémoire
- Taux de hit acceptables (> 40%)
- Pas de fuites mémoire

### Systèmes de Traitement par Lots

**Objectifs :** Stabilité sur longues périodes, usage efficace des ressources
**Stratégie de Configuration :**
```python
config = MemoryConfig(
    max_objects_per_key=30,                    # Taille pool modérée
    ttl_seconds=7200.0,             # TTL long (2 heures)
    enable_background_cleanup=False, # Contrôle nettoyage manuel
    max_validation_attempts=3,      # Validation robuste
    cleanup_interval_seconds=600.0          # Nettoyage peu fréquent
)
```

**Focus Monitoring :**
- Stabilité mémoire long-terme
- Taux d'échec de validation
- Efficacité nettoyage manuel périodique

### Pools de Connexions Base de Données

**Objectifs :** Réutilisation maximale, fiabilité des connexions
**Stratégie de Configuration :**
```python
config = MemoryConfig(
    max_objects_per_key=25,                    # Taille pool correspondant aux limites de connexion
    ttl_seconds=3600.0,             # TTL long (1 heure)
    max_validation_attempts=3,      # Validation connexion robuste
    max_corrupted_objects=2,   # Détection rapide des mauvaises connexions
    enable_logging=True             # Audit trail complet
)
```

**Focus Monitoring :**
- Taux de succès validation connexion
- Stabilité connexion long-terme
- Événements d'épuisement du pool

## Techniques d'Optimisation de Performance

### Optimisation de Taille de Pool

**Méthodologie :**
1. Commencer avec la concurrence pic attendue comme taille initiale de pool
2. Surveiller les taux de hit sur des périodes de charge représentatives
3. Augmenter graduellement la taille du pool jusqu'à ce que les améliorations de taux de hit plafonnent
4. Équilibrer usage mémoire contre gains de performance

```python
# Optimisation itérative de taille de pool
pool_sizes = [10, 25, 50, 75, 100]
best_config = None
best_performance = 0

for size in pool_sizes:
    config = MemoryConfig(max_objects_per_key=size)
    # Exécuter charge de travail représentative
    # Mesurer performance
    performance_score = measure_performance(config)
    if performance_score > best_performance:
        best_performance = performance_score
        best_config = config
```

### Optimisation TTL

**Méthodologie :**
1. Analyser le coût de création d'objet vs. exigences de fraîcheur des données
2. Commencer avec des valeurs TTL conservatrices
3. Surveiller l'âge des objets au moment de l'acquisition
4. Ajuster le TTL pour équilibrer réutilisation avec fraîcheur

```python
# Analyse TTL
report = pool.manager.get_performance_report(detailed=True)
avg_object_age = report['performance']['avg_object_age_ms']

if avg_object_age < ttl_seconds * 0.1 * 1000:  # Objets utilisés dans les 10% du TTL
    # Peut potentiellement augmenter TTL pour meilleure réutilisation
    new_ttl = ttl_seconds * 1.5
```

### Optimisation de Concurrence

**Méthodologie :**
1. Surveiller les taux de contention de verrous sous charge
2. Ajuster max_expected_concurrency basé sur les nombres de threads réels
3. Considérer partitionnement de pool pour scenarios de concurrence extrême

```python
# Analyse de concurrence
contention_rate = report['performance']['lock_contention_rate']

if contention_rate > 0.25:  # Contention élevée
    # Options :
    # 1. Augmenter max_expected_concurrency
    # 2. Augmenter cleanup_interval_seconds
    # 3. Considérer instances de pool multiples
    pass
```

## Dépannage des Problèmes de Performance

### Taux de Hit Faibles

**Symptômes :** Taux de création d'objets élevés, performance médiocre
**Diagnostic :**
```python
stats = pool.get_basic_stats()
hit_rate = stats['counters']['reuses'] / (stats['counters']['creates'] + stats['counters']['reuses'])
if hit_rate < 0.5:
    print("ALERTE : Taux de hit faible détecté")
```

**Solutions :**
1. Augmenter la taille du pool (`max_objects_per_key`)
2. Étendre le TTL (`ttl_seconds`)
3. Réviser l'implémentation `get_key()` de la factory pour des clés sur-granulaires
4. Vérifier la logique de validation d'objet pour rejets excessifs

### Latence d'Acquisition Élevée

**Symptômes :** Temps de réponse lents, temps d'acquisition moyens élevés
**Diagnostic :**
```python
report = pool.manager.get_performance_report(detailed=True)
avg_time = report['performance']['avg_acquisition_time_ms']
if avg_time > 20.0:
    print("ALERTE : Latence d'acquisition élevée")
```

**Solutions :**
1. Réduire les tentatives de validation (`max_validation_attempts`)
2. Optimiser la méthode `validate()` de la factory
3. Réduire la contention de verrous via ajustements de configuration
4. Profiler les méthodes `create()` et `reset()` de la factory

### Fuites Mémoire

**Symptômes :** Usage mémoire en croissance continue, taille de pool qui augmente
**Diagnostic :**
```python
# Surveiller la croissance du pool dans le temps
stats_history = []
# Collecter stats périodiquement
for _ in range(10):
    time.sleep(60)
    stats_history.append(pool.get_basic_stats()['total_pooled_objects'])

growth_rate = (stats_history[-1] - stats_history[0]) / len(stats_history)
if growth_rate > 0.1:  # Croissance de plus de 0.1 objets par minute
    print("ALERTE : Fuite mémoire possible détectée")
```

**Solutions :**
1. Réviser la méthode `reset()` de la factory pour nettoyage incomplet
2. Vérifier les références circulaires dans les objets gérés
3. Implémenter une méthode `destroy()` appropriée pour nettoyage des ressources
4. Réduire le TTL pour forcer une disposition plus fréquente des objets

### Contention de Verrous

**Symptômes :** Taux de contention de verrous élevés, blocage de threads
**Diagnostic :**
```python
contention_rate = report['performance']['lock_contention_rate']
if contention_rate > 0.3:
    print("ALERTE : Contention de verrous élevée")
```

**Solutions :**
1. Augmenter les intervalles de nettoyage pour réduire l'usage de verrous d'arrière-plan
2. Optimiser les méthodes de factory pour réduire le temps passé dans les verrous
3. Considérer instances de pool multiples pour différents types d'objets
4. Réviser les patterns de threading de l'application

## Configuration Avancée

### Configuration Personnalisée avec Surcharges

```python
# Commencer avec un preset et personnaliser des paramètres spécifiques
base_config = MemoryConfigFactory.create_preset(MemoryPreset.HIGH_THROUGHPUT)

# Créer configuration personnalisée avec surcharges
custom_config = MemoryConfig(
    max_objects_per_key=base_config.max_objects_per_key * 2,        # Doubler la taille du pool
    ttl_seconds=base_config.ttl_seconds / 2,  # Diviser par deux le TTL
    enable_logging=True,                      # Ajouter logging
    # Tous autres paramètres hérités du preset HIGH_THROUGHPUT
    cleanup_interval_seconds=base_config.cleanup_interval_seconds,
    max_expected_concurrency=base_config.max_expected_concurrency,
    # ... autres paramètres selon besoin
)

pool = SmartObjectManager(factory, default_config=custom_config)
```

### Configuration par Clé

```python
# Définir des configurations spécifiques pour différents types d'objets
pool.set_config_for_key("large_images", MemoryConfig(
    max_objects_per_key=10,        # Moins d'objets volumineux
    ttl_seconds=300.0,  # TTL plus court pour objets volumineux
))

pool.set_config_for_key("small_buffers", MemoryConfig(
    max_objects_per_key=100,       # Plus de petits objets
    ttl_seconds=1800.0, # TTL plus long pour petits objets
))
```

### Mises à Jour de Configuration Dynamiques

```python
# Mettre à jour la configuration pendant l'exécution
new_config = MemoryConfig(max_objects_per_key=150)
pool.manager.switch_preset(MemoryPreset.HIGH_THROUGHPUT)

# Ou mettre à jour des paramètres spécifiques
pool.default_config.max_objects_per_key = 150
pool.default_config.ttl_seconds = 2400.0  # 40 minutes
```

Ce guide complet fournit les bases pour optimiser votre configuration de pool de mémoire adaptatif pour une performance maximale à travers divers cas d'usage et environnements.
