"""Config flow for Better Shutters integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_BASE_COVER,
    CONF_SCHEDULE,
    DEFAULT_NAME,
    CONF_TIME,
    CONF_POSITION,
)

_LOGGER = logging.getLogger(__name__)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Verify that the selected cover exists
    entity_registry = er.async_get(hass)
    if not entity_registry.async_get(data[CONF_BASE_COVER]):
        raise ValueError("Selected cover does not exist")
    
    return {"title": data[CONF_NAME]}

class BetterShuttersConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Better Shutters."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BetterShuttersOptionsFlow:
        """Get the options flow for this handler."""
        return BetterShuttersOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                await self.async_set_unique_id(f"{DOMAIN}_{user_input[CONF_BASE_COVER]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except ValueError:
                errors["base"] = "invalid_cover"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Get all cover entities
        cover_entities = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="cover")
        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_BASE_COVER): cover_entities,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

class BetterShuttersOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.schedule_index = 0
        self.schedule = list(self.config_entry.options.get(CONF_SCHEDULE, []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_schedule()

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage schedule settings."""
        errors = {}

        if user_input is not None:
            if user_input.get("remove_entry") is not None:
                entry_index = user_input["remove_entry"]
                if 0 <= entry_index < len(self.schedule):
                    self.schedule.pop(entry_index)
            elif user_input.get(CONF_TIME) is not None:
                # Add new schedule entry
                new_entry = {
                    CONF_TIME: user_input[CONF_TIME],
                    CONF_POSITION: user_input[CONF_POSITION],
                }
                self.schedule.append(new_entry)

            if user_input.get("finish", False):
                return self.async_create_entry(
                    title="", data={CONF_SCHEDULE: self.schedule}
                )

        options_schema = {
            vol.Optional("remove_entry"): vol.In(
                {i: f"Remove {entry[CONF_TIME]} -> {entry[CONF_POSITION]}%" 
                 for i, entry in enumerate(self.schedule)}
            ),
            vol.Optional(CONF_TIME): selector.TimeSelector(),
            vol.Optional(CONF_POSITION): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    mode="slider",
                    unit_of_measurement="%"
                )
            ),
            vol.Optional("finish", default=False): bool,
        }

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(options_schema),
            errors=errors,
            description_placeholders={
                "current_schedule": "\n".join(
                    f"- {entry[CONF_TIME]} -> {entry[CONF_POSITION]}%"
                    for entry in self.schedule
                )
            },
        ) 