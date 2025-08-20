"""Conversation support for Mammouth AI."""

from __future__ import annotations

import logging
from typing import Literal

from homeassistant.components.conversation import (ChatLog, ConversationEntity,
                                                   ConversationInput,
                                                   ConversationResult)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, template

from .const import CONF_LLM_HASS_API, CONF_PROMPT, DEFAULT_PROMPT, DOMAIN
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

                # Obtenir les états des entités pour le contexte
                exposed_entities = []
                all_states = self.hass.states.async_all()
                _LOGGER.debug("Total entities in HA: %d", len(all_states))
                
                for state in all_states:
                    if state.domain in [
                        "sensor",
                        "binary_sensor",
                        "light",
                        "switch",
                        "climate",
                        "cover",
                    ]:
                        exposed_entities.append(
                            {
                                "entity_id": state.entity_id,
                                "name": state.attributes.get(
                                    "friendly_name", state.entity_id
                                ),
                                "state": state.state,
                                "unit": state.attributes.get("unit_of_measurement", ""),
                                "device_class": state.attributes.get(
                                    "device_class", ""
                                ),
                                "attributes": dict(state.attributes),
                            }
                        )
                
                _LOGGER.debug("Exposed entities count: %d", len(exposed_entities))
                if exposed_entities:
                    _LOGGER.debug("First few exposed entities: %s", 
                                  [e["entity_id"] for e in exposed_entities[:5]])

                template_vars = {
                    "ha_name": ha_name,
                    "user_name": user_name,
                    "exposed_entities": exposed_entities,
                }
                _LOGGER.debug("Template variables: ha_name=%s, user_name=%s, entities_count=%d", 
                              ha_name, user_name, len(exposed_entities))
                
                system_prompt = template.Template(
                    system_prompt, self.hass
                ).async_render(template_vars, parse_result=False)
                
                _LOGGER.debug("Rendered system prompt length: %d characters", len(system_prompt))
                _LOGGER.debug("Rendered system prompt (first 500 chars): %s", system_prompt[:500])
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
