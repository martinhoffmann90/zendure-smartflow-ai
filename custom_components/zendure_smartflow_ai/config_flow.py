from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import *


class ZendureSmartFlowAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Zendure SmartFlow AI",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOC_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PRICE_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_SOC_MIN, default=DEFAULTS[CONF_SOC_MIN]):
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=50,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                vol.Required(CONF_SOC_MAX, default=DEFAULTS[CONF_SOC_MAX]):
                    NumberSelector(
                        NumberSelectorConfig(
                            min=50,
                            max=100,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                vol.Required(CONF_MAX_CHARGE, default=DEFAULTS[CONF_MAX_CHARGE]):
                    NumberSelector(
                        NumberSelectorConfig(
                            min=100,
                            max=5000,
                            step=50,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="W",
                        )
                    ),
                vol.Required(CONF_MAX_DISCHARGE, default=DEFAULTS[CONF_MAX_DISCHARGE]):
                    NumberSelector(
                        NumberSelectorConfig(
                            min=100,
                            max=3000,
                            step=50,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="W",
                        )
                    ),
                vol.Required(CONF_EXPENSIVE, default=DEFAULTS[CONF_EXPENSIVE]):
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=1.0,
                            step=0.01,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="€/kWh",
                        )
                    ),
                vol.Required(CONF_EXTREME, default=DEFAULTS[CONF_EXTREME]):
                    NumberSelector(
                        NumberSelectorConfig(
                            min=0.1,
                            max=1.5,
                            step=0.01,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="€/kWh",
                        )
                    ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
