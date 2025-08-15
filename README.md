# Mammouth AI - Intégration Home Assistant

Une intégration Home Assistant qui connecte votre maison intelligente à **Mammouth AI**, la plateforme unifiée qui donne accès à **tous les grands modèles d'IA** du marché.

## 🌟 Pourquoi Mammouth AI ?

**Mammouth AI** est bien plus qu'un simple service d'IA - c'est votre **gateway universel** vers l'ensemble de l'écosystème des modèles de langage :

### 🎯 Accès Unifié à Tous les Modèles
- **OpenAI** : GPT-4, GPT-4 Turbo, GPT-3.5
- **Anthropic** : Claude 3.5 Sonnet, Claude 3 Haiku, Claude 3 Opus  
- **Google** : Gemini Pro, Gemini Ultra, PaLM 2
- **Meta** : Llama 2, Code Llama
- **Mistral AI** : Mistral 7B, Mixtral 8x7B
- **Cohere** : Command, Command-Light
- **Et bien d'autres...**

### 💡 Avantages Clés
- ✅ **Une seule clé API** pour accéder à tous les modèles
- ✅ **Prix optimisés** et transparents
- ✅ **Basculement automatique** entre modèles selon vos besoins
- ✅ **Performance uniforme** avec une API standardisée
- ✅ **Support multilingue** natif
- ✅ **Pas de vendor lock-in** - changez de modèle en un clic

## 🏠 Fonctionnalités Home Assistant

Cette intégration transforme votre Home Assistant en **assistant conversationnel intelligent** capable de :

- 🗣️ **Conversations naturelles** avec votre maison intelligente
- 🎛️ **Contrôle vocal avancé** de vos appareils connectés  
- 📊 **Analyse intelligente** de vos données IoT
- 🤖 **Automatisations conversationnelles** personnalisées
- 🌍 **Support multilingue** (7 langues supportées)
- 📱 **Intégration native** avec l'interface Home Assistant

## 🚀 Installation

### Via HACS (Recommandé)
1. Ouvrez HACS dans Home Assistant
2. Cliquez sur "Intégrations"
3. Cliquez sur le menu ⋮ puis "Dépôts personnalisés"
4. Ajoutez cette URL : `https://github.com/malcom0106/mammouth-ai-integration`
5. Recherchez "Mammouth AI" et installez
6. Redémarrez Home Assistant

### Installation Manuelle
1. Téléchargez les fichiers de ce repository
2. Copiez le dossier `custom_components/mammouth_ai/` vers `config/custom_components/`
3. Redémarrez Home Assistant

## ⚙️ Configuration

### 1. Obtenez votre clé API
Inscrivez-vous sur [Mammouth AI](https://mammouth.ai) et obtenez votre clé API unique.

### 2. Ajoutez l'intégration
1. Allez dans **Paramètres** > **Appareils et services**
2. Cliquez sur **+ Ajouter une intégration**
3. Recherchez "Mammouth AI"
4. Entrez votre clé API
5. Configurez vos préférences

### 3. Configuration Avancée
- **Modèle** : Choisissez parmi tous les modèles disponibles
- **Température** : Ajustez la créativité des réponses (0.0 à 2.0)
- **Tokens Max** : Limitez la longueur des réponses
- **Prompt Système** : Personnalisez le comportement de l'IA
- **API Home Assistant** : Activez l'accès aux données de votre maison

## 💬 Utilisation

Une fois configurée, votre assistant Mammouth AI sera disponible :

- Dans l'**interface de conversation** de Home Assistant
- Via les **commandes vocales** (avec un assistant vocal)
- Dans les **automatisations** comme service de conversation
- Avec l'**Assistant Google**, **Alexa**, ou **Siri** via Home Assistant

### Exemples de Commandes
```
"Allume les lumières du salon"
"Quelle est la température dans la chambre ?"
"Active le mode nuit"
"Raconte-moi une blague"
"Résume la consommation énergétique d'aujourd'hui"
```

## 🌍 Langues Supportées

L'interface est disponible en 7 langues :
- 🇫🇷 Français
- 🇬🇧 Anglais  
- 🇪🇸 Espagnol
- 🇩🇪 Allemand
- 🇮🇹 Italien
- 🇵🇹 Portugais
- 🇳🇱 Néerlandais

## 🛠️ Développement

### Prérequis
- Python 3.12+
- Home Assistant 2025.8+

### Environnement de Développement
```bash
# Créer l'environnement virtuel
python3.12 -m venv venv_ha2025
source venv_ha2025/bin/activate  # Linux/Mac
# venv_ha2025\Scripts\activate   # Windows

# Installer les dépendances
pip install homeassistant
pip install pytest pytest-asyncio

# Lancer Home Assistant en local
python run_ha.py
```

### Tests
```bash
# Lancer tous les tests
python -m pytest tests/ -v

# Tests avec couverture
python -m pytest --cov=custom_components.mammouth_ai tests/

# Test API direct
python test_api.py
```

## 🤝 Contribution

Les contributions sont les bienvenues ! Voici comment contribuer :

1. Forkez le projet
2. Créez votre branche (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add AmazingFeature'`)
4. Poussez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🆘 Support

- 📖 **Documentation** : [Wiki du projet](https://github.com/votre_username/mammouth-ai-integration/wiki)
- 🐛 **Bugs** : [Issues GitHub](https://github.com/votre_username/mammouth-ai-integration/issues)
- 💬 **Discussions** : [Forum de la communauté](https://github.com/votre_username/mammouth-ai-integration/discussions)
- 🌐 **Mammouth AI** : [Site officiel](https://mammouth.ai)

## 🎯 Roadmap

- [ ] Support des modèles d'image (DALL-E, Midjourney, etc.)
- [ ] Intégration avec Home Assistant Voice
- [ ] Tableaux de bord conversationnels
- [ ] Automatisations basées sur l'IA
- [ ] Plugins pour appareils spécifiques
- [ ] Mode hors ligne avec modèles locaux

---

**Transformez votre maison intelligente avec la puissance unifiée de tous les modèles d'IA !** 🏠✨