from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,

    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,

    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,

    CONF_GRID_MODE,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,

    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
)


class ZendureSmartFlowAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow for Zendure SmartFlow AI"""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # ==================================================
    # STEP 1 – Basis-Setup
    # ==================================================
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data = dict(user_input)

            # Grid-Split → extra Schritt
            if user_input[CONF_GRID_MODE] == GRID_MODE_SPLIT:
                return await self.async_step_grid_split()

            # Single Grid → direkt fertig
            return self.async_create_entry(
                title="Zendure SmartFlow AI",
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PV_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_LOAD_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_PRICE_EXPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),

                vol.Required(CONF_AC_MODE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Required(CONF_INPUT_LIMIT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Required(CONF_OUTPUT_LIMIT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),

                vol.Required(CONF_GRID_MODE, default=GRID_MODE_SINGLE): selector.SelectSelector(
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
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    # ==================================================
    # STEP 2 – Grid Split (Import / Export)
    # ==================================================
    async def async_step_grid_split(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            return self.async_create_entry(
                title="Zendure SmartFlow AI",
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_GRID_IMPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_GRID_EXPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="grid_split",
            data_schema=schema,
            errors=errors,
        )
