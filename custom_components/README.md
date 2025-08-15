# Mammouth AI for Home Assistant

[![HACS Custom][hacs_custom_badge]][hacs_custom]
[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

![Project Maintenance][maintenance-shield]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

[![Community Forum][forum-shield]][forum]

Intégration **Mammouth AI** dans Home Assistant - **L'accès unifié à TOUS les modèles d'IA** (OpenAI, Claude, Gemini, Llama, Mistral...) avec une seule clé API.

![Mammouth AI Logo](https://raw.githubusercontent.com/votre-username/ha-mammouth-ai/main/images/logo.png)

## 🌟 Pourquoi Mammouth AI ?

**Mammouth AI** révolutionne l'IA conversationnelle en offrant **l'accès unifié à TOUS les grands modèles** :

### 🎯 Tous les Modèles en Un
- **OpenAI** : GPT-4, GPT-4 Turbo, GPT-3.5
- **Anthropic** : Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku  
- **Google** : Gemini Pro, Gemini Ultra, PaLM 2
- **Meta** : Llama 2, Code Llama, Llama 3
- **Mistral AI** : Mistral 7B, Mixtral 8x7B, Mistral Large
- **Cohere** : Command, Command-Light
- **Et bien d'autres modèles...**

### 💡 Avantages Uniques
- ✅ **Une seule clé API** pour tous les modèles
- ✅ **Prix optimisés** et transparents
- ✅ **Pas de vendor lock-in** - changez de modèle instantanément
- ✅ **Performance uniforme** avec API standardisée
- ✅ **Basculement intelligent** selon vos besoins

## ✨ Fonctionnalités Home Assistant

- 🗣️ **Conversations naturelles** avec tous les modèles d'IA
- 🏠 **Contrôle domotique intelligent** via commandes vocales
- 🔄 **Streaming en temps réel** pour des réponses fluides
- 🌍 **Support multilingue** (7 langues : FR, EN, ES, DE, IT, PT, NL)
- ⚙️ **Configuration flexible** des paramètres IA
- 📱 **Interface utilisateur** intégrée dans Home Assistant
- 🔐 **Sécurisé** avec authentification API
- 🚀 **Performance optimisée** avec gestion d'erreurs robuste

## 📋 Prérequis

- **Home Assistant 2025.8.0 ou plus récent**
- **Python 3.12+** (requis pour HA 2025.x)
- Compte Mammouth.ai avec clé API valide
- Accès internet pour les requêtes API

## 🚀 Installation

### Via HACS (Recommandé)

1. **Ajouter le repository personnalisé :**
   - Ouvrez HACS dans Home Assistant
   - Allez dans "Intégrations"
   - Cliquez sur les 3 points en haut à droite
   - Sélectionnez "Repositories personnalisés"
   - Ajoutez : `https://github.com/votre-username/ha-mammouth-ai`
   - Catégorie : "Integration"

2. **Installer l'intégration :**
   - Recherchez "Mammouth AI" dans HACS
   - Cliquez sur "Télécharger"
   - Redémarrez Home Assistant

### Installation manuelle

1. **Vérifier les prérequis :**
   - Home Assistant 2025.8.0+ installé
   - Python 3.12+ disponible sur le système

2. **Télécharger les fichiers :**
   ```bash
   cd /config/custom_components/
   git clone https://github.com/votre-username/ha-mammouth-ai.git mammouth_ai
   ```

3. **Redémarrer Home Assistant**

## ⚙️ Configuration

### 1. Interface graphique

1. Allez dans **Configuration** → **Intégrations**
2. Cliquez sur **"Ajouter une intégration"**
3. Recherchez **"Mammouth AI"**
4. Suivez l'assistant de configuration :
   - **Clé API** : Votre clé API Mammouth.ai
   - **URL de base** : `https://api.mammouth.ai/v1` (par défaut)
   - **Modèle** : Choisir le modèle IA souhaité

### 2. Configuration YAML (Optionnelle)

```yaml
# configuration.yaml
conversation:
  - platform: mammouth_ai
    api_key: !secret mammouth_api_key
    base_url: "https://api.mammouth.ai/v1"
    model: "mammouth-chat"
    max_tokens: 1000
    temperature: 0.7
```

```yaml
# secrets.yaml  
mammouth_api_key: "votre_clé_api_secrète"
```

## 🎯 Utilisation

### Conversations de base

L'intégration se connecte automatiquement au système de conversation de Home Assistant :

```yaml
# Exemple d'automatisation
automation:
  - alias: "Assistant vocal intelligent"
    trigger:
      - platform: conversation
        command: 
          - "Mammouth, comment ça va ?"
          - "Peux-tu m'aider ?"
    action:
      - service: conversation.process
        data:
          agent_id: mammouth_ai
          text: "{{ trigger.data.text }}"
```

### Contrôle domotique

```yaml
# Exemples de commandes supportées
- "Mammouth, allume les lumières du salon"
- "Dis-moi la température extérieure"
- "Ferme tous les volets de la maison"
- "Prépare une ambiance romantique"
- "Que dois-je savoir sur ma maison aujourd'hui ?"
```

### Service custom

```yaml
# Appel direct au service
service: mammouth_ai.ask
data:
  message: "Analyse l'état de ma maison et donne-moi un rapport"
  conversation_id: "salon_chat"
  include_context: true
```

## 🔧 Options de configuration

| Option | Type | Défaut | Description |
|--------|------|--------|-------------|
| `api_key` | string | **Requis** | Clé API Mammouth.ai |
| `base_url` | string | `https://api.mammouth.ai/v1` | URL de l'API |
| `model` | string | `mammouth-chat` | Modèle IA à utiliser |
| `max_tokens` | integer | `1000` | Nombre maximum de tokens |
| `temperature` | float | `0.7` | Créativité des réponses (0.0-2.0) |
| `top_p` | float | `1.0` | Diversité vocabulaire |
| `frequency_penalty` | float | `0.0` | Pénalité répétition |
| `presence_penalty` | float | `0.0` | Pénalité redondance |
| `timeout` | integer | `30` | Timeout requêtes (secondes) |
| `streaming` | boolean | `true` | Réponses en streaming |

## 🛠️ Développement

### Configuration environnement (HA 2025.x)

```bash
# Cloner le projet
git clone https://github.com/votre-username/ha-mammouth-ai.git
cd ha-mammouth-ai

# Créer environnement virtuel avec Python 3.12+
python3.12 -m venv venv_ha2025
source venv_ha2025/bin/activate  # Linux/Mac
# venv_ha2025\Scripts\activate   # Windows

# Installer Home Assistant 2025.7.30+ et dépendances
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Tests

```bash
# Tests unitaires
python -m pytest tests/ -v

# Tests d'intégration
python -m pytest tests/test_integration.py

# Test API direct
python test_api.py

# Coverage
python -m pytest --cov=custom_components.mammouth_ai tests/
```

### Qualité du code

```bash
# Formatage
black custom_components/
isort custom_components/

# Linting
flake8 custom_components/
pylint custom_components/mammouth_ai/

# Type checking
mypy custom_components/mammouth_ai/
```

### Pre-commit hooks

```bash
# Installation
pre-commit install

# Test manuel
pre-commit run --all-files
```

## 🐛 Dépannage

### Problèmes courants

**❌ Erreur d'authentification**
```
Vérifiez votre clé API dans Configuration → Intégrations → Mammouth AI
```

**❌ Timeout de connexion**
```yaml
# Augmentez le timeout dans les options
timeout: 60
```

**❌ Réponses incohérentes**
```yaml
# Ajustez la température
temperature: 0.3  # Plus déterministe
temperature: 1.2  # Plus créatif
```

### Logs de debug

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.mammouth_ai: debug
    custom_components.mammouth_ai.coordinator: debug
```

### Test de connectivité

```python
# Dans Developer Tools → Services
service: mammouth_ai.test_connection
data: {}
```

## 📊 Monitoring

### Métriques disponibles

- `sensor.mammouth_ai_requests_total` - Total des requêtes
- `sensor.mammouth_ai_requests_failed` - Requêtes échouées  
- `sensor.mammouth_ai_average_response_time` - Temps de réponse moyen
- `sensor.mammouth_ai_tokens_used` - Tokens consommés

### Dashboard exemple

```yaml
# ui-lovelace.yaml
type: entities
title: Mammouth AI Stats
entities:
  - sensor.mammouth_ai_requests_total
  - sensor.mammouth_ai_requests_failed
  - sensor.mammouth_ai_average_response_time
  - sensor.mammouth_ai_tokens_used
```

## 🤝 Contribution

Les contributions sont les bienvenues ! 

1. **Fork** le projet
2. **Créer** une branche feature (`git checkout -b feature/AmazingFeature`)
3. **Commiter** vos changements (`git commit -m 'Add AmazingFeature'`)
4. **Pusher** sur la branche (`git push origin feature/AmazingFeature`)
5. **Ouvrir** une Pull Request

### Guidelines

- Suivre les standards de code Python/Home Assistant
- Ajouter des tests pour les nouvelles fonctionnalités
- Mettre à jour la documentation
- Respecter les conventions de commit

## 📝 Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique des versions.

### Version 2.0.0 (HA 2025.x)
- 🚀 **Compatible Home Assistant 2025.8+**
- 🔄 **Architecture modernisée** avec ConversationEntity
- 💬 **ChatLog automatique** pour historique de conversation
- 🐍 **Python 3.12+** requis
- 🛠️ **Platform-based setup** moderne
- 🔧 **Corrections encodage** Windows

### Version 1.0.0
- 🎉 Version initiale (HA 2024.x)
- ✅ Support conversation basique
- ✅ Configuration via UI
- ✅ Streaming des réponses

## 📄 Licence

Ce projet est sous licence MIT - voir [LICENSE](LICENSE) pour plus de détails.

## 🙏 Remerciements

- [Mammouth.ai](https://mammouth.ai) pour leur excellente API
- La communauté [Home Assistant](https://home-assistant.io)
- Tous les [contributeurs](https://github.com/malcom0106/ha-mammouth-ai/graphs/contributors)

## 💬 Support

- 🐛 **Bug reports** : [GitHub Issues](https://github.com/malcom0106/ha-mammouth-ai/issues)
- 💡 **Feature requests** : [GitHub Discussions](https://github.com/malcom0106/ha-mammouth-ai/discussions)
- 🗨️ **Questions** : [Community Forum](https://community.home-assistant.io/)
- 💬 **Discord** : [Home Assistant Discord](https://discord.gg/home-assistant)

## ☕ Soutenir le projet

Si ce projet vous aide, considérez m'offrir un café ! ☕

[![Buy Me A Coffee][buymecoffeebadge]][buymecoffee]

---

**⭐ N'oubliez pas de mettre une étoile si ce projet vous plaît !**

---

<!-- Badges -->
[hacs_custom_badge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs_custom]: https://github.com/custom-components/hacs
[releases-shield]: https://img.shields.io/github/release/votre-username/ha-mammouth-ai.svg?style=for-the-badge
[releases]: https://github.com/votre-username/ha-mammouth-ai/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/votre-username/ha-mammouth-ai.svg?style=for-the-badge
[commits]: https://github.com/votre-username/ha-mammouth-ai/commits/main
[license-shield]: https://img.shields.io/github/license/votre-username/ha-mammouth-ai.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40votre--username-blue.svg?style=for-the-badge
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[buymecoffee]: https://www.buymeacoffee.com/votre-username
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/