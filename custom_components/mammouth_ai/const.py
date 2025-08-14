"""Constants for the Mammouth AI integration."""

DOMAIN = "mammouth_ai"
MANUFACTURER = "Mammouth"

# Configuration
CONF_API_KEY = "api_key"
CONF_BASE_URL = "base_url"
CONF_MODEL = "model"
CONF_PROMPT = "prompt"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_TIMEOUT = "timeout"
CONF_LLM_HASS_API = "llm_hass_api"  # Ajout de cette constante

# Valeurs par défaut
DEFAULT_BASE_URL = "https://api.mammouth.ai/v1"
DEFAULT_MODEL = "mammouth-default"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TIMEOUT = 30
DEFAULT_PROMPT = """Tu es un assistant vocal pour Home Assistant nommé {ha_name}.
Tu aides l'utilisateur avec sa maison connectée.
Réponds en français de manière concise et utile.
L'utilisateur actuel est : {user_name}"""

# API Endpoints
API_CHAT_COMPLETIONS = "chat/completions"
API_MODELS = "models"

# Erreurs
ERROR_AUTH = "Clé API invalide"
ERROR_CONNECT = "Impossible de se connecter à Mammouth AI"
ERROR_TIMEOUT = "Délai d'attente dépassé"
ERROR_UNKNOWN = "Erreur inconnue"
