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
CONF_ENABLE_MEMORY = "enable_memory"
CONF_MAX_MESSAGES = "max_messages"
CONF_MEMORY_TIMEOUT = "memory_timeout"
CONF_MAX_ENTITIES = "max_entities"
CONF_ENTITY_DOMAINS = "entity_domains"
CONF_EXCLUDE_AREAS = "exclude_areas"
CONF_SMART_FILTERING = "smart_filtering"
CONF_MINIMAL_ATTRIBUTES = "minimal_attributes"

# Valeurs par défaut
DEFAULT_BASE_URL = "https://api.mammouth.ai/v1"
DEFAULT_MODEL = "mammouth-default"
DEFAULT_MAX_TOKENS = 1000
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TIMEOUT = 30
DEFAULT_ENABLE_MEMORY = True
DEFAULT_MAX_MESSAGES = 10
DEFAULT_MEMORY_TIMEOUT = 24
DEFAULT_MAX_ENTITIES = 50
DEFAULT_ENTITY_DOMAINS = [
    "sensor",
    "binary_sensor",
    "light",
    "switch",
    "climate",
    "cover",
]
DEFAULT_EXCLUDE_AREAS: list[str] = []
DEFAULT_SMART_FILTERING = True
DEFAULT_MINIMAL_ATTRIBUTES = False
DEFAULT_PROMPT = (
    "Tu es un assistant vocal pour Home Assistant nommé {{ ha_name }}.\n"
    "Tu aides l'utilisateur avec sa maison connectée.\n"
    "Réponds en français de manière concise et utile.\n"
    "L'utilisateur actuel est : {{ user_name }}\n\n"
    "Entités disponibles ({{ entities_count }} au total) :\n"
    "{% for domain, entities in entities_by_domain.items() %}"
    "{{ domain|title }} ({{ entities|length }}) :\n"
    "{% for entity in entities %}"
    "- {{ entity.name }} : {{ entity.state }}{{ entity.unit }}\n"
    "{% endfor %}\n"
    "{% endfor %}\n"
    "Utilise ces informations pour répondre aux questions sur l'état des appareils."
)

# API Endpoints
API_CHAT_COMPLETIONS = "chat/completions"
API_MODELS = "models"

# Erreurs
ERROR_AUTH = "Clé API invalide"
ERROR_CONNECT = "Impossible de se connecter à Mammouth AI"
ERROR_TIMEOUT = "Délai d'attente dépassé"
ERROR_UNKNOWN = "Erreur inconnue"
