from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    # settings keys
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_PROFIT_MARGIN_PERCENT,
    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_PROFIT_MARGIN_PERCENT,
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    setting_key: str
    default_value: float


NUMBERS: tuple[ZendureNumberEntityDescription, ...] = (
    ZendureNumberEntityDescription(
        key=SETTING_SOC_MIN,
        translation_key="soc_min",
        setting_key=SETTING_SOC_MIN,
        default_value=DEFAULT_SOC_MIN,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        icon="mdi:battery-10",
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_SOC_MAX,
        translation_key="soc_max",
        setting_key=SETTING_SOC_MAX,
        default_value=DEFAULT_SOC_MAX,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        icon="mdi:battery-90",
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_CHARGE,
        translation_key="max_charge",
        setting_key=SETTING_MAX_CHARGE,
        default_value=DEFAULT_MAX_CHARGE,
        native_min_value=0,
        native_max_value=2400,
        native_step=10,
        icon="mdi:battery-charging",
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_DISCHARGE,
        translation_key="max_discharge",
        setting_key=SETTING_MAX_DISCHARGE,
        default_value=DEFAULT_MAX_DISCHARGE,
        native_min_value=0,
        native_max_value=2400,
        native_step=10,
        icon="mdi:battery-minus",
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        translation_key="very_expensive_threshold",
        setting_key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        default_value=DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        icon="mdi:currency-eur",
        native_unit_of_measurement="€/kWh",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_PROFIT_MARGIN_PERCENT,
        translation_key="profit_margin_percent",
        setting_key=SETTING_PROFIT_MARGIN_PERCENT,
        default_value=DEFAULT_PROFIT_MARGIN_PERCENT,
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        icon="mdi:percent",
        native_unit_of_measurement="%",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_entities(ZendureSmartFlowNumber(entry, coordinator, d) for d in NUMBERS)


class ZendureSmartFlowNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureNumberEntityDescription) -> None:
        self.entity_description = description
        self.coordinator = coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

        # store setting in coordinator runtime dict
        if "settings" not in coordinator.runtime_mode:
            coordinator.runtime_mode["settings"] = "__settings__"

        # use hass states as source of truth after creation, but we need initial value
        self._native_value = float(description.default_value)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        return self._native_value

    async def async_set_native_value(self, value: float) -> None:
        self._native_value = float(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        # Keep entity alive even if coordinator updates; numbers are local settings
        self.async_write_ha_state()
