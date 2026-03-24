# Guide de Monitoring & Métriques

## Vue d'ensemble

Le système de Pool de Mémoire Adaptatif fournit des capacités complètes de monitoring et métriques pour les environnements de production. Ce guide couvre la collecte de métriques de performance, le monitoring de santé, les systèmes d'alerte, l'intégration dashboard et les approches de monitoring temps réel.

## Système de Collecte de Métriques

### Activation des Métriques de Performance

Les métriques de performance sont la fondation du monitoring. Activez-les dans votre configuration de pool :

```python
from smartpool.config import MemoryConfig
from smartpool.core.smartpool_manager import SmartObjectManager

# Activer la collecte complète de métriques
config = MemoryConfig(
    enable_performance_metrics=True,     # Activer collecte de métriques
    enable_acquisition_tracking=True,        # Suivre timing détaillé
    enable_lock_contention_tracking=True,         # Surveiller problèmes threading
    max_performance_history_size=2000       # Conserver 2000 échantillons historiques
)

pool = SmartObjectManager(factory, default_config=config)
```

### Types de Métriques Principales

#### Snapshot de Performance
Données de performance temps réel capturées à un moment spécifique :

```python
# Obtenir le snapshot de performance actuel
snapshot = pool.performance_metrics.create_snapshot()

print(f"Total acquisitions : {snapshot.total_acquisitions}")
print(f"Taux de hit : {snapshot.hit_rate:.2%}")
print(f"Temps d'acquisition moyen : {snapshot.avg_acquisition_time_ms:.2f}ms")
print(f"Temps 95e percentile : {snapshot.p95_acquisition_time_ms:.2f}ms")
print(f"Débit : {snapshot.acquisitions_per_second:.1f} ops/sec")
print(f"Taux contention verrous : {snapshot.lock_contention_rate:.2%}")
```

#### Indicateurs Clés de Performance

**Taux de Hit**
- Définition : Pourcentage de requêtes servies depuis le pool vs création nouveaux objets
- Formule : `reuses / (creates + reuses)`
- Cible : > 60% (général), > 80% (applications haute performance)

**Temps d'Acquisition**
- Définition : Temps pour acquérir un objet depuis le pool
- Métriques : Moyenne, P95, P99, Min/Max
- Cible : < 20ms moyenne, < 50ms P95

**Débit**
- Définition : Opérations par seconde
- Calcul : Acquisitions dans fenêtre temporelle récente
- Usage : Planification capacité et analyse charge

**Taux de Contention de Verrous**
- Définition : Pourcentage d'acquisitions subissant contention de verrous
- Cible : < 20% pour systèmes sains
- Seuil critique : > 40%

### Suivi Historique

Le système maintient des données de performance historiques pour analyse de tendances :

```python
# Obtenir rapport de performance complet avec tendances
report = pool.performance_metrics.get_performance_report(last_n_snapshots=20)

print("=== Métriques Actuelles ===")
current = report['current_metrics']
print(f"Taux de hit : {current['hit_rate']:.2%}")
print(f"Temps moyen : {current['avg_acquisition_time_ms']:.2f}ms")

print("\n=== Tendances (20 derniers snapshots) ===")
trends = report['trends']
hit_rates = trends['hit_rate_trend']
if len(hit_rates) > 1:
    trend_direction = "↑" if hit_rates[-1] > hit_rates[0] else "↓"
    print(f"Tendance taux hit : {hit_rates[0]:.2%} → {hit_rates[-1]:.2%} {trend_direction}")

print("\n=== Alertes ===")
for alert in report['alerts']:
    print(f"⚠️  {alert['metric']}: {alert['message']} (sévérité: {alert['severity']})")

print("\n=== Recommandations ===")
for rec in report['recommendations']:
    print(f"💡 {rec['area']}: {rec['suggestion']}")
```

## Monitoring de Santé

### Évaluation de Statut de Santé

Le système évalue automatiquement la santé du pool basé sur plusieurs facteurs :

```python
# Obtenir statut de santé complet
health = pool.get_health_status()

print(f"Statut Global : {health['status'].upper()}")  # healthy/warning/critical
print(f"Taux de Hit : {health['hit_rate']:.2%}")
print(f"Taux de Corruption : {health['corruption_rate']:.2%}")
print(f"Total Requêtes : {health['total_requests']}")
print(f"Objets Poolés : {health['total_pooled_objects']}")
print(f"Objets Actifs : {health['active_objects_count']}")

if health['issues']:
    print("\n🚨 Problèmes Détectés :")
    for issue in health['issues']:
        print(f"  - {issue}")
```

### Niveaux de Statut de Santé

#### Sain (Healthy)
- Taux de hit > 30%
- Taux de corruption < 10%
- Pas d'échecs de validation critiques
- Indicateurs d'opération normale

#### Avertissement (Warning)
- Un problème mineur détecté
- Taux de hit 20-30%
- Légère augmentation taux de corruption
- Nécessite surveillance

#### Critique (Critical)
- Multiples problèmes détectés
- Taux de hit < 20%
- Taux de corruption élevé (> 10%)
- Échecs de validation fréquents
- Attention immédiate requise

### Seuils de Santé Personnalisés

Configurer des seuils d'évaluation de santé personnalisés :

```python
# Monitoring de santé personnalisé avec seuils spécifiques
class CustomHealthMonitor:
    def __init__(self, pool, thresholds=None):
        self.pool = pool
        self.thresholds = thresholds or {
            'min_hit_rate': 0.4,           # 40% taux hit minimum
            'max_corruption_rate': 0.05,   # 5% corruption maximum
            'max_avg_time_ms': 25.0,       # 25ms temps moyen maximum
            'max_lock_contention': 0.3     # 30% contention verrous maximum
        }
    
    def assess_health(self):
        stats = self.pool.get_basic_stats()
        health = self.pool.get_health_status()
        issues = []
        
        # Vérifier taux de hit
        if health['hit_rate'] < self.thresholds['min_hit_rate']:
            issues.append(f"Taux hit {health['hit_rate']:.1%} en dessous de {self.thresholds['min_hit_rate']:.1%}")
        
        # Vérifier temps de réponse si métriques disponibles
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            if snapshot.avg_acquisition_time_ms > self.thresholds['max_avg_time_ms']:
                issues.append(f"Temps de réponse moyen {snapshot.avg_acquisition_time_ms:.1f}ms trop élevé")
        
        # Déterminer statut
        if not issues:
            status = "healthy"
        elif len(issues) == 1:
            status = "warning"
        else:
            status = "critical"
        
        return {
            'status': status,
            'issues': issues,
            'timestamp': time.time()
        }

# Usage
monitor = CustomHealthMonitor(pool)
health = monitor.assess_health()
```

## Intégration Dashboard

### Résumé Dashboard

Obtenir métriques formatées pour affichage dashboard :

```python
# Obtenir métriques prêtes pour dashboard
dashboard = pool.manager.get_dashboard_summary()

print("=== Dashboard Pool ===")
print(f"Statut : {dashboard['status']}")
print(f"Preset : {dashboard['preset']}")

metrics = dashboard['metrics']
print(f"Taux Hit : {metrics['hit_rate']:.1%}")
print(f"Objets Poolés : {metrics['total_pooled_objects']}")
print(f"Objets Actifs : {metrics['active_objects_count']}")
print(f"Total Créations : {metrics['total_creates']}")
print(f"Total Réutilisations : {metrics['total_reuses']}")

# Métriques avancées si disponibles
if 'advanced_metrics' in dashboard:
    adv = dashboard['advanced_metrics']
    print(f"Temps Réponse Moy : {adv['avg_response_time_ms']:.1f}ms")
    print(f"Temps Réponse P95 : {adv['p95_response_time_ms']:.1f}ms")
    print(f"Débit : {adv['throughput_ops_sec']:.1f} ops/sec")
    print(f"Contention Verrous : {adv['lock_contention_rate']:.1%}")

# Comptage alertes
print(f"Alertes Actives : {dashboard.get('alerts', 0)}")
print(f"Avertissements : {dashboard.get('warnings', 0)}")
```

### Intégration Dashboard Web

Créer des endpoints API REST pour monitoring web :

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/pools/status")
async def get_pool_status():
    """Obtenir statut de santé global du pool."""
    health = pool.get_health_status()
    
    if health['status'] == 'critical':
        return JSONResponse(content=health, status_code=503)
    elif health['status'] == 'warning':
        return JSONResponse(content=health, status_code=200)
    else:
        return health

@app.get("/api/pools/dashboard")
async def get_dashboard():
    """Obtenir métriques dashboard."""
    return pool.manager.get_dashboard_summary()

@app.get("/api/pools/metrics")
async def get_detailed_metrics():
    """Obtenir métriques de performance détaillées."""
    if not pool.performance_metrics:
        return {"error": "Métriques de performance non activées"}
    
    report = pool.performance_metrics.get_performance_report()
    return {
        "current": report['current_metrics'],
        "trends": report['trends'],
        "alerts": report['alerts']
    }

@app.get("/api/pools/stats")
async def get_raw_stats():
    """Obtenir statistiques brutes."""
    return pool.get_basic_stats()
```

## Système d'Alertes

### Génération d'Alertes Automatique

Le système génère des alertes basées sur des seuils de performance :

```python
# Obtenir alertes actuelles depuis métriques de performance
if pool.performance_metrics:
    report = pool.performance_metrics.get_performance_report()
    
    for alert in report['alerts']:
        severity = alert['severity']  # low, medium, high, critical
        metric = alert['metric']      # hit_rate, response_time, etc.
        message = alert['message']    # Description lisible par humain
        
        print(f"[{severity.upper()}] {metric}: {message}")
        
        # Prendre action basée sur sévérité
        if severity == 'critical':
            # Envoyer notification immédiate
            send_critical_alert(alert)
        elif severity == 'high':
            # Logger et surveiller
            logger.warning(f"Alerte sévérité élevée : {message}")
```

### Types d'Alertes et Seuils

#### Alertes Performance
- **Taux Hit Faible** : < 50% taux hit (medium), < 30% (high)
- **Temps Réponse Élevé** : > 50ms moyenne (medium), > 100ms (high)
- **Contention Verrous Élevée** : > 30% (medium), > 50% (critical)
- **Débit Faible** : Dégradation significative du débit

#### Alertes Santé
- **Taux Corruption Élevé** : > 5% taux de corruption
- **Échecs Validation** : Échecs de validation fréquents
- **Fuites Mémoire** : Taille pool en croissance continue
- **Contention Threads** : Attente excessive de verrous

### Implémentation d'Alertes Personnalisées

```python
import time
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class Alert:
    pool_name: str
    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    value: float
    threshold: float
    timestamp: float

class AlertManager:
    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {
            'hit_rate_low': 0.4,
            'response_time_high': 50.0,
            'lock_contention_high': 0.3,
            'corruption_rate_high': 0.05
        }
        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
    
    def check_alerts(self, pool_name: str, pool) -> List[Alert]:
        """Vérifier conditions d'alerte et retourner nouvelles alertes."""
        alerts = []
        
        # Obtenir métriques actuelles
        health = pool.get_health_status()
        
        # Vérifier taux de hit
        if health['hit_rate'] < self.thresholds['hit_rate_low']:
            severity = 'high' if health['hit_rate'] < 0.3 else 'medium'
            alerts.append(Alert(
                pool_name=pool_name,
                alert_type='low_hit_rate',
                severity=severity,
                message=f"Taux hit {health['hit_rate']:.1%} en dessous du seuil",
                value=health['hit_rate'],
                threshold=self.thresholds['hit_rate_low'],
                timestamp=time.time()
            ))
        
        # Vérifier temps de réponse si métriques disponibles
        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()
            
            if snapshot.avg_acquisition_time_ms > self.thresholds['response_time_high']:
                severity = 'critical' if snapshot.avg_acquisition_time_ms > 100 else 'high'
                alerts.append(Alert(
                    pool_name=pool_name,
                    alert_type='high_response_time',
                    severity=severity,
                    message=f"Temps réponse {snapshot.avg_acquisition_time_ms:.1f}ms trop élevé",
                    value=snapshot.avg_acquisition_time_ms,
                    threshold=self.thresholds['response_time_high'],
                    timestamp=time.time()
                ))
        
        return alerts
    
    def process_alerts(self, alerts: List[Alert]):
        """Traiter nouvelles alertes et prendre actions appropriées."""
        for alert in alerts:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Prendre action basée sur sévérité
            if alert.severity == 'critical':
                self.send_critical_notification(alert)
            elif alert.severity == 'high':
                self.send_high_priority_notification(alert)
            else:
                self.log_alert(alert)
    
    def send_critical_notification(self, alert: Alert):
        """Envoyer notification immédiate pour alertes critiques."""
        # Implémenter votre système de notification
        print(f"🚨 ALERTE CRITIQUE : {alert.message}")
        # Pourrait envoyer email, message Slack, alerte PagerDuty, etc.
    
    def send_high_priority_notification(self, alert: Alert):
        """Envoyer notification haute priorité."""
        print(f"⚠️  HAUTE PRIORITÉ : {alert.message}")
        # Pourrait envoyer au système monitoring, chat équipe, etc.
    
    def log_alert(self, alert: Alert):
        """Logger alertes priorité plus faible."""
        print(f"📝 ALERTE : {alert.message}")

# Usage
alert_manager = AlertManager()

def monitor_pool():
    """Fonction monitoring périodique."""
    alerts = alert_manager.check_alerts("main_pool", pool)
    if alerts:
        alert_manager.process_alerts(alerts)

# Exécuter monitoring périodiquement
import threading
def monitoring_loop():
    while True:
        monitor_pool()
        time.sleep(60)  # Vérifier chaque minute

monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
monitor_thread.start()
```

## Monitoring Temps Réel

### Configuration Monitoring Continu

```python
import time
import threading
from collections import deque

class RealTimeMonitor:
    def __init__(self, pool, update_interval=5.0):
        self.pool = pool
        self.update_interval = update_interval
        self.running = False
        self.monitor_thread = None
        self.metrics_history = deque(maxlen=100)  # Conserver 100 derniers échantillons
        self.callbacks = []
    
    def add_callback(self, callback):
        """Ajouter fonction callback pour recevoir mises à jour temps réel."""
        self.callbacks.append(callback)
    
    def start(self):
        """Démarrer monitoring temps réel."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("Monitoring temps réel démarré")
    
    def stop(self):
        """Arrêter monitoring temps réel."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("Monitoring temps réel arrêté")
    
    def _monitor_loop(self):
        """Boucle monitoring principale."""
        while self.running:
            try:
                # Collecter métriques actuelles
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Appeler tous callbacks enregistrés
                for callback in self.callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        print(f"Erreur callback : {e}")
                
                time.sleep(self.update_interval)
            
            except Exception as e:
                print(f"Erreur boucle monitor : {e}")
                time.sleep(self.update_interval)
    
    def _collect_metrics(self):
        """Collecter snapshot métriques actuelles."""
        health = self.pool.get_health_status()
        stats = self.pool.get_basic_stats()
        
        metrics = {
            'timestamp': time.time(),
            'status': health['status'],
            'hit_rate': health['hit_rate'],
            'corruption_rate': health['corruption_rate'],
            'total_pooled_objects': health['total_pooled_objects'],
            'active_objects_count': health['active_objects_count'],
            'total_requests': health['total_requests']
        }
        
        # Ajouter métriques performance si disponibles
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            metrics.update({
                'avg_acquisition_time_ms': snapshot.avg_acquisition_time_ms,
                'p95_acquisition_time_ms': snapshot.p95_acquisition_time_ms,
                'throughput_ops_sec': snapshot.acquisitions_per_second,
                'lock_contention_rate': snapshot.lock_contention_rate
            })
        
        return metrics
    
    def get_recent_metrics(self, n=10):
        """Obtenir historique métriques récentes."""
        return list(self.metrics_history)[-n:]

# Exemple usage
def print_metrics_callback(metrics):
    """Callback simple pour imprimer métriques."""
    print(f"[{time.strftime('%H:%M:%S')}] "
          f"Taux Hit : {metrics['hit_rate']:.1%} | "
          f"Actifs : {metrics['active_objects_count']} | "
          f"Statut : {metrics['status']}")

def alert_callback(metrics):
    """Callback pour vérifier conditions d'alerte."""
    if metrics['hit_rate'] < 0.5:
        print(f"⚠️  Alerte taux hit faible : {metrics['hit_rate']:.1%}")
    
    if metrics.get('avg_acquisition_time_ms', 0) > 50:
        print(f"⚠️  Alerte latence élevée : {metrics['avg_acquisition_time_ms']:.1f}ms")

# Configuration monitoring temps réel
monitor = RealTimeMonitor(pool, update_interval=10.0)  # Toutes les 10 secondes
monitor.add_callback(print_metrics_callback)
monitor.add_callback(alert_callback)

# Démarrer monitoring
monitor.start()

# Plus tard, arrêter monitoring
# monitor.stop()
```

## Statistiques Clés et Métriques par Clé

### Statistiques Niveau Pool

```python
# Obtenir statistiques complètes du pool
stats = pool.get_basic_stats()

print("=== Statistiques Pool ===")
print(f"Total créations : {stats['counters'].get('creates', 0)}")
print(f"Total réutilisations : {stats['counters'].get('reuses', 0)}")
print(f"Hits actuels : {stats['counters'].get('hits', 0)}")
print(f"Misses actuels : {stats['counters'].get('misses', 0)}")
print(f"Objets poolés : {stats.get('total_pooled_objects', 0)}")
print(f"Objets actifs : {stats.get('active_objects_count', 0)}")
print(f"Objets corrompus : {stats['counters'].get('corrupted', 0)}")
print(f"Échecs validation : {stats['counters'].get('validation_failures', 0)}")
```

### Analyse Performance par Clé

```python
# Obtenir statistiques détaillées par clé
if pool.performance_metrics:
    report = pool.performance_metrics.get_performance_report()
    
    print("\n=== Top Clés par Usage ===")
    for key, usage_count in report['current_metrics']['top_keys_by_usage']:
        print(f"{key}: {usage_count} acquisitions")
    
    print("\n=== Clés les Plus Lentes ===")
    for key, avg_time in report['current_metrics']['slowest_keys']:
        print(f"{key}: {avg_time:.2f}ms moyenne")

# Obtenir statistiques spécifiques par clé si disponibles
def get_key_statistics():
    """Obtenir statistiques performance par clé."""
    if hasattr(pool.performance_metrics, 'get_key_statistics'):
        key_stats = pool.performance_metrics.get_key_statistics()
        
        for key, stats in key_stats.items():
            print(f"\nClé : {key}")
            print(f"  Comptage usage : {stats['usage_count']}")
            print(f"  Taux hit : {stats['hit_rate']:.2%}")
            print(f"  Temps moyen : {stats['avg_time_ms']:.2f}ms")
            print(f"  Temps total : {stats['total_time_ms']:.1f}ms")

get_key_statistics()
```

## Bonnes Pratiques Monitoring Production

### Checklist Monitoring

#### Métriques Essentielles à Surveiller
- **Taux Hit** : Indicateur d'efficacité principal
- **Temps Réponse** : Percentiles P50, P95, P99
- **Débit** : Opérations par seconde
- **Taux Erreurs** : Échecs validation, taux corruption
- **Usage Ressources** : Objets actifs, consommation mémoire

#### Seuils d'Alerte Recommandés
- **Taux Hit** : Avertissement < 60%, Critique < 40%
- **Temps Réponse** : Avertissement > 20ms moy, Critique > 50ms moy
- **Contention Verrous** : Avertissement > 20%, Critique > 40%
- **Taux Corruption** : Avertissement > 1%, Critique > 5%

#### Fréquence Monitoring
- **Dashboard Temps Réel** : Mises à jour 5-10 secondes
- **Vérifications Alertes** : Intervalles 1-2 minutes
- **Rapports Historiques** : Agrégations horaires/quotidiennes
- **Health Checks** : Intervalles 30-60 secondes

### Intégration avec Systèmes de Monitoring

#### Intégration Prometheus/Grafana

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

class PrometheusMetrics:
    def __init__(self):
        # Compteurs
        self.acquisitions_total = Counter('pool_acquisitions_total', 'Total acquisitions', ['pool', 'result'])
        self.corrupted_objects_total = Counter('pool_corrupted_objects_total', 'Objets corrompus', ['pool'])
        
        # Histogrammes
        self.acquisition_duration = Histogram('pool_acquisition_duration_seconds', 'Temps acquisition', ['pool'])
        
        # Jauges
        self.hit_rate = Gauge('pool_hit_rate', 'Taux hit actuel', ['pool'])
        self.active_objects_count = Gauge('pool_active_objects_count', 'Objets actifs', ['pool'])
        self.total_pooled_objects = Gauge('pool_total_pooled_objects', 'Objets poolés', ['pool'])
    
    def update_from_pool(self, pool_name, pool):
        """Mettre à jour métriques Prometheus depuis état pool."""
        health = pool.get_health_status()
        stats = pool.get_basic_stats()
        
        # Mettre à jour jauges
        self.hit_rate.labels(pool=pool_name).set(health['hit_rate'])
        self.active_objects_count.labels(pool=pool_name).set(health['active_objects_count'])
        self.total_pooled_objects.labels(pool=pool_name).set(health['total_pooled_objects'])

# Démarrer serveur métriques Prometheus
prometheus_metrics = PrometheusMetrics()
start_http_server(8000)  # Métriques disponibles à http://localhost:8000/metrics

# Mettre à jour métriques périodiquement
def update_prometheus_metrics():
    prometheus_metrics.update_from_pool("main_pool", pool)

# Planifier mises à jour régulières
import threading
import time

def prometheus_update_loop():
    while True:
        update_prometheus_metrics()
        time.sleep(10)  # Mise à jour toutes les 10 secondes

prometheus_thread = threading.Thread(target=prometheus_update_loop, daemon=True)
prometheus_thread.start()
```

#### Intégration Logging

```python
import logging
import json

# Configuration logging structuré pour métriques
metrics_logger = logging.getLogger('pool.metrics')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
metrics_logger.addHandler(handler)
metrics_logger.setLevel(logging.INFO)

def log_metrics_periodically():
    """Logger métriques en format structuré."""
    health = pool.get_health_status()
    
    metrics_data = {
        'timestamp': time.time(),
        'pool_status': health['status'],
        'hit_rate': health['hit_rate'],
        'corruption_rate': health['corruption_rate'],
        'active_objects_count': health['active_objects_count'],
        'total_pooled_objects': health['total_pooled_objects'],
        'total_requests': health['total_requests']
    }
    
    if pool.performance_metrics:
        snapshot = pool.performance_metrics.create_snapshot()
        metrics_data.update({
            'avg_acquisition_time_ms': snapshot.avg_acquisition_time_ms,
            'p95_acquisition_time_ms': snapshot.p95_acquisition_time_ms,
            'throughput_ops_sec': snapshot.acquisitions_per_second
        })
    
    metrics_logger.info(json.dumps(metrics_data))

# Logger métriques toutes les 5 minutes
def metrics_logging_loop():
    while True:
        log_metrics_periodically()
        time.sleep(300)  # 5 minutes

logging_thread = threading.Thread(target=metrics_logging_loop, daemon=True)
logging_thread.start()
```

Ce système complet de monitoring et métriques fournit l'observabilité nécessaire pour les déploiements production, permettant une gestion proactive des performances et une identification rapide des problèmes.