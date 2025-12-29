from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,

    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_EMERGENCY_SOC,
    SETTING_EMERGENCY_CHARGE_W,
    SETTING_PROFIT_MARGIN_PCT,

    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_EMERGENCY_CHARGE_W,
    DEFAULT_PROFIT_MARGIN_PCT,
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
        icon="mdi:battery-20",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_SOC_MAX,
        translation_key="soc_max",
        setting_key=SETTING_SOC_MAX,
        default_value=DEFAULT_SOC_MAX,
        icon="mdi:battery",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_CHARGE,
        translation_key="max_charge",
        setting_key=SETTING_MAX_CHARGE,
        default_value=DEFAULT_MAX_CHARGE,
        icon="mdi:flash",
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_MAX_DISCHARGE,
        translation_key="max_discharge",
        setting_key=SETTING_MAX_DISCHARGE,
        default_value=DEFAULT_MAX_DISCHARGE,
        icon="mdi:flash-outline",
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_PRICE_THRESHOLD,
        translation_key="price_threshold",
        setting_key=SETTING_PRICE_THRESHOLD,
        default_value=DEFAULT_PRICE_THRESHOLD,
        icon="mdi:currency-eur",
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        translation_key="very_expensive_threshold",
        setting_key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        default_value=DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        icon="mdi:currency-eur",
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_EMERGENCY_SOC,
        translation_key="emergency_soc",
        setting_key=SETTING_EMERGENCY_SOC,
        default_value=DEFAULT_EMERGENCY_SOC,
        icon="mdi:alert",
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_EMERGENCY_CHARGE_W,
        translation_key="emergency_charge_w",
        setting_key=SETTING_EMERGENCY_CHARGE_W,
        default_value=DEFAULT_EMERGENCY_CHARGE_W,
        icon="mdi:flash-alert",
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key=SETTING_PROFIT_MARGIN_PCT,
        translation_key="profit_margin_pct",
        setting_key=SETTING_PROFIT_MARGIN_PCT,
        default_value=DEFAULT_PROFIT_MARGIN_PCT,
        icon="mdi:percent",
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        native_unit_of_measurement="%",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_entities([ZendureSettingNumber(entry, coordinator, d) for d in NUMBERS])


class ZendureSettingNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureNumberEntityDescription) -> None:
        self.entity_description = description
        self.coordinator = coordinator
        self._entry = entry

        # stable entity_id pattern: number.zendure_smartflow_ai_<setting_key>
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

        self._attr_native_value = float(description.default_value)

    @property
    def available(self) -> bool:
        return True

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = float(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last = await self.async_get_last_state()
        if last and last.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = float(str(last.state).replace(",", "."))
            except Exception:
                pass

        self.async_write_ha_state()
