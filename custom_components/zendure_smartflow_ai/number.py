from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_FREEZE_SECONDS,
)
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class _NumSpec:
    key: str
    name: str
    unit: str | None
    min_value: float
    max_value: float
    step: float
    default: float
    getter: Callable[[ZendureSmartFlowCoordinator], float]
    setter: Callable[[ZendureSmartFlowCoordinator, float], None]


def _setattr(obj, key: str, val: float) -> None:
    setattr(obj, key, val)


NUMBERS: list[_NumSpec] = [
    _NumSpec(
        key="soc_min",
        name="SoC Minimum",
        unit="%",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        default=DEFAULT_SOC_MIN,
        getter=lambda c: float(c.soc_min),
        setter=lambda c, v: _setattr(c, "soc_min", float(v)),
    ),
    _NumSpec(
        key="soc_max",
        name="SoC Maximum",
        unit="%",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        default=DEFAULT_SOC_MAX,
        getter=lambda c: float(c.soc_max),
        setter=lambda c, v: _setattr(c, "soc_max", float(v)),
    ),
    _NumSpec(
        key="max_charge",
        name="Max Ladeleistung",
        unit="W",
        min_value=0.0,
        max_value=5000.0,
        step=1.0,
        default=DEFAULT_MAX_CHARGE,
        getter=lambda c: float(c.max_charge),
        setter=lambda c, v: _setattr(c, "max_charge", float(v)),
    ),
    _NumSpec(
        key="max_discharge",
        name="Max Entladeleistung",
        unit="W",
        min_value=0.0,
        max_value=5000.0,
        step=1.0,
        default=DEFAULT_MAX_DISCHARGE,
        getter=lambda c: float(c.max_discharge),
        setter=lambda c, v: _setattr(c, "max_discharge", float(v)),
    ),
    _NumSpec(
        key="expensive_threshold",
        name="Schwelle Teuer",
        unit="€/kWh",
        min_value=0.0,
        max_value=2.0,
        step=0.01,
        default=DEFAULT_EXPENSIVE_THRESHOLD,
        getter=lambda c: float(c.expensive_threshold),
        setter=lambda c, v: _setattr(c, "expensive_threshold", float(v)),
    ),
    _NumSpec(
        key="very_expensive_threshold",
        name="Schwelle Sehr teuer",
        unit="€/kWh",
        min_value=0.0,
        max_value=2.0,
        step=0.01,
        default=DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        getter=lambda c: float(c.very_expensive_threshold),
        setter=lambda c, v: _setattr(c, "very_expensive_threshold", float(v)),
    ),
    _NumSpec(
        key="freeze_seconds",
        name="Recommendation-Freeze",
        unit="s",
        min_value=0.0,
        max_value=600.0,
        step=1.0,
        default=float(DEFAULT_FREEZE_SECONDS),
        getter=lambda c: float(c.freeze_seconds),
        setter=lambda c, v: _setattr(c, "freeze_seconds", int(round(v, 0))),
    ),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSmartFlowAINumber(coordinator, entry, spec) for spec in NUMBERS])


class ZendureSmartFlowAINumber(CoordinatorEntity[ZendureSmartFlowCoordinator], NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, spec: _NumSpec) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._spec = spec

        self._attr_unique_id = f"{entry.entry_id}_{spec.key}"
        self._attr_name = spec.name

        self._attr_native_unit_of_measurement = spec.unit
        self._attr_native_min_value = spec.min_value
        self._attr_native_max_value = spec.max_value
        self._attr_native_step = spec.step

        # set default into coordinator (first boot)
        spec.setter(self.coordinator, spec.default)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="TK-Multimedia / Community",
            model="SmartFlow AI",
        )

    @property
    def native_value(self) -> float:
        return float(self._spec.getter(self.coordinator))

    async def async_set_native_value(self, value: float) -> None:
        self._spec.setter(self.coordinator, float(value))
        # No coordinator refresh needed; it applies next tick
        self.async_write_ha_state()
