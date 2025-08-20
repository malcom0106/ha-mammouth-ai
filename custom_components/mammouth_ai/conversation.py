"""Conversation support for Mammouth AI."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Literal

from homeassistant.components.conversation import (
    ChatLog,
    ConversationEntity,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, template

from .const import (
    CONF_ENTITY_DOMAINS,
    CONF_EXCLUDE_AREAS,
    CONF_LLM_HASS_API,
    CONF_MAX_ENTITIES,
    CONF_MINIMAL_ATTRIBUTES,
    CONF_PROMPT,
    CONF_SMART_FILTERING,
    DEFAULT_ENTITY_DOMAINS,
    DEFAULT_EXCLUDE_AREAS,
    DEFAULT_MAX_ENTITIES,
    DEFAULT_MINIMAL_ATTRIBUTES,
    DEFAULT_PROMPT,
    DEFAULT_SMART_FILTERING,
    DOMAIN,
)
from .coordinator import MammouthDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class MammouthConversationEntity(ConversationEntity):
    """Mammouth AI conversation entity."""

    def __init__(
        self,
        coordinator: MammouthDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._attr_name = f"Mammouth AI ({config_entry.title})"
        self._attr_unique_id = config_entry.entry_id

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return "Powered by Mammouth AI"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return list of supported languages."""
        return MATCH_ALL

    def _extract_relevant_domains_from_query(self, query: str) -> set[str]:
        """Extract relevant domains from user query using keyword matching."""
        domain_keywords = {
            "light": [
                # French
                "lumière",
                "éclairage",
                "allume",
                "éteins",
                "lampe",
                # English
                "light",
                "lamp",
                "turn on",
                "turn off",
                "illuminate",
                # Spanish
                "luz",
                "lámpara",
                "encender",
                "apagar",
                "iluminar",
                # German
                "licht",
                "lampe",
                "anschalten",
                "ausschalten",
                # Italian
                "luce",
                "lampada",
                "accendi",
                "spegni",
                # Portuguese
                "luz",
                "lâmpada",
                "ligar",
                "desligar",
                # Dutch
                "licht",
                "lamp",
                "aan",
                "uit",
            ],
            "switch": [
                # French
                "interrupteur",
                "prise",
                "allume",
                "éteins",
                # English
                "switch",
                "plug",
                "outlet",
                "turn on",
                "turn off",
                # Spanish
                "interruptor",
                "enchufe",
                "encender",
                "apagar",
                # German
                "schalter",
                "steckdose",
                "anschalten",
                "ausschalten",
                # Italian
                "interruttore",
                "presa",
                "accendi",
                "spegni",
                # Portuguese
                "interruptor",
                "tomada",
                "ligar",
                "desligar",
                # Dutch
                "schakelaar",
                "stopcontact",
                "aan",
                "uit",
            ],
            "sensor": [
                # French
                "température",
                "humidité",
                "capteur",
                "mesure",
                # English
                "temperature",
                "humidity",
                "sensor",
                "measure",
                # Spanish
                "temperatura",
                "humedad",
                "sensor",
                "medida",
                # German
                "temperatur",
                "feuchtigkeit",
                "sensor",
                "messung",
                # Italian
                "temperatura",
                "umidità",
                "sensore",
                "misura",
                # Portuguese
                "temperatura",
                "umidade",
                "sensor",
                "medida",
                # Dutch
                "temperatuur",
                "vochtigheid",
                "sensor",
                "meting",
            ],
            "binary_sensor": [
                # French
                "détecteur",
                "mouvement",
                "porte",
                "fenêtre",
                "ouvert",
                "fermé",
                # English
                "detector",
                "motion",
                "door",
                "window",
                "open",
                "closed",
                # Spanish
                "detector",
                "movimiento",
                "puerta",
                "ventana",
                "abierto",
                "cerrado",
                # German
                "detektor",
                "bewegung",
                "tür",
                "fenster",
                "offen",
                "geschlossen",
                # Italian
                "rilevatore",
                "movimento",
                "porta",
                "finestra",
                "aperto",
                "chiuso",
                # Portuguese
                "detector",
                "movimento",
                "porta",
                "janela",
                "aberto",
                "fechado",
                # Dutch
                "detector",
                "beweging",
                "deur",
                "raam",
                "open",
                "gesloten",
            ],
            "climate": [
                # French
                "chauffage",
                "climatisation",
                "thermostat",
                "température",
                # English
                "heating",
                "air conditioning",
                "thermostat",
                "temperature",
                # Spanish
                "calefacción",
                "aire acondicionado",
                "termostato",
                "temperatura",
                # German
                "heizung",
                "klimaanlage",
                "thermostat",
                "temperatur",
                # Italian
                "riscaldamento",
                "aria condizionata",
                "termostato",
                "temperatura",
                # Portuguese
                "aquecimento",
                "ar condicionado",
                "termostato",
                "temperatura",
                # Dutch
                "verwarming",
                "airconditioning",
                "thermostaat",
                "temperatuur",
            ],
            "cover": [
                # French
                "volet",
                "store",
                "rideau",
                "garage",
                # English
                "cover",
                "blind",
                "curtain",
                "shutter",
                "garage",
                # Spanish
                "persiana",
                "cortina",
                "toldo",
                "garaje",
                # German
                "jalousie",
                "vorhang",
                "rollladen",
                "garage",
                # Italian
                "tapparella",
                "tenda",
                "persiana",
                "garage",
                # Portuguese
                "persiana",
                "cortina",
                "toldo",
                "garagem",
                # Dutch
                "jaloezie",
                "gordijn",
                "rolluik",
                "garage",
            ],
        }

        query_lower = query.lower()
        relevant_domains = set()

        for domain, keywords in domain_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                relevant_domains.add(domain)

        return relevant_domains

    def _filter_entities_by_area(self, states, exclude_areas: list[str]):
        """Filter entities by area."""
        if not exclude_areas:
            return states

        filtered_states = []
        for state in states:
            area_id = None
            if hasattr(state, "attributes") and "area_id" in state.attributes:
                area_id = state.attributes["area_id"]

            if area_id not in exclude_areas:
                filtered_states.append(state)

        return filtered_states

    def _get_essential_attributes(self, state, minimal: bool):
        """Get essential attributes only, reducing token usage."""
        base_attrs = {
            "friendly_name": state.attributes.get("friendly_name", state.entity_id),
            "unit_of_measurement": state.attributes.get("unit_of_measurement", ""),
            "device_class": state.attributes.get("device_class", ""),
        }

        if not minimal:
            base_attrs.update(
                {
                    "icon": state.attributes.get("icon", ""),
                    "state_class": state.attributes.get("state_class", ""),
                }
            )

        return base_attrs

    def _filter_and_prepare_entities(self, user_query: str):
        """Filter and prepare entities for API call with optimizations."""
        # Get configuration options
        config_options = self._config_entry.options
        max_entities = config_options.get(CONF_MAX_ENTITIES, DEFAULT_MAX_ENTITIES)
        allowed_domains = config_options.get(
            CONF_ENTITY_DOMAINS, DEFAULT_ENTITY_DOMAINS
        )
        exclude_areas = config_options.get(CONF_EXCLUDE_AREAS, DEFAULT_EXCLUDE_AREAS)
        smart_filtering = config_options.get(
            CONF_SMART_FILTERING, DEFAULT_SMART_FILTERING
        )
        minimal_attributes = config_options.get(
            CONF_MINIMAL_ATTRIBUTES, DEFAULT_MINIMAL_ATTRIBUTES
        )

        all_states = self.hass.states.async_all()
        _LOGGER.debug("Total entities in HA: %d", len(all_states))

        # Filter by area first
        filtered_states = self._filter_entities_by_area(all_states, exclude_areas)

        # Filter by domain
        domain_filtered_states = [
            state
            for state in filtered_states
            if state.domain in allowed_domains
            and state.state not in ["unknown", "unavailable"]
        ]

        # Smart filtering based on user query
        if smart_filtering:
            relevant_domains = self._extract_relevant_domains_from_query(user_query)
            if relevant_domains:
                smart_filtered_states = [
                    state
                    for state in domain_filtered_states
                    if state.domain in relevant_domains
                ]
                # If smart filtering yields results, use it;
                # otherwise fall back to all domains
                if smart_filtered_states:
                    domain_filtered_states = smart_filtered_states
                    _LOGGER.debug(
                        "Smart filtering applied: %s domains", relevant_domains
                    )

        # Limit total number of entities
        if len(domain_filtered_states) > max_entities:
            domain_filtered_states = domain_filtered_states[:max_entities]
            _LOGGER.debug("Limited entities to %d", max_entities)

        # Prepare entities with reduced attributes
        entities_by_domain = defaultdict(list)
        for state in domain_filtered_states:
            essential_attrs = self._get_essential_attributes(state, minimal_attributes)
            entity_data = {
                "entity_id": state.entity_id,
                "name": essential_attrs.get("friendly_name", state.entity_id),
                "state": state.state,
                "unit": essential_attrs.get("unit_of_measurement", ""),
            }

            # Add device_class only if it exists and not minimal
            if not minimal_attributes and essential_attrs.get("device_class"):
                entity_data["device_class"] = essential_attrs["device_class"]

            entities_by_domain[state.domain].append(entity_data)

        _LOGGER.debug(
            "Filtered entities by domain: %s",
            {domain: len(entities) for domain, entities in entities_by_domain.items()},
        )

        return dict(entities_by_domain), sum(
            len(entities) for entities in entities_by_domain.values()
        )

    async def _async_handle_message(
        self, user_input: ConversationInput, chat_log: ChatLog
    ) -> ConversationResult:
        """Handle a conversation message."""
        intent_response = intent.IntentResponse(language=user_input.language)

        # Obtenir le prompt système
        system_prompt = self._config_entry.options.get(CONF_PROMPT, DEFAULT_PROMPT)

        # Si l'option d'API HA est activée, traiter les templates
        llm_hass_api_enabled = self._config_entry.options.get(CONF_LLM_HASS_API, True)
        _LOGGER.debug("LLM HASS API enabled: %s", llm_hass_api_enabled)

        if llm_hass_api_enabled:
            try:
                # Obtenir les informations utilisateur
                user_name = "Utilisateur"
                if user_input.context and user_input.context.user_id:
                    user = await self.hass.auth.async_get_user(
                        user_input.context.user_id
                    )
                    if user and user.name:
                        user_name = user.name

                # Rendre le template avec les variables HA
                ha_name = self.hass.config.location_name or "Jean Claude"

                # Utiliser le nouveau système de filtrage optimisé
                entities_by_domain, entities_count = self._filter_and_prepare_entities(
                    user_input.text
                )

                _LOGGER.debug("Optimized entities count: %d", entities_count)
                if entities_by_domain:
                    _LOGGER.debug(
                        "Entities by domain: %s",
                        {
                            domain: len(entities)
                            for domain, entities in entities_by_domain.items()
                        },
                    )

                template_vars = {
                    "ha_name": ha_name,
                    "user_name": user_name,
                    "entities_by_domain": entities_by_domain,
                    "entities_count": entities_count,
                }
                _LOGGER.debug(
                    "Template variables: ha_name=%s, user_name=%s, entities_count=%d",
                    ha_name,
                    user_name,
                    entities_count,
                )

                system_prompt = template.Template(
                    system_prompt, self.hass
                ).async_render(template_vars, parse_result=False)

                _LOGGER.debug(
                    "Rendered system prompt length: %d characters", len(system_prompt)
                )
                _LOGGER.debug(
                    "Rendered system prompt (first 500 chars): %s", system_prompt[:500]
                )
            except TemplateError as err:
                _LOGGER.error("Error rendering prompt template: %s", err)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    f"Erreur de template: {err}",
                )
                return ConversationResult(
                    response=intent_response,
                )

        # Construire les messages pour l'API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input.text},
        ]

        _LOGGER.debug("Sending request to Mammouth AI: %s", user_input.text)

        try:
            # Obtenir l'ID utilisateur pour la mémoire
            user_id = None
            if user_input.context and user_input.context.user_id:
                user_id = user_input.context.user_id

            # Appel à l'API Mammouth avec mémoire
            response_text = await self.coordinator.async_chat_completion_with_memory(
                messages, user_id=user_id, conversation_id=user_input.conversation_id
            )

            _LOGGER.debug("Received response from Mammouth AI: %s", response_text)

            intent_response.async_set_speech(response_text)

        except HomeAssistantError as err:
            _LOGGER.error("Error processing conversation: %s", err)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Erreur de l'assistant Mammouth: {err}",
            )

        return ConversationResult(
            response=intent_response,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Mammouth AI conversation platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entity = MammouthConversationEntity(coordinator, config_entry)
    async_add_entities([entity])
    _LOGGER.debug("Mammouth AI conversation entity added")
