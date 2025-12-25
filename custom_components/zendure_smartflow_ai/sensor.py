from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureAiStatusSensor(coordinator, entry),
            ZendureRecommendationSensor(coordinator, entry),
            ZendureDebugSensor(coordinator, entry),
            ZendureOnlineSensor(coordinator, entry),
        ],
        True,
    )


class _
