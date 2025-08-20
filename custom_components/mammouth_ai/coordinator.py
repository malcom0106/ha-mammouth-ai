"""Data update coordinator for Mammouth AI."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

from .const import (API_CHAT_COMPLETIONS, CONF_API_KEY, CONF_BASE_URL,
                    CONF_ENABLE_MEMORY, CONF_MAX_MESSAGES, CONF_MEMORY_TIMEOUT,
                    CONF_MODEL, CONF_TIMEOUT, DEFAULT_ENABLE_MEMORY,
                    DEFAULT_MAX_MESSAGES, DEFAULT_MEMORY_TIMEOUT,
                    DEFAULT_TIMEOUT, DOMAIN, ERROR_AUTH, ERROR_CONNECT,
                    ERROR_TIMEOUT, ERROR_UNKNOWN)

_LOGGER = logging.getLogger(__name__)


class MammouthDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching data from Mammouth AI."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self._api_key = entry.data[CONF_API_KEY]
        self._base_url = entry.data[CONF_BASE_URL]
        self._model = entry.data[CONF_MODEL]
        self._timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

        # Configuration de la mémoire
        self._enable_memory = entry.options.get(
            CONF_ENABLE_MEMORY, DEFAULT_ENABLE_MEMORY
        )
        self._max_messages = entry.options.get(CONF_MAX_MESSAGES, DEFAULT_MAX_MESSAGES)
        self._memory_timeout = entry.options.get(
            CONF_MEMORY_TIMEOUT, DEFAULT_MEMORY_TIMEOUT
        )

        # Stockage de l'historique des conversations par utilisateur
        self._conversation_history: Dict[str, List[Dict[str, Any]]] = {}
        self._conversation_timestamps: Dict[str, datetime] = {}

        self._session = async_get_clientsession(hass)
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),  # Health check
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            return await self._async_health_check()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_validate_connection(self) -> bool:
        """Test if we can authenticate with the API."""
        try:
            await self._async_health_check()
            return True
        except Exception as err:
            _LOGGER.error("Connection validation failed: %s", err)
            raise

    async def _async_health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        url = f"{self._base_url.rstrip('/')}/models"

        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.get(url, headers=self._headers) as response:
                    if response.status == 401:
                        raise ConfigEntryAuthFailed(ERROR_AUTH)
                    if response.status != 200:
                        raise HomeAssistantError(f"HTTP {response.status}")

                    data = await response.json()
                    return {"status": "healthy", "models": data.get("data", [])}

        except asyncio.TimeoutError as err:
            raise HomeAssistantError(ERROR_TIMEOUT) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(ERROR_CONNECT) from err

    def _get_conversation_key(
        self, user_id: Optional[str] = None, conversation_id: Optional[str] = None
    ) -> str:
        """Generate conversation key."""
        # Pour maintenir une continuité de conversation par utilisateur,
        # nous utilisons uniquement l'user_id comme clé principale
        # Cela évite les interruptions de mémoire lors de nouvelles sessions
        key = user_id or "default"
        _LOGGER.debug(
            "Generated conversation key: %s (user_id=%s, conversation_id=%s)",
            key,
            user_id,
            conversation_id,
        )
        return key

    def _cleanup_expired_conversations(self) -> None:
        """Clean up expired conversation history."""
        if not self._enable_memory:
            return

        now = datetime.now()
        expired_keys = []

        for key, timestamp in self._conversation_timestamps.items():
            if (now - timestamp).total_seconds() > (self._memory_timeout * 3600):
                expired_keys.append(key)

        for key in expired_keys:
            self._conversation_history.pop(key, None)
            self._conversation_timestamps.pop(key, None)
            _LOGGER.debug("Expired conversation history for key: %s", key)

    def _truncate_conversation_history(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Truncate conversation history to max_messages preserving system message."""
        if len(messages) <= self._max_messages:
            return messages

        # Garder le message système (premier message)
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        other_messages = [msg for msg in messages if msg.get("role") != "system"]

        # Garder les derniers messages jusqu'à la limite
        if len(other_messages) > (self._max_messages - len(system_messages)):
            other_messages = other_messages[
                -(self._max_messages - len(system_messages)) :
            ]

        return system_messages + other_messages

    async def async_chat_completion_with_memory(
        self,
        messages: List[Dict[str, str]],
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Get chat completion from Mammouth AI with conversation memory."""
        _LOGGER.debug(
            "Memory enabled: %s, user_id: %s, conversation_id: %s",
            self._enable_memory,
            user_id,
            conversation_id,
        )

        if not self._enable_memory:
            _LOGGER.debug("Memory disabled, using direct chat completion")
            return await self.async_chat_completion(messages, **kwargs)

        # Nettoyer les conversations expirées
        self._cleanup_expired_conversations()

        # Générer la clé de conversation
        conv_key = self._get_conversation_key(user_id, conversation_id)

        # Récupérer l'historique existant
        if conv_key not in self._conversation_history:
            self._conversation_history[conv_key] = []
            _LOGGER.debug("Created new conversation history for key: %s", conv_key)
        else:
            _LOGGER.debug(
                "Found existing conversation history for key: %s with %d messages",
                conv_key,
                len(self._conversation_history[conv_key]),
            )

        # Ajouter les nouveaux messages à l'historique
        conversation_messages = self._conversation_history[conv_key].copy()

        # Ajouter ou mettre à jour le message système
        system_message = next(
            (msg for msg in messages if msg.get("role") == "system"), None
        )
        if system_message:
            # Supprimer l'ancien message système s'il existe
            conversation_messages = [
                msg for msg in conversation_messages if msg.get("role") != "system"
            ]
            # Insérer le nouveau message système au début
            conversation_messages.insert(0, system_message)

        # Ajouter le nouveau message utilisateur
        user_message = next(
            (msg for msg in messages if msg.get("role") == "user"), None
        )
        if user_message:
            conversation_messages.append(user_message)
            _LOGGER.debug(
                "Adding user message to conversation %s: %s",
                conv_key,
                (
                    user_message["content"][:100] + "..."
                    if len(user_message["content"]) > 100
                    else user_message["content"]
                ),
            )

        # Tronquer l'historique si nécessaire
        conversation_messages = self._truncate_conversation_history(
            conversation_messages
        )

        # Mettre à jour le timestamp
        self._conversation_timestamps[conv_key] = datetime.now()

        try:
            # Faire l'appel API avec l'historique complet
            response_text = await self.async_chat_completion(
                conversation_messages, **kwargs
            )

            # Ajouter la réponse à l'historique
            conversation_messages.append(
                {"role": "assistant", "content": response_text}
            )

            # Sauvegarder l'historique mis à jour
            self._conversation_history[conv_key] = self._truncate_conversation_history(
                conversation_messages
            )

            _LOGGER.debug(
                "Conversation history updated for key %s: %d messages",
                conv_key,
                len(self._conversation_history[conv_key]),
            )

            return response_text

        except Exception as err:
            _LOGGER.error("Chat completion with memory failed: %s", err)
            raise

    async def async_chat_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Get chat completion from Mammouth AI."""
        url = f"{self._base_url.rstrip('/')}/{API_CHAT_COMPLETIONS}"

        payload = {
            "model": self._model,
            "messages": messages,
            **kwargs,
        }

        try:
            async with async_timeout.timeout(self._timeout):
                async with self._session.post(
                    url, headers=self._headers, json=payload
                ) as response:
                    if response.status == 401:
                        raise ConfigEntryAuthFailed(ERROR_AUTH)
                    if response.status != 200:
                        text = await response.text()
                        raise HomeAssistantError(f"HTTP {response.status}: {text}")

                    data = await response.json()

                    if "choices" not in data or not data["choices"]:
                        raise HomeAssistantError("No response from AI")

                    return data["choices"][0]["message"]["content"]

        except asyncio.TimeoutError as err:
            raise HomeAssistantError(ERROR_TIMEOUT) from err
        except aiohttp.ClientError as err:
            raise HomeAssistantError(ERROR_CONNECT) from err
        except Exception as err:
            _LOGGER.error("Chat completion failed: %s", err)
            raise HomeAssistantError(ERROR_UNKNOWN) from err

    async def async_clear_conversation_memory(
        self, user_id: Optional[str] = None, conversation_id: Optional[str] = None
    ) -> None:
        """Clear conversation memory for a specific user/conversation."""
        conv_key = self._get_conversation_key(user_id, conversation_id)

        if conv_key in self._conversation_history:
            del self._conversation_history[conv_key]
            _LOGGER.debug("Cleared conversation history for key: %s", conv_key)

        if conv_key in self._conversation_timestamps:
            del self._conversation_timestamps[conv_key]

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        _LOGGER.debug("Shutting down Mammouth AI coordinator")
        # Vider la mémoire
        self._conversation_history.clear()
        self._conversation_timestamps.clear()
