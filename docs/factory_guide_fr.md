# Guide de Création de Factory - SmartPool - Pool de Mémoire Intelligent

## Introduction

Ce guide fournit des instructions complètes pour créer des factories personnalisées pour le système de pool de mémoire adaptatif. Une factory est responsable de créer, réinitialiser, valider et détruire les objets gérés par le pool de mémoire.

## Comprendre l'Interface ObjectFactory

La classe abstraite `ObjectFactory` définit le contrat que toutes les factories doivent implémenter :

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import sys

T = TypeVar("T")

class ObjectFactory(ABC, Generic[T]):
    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """Créer une nouvelle instance d'objet."""
        
    @abstractmethod  
    def reset(self, obj: T) -> bool:
        """Remettre l'objet à l'état initial pour réutilisation."""
        
    @abstractmethod
    def validate(self, obj: T) -> bool:
        """Valider l'intégrité et l'utilisabilité de l'objet."""
        
    @abstractmethod
    def get_key(self, *args, **kwargs) -> str:
        """Générer une clé de pooling unique basée sur les paramètres."""
        
    def destroy(self, obj: T) -> None:
        """Nettoyer les ressources de l'objet (optionnel à surcharger)."""
        pass
        
    def estimate_size(self, obj: T) -> int:
        """Estimer la taille mémoire de l'objet (optionnel à surcharger)."""
        return sys.getsizeof(obj)
```

## Méthodes Obligatoires

### 1. create(*args, **kwargs) -> T

Crée et retourne une nouvelle instance du type d'objet géré.

**Objectif :**
- Instancier des objets quand le pool est vide ou nécessite une expansion
- Gérer les paramètres de construction variables via args/kwargs
- Retourner des objets correctement initialisés prêts à l'usage

**Directives d'Implémentation :**
```python
def create(self, *args, **kwargs) -> MonObjet:
    # Extraire les paramètres avec des valeurs par défaut
    size = args[0] if args else kwargs.get('size', 1024)
    mode = kwargs.get('mode', 'default')
    
    # Créer et configurer l'objet
    obj = MonObjet(size)
    obj.configure(mode=mode)
    return obj
```

**Bonnes Pratiques :**
- Gérer gracieusement les arguments positionnels et nommés
- Fournir des valeurs par défaut sensées pour les paramètres manquants
- Valider les paramètres d'entrée et lever des exceptions claires pour les entrées invalides
- Garder la création légère pour éviter les pénalités de performance du pool

### 2. reset(obj: T) -> bool

Remet un objet dans un état propre et réutilisable avant de le retourner au pool.

**Objectif :**
- Effacer l'état transitoire de l'usage précédent
- Restaurer l'objet à sa configuration initiale
- Préparer l'objet pour la prochaine acquisition du pool

**Valeur de Retour :**
- `True` : Objet réinitialisé avec succès et prêt pour réutilisation
- `False` : Réinitialisation échouée, l'objet doit être détruit

**Directives d'Implémentation :**
```python
def reset(self, obj: MonObjet) -> bool:
    try:
        # Vider les structures de données
        obj.data.clear()
        
        # Réinitialiser les variables d'état
        obj.position = 0
        obj.mode = 'default'
        
        # Réinitialiser les flux ou buffers
        if hasattr(obj, 'buffer'):
            obj.buffer.seek(0)
            obj.buffer.truncate(0)
            
        return True
    except (AttributeError, TypeError, IOError):
        return False
```

**Bonnes Pratiques :**
- Gérer toutes les exceptions possibles gracieusement
- Réinitialiser l'état coûteux-à-recréer tout en préservant la structure
- Vérifier l'intégrité de l'objet pendant le processus de reset
- Garder les opérations de reset rapides pour minimiser l'overhead du pool

### 3. validate(obj: T) -> bool

Valide qu'un objet est dans un état utilisable et approprié pour la gestion du pool.

**Objectif :**
- Vérifier l'intégrité de l'objet avant acquisition depuis le pool
- Vérifier la corruption ou l'état invalide
- S'assurer que l'objet répond aux exigences de réutilisation

**Valeur de Retour :**
- `True` : L'objet est valide et peut être utilisé
- `False` : L'objet est invalide et doit être détruit

**Directives d'Implémentation :**
```python
def validate(self, obj: MonObjet) -> bool:
    try:
        # Vérification de type
        if not isinstance(obj, MonObjet):
            return False
            
        # Validation d'état
        if not hasattr(obj, 'data') or obj.data is None:
            return False
            
        # Validation fonctionnelle
        if hasattr(obj, 'is_connected'):
            if not obj.is_connected():
                return False
                
        # Limites de taille
        if len(obj.data) > self.MAX_SIZE:
            return False
            
        return True
    except (AttributeError, TypeError):
        return False
```

**Bonnes Pratiques :**
- Vérifier le type d'objet et les attributs essentiels
- Valider l'état fonctionnel (connexions, handles de fichier, etc.)
- Tester les opérations critiques sans effets de bord
- Retourner False pour toute incertitude plutôt que risquer la corruption

### 4. get_key(*args, **kwargs) -> str

Génère une clé string unique qui groupe des objets similaires ensemble pour un pooling efficace.

**Objectif :**
- Permettre la segmentation du pool par caractéristiques d'objet
- Grouper les objets avec des paramètres de création similaires
- Optimiser l'efficacité du pool via une catégorisation appropriée

**Directives d'Implémentation :**
```python
def get_key(self, *args, **kwargs) -> str:
    # Clé simple basée sur le paramètre principal
    size = args[0] if args else kwargs.get('size', 1024)
    return f"monobjet_{size}"
    
    # Clé complexe avec plusieurs paramètres
    size = args[0] if args else kwargs.get('size', 1024)
    mode = kwargs.get('mode', 'default')
    return f"monobjet_{size}_{mode}"
    
    # Groupement par plage de taille pour efficacité
    size = args[0] if args else kwargs.get('size', 1024)
    size_bucket = (size // 1024) * 1024  # Arrondir au KB le plus proche
    return f"monobjet_{size_bucket}"
```

**Bonnes Pratiques :**
- Inclure les paramètres qui affectent significativement les caractéristiques de l'objet
- Grouper les tailles similaires ensemble en utilisant des buckets pour l'efficacité
- Garder les clés courtes mais descriptives
- Assurer la génération de clé cohérente pour des paramètres identiques
- Éviter d'inclure des paramètres hautement variables qui empêcheraient le pooling

## Méthodes Optionnelles

### destroy(obj: T) -> None

Nettoie les ressources de l'objet avant disposition permanente.

**Quand Surcharger :**
- Les objets détiennent des ressources externes (handles de fichier, connexions DB, sockets réseau)
- Les objets ont des callbacks ou listeners enregistrés
- Les objets maintiennent des références vers d'autres ressources

**Exemple d'Implémentation :**
```python
def destroy(self, obj: MonObjet) -> None:
    try:
        # Fermer les ressources externes
        if hasattr(obj, 'connection') and obj.connection:
            obj.connection.close()
            
        # Désenregistrer les callbacks
        if hasattr(obj, 'unregister'):
            obj.unregister()
            
        # Vider les grandes structures de données
        if hasattr(obj, 'large_data'):
            obj.large_data.clear()
    except Exception:
        # Logger l'erreur mais ne pas lever - l'objet est détruit de toute façon
        pass
```

### estimate_size(obj: T) -> int

Fournit une estimation de taille mémoire pour la gestion et le reporting du pool.

**Quand Surcharger :**
- Le `sys.getsizeof()` par défaut est insuffisant pour votre type d'objet
- L'objet détient des structures de données imbriquées complexes
- Le suivi précis de la mémoire est important pour votre cas d'usage

**Exemple d'Implémentation :**
```python
def estimate_size(self, obj: MonObjet) -> int:
    base_size = sys.getsizeof(obj)
    
    # Ajouter la taille des données contenues
    if hasattr(obj, 'data') and obj.data:
        base_size += sys.getsizeof(obj.data)
        if isinstance(obj.data, dict):
            for k, v in obj.data.items():
                base_size += sys.getsizeof(k) + sys.getsizeof(v)
    
    return base_size
```

## Exemple Complet de Factory

Voici une implémentation complète d'une factory pour objets de configuration :

```python
import time
import sys
from typing import Dict, Any
from dataclasses import dataclass, field
from smartpool.core.factory_interface import ObjectFactory

@dataclass
class ObjetConfig:
    """Objet de configuration avec stockage dictionnaire et métadonnées."""
    name: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    version: int = 1
    _dirty: bool = field(default=False, init=False)
    
    def set_setting(self, key: str, value: Any):
        self.settings[key] = value
        self._dirty = True
    
    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)
    
    def is_valid(self) -> bool:
        return (isinstance(self.settings, dict) and 
                isinstance(self.name, str) and 
                self.version > 0)

class ObjetConfigFactory(ObjectFactory[ObjetConfig]):
    """Factory pour objets de configuration avec pooling intelligent."""
    
    MAX_SETTINGS_SIZE = 1000  # Nombre maximum de paramètres
    
    def create(self, *args, **kwargs) -> ObjetConfig:
        """Créer un nouvel objet de configuration."""
        name = args[0] if args else kwargs.get('name', 'default')
        initial_settings = kwargs.get('settings', {})
        
        config_obj = ObjetConfig(name=name)
        config_obj.settings.update(initial_settings)
        return config_obj
    
    def reset(self, obj: ObjetConfig) -> bool:
        """Réinitialiser l'objet de configuration pour réutilisation."""
        try:
            # Vider les données dynamiques mais préserver la structure
            obj.settings.clear()
            obj.name = ""
            obj.version = 1
            obj._dirty = False
            obj.created_at = time.time()
            return True
        except (AttributeError, TypeError):
            return False
    
    def validate(self, obj: ObjetConfig) -> bool:
        """Valider l'intégrité de l'objet de configuration."""
        try:
            # Validation de type et structure
            if not isinstance(obj, ObjetConfig):
                return False
                
            # Validation d'état
            if not obj.is_valid():
                return False
                
            # Limites de taille
            if len(obj.settings) > self.MAX_SETTINGS_SIZE:
                return False
                
            return True
        except (AttributeError, TypeError):
            return False
    
    def get_key(self, *args, **kwargs) -> str:
        """Générer une clé de pooling basée sur le pattern d'usage attendu."""
        # Grouper par pattern de nom pour des configurations similaires
        name = args[0] if args else kwargs.get('name', 'default')
        
        # Créer des catégories pour un meilleur pooling
        if name.startswith('user_'):
            return "config_user"
        elif name.startswith('system_'):
            return "config_system"
        else:
            return "config_default"
    
    def estimate_size(self, obj: ObjetConfig) -> int:
        """Estimer l'usage mémoire incluant les données imbriquées."""
        base_size = sys.getsizeof(obj)
        
        # Ajouter la taille du dictionnaire de paramètres
        if obj.settings:
            base_size += sys.getsizeof(obj.settings)
            for key, value in obj.settings.items():
                base_size += sys.getsizeof(key) + sys.getsizeof(value)
        
        return base_size
```

## Intégration avec le Pool de Mémoire

Une fois votre factory implémentée, intégrez-la avec le système de pool de mémoire :

```python
from smartpool.core.smartpool_manager import SmartObjectManager
from smartpool.config import MemoryPreset

# Créer une instance de factory
factory = ObjetConfigFactory()

# Créer le pool de mémoire avec la factory
pool = SmartObjectManager(
    factory=factory,
    preset=MemoryPreset.HIGH_THROUGHPUT
)

# Utiliser le pool
with pool.acquire_context('user_profile', settings={'theme': 'dark'}) as config:
    config.set_setting('language', 'fr')
    value = config.get_setting('theme')
    # L'objet est automatiquement retourné au pool quand le contexte se ferme

# Arrêter le pool quand terminé
pool.shutdown()
```

## Patterns Courants et Bonnes Pratiques

### Gestion d'Erreurs
```python
def reset(self, obj: T) -> bool:
    try:
        # Opérations de reset
        return True
    except Exception as e:
        # Logger l'erreur si nécessaire, mais ne pas lever
        logger.warning(f"Reset échoué pour {type(obj)}: {e}")
        return False
```

### Validation de Paramètres
```python
def create(self, *args, **kwargs) -> T:
    # Valider les paramètres requis
    if not args and 'required_param' not in kwargs:
        raise ValueError("required_param doit être fourni")
    
    # Nettoyer et valider les entrées
    size = args[0] if args else kwargs.get('size', 1024)
    if size <= 0:
        raise ValueError("size doit être positif")
```

### Génération de Clé Efficace
```python
def get_key(self, *args, **kwargs) -> str:
    # Utiliser des buckets de taille pour un meilleur pooling
    size = args[0] if args else kwargs.get('size', 1024)
    bucket = ((size - 1) // 1024 + 1) * 1024  # Arrondir au KB supérieur
    mode = kwargs.get('mode', 'default')
    return f"monobjet_{bucket}_{mode}"
```

### Gestion des Ressources
```python
def destroy(self, obj: T) -> None:
    # Toujours utiliser try-except dans les méthodes destroy
    try:
        if hasattr(obj, 'cleanup'):
            obj.cleanup()
    except Exception:
        pass  # Ignorer les erreurs pendant la destruction
```

## Tester Votre Factory

Créer des tests complets pour votre implémentation de factory :

```python
import unittest
from unittest.mock import Mock

class TestObjetConfigFactory(unittest.TestCase):
    def setUp(self):
        self.factory = ObjetConfigFactory()
    
    def test_create_with_args(self):
        obj = self.factory.create('test_config')
        self.assertEqual(obj.name, 'test_config')
        self.assertIsInstance(obj.settings, dict)
    
    def test_create_with_kwargs(self):
        obj = self.factory.create(name='test', settings={'key': 'value'})
        self.assertEqual(obj.name, 'test')
        self.assertEqual(obj.settings['key'], 'value')
    
    def test_reset_success(self):
        obj = self.factory.create('test')
        obj.settings['key'] = 'value'
        obj_is_dirty = True
        
        result = self.factory.reset(obj)
        self.assertTrue(result)
        self.assertEqual(len(obj.settings), 0)
        self.assertFalse(obj._dirty)
    
    def test_validate_valid_object(self):
        obj = self.factory.create('test')
        self.assertTrue(self.factory.validate(obj))
    
    def test_validate_invalid_object(self):
        self.assertFalse(self.factory.validate("pas un objet config"))
        self.assertFalse(self.factory.validate(None))
    
    def test_key_generation(self):
        key1 = self.factory.get_key('user_profile')
        key2 = self.factory.get_key('user_settings')
        self.assertEqual(key1, key2)  # Les deux devraient utiliser 'config_user'
```

## Considérations de Performance

### Opérations de Reset Efficaces
- Vider les conteneurs au lieu de les recréer
- Réinitialiser les variables simples aux valeurs par défaut
- Éviter les opérations coûteuses dans les méthodes reset

### Génération de Clé Intelligente
- Grouper les objets similaires ensemble pour une meilleure réutilisation
- Éviter les clés sur-granulaires qui empêchent le pooling
- Utiliser des buckets de taille pour les paramètres numériques

### Gestion Mémoire
- Implémenter destroy() pour les objets avec des ressources externes
- Fournir des estimations de taille précises pour le suivi mémoire
- Vider les grandes structures de données dans les méthodes reset()

## Dépannage des Problèmes Courants

### Objets Non Réutilisés
- Vérifier si get_key() génère des clés cohérentes pour des paramètres similaires
- Vérifier que reset() retourne True et nettoie correctement l'état de l'objet
- S'assurer que validate() ne rejette pas les objets valides

### Fuites Mémoire
- Implémenter la méthode destroy() pour les objets avec des ressources externes
- Vider les grandes structures de données dans la méthode reset()
- Vérifier les références circulaires dans les objets gérés

### Problèmes de Performance
- Profiler les méthodes create(), reset(), et validate()
- Optimiser la génération de clé pour les cas courants
- Considérer la mise en cache des vérifications de validation coûteuses

Ce guide complet devrait vous permettre de créer des factories efficaces et robustes pour tout type d'objet dans le système de pool de mémoire adaptatif.
