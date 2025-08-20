"""Config flow for Mammouth AI integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (CONF_BASE_URL, CONF_ENABLE_MEMORY, CONF_LLM_HASS_API,
                    CONF_MAX_MESSAGES, CONF_MAX_TOKENS, CONF_MEMORY_TIMEOUT,
                    CONF_MODEL, CONF_PROMPT, CONF_TEMPERATURE, CONF_TIMEOUT,
                    DEFAULT_BASE_URL, DEFAULT_ENABLE_MEMORY,
                    DEFAULT_MAX_MESSAGES, DEFAULT_MAX_TOKENS,
                    DEFAULT_MEMORY_TIMEOUT, DEFAULT_MODEL, DEFAULT_PROMPT,
                    DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT, DOMAIN)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_BASE_URL): str,
        vol.Optional(CONF_MODEL): str,
    }
)


class MammouthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mammouth AI."""

    VERSION = 1

    def is_matching(self, other_flow):
        """Return True if flow is for same device/entity."""
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        # Appliquer les valeurs par défaut
        if not user_input.get(CONF_BASE_URL):
            user_input[CONF_BASE_URL] = DEFAULT_BASE_URL
        if not user_input.get(CONF_MODEL):
            user_input[CONF_MODEL] = DEFAULT_MODEL

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Mammouth AI options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PROMPT,
                        default=self.config_entry.options.get(
                            CONF_PROMPT, DEFAULT_PROMPT
                        ),
                    ): str,
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=self.config_entry.options.get(
                            CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=self.config_entry.options.get(
                            CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                        ),
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_TIMEOUT, DEFAULT_TIMEOUT
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        default=self.config_entry.options.get(CONF_LLM_HASS_API, True),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_ENABLE_MEMORY,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_MEMORY, DEFAULT_ENABLE_MEMORY
                        ),
                    ): cv.boolean,
                    vol.Optional(
                        CONF_MAX_MESSAGES,
                        default=self.config_entry.options.get(
                            CONF_MAX_MESSAGES, DEFAULT_MAX_MESSAGES
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_MEMORY_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_MEMORY_TIMEOUT, DEFAULT_MEMORY_TIMEOUT
                        ),
                    ): cv.positive_int,
                }
            ),
        )


# Classes d'exception et fonction de validation (inchangées)
class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)

    headers = {
        "Authorization": f"Bearer {data[CONF_API_KEY]}",
        "Content-Type": "application/json",
    }

    try:
        async with session.get(
            f"{data[CONF_BASE_URL]}/models",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 401:
                raise InvalidAuth
            if response.status != 200:
                raise CannotConnect

    except aiohttp.ClientError as exc:
        raise CannotConnect from exc

    return {"title": "Mammouth AI"}
