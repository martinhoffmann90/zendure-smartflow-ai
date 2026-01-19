from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    STATUS_ENUMS,
    AI_STATUS_ENUMS,
    RECO_ENUMS,
    NEXT_ACTION_STATE_ENUMS,
    NEXT_PLANNED_ACTION_ENUMS,
)

PLANNING_STATUS_ENUMS = [
    "not_checked",
    "sensor_invalid",
    "planning_inactive_mode",
    "planning_blocked_soc_full",
    "planning_blocked_pv_surplus",
    "planning_no_price_now",
    "planning_no_price_data",
    "planning_no_peak_detected",
    "planning_peak_detected_insufficient_window",
    "planning_waiting_for_cheap_window",
    "planning_charge_now",
    "planning_last_chance",
]

@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    runtime_key: str

    def __post_init__(self):
        if not self.key:
            raise ValueError("SensorEntityDescription without key detected")

# ==================================================
# SENSOR DEFINITIONS
# ==================================================
SENSORS: tuple[ZendureSensorEntityDescription, ...] = (

    # --- Core status ---
    ZendureSensorEntityDescription(
        key="status",
        translation_key="status",
        runtime_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_ENUMS,
        icon="mdi:power-plug",
    ),
    ZendureSensorEntityDescription(
        key="ai_status",
        translation_key="ai_status",
        runtime_key="ai_status",
        device_class=SensorDeviceClass.ENUM,
        options=AI_STATUS_ENUMS,
        icon="mdi:robot",
    ),
    ZendureSensorEntityDescription(
        key="recommendation",
        translation_key="recommendation",
        runtime_key="recommendation",
        device_class=SensorDeviceClass.ENUM,
        options=RECO_ENUMS,
        icon="mdi:lightbulb-outline",
    ),

    # --- Realtime next action ---
    ZendureSensorEntityDescription(
        key="next_action_state",
        translation_key="next_action_state",
        runtime_key="next_action_state",
        device_class=SensorDeviceClass.ENUM,
        options=NEXT_ACTION_STATE_ENUMS,
        icon="mdi:clock-outline",
    ),
    ZendureSensorEntityDescription(
        key="next_action_time",
        translation_key="next_action_time",
        runtime_key="next_action_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-start",
    ),

    # --- Future planning (V1.4.0) ---
    ZendureSensorEntityDescription(
        key="next_planned_action",
        translation_key="next_planned_action",
        runtime_key="next_planned_action",
        device_class=SensorDeviceClass.ENUM,
        options=NEXT_PLANNED_ACTION_ENUMS,
        icon="mdi:calendar-clock",
    ),
    ZendureSensorEntityDescription(
        key="next_planned_action_time",
        translation_key="next_planned_action_time",
        runtime_key="next_planned_action_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-start",
    ),

    # --- Debug / reasoning ---
    ZendureSensorEntityDescription(
        key="decision_reason",
        translation_key="decision_reason",
        runtime_key="decision_reason",
        icon="mdi:head-question-outline",
    ),
    ZendureSensorEntityDescription(
        key="ai_debug",
        translation_key="ai_debug",
        runtime_key="debug",
        icon="mdi:bug",
    ),

    # --- Planning transparency ---
    ZendureSensorEntityDescription(
        key="planning_status",
        translation_key="planning_status",
        runtime_key="planning_status",
        device_class=SensorDeviceClass.ENUM,
        options=PLANNING_STATUS_ENUMS,
        icon="mdi:timeline-alert",
    ),
    ZendureSensorEntityDescription(
        key="planning_active",
        translation_key="planning_active",
        runtime_key="planning_active",
        icon="mdi:flash",
    ),
    ZendureSensorEntityDescription(
        key="planning_target_soc",
        translation_key="planning_target_soc",
        runtime_key="planning_target_soc",
        native_unit_of_measurement="%",
        icon="mdi:battery-high",
    ),
    ZendureSensorEntityDescription(
        key="planning_reason",
        translation_key="planning_reason",
        runtime_key="planning_reason",
        icon="mdi:text-long",
    ),

    # --- Energy / economics ---
    ZendureSensorEntityDescription(
        key="house_load",
        translation_key="house_load",
        runtime_key="house_load",
        native_unit_of_measurement="W",
        icon="mdi:home-lightning-bolt",
    ),
    ZendureSensorEntityDescription(
        key="price_now",
        translation_key="price_now",
        runtime_key="price_now",
        native_unit_of_measurement="€/kWh",
        icon="mdi:currency-eur",
    ),
    ZendureSensorEntityDescription(
        key="avg_charge_price",
        translation_key="avg_charge_price",
        runtime_key="avg_charge_price",
        native_unit_of_measurement="€/kWh",
        icon="mdi:scale-balance",
    ),
    ZendureSensorEntityDescription(
        key="profit_eur",
        translation_key="profit_eur",
        runtime_key="profit_eur",
        native_unit_of_measurement="€",
        icon="mdi:cash",
    ),
)

# ==================================================
# SETUP
# ==================================================
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_entities(ZendureSmartFlowSensor(entry, coordinator, d) for d in SENSORS)

# ==================================================
# SENSOR ENTITY
# ==================================================
class ZendureSmartFlowSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        description: ZendureSensorEntityDescription,
    ) -> None:
        self.entity_description = description
        self.coordinator = coordinator

        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        details = data.get("details") or {}
        key = self.entity_description.runtime_key

        if key in details:
            return details.get(key)

        return data.get(key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return data.get("details")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
