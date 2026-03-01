# Guide de Troubleshooting & Diagnostic

## Vue d'ensemble

Ce guide complet fournit des approches systématiques pour diagnostiquer et résoudre les problèmes avec le système de SmartPool - Pool de Mémoire Intelligent. Il couvre les problèmes courants, les outils de diagnostic, les méthodologies de troubleshooting étape par étape, et les mesures préventives pour les environnements de production.

## Problèmes Courants et Symptômes

### Problèmes de Performance

#### Taux de Hit Faible
**Symptômes :**
- Fréquence de création d'objets élevée
- Performance applicative médiocre
- Allocations mémoire accrues

**Commandes de Diagnostic :**
```python
# Vérifier le taux de hit actuel
total_requests = stats['counters'].get('hits', 0) + stats['counters'].get('misses', 0)
hit_rate = stats['counters'].get('hits', 0) / max(1, total_requests)
print(f"Taux de hit : {hit_rate:.2%}")

# Analyse détaillée
health = pool.get_health_status()
if health['hit_rate'] < 0.6:
    print(f"⚠️  Taux de hit faible détecté : {health['hit_rate']:.2%}")
```

**Causes Racines :**
1. **Pool trop petit** : Pas assez d'objets pour satisfaire les requêtes concurrentes
2. **TTL trop court** : Les objets expirent avant réutilisation
3. **Clés sur-granulaires** : Factory `get_key()` crée trop de clés uniques
4. **Échecs de validation** : Les objets échouent la validation et sont détruits

#### Latence d'Acquisition Élevée
**Symptômes :**
- Temps de réponse lents
- Temps d'acquisition moyens élevés
- Blocage de threads

**Commandes de Diagnostic :**
```python
# Vérifier les temps d'acquisition
if pool.performance_metrics:
    snapshot = pool.performance_metrics.create_snapshot()
    print(f"Temps d'acquisition moyen : {snapshot.avg_acquisition_time_ms:.2f}ms")
    print(f"Temps 95e percentile : {snapshot.p95_acquisition_time_ms:.2f}ms")
    
    if snapshot.avg_acquisition_time_ms > 20.0:
        print("⚠️  Latence élevée détectée")
```

**Causes Racines :**
1. **Validation excessive** : Trop de tentatives de validation
2. **Méthodes factory lentes** : `create()`, `reset()`, ou `validate()` sont coûteuses
3. **Contention de verrous** : Plusieurs threads en compétition pour l'accès au pool
4. **Pool plein** : Pas d'objets disponibles, forçant la création

#### Contention de Verrous
**Symptômes :**
- Threads en attente d'accès au pool
- Taux de contention de verrous élevés
- Performance concurrente dégradée

**Commandes de Diagnostic :**
```python
# Vérifier la contention de verrous
if pool.performance_metrics:
    snapshot = pool.performance_metrics.create_snapshot()
    contention_rate = snapshot.lock_contention_rate
    print(f"Taux de contention de verrous : {contention_rate:.2%}")
    
    if contention_rate > 0.3:
        print("⚠️  Contention de verrous élevée détectée")
```

### Problèmes Mémoire

#### Fuites Mémoire
**Symptômes :**
- Usage mémoire en croissance continue
- Taille du pool augmentant dans le temps
- Erreurs de mémoire insuffisante

**Commandes de Diagnostic :**
```python
import psutil
import time

def monitor_memory_growth():
    """Surveiller l'usage mémoire du pool dans le temps."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    initial_objects = pool.get_basic_stats().get('total_pooled_objects', 0)
    
    time.sleep(300)  # Attendre 5 minutes
    
    final_memory = process.memory_info().rss
    final_objects = pool.get_basic_stats().get('total_pooled_objects', 0)
    
    memory_growth = (final_memory - initial_memory) / 1024 / 1024  # MB
    object_growth = final_objects - initial_objects
    
    print(f"Croissance mémoire : {memory_growth:.1f} MB")
    print(f"Croissance objets : {object_growth}")
    
    if memory_growth > 50 and object_growth > 10:
        print("⚠️  Fuite mémoire possible détectée")

monitor_memory_growth()
```

#### Corruption d'Objets
**Symptômes :**
- Échecs de validation
- Avertissements d'objets corrompus
- Erreurs applicatives inattendues

**Commandes de Diagnostic :**
```python
# Vérifier les statistiques de corruption
stats = pool.get_basic_stats()
corrupted_count = stats['counters'].get('corrupted', 0)
validation_failures = stats['counters'].get('validation_failures', 0)

print(f"Objets corrompus : {corrupted_count}")
print(f"Échecs de validation : {validation_failures}")

if corrupted_count > 0:
    print("⚠️  Corruption d'objets détectée")
```

## Outils de Diagnostic Intégrés

### Système PoolDiagnostic

Le système inclut des outils de diagnostic complets pour la détection automatique de problèmes :

```python
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, List
import time

@dataclass
class DiagnosticReport:
    """Rapport de diagnostic complet."""
    timestamp: float
    pool_name: str
    issue_severity: str  # 'low', 'medium', 'high', 'critical'
    issues_found: List[str]
    recommendations: List[str]
    detailed_stats: Dict[str, Any]
    memory_usage: Dict[str, Any]
    thread_info: Dict[str, Any]

class PoolDiagnostic:
    """Outil de diagnostic avancé pour pools de mémoire."""
    
    def __init__(self, pool, pool_name="default"):
        self.pool = pool
        self.pool_name = pool_name
        self.monitoring_data = deque(maxlen=100)
        self._start_time = time.time()
    
    def collect_basic_diagnostics(self) -> Dict[str, Any]:
        """Collecter diagnostics complets du pool."""
        stats = self.pool.get_basic_stats()
        health = self.pool.get_health_status()
        
        diagnostics = {
            'uptime': time.time() - self._start_time,
            'total_requests': stats['counters'].get('hits', 0) + stats['counters'].get('misses', 0),
            'hit_rate': health['hit_rate'],
            'corruption_rate': health['corruption_rate'],
            'active_objects_count': health['active_objects_count'],
            'total_pooled_objects': health['total_pooled_objects'],
            'memory_mb': self._estimate_memory_usage()
        }
        
        # Ajouter métriques performance si disponibles
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            diagnostics.update({
                'avg_acquisition_time_ms': snapshot.avg_acquisition_time_ms,
                'p95_acquisition_time_ms': snapshot.p95_acquisition_time_ms,
                'lock_contention_rate': snapshot.lock_contention_rate,
                'throughput_ops_sec': snapshot.acquisitions_per_second
            })
        
        return diagnostics
    
    def detect_performance_issues(self) -> List[str]:
        """Détecter problèmes liés à la performance."""
        issues = []
        stats = self.pool.get_basic_stats()
        
        # Vérifier taux de hit
        total_requests = stats['counters'].get('hits', 0) + stats['counters'].get('misses', 0)
        if total_requests > 0:
            hit_rate = stats['counters'].get('hits', 0) / total_requests
            if hit_rate < 0.3:
                issues.append(f"Critique : Taux de hit très faible ({hit_rate:.1%})")
            elif hit_rate < 0.6:
                issues.append(f"Avertissement : Taux de hit sous-optimal ({hit_rate:.1%})")
        
        # Vérifier métriques performance
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            
            if snapshot.avg_acquisition_time_ms > 50:
                issues.append(f"Critique : Temps acquisition moyen élevé ({snapshot.avg_acquisition_time_ms:.1f}ms)")
            elif snapshot.avg_acquisition_time_ms > 20:
                issues.append(f"Avertissement : Temps acquisition moyen élevé ({snapshot.avg_acquisition_time_ms:.1f}ms)")
            
            if snapshot.lock_contention_rate > 0.4:
                issues.append(f"Critique : Contention verrous très élevée ({snapshot.lock_contention_rate:.1%})")
            elif snapshot.lock_contention_rate > 0.2:
                issues.append(f"Avertissement : Contention verrous élevée ({snapshot.lock_contention_rate:.1%})")
        
        return issues
    
    def detect_memory_issues(self) -> List[str]:
        """Détecter problèmes liés à la mémoire."""
        issues = []
        
        # Vérifier fuites mémoire
        if len(self.monitoring_data) > 10:
            recent_memory = [d['memory_mb'] for d in list(self.monitoring_data)[-10:]]
            growth_rate = (recent_memory[-1] - recent_memory[0]) / len(recent_memory)
            
            if growth_rate > 5:  # > 5MB par échantillon
                issues.append(f"Critique : Fuite mémoire possible (croissance : {growth_rate:.1f}MB/échantillon)")
            elif growth_rate > 1:
                issues.append(f"Avertissement : Croissance mémoire détectée ({growth_rate:.1f}MB/échantillon)")
        
        # Vérifier taux de corruption
        health = self.pool.get_health_status()
        if health['corruption_rate'] > 0.1:
            issues.append(f"Critique : Taux corruption élevé ({health['corruption_rate']:.1%})")
        elif health['corruption_rate'] > 0.02:
            issues.append(f"Avertissement : Taux corruption élevé ({health['corruption_rate']:.1%})")
        
        return issues
    
    def generate_comprehensive_report(self) -> DiagnosticReport:
        """Générer rapport de diagnostic complet."""
        diagnostics = self.collect_basic_diagnostics()
        performance_issues = self.detect_performance_issues()
        memory_issues = self.detect_memory_issues()
        
        all_issues = performance_issues + memory_issues
        
        # Déterminer sévérité globale
        severity = "low"
        if any("Critique" in issue for issue in all_issues):
            severity = "critical"
        elif any("Avertissement" in issue for issue in all_issues):
            severity = "medium"
        elif all_issues:
            severity = "low"
        
        # Générer recommandations
        recommendations = self._generate_recommendations(all_issues, diagnostics)
        
        return DiagnosticReport(
            timestamp=time.time(),
            pool_name=self.pool_name,
            issue_severity=severity,
            issues_found=all_issues,
            recommendations=recommendations,
            detailed_stats=diagnostics,
            memory_usage=self._analyze_memory_usage(),
            thread_info={'active_threads': self._count_active_threads()}
        )
    
    def _generate_recommendations(self, issues: List[str], diagnostics: Dict[str, Any]) -> List[str]:
        """Générer recommandations actionables basées sur les problèmes."""
        recommendations = []
        
        # Recommandations taux de hit
        if any("taux de hit" in issue.lower() for issue in issues):
            if diagnostics['hit_rate'] < 0.5:
                recommendations.append("Augmenter max_objects_per_key du pool pour améliorer réutilisation objets")
                recommendations.append("Considérer étendre TTL pour garder objets plus longtemps")
            recommendations.append("Réviser get_key() factory pour clés sur-granulaires")
        
        # Recommandations latence
        if any("acquisition" in issue.lower() for issue in issues):
            recommendations.append("Réduire max_validation_attempts pour accélérer acquisition")
            recommendations.append("Profiler méthodes factory (create, reset, validate) pour performance")
            recommendations.append("Considérer augmenter taille pool pour réduire overhead création")
        
        # Recommandations contention verrous
        if any("contention" in issue.lower() for issue in issues):
            recommendations.append("Augmenter cleanup_interval_seconds pour réduire usage verrous arrière-plan")
            recommendations.append("Optimiser méthodes factory pour minimiser temps dans verrous")
            recommendations.append("Considérer instances pool multiples pour différents types objets")
        
        # Recommandations mémoire
        if any("mémoire" in issue.lower() or "fuite" in issue.lower() for issue in issues):
            recommendations.append("Réviser méthode reset() factory pour nettoyage incomplet")
            recommendations.append("Implémenter méthode destroy() appropriée pour nettoyage ressources")
            recommendations.append("Vérifier références circulaires dans objets gérés")
            recommendations.append("Réduire TTL pour forcer disposition objets plus fréquente")
        
        # Recommandations corruption
        if any("corruption" in issue.lower() for issue in issues):
            recommendations.append("Réviser implémentation méthode validate() factory")
            recommendations.append("Vérifier problèmes thread safety dans méthodes factory")
            recommendations.append("Augmenter max_validation_attempts pour échecs transitoires")
        
        return recommendations
    
    def _estimate_memory_usage(self) -> float:
        """Estimer usage mémoire pool en MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def _analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyser usage mémoire détaillé."""
        stats = self.pool.get_basic_stats()
        
        return {
            'process_memory_mb': self._estimate_memory_usage(),
            'total_pooled_objects': stats.get('total_pooled_objects', 0),
            'active_objects_count': stats.get('active_objects_count', 0),
            'estimated_pool_memory_mb': stats.get('total_pooled_objects', 0) * 0.1  # Estimation approximative
        }
    
    def _count_active_threads(self) -> int:
        """Compter threads actifs."""
        import threading
        return threading.active_count()

# Exemple d'usage
diagnostic = PoolDiagnostic(pool, "production_pool")
report = diagnostic.generate_comprehensive_report()

print(f"=== Rapport de Diagnostic ===")
print(f"Pool : {report.pool_name}")
print(f"Sévérité : {report.issue_severity}")
print(f"Problèmes trouvés : {len(report.issues_found)}")

for issue in report.issues_found:
    print(f"  🔍 {issue}")

print(f"\nRecommandations :")
for rec in report.recommendations:
    print(f"  💡 {rec}")
```

### Monitoring Temps Réel

Configurer surveillance continue avec détection automatique de problèmes :

```python
import threading
from collections import deque

class RealTimeMonitor:
    """Monitoring pool temps réel avec alertes."""
    
    def __init__(self, pool, interval=30.0):
        self.pool = pool
        self.interval = interval
        self.running = False
        self.thread = None
        self.alerts = deque(maxlen=50)
        
        # Seuils d'alerte
        self.thresholds = {
            'hit_rate_low': 0.4,
            'response_time_high': 50.0,
            'lock_contention_high': 0.3,
            'memory_growth_high': 10.0  # MB par intervalle
        }
        
        self.previous_memory = 0.0
    
    def start(self):
        """Démarrer monitoring temps réel."""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("Monitoring temps réel démarré")
    
    def stop(self):
        """Arrêter monitoring."""
        self.running = False
        if self.thread:
            self.thread.join()
        print("Monitoring temps réel arrêté")
    
    def _monitor_loop(self):
        """Boucle monitoring principale."""
        while self.running:
            try:
                self._check_alerts()
                time.sleep(self.interval)
            except Exception as e:
                print(f"Erreur monitor : {e}")
                time.sleep(self.interval)
    
    def _check_alerts(self):
        """Vérifier conditions d'alerte."""
        health = self.pool.get_health_status()
        
        # Vérifier taux de hit
        if health['hit_rate'] < self.thresholds['hit_rate_low']:
            self._add_alert('low_hit_rate', 
                          f"Taux hit {health['hit_rate']:.1%} en dessous seuil",
                          'medium')
        
        # Vérifier métriques performance
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            
            if snapshot.avg_acquisition_time_ms > self.thresholds['response_time_high']:
                severity = 'critical' if snapshot.avg_acquisition_time_ms > 100 else 'high'
                self._add_alert('high_response_time',
                              f"Temps réponse {snapshot.avg_acquisition_time_ms:.1f}ms trop élevé",
                              severity)
            
            if snapshot.lock_contention_rate > self.thresholds['lock_contention_high']:
                self._add_alert('high_lock_contention',
                              f"Contention verrous {snapshot.lock_contention_rate:.1%} trop élevée",
                              'high')
        
        # Vérifier croissance mémoire
        current_memory = self._get_memory_usage()
        if self.previous_memory > 0:
            growth = current_memory - self.previous_memory
            if growth > self.thresholds['memory_growth_high']:
                self._add_alert('memory_growth',
                              f"Mémoire a crû de {growth:.1f}MB en {self.interval}s",
                              'high')
        self.previous_memory = current_memory
    
    def _add_alert(self, alert_type: str, message: str, severity: str):
        """Ajouter nouvelle alerte."""
        alert = {
            'timestamp': time.time(),
            'type': alert_type,
            'message': message,
            'severity': severity
        }
        self.alerts.append(alert)
        
        # Imprimer alerte immédiatement
        severity_symbol = {'low': '📘', 'medium': '⚠️', 'high': '🔴', 'critical': '🚨'}
        print(f"{severity_symbol.get(severity, '❓')} [{severity.upper()}] {message}")
    
    def _get_memory_usage(self) -> float:
        """Obtenir usage mémoire actuel en MB."""
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def get_recent_alerts(self, minutes=60) -> List[Dict]:
        """Obtenir alertes récentes dans fenêtre temporelle spécifiée."""
        cutoff = time.time() - (minutes * 60)
        return [alert for alert in self.alerts if alert['timestamp'] > cutoff]

# Usage
monitor = RealTimeMonitor(pool, interval=60.0)  # Vérifier chaque minute
monitor.start()

# Plus tard, obtenir alertes récentes
recent_alerts = monitor.get_recent_alerts(30)  # 30 dernières minutes
print(f"Alertes dans les 30 dernières minutes : {len(recent_alerts)}")
```

## Méthodologies de Troubleshooting Systématiques

### Processus de Diagnostic Étape par Étape

#### 1. Évaluation Initiale
```python
def quick_health_check(pool):
    """Effectuer évaluation rapide de santé."""
    print("=== Vérification Rapide de Santé ===")
    
    # Santé de base
    health = pool.get_health_status()
    print(f"Statut : {health['status']}")
    print(f"Taux Hit : {health['hit_rate']:.2%}")
    print(f"Objets Actifs : {health['active_objects_count']}")
    print(f"Objets Poolés : {health['total_pooled_objects']}")
    
    # Signaux d'alarme immédiats
    red_flags = []
    if health['status'] == 'critical':
        red_flags.append("Pool en état critique")
    if health['hit_rate'] < 0.3:
        red_flags.append(f"Taux de hit très faible : {health['hit_rate']:.2%}")
    if len(health['issues']) > 3:
        red_flags.append(f"Multiples problèmes détectés : {len(health['issues'])}")
    
    if red_flags:
        print("\n🚨 Problèmes Immédiats :")
        for flag in red_flags:
            print(f"  - {flag}")
        return False
    
    print("✅ Pas de problèmes critiques immédiats")
    return True

# Exécuter vérification rapide
if not quick_health_check(pool):
    print("⚠️  Nécessite attention immédiate")
```

#### 2. Analyse de Performance Détaillée
```python
def detailed_performance_analysis(pool):
    """Analyse de performance complète."""
    print("\n=== Analyse de Performance ===")
    
    # Obtenir métriques complètes
    if pool.performance_metrics:
        report = pool.performance_metrics.get_performance_report()
        current = report['current_metrics']
        
        print(f"Total Acquisitions : {current['total_acquisitions']}")
        print(f"Taux Hit : {current['hit_rate']:.2%}")
        print(f"Temps Moyen : {current['avg_acquisition_time_ms']:.2f}ms")
        print(f"Temps P95 : {current['p95_acquisition_time_ms']:.2f}ms")
        print(f"Débit : {current.get('acquisitions_per_second', 0):.1f} ops/sec")
        
        # Problèmes de performance
        if current['hit_rate'] < 0.6:
            print(f"⚠️  Taux hit en dessous optimal (cible : >60%)")
        
        if current['avg_acquisition_time_ms'] > 20:
            print(f"⚠️  Latence moyenne élevée (cible : <20ms)")
        
        if current.get('lock_contention_rate', 0) > 0.2:
            print(f"⚠️  Contention verrous élevée (cible : <20%)")
        
        # Analyse tendances
        trends = report['trends']
        if len(trends['hit_rate_trend']) > 1:
            hit_trend = trends['hit_rate_trend'][-1] - trends['hit_rate_trend'][0]
            direction = "↑" if hit_trend > 0 else "↓"
            print(f"Tendance Taux Hit : {direction} {abs(hit_trend):.2%}")
    else:
        print("⚠️  Métriques performance non activées - analyse limitée")

detailed_performance_analysis(pool)
```

#### 3. Analyse Mémoire et Ressources
```python
def memory_resource_analysis(pool):
    """Analyser usage mémoire et consommation ressources."""
    print("\n=== Analyse Mémoire & Ressources ===")
    
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        print(f"Mémoire Processus : {memory_info.rss / 1024 / 1024:.1f} MB")
        print(f"Mémoire Virtuelle : {memory_info.vms / 1024 / 1024:.1f} MB")
        
        # Mémoire spécifique pool
        stats = pool.get_basic_stats()
        total_pooled_objects = stats.get('total_pooled_objects', 0)
        active_objects_count = stats.get('active_objects_count', 0)
        
        print(f"Objets Poolés : {total_pooled_objects}")
        print(f"Objets Actifs : {active_objects_count}")
        print(f"Total Objets : {total_pooled_objects + active_objects_count}")
        
        # Efficacité mémoire
        if total_pooled_objects > 0:
            efficiency = active_objects_count / (total_pooled_objects + active_objects_count)
            print(f"Utilisation Objets : {efficiency:.2%}")
            
            if efficiency < 0.2:
                print("⚠️  Utilisation objets faible - considérer réduire taille pool")
        
        # Vérifier croissance mémoire
        if hasattr(pool, '_previous_memory'):
            growth = memory_info.rss - pool._previous_memory
            if growth > 10 * 1024 * 1024:  # 10MB
                print(f"⚠️  Croissance mémoire détectée : {growth / 1024 / 1024:.1f} MB")
        pool._previous_memory = memory_info.rss
        
    except ImportError:
        print("❌ psutil non disponible - installer pour analyse mémoire détaillée")

memory_resource_analysis(pool)
```

### Solutions Spécifiques aux Problèmes

#### Résoudre Problèmes de Taux de Hit Faible

**Étape 1 : Identifier Cause Racine**
```python
def diagnose_low_hit_rate(pool):
    """Diagnostiquer raisons du taux de hit faible."""
    stats = pool.get_basic_stats()
    config = pool.default_config
    
    creates = stats['counters'].get('creates', 0)
    reuses = stats['counters'].get('reuses', 0)
    hits = stats['counters'].get('hits', 0)
    misses = stats['counters'].get('misses', 0)
    
    print("=== Diagnostic Taux de Hit ===")
    print(f"Créations : {creates}")
    print(f"Réutilisations : {reuses}")
    print(f"Hits actuels : {hits}")
    print(f"Misses actuels : {misses}")
    print(f"Taille Pool (max) : {config.max_objects_per_key}")
    print(f"TTL : {config.ttl_seconds}s")
    
    # Analyser patterns
    if creates > reuses * 2:
        print("🔍 Ratio création/réutilisation élevé suggère :")
        print("  - Pool trop petit pour la demande")
        print("  - Objets expirant trop rapidement")
        print("  - Clés factory trop granulaires")
    
    if misses > hits:
        print("🔍 Taux miss élevé suggère :")
        print("  - Pool épuisé sous charge")
        print("  - Besoin taille pool plus grande")

diagnose_low_hit_rate(pool)
```

**Étape 2 : Appliquer Solutions**
```python
def fix_low_hit_rate(pool):
    """Appliquer corrections pour taux de hit faible."""
    print("\n=== Application Corrections Taux Hit ===")
    
    # Solution 1 : Augmenter taille pool
    current_size = pool.default_config.max_objects_per_key
    recommended_size = int(current_size * 1.5)
    print(f"1. Augmenter max_objects_per_key de {current_size} à {recommended_size}")
    
    # Solution 2 : Étendre TTL
    current_ttl = pool.default_config.ttl_seconds
    recommended_ttl = int(current_ttl * 1.2)
    print(f"2. Étendre TTL de {current_ttl}s à {recommended_ttl}s")
    
    # Solution 3 : Vérifier génération clés factory
    print("3. Réviser méthode get_key() factory :")
    print("   - Les clés sont-elles trop spécifiques ?")
    print("   - Les objets similaires peuvent-ils partager des clés ?")
    print("   - Considérer stratégies de bucketing")
    
    # Appliquer changements
    pool.default_config.max_objects_per_key = recommended_size
    pool.default_config.ttl_seconds = recommended_ttl
    
    print("✅ Corrections appliquées - surveiller amélioration")

fix_low_hit_rate(pool)
```

#### Résoudre Problèmes de Latence Élevée

**Étape 1 : Identifier Goulots d'Étranglement**
```python
def diagnose_high_latency(pool):
    """Diagnostiquer causes de latence d'acquisition élevée."""
    if not pool.performance_metrics:
        print("❌ Métriques performance requises pour diagnostic latence")
        return
    
    snapshot = pool.performance_metrics.create_snapshot()
    
    print("=== Diagnostic Latence ===")
    print(f"Temps Moyen : {snapshot.avg_acquisition_time_ms:.2f}ms")
    print(f"Temps P95 : {snapshot.p95_acquisition_time_ms:.2f}ms")
    print(f"Temps P99 : {snapshot.p99_acquisition_time_ms:.2f}ms")
    
    # Identifier causes probables
    if snapshot.lock_contention_rate > 0.2:
        print("🔍 Contention verrous élevée contribue à la latence")
    
    config = pool.default_config
    if config.max_validation_attempts > 2:
        print(f"🔍 Tentatives validation élevées ({config.max_validation_attempts}) peuvent causer délais")
    
    # Vérifier si pool est fréquemment plein
    stats = pool.get_basic_stats()
    if stats['counters'].get('creates', 0) > stats['counters'].get('reuses', 0):
        print("🔍 Création objets fréquente suggère épuisement pool")

diagnose_high_latency(pool)
```

**Étape 2 : Appliquer Corrections Latence**
```python
def fix_high_latency(pool):
    """Appliquer corrections pour latence élevée."""
    print("\n=== Application Corrections Latence ===")
    
    # Correction 1 : Réduire tentatives validation
    current_attempts = pool.default_config.max_validation_attempts
    if current_attempts > 2:
        pool.default_config.max_validation_attempts = 2
        print(f"1. Réduit tentatives validation de {current_attempts} à 2")
    
    # Correction 2 : Augmenter intervalle nettoyage pour réduire contention verrous
    current_interval = pool.default_config.cleanup_interval_seconds
    new_interval = current_interval * 1.5
    pool.default_config.cleanup_interval_seconds = new_interval
    print(f"2. Augmenté intervalle nettoyage de {current_interval}s à {new_interval}s")
    
    # Correction 3 : Profiler méthodes factory
    print("3. Profiler méthodes factory :")
    print("   - Chronométrer exécution méthode create()")
    print("   - Chronométrer exécution méthode validate()")
    print("   - Chronométrer exécution méthode reset()")
    print("   - Optimiser méthodes lentes")
    
    print("✅ Corrections latence appliquées")

fix_high_latency(pool)
```

#### Résoudre Problèmes de Fuites Mémoire

**Étape 1 : Détecter Fuites Mémoire**
```python
def detect_memory_leaks(pool):
    """Détecter fuites mémoire potentielles."""
    print("=== Détection Fuites Mémoire ===")
    
    # Surveiller dans le temps
    import gc
    import weakref
    
    # Forcer garbage collection
    gc.collect()
    
    # Vérifier comptages objets croissants
    stats = pool.get_basic_stats()
    print(f"Objets poolés : {stats.get('total_pooled_objects', 0)}")
    print(f"Objets actifs : {stats.get('active_objects_count', 0)}")
    
    # Vérifier active manager pour refs mortes
    if hasattr(pool, 'active_manager'):
        try:
            dead_refs = pool.active_manager.cleanup_dead_weakrefs()
            if dead_refs > 0:
                print(f"🔍 Trouvé {dead_refs} références faibles mortes")
        except:
            pass
    
    # Usage mémoire
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"Mémoire processus : {memory_mb:.1f} MB")
    except ImportError:
        print("Installer psutil pour monitoring mémoire")

detect_memory_leaks(pool)
```

**Étape 2 : Corriger Fuites Mémoire**
```python
def fix_memory_leaks(pool):
    """Appliquer corrections fuites mémoire."""
    print("\n=== Corrections Fuites Mémoire ===")
    
    # Correction 1 : Forcer nettoyage
    print("1. Effectuer nettoyage complet...")
    if hasattr(pool, 'operations_manager'):
        expired_count = pool.operations_manager.cleanup_expired_objects()
        print(f"   Nettoyé {expired_count} objets expirés")
    
    if hasattr(pool, 'active_manager'):
        dead_refs = pool.active_manager.cleanup_dead_weakrefs()
        print(f"   Nettoyé {dead_refs} références faibles mortes")
    
    # Correction 2 : Réduire TTL pour nettoyage plus rapide
    current_ttl = pool.default_config.ttl_seconds
    if current_ttl > 300:  # Si > 5 minutes
        pool.default_config.ttl_seconds = 300
        print(f"2. Réduit TTL de {current_ttl}s à 300s pour nettoyage plus rapide")
    
    # Correction 3 : Réviser méthode reset factory
    print("3. Réviser implémentation factory :")
    print("   - S'assurer que reset() vide toutes structures données")
    print("   - Implémenter destroy() pour nettoyage ressources")
    print("   - Vérifier références circulaires")
    
    # Correction 4 : Forcer garbage collection
    import gc
    collected = gc.collect()
    print(f"4. Garbage collection a libéré {collected} objets")
    
    print("✅ Corrections fuites mémoire appliquées")

fix_memory_leaks(pool)
```

#### Résoudre Problèmes de Corruption

**Étape 1 : Analyser Patterns Corruption**
```python
def analyze_corruption(pool):
    """Analyser patterns corruption objets."""
    print("=== Analyse Corruption ===")
    
    stats = pool.get_basic_stats()
    corrupted = stats['counters'].get('corrupted', 0)
    validation_failures = stats['counters'].get('validation_failures', 0)
    
    print(f"Objets corrompus : {corrupted}")
    print(f"Échecs validation : {validation_failures}")
    
    if corrupted > 0:
        print("🔍 Corruption détectée - causes possibles :")
        print("   - Problèmes thread safety dans méthodes factory")
        print("   - Implémentation reset() incomplète")
        print("   - Modification externe objets poolés")
        print("   - Méthode validate() factory trop stricte")
    
    # Vérifier seuil corruption
    threshold = pool.default_config.max_corrupted_objects
    print(f"Seuil corruption : {threshold}")
    
    if corrupted >= threshold:
        print("⚠️  Seuil corruption dépassé")

analyze_corruption(pool)
```

**Étape 2 : Corriger Problèmes Corruption**
```python
def fix_corruption(pool):
    """Appliquer corrections problèmes corruption."""
    print("\n=== Corrections Corruption ===")
    
    # Correction 1 : Réviser thread safety factory
    print("1. Révision Thread Safety Factory :")
    print("   - S'assurer méthodes factory sont thread-safe")
    print("   - Éviter état mutable partagé dans factory")
    print("   - Utiliser verrous si nécessaire dans méthodes factory")
    
    # Correction 2 : Améliorer validation
    print("2. Améliorations Validation :")
    print("   - Réviser logique méthode validate()")
    print("   - Rendre validation moins stricte si approprié")
    print("   - Ajouter meilleure gestion erreurs dans validate()")
    
    # Correction 3 : Améliorer méthode reset
    print("3. Amélioration Méthode Reset :")
    print("   - S'assurer reset() vide complètement état objet")
    print("   - Tester reset avec différents états objets")
    print("   - Ajouter validation après reset")
    
    # Correction 4 : Augmenter tentatives validation pour problèmes transitoires
    current_attempts = pool.default_config.max_validation_attempts
    if current_attempts == 1:
        pool.default_config.max_validation_attempts = 2
        print(f"4. Augmenté tentatives validation de 1 à 2")
    
    print("✅ Corrections corruption appliquées")

fix_corruption(pool)
```

## Mesures Préventives

### Configuration Monitoring Proactif

```python
def setup_proactive_monitoring(pool):
    """Configurer monitoring proactif complet."""
    print("=== Configuration Monitoring Proactif ===")
    
    # 1. Activer métriques complètes
    pool.default_config.enable_performance_metrics = True
    pool.default_config.enable_acquisition_tracking = True
    pool.default_config.enable_lock_contention_tracking = True
    
    # 2. Configurer monitoring diagnostic
    diagnostic = PoolDiagnostic(pool)
    
    # 3. Configurer monitoring temps réel
    monitor = RealTimeMonitor(pool, interval=300)  # 5 minutes
    monitor.start()
    
    # 4. Configurer health checks périodiques
    def periodic_health_check():
        while True:
            time.sleep(1800)  # Toutes les 30 minutes
            health = pool.get_health_status()
            if health['status'] != 'healthy':
                print(f"⚠️  Health check échoué : {health['status']}")
                report = diagnostic.generate_comprehensive_report()
                for issue in report.issues_found:
                    print(f"   - {issue}")
    
    health_thread = threading.Thread(target=periodic_health_check, daemon=True)
    health_thread.start()
    
    print("✅ Monitoring proactif configuré")
    return diagnostic, monitor

diagnostic, monitor = setup_proactive_monitoring(pool)
```

### Bonnes Pratiques Configuration

```python
def apply_best_practice_config(pool, environment='production'):
    """Appliquer configuration bonnes pratiques pour environnement."""
    print(f"=== Application Bonnes Pratiques pour {environment} ===")
    
    if environment == 'production':
        # Paramètres production
        pool.default_config.enable_performance_metrics = True
        pool.default_config.enable_logging = False  # Désactiver logs debug
        pool.default_config.max_validation_attempts = 2
        pool.default_config.cleanup_interval_seconds = 300.0  # 5 minutes
        pool.default_config.max_corrupted_objects = 5
        
    elif environment == 'development':
        # Paramètres développement
        pool.default_config.enable_performance_metrics = True
        pool.default_config.enable_logging = True
        pool.default_config.max_validation_attempts = 3
        pool.default_config.cleanup_interval_seconds = 60.0  # 1 minute
        pool.default_config.max_corrupted_objects = 1  # Strict
        
    elif environment == 'testing':
        # Paramètres test
        pool.default_config.enable_performance_metrics = False  # Tests plus rapides
        pool.default_config.enable_logging = True
        pool.default_config.max_validation_attempts = 1
        pool.default_config.cleanup_interval_seconds = 10.0
        pool.default_config.max_corrupted_objects = 0  # Très strict
    
    print(f"✅ Configuration {environment} appliquée")

apply_best_practice_config(pool, 'production')
```

## Études de Cas

### Étude de Cas 1 : Plateforme E-commerce

**Problème :** Latence élevée dans traitement images produits pendant trafic pic
**Symptômes :**
- Temps d'acquisition moyen : 150ms
- Contention verrous élevée : 45%
- Taux de hit faible : 35%

**Processus de Diagnostic :**
```python
# Évaluation initiale a révélé épuisement pool
diagnostic = PoolDiagnostic(pool, "image_processor")
report = diagnostic.generate_comprehensive_report()

# Trouvé : Taille pool (20) trop petite pour charge pic (100+ requêtes concurrentes)
# Trouvé : Méthode create() factory image prenant 100ms en moyenne
# Trouvé : TTL trop court (60s) pour objets images coûteux
```

**Solution Appliquée :**
```python
# 1. Augmenté taille pool
pool.default_config.max_objects_per_key = 100

# 2. Étendu TTL pour objets coûteux
pool.default_config.ttl_seconds = 1800  # 30 minutes

# 3. Optimisé méthode create factory
# - Ajouté bucketing taille image dans get_key()
# - Amélioré algorithme création image

# 4. Réduit contention verrous
pool.default_config.cleanup_interval_seconds = 600  # 10 minutes
```

**Résultats :**
- Temps acquisition moyen : 25ms (amélioration 83%)
- Contention verrous : 12% (amélioration 73%)
- Taux de hit : 78% (amélioration 123%)

### Étude de Cas 2 : Pool Connexions Base de Données

**Problème :** Fuite mémoire dans pool connexions microservice
**Symptômes :**
- Usage mémoire croissant 50MB/heure
- Taille pool augmentant continuellement
- Échecs connexion occasionnels

**Processus de Diagnostic :**
```python
# Analyse mémoire a montré connexions pas correctement nettoyées
def diagnose_connection_leak():
    # Trouvé : reset() factory ne ferme pas transactions base de données
    # Trouvé : Références faibles pas nettoyées
    # Trouvé : Objets connexion tenant références circulaires
```

**Solution Appliquée :**
```python
# 1. Corrigé méthode reset factory
def reset(self, connection):
    try:
        if connection.in_transaction():
            connection.rollback()
        connection.reset()  # Vider état session
        return True
    except:
        return False

# 2. Ajouté méthode destroy appropriée
def destroy(self, connection):
    try:
        connection.close()
    except:
        pass

# 3. Réduit TTL et augmenté fréquence nettoyage
pool.default_config.ttl_seconds = 300  # 5 minutes
pool.default_config.cleanup_interval_seconds = 60  # 1 minute
```

**Résultats :**
- Fuite mémoire éliminée
- Taille pool stable
- Fiabilité connexion améliorée

Ce guide complet de troubleshooting fournit des approches systématiques pour identifier, diagnostiquer et résoudre les problèmes dans les environnements de production. Le monitoring régulier et la maintenance proactive préviennent la plupart des problèmes avant qu'ils n'impactent les utilisateurs.