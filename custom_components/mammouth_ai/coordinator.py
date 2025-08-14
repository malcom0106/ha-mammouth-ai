"""Data update coordinator for Mammouth AI."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, List

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    API_CHAT_COMPLETIONS,
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_MODEL,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    ERROR_AUTH,
    ERROR_CONNECT,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
)

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
                        raise Exception(ERROR_AUTH)
                    elif response.status != 200:
                        raise Exception(f"HTTP {response.status}")
                    
                    data = await response.json()
                    return {"status": "healthy", "models": data.get("data", [])}
                    
        except asyncio.TimeoutError as err:
            raise Exception(ERROR_TIMEOUT) from err
        except aiohttp.ClientError as err:
            raise Exception(ERROR_CONNECT) from err

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
                    url, 
                    headers=self._headers, 
                    json=payload
                ) as response:
                    if response.status == 401:
                        raise Exception(ERROR_AUTH)
                    elif response.status != 200:
                        text = await response.text()
                        raise Exception(f"HTTP {response.status}: {text}")
                    
                    data = await response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        raise Exception("No response from AI")
                    
                    return data["choices"][0]["message"]["content"]
                    
        except asyncio.TimeoutError as err:
            raise Exception(ERROR_TIMEOUT) from err
        except aiohttp.ClientError as err:
            raise Exception(ERROR_CONNECT) from err
        except Exception as err:
            _LOGGER.error("Chat completion failed: %s", err)
            raise Exception(ERROR_UNKNOWN) from err

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        _LOGGER.debug("Shutting down Mammouth AI coordinator")
        # Cleanup if needed

