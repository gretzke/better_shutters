"""Cover platform for Better Shutters."""
from datetime import datetime
import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.const import (
    CONF_NAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_BASE_COVER,
    CONF_SCHEDULE,
    CONF_TIME,
    CONF_POSITION,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCHEDULE_ENTRY = vol.Schema({
    vol.Required(CONF_TIME): cv.time,
    vol.Required(CONF_POSITION): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
})

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_BASE_COVER): cv.entity_id,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_SCHEDULE): vol.All(cv.ensure_list, [SCHEDULE_ENTRY]),
    }
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Better Shutters cover from config entry."""
    config = config_entry.data
    name = config[CONF_NAME]
    base_cover = config[CONF_BASE_COVER]
    schedule = config_entry.options.get(CONF_SCHEDULE, [])

    async_add_entities([BetterShutterCover(hass, name, base_cover, schedule)])

class BetterShutterCover(CoverEntity):
    """Representation of a Better Shutter cover."""

    def __init__(self, hass, name, base_cover, schedule):
        """Initialize the cover."""
        self._hass = hass
        self._name = name
        self._base_cover = base_cover
        self._schedule = schedule
        self._attr_unique_id = f"{DOMAIN}_{base_cover}"
        self._attr_supported_features = None
        
        # Schedule the updates
        for entry in schedule:
            self._schedule_update(entry)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the cover."""
        base_cover = self._hass.states.get(self._base_cover)
        return base_cover.attributes.get("device_class") if base_cover else None

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._attr_supported_features is None:
            base_cover = self._hass.states.get(self._base_cover)
            if base_cover:
                self._attr_supported_features = base_cover.attributes.get("supported_features", 0)
        return self._attr_supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        state = self._hass.states.get(self._base_cover)
        return state.state == STATE_CLOSED if state else None

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        state = self._hass.states.get(self._base_cover)
        return state.attributes.get(ATTR_POSITION) if state else None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._hass.services.async_call(
            "cover", "open_cover", {"entity_id": self._base_cover}
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._hass.services.async_call(
            "cover", "close_cover", {"entity_id": self._base_cover}
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            await self._hass.services.async_call(
                "cover",
                "set_cover_position",
                {"entity_id": self._base_cover, "position": kwargs[ATTR_POSITION]},
            )

    def _schedule_update(self, entry):
        """Schedule an update based on time."""
        time = entry[CONF_TIME]
        position = entry[CONF_POSITION]
        
        # Calculate the next time this should run
        now = datetime.now()
        scheduled_time = now.replace(
            hour=time.hour, minute=time.minute, second=0, microsecond=0
        )
        
        # If the time has passed for today, schedule for tomorrow
        if scheduled_time <= now:
            scheduled_time = scheduled_time.replace(day=scheduled_time.day + 1)

        # Schedule the update
        self._hass.helpers.event.async_track_point_in_time(
            self._handle_schedule,
            scheduled_time,
        )

    async def _handle_schedule(self, now):
        """Handle scheduled updates."""
        for entry in self._schedule:
            if entry[CONF_TIME].hour == now.hour and entry[CONF_TIME].minute == now.minute:
                await self.async_set_cover_position(position=entry[CONF_POSITION])
                # Reschedule for tomorrow
                self._schedule_update(entry)
                break 