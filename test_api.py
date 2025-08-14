"""Script pour tester l'API Mammouth.ai directement."""
import asyncio
import aiohttp
import json
import yaml
import os

def load_config():
    """Charge la configuration depuis le fichier YAML."""
    config_path = os.path.join("config", "configuration.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            return config.get('mammouth_ai', {})
    except Exception as e:
        print(f"❌ Erreur lors du chargement de la configuration: {e}")
        return {}

async def test_mammouth_api():
    """Test direct de l'API."""
    # Charger la configuration
    config = load_config()
    api_key = config.get('api_key', '')
    base_url = config.get('base_url', '')
    
    if not api_key or not base_url:
        print("Configuration manquante. Verifiez config/configuration.yaml")
        return
    
    print(f"Configuration utilisee:")
    print(f"   API Key: {api_key[:10]}...")
    print(f"   Base URL: {base_url}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Test connection
    async with aiohttp.ClientSession() as session:
        # Test 1: Lister les modèles
        try:
            async with session.get(f"{base_url}/models", headers=headers) as resp:
                if resp.status == 200:
                    models = await resp.json()
                    print("✅ Connexion OK")
                    print(f"Modèles disponibles: {json.dumps(models, indent=2)}")
                else:
                    print(f"❌ Erreur connexion: {resp.status}")
                    print(await resp.text())
        except Exception as e:
            print(f"❌ Erreur: {e}")
        
        # Test 2: Chat completion
        try:
            payload = {
                "model": "gpt-4.1-mini",  # Remplacez par le bon modèle
                "messages": [
                    {"role": "user", "content": "Bonjour, comment allez-vous ?"}
                ],
                "max_tokens": 100
            }
            
            async with session.post(f"{base_url}/chat/completions", 
                                  headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print("✅ Chat completion OK")
                    print(f"Réponse: {result['choices'][0]['message']['content']}")
                else:
                    print(f"❌ Erreur chat: {resp.status}")
                    print(await resp.text())
        except Exception as e:
            print(f"❌ Erreur chat: {e}")

if __name__ == "__main__":
    asyncio.run(test_mammouth_api())
