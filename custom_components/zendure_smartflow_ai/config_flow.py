from __future__ import annotations

import voluptuous as vol
from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector, entity_registry as er

from .const import *


def _find_first_entity(
    hass: HomeAssistant,
    domain: str,
):
    reg = er.async_get(hass)
    for ent in reg.entities.values():
        if ent.domain == domain:
            return ent.entity_id
    return None


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title="Zendure SmartFlow AI",
                data=user_input,
            )

        hass = self.hass

        # sinnvolle Vorschläge (nur grob!)
        soc_guess = _find_first_entity(hass, "sensor")
        pv_guess = _find_first_entity(hass, "sensor")
        load_guess = _find_first_entity(hass, "sensor")
        price_export_guess = _find_first_entity(hass, "sensor")

        schema = vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY, default=soc_guess):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Required(CONF_PV_ENTITY, default=pv_guess):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Required(CONF_LOAD_ENTITY, default=load_guess):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                # 🔥 WICHTIG: Tibber Diagramm-Datenexport
                vol.Required(CONF_PRICE_EXPORT_ENTITY, default=price_export_guess):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Required(CONF_AC_MODE_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="select")
                    ),

                vol.Required(CONF_GRID_MODE, default=GRID_MODE_SINGLE):
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {
                                    "value": GRID_MODE_SINGLE,
                                    "label": "Ein Sensor (Bezug + / Einspeisung −)"
                                },
                                {
                                    "value": GRID_MODE_SPLIT,
                                    "label": "Zwei Sensoren (Bezug und Einspeisung getrennt)"
                                },
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),

                vol.Optional(CONF_GRID_POWER_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Optional(CONF_GRID_IMPORT_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Optional(CONF_GRID_EXPORT_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
