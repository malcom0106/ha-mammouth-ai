"""The Mammouth AI integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MammouthDataUpdateCoordinator

PLATFORMS = ["conversation"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mammouth AI from a config entry."""
    _LOGGER.debug("Setting up Mammouth AI integration")

    coordinator = MammouthDataUpdateCoordinator(hass, entry)

    # Test de connexion initial
    try:
        await coordinator.async_validate_connection()
    except Exception as err:
        _LOGGER.error("Failed to connect to Mammouth AI: %s", err)
        raise ConfigEntryNotReady(f"Unable to connect to Mammouth AI: {err}") from err

    # Stockage du coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Écouter les changements d'options
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _LOGGER.info("Mammouth AI integration setup completed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Mammouth AI integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Nettoyer les données
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator and hasattr(coordinator, "async_shutdown"):
            await coordinator.async_shutdown()

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options changes."""
    await hass.config_entries.async_reload(entry.entry_id)
