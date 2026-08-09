"""Adds config flow for LibreLink."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    LibreLinkAPI,
    LibreLinkAPIAuthenticationError,
    LibreLinkAPIConnectionError,
    LibreLinkAPIError,
)
from .const import BASE_URL_LIST, CONF_DISPLAY_NAME, CONF_PATIENT_ID, DOMAIN, LOGGER
from .units import UNITS_OF_MEASUREMENT


class LibreLinkFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for LibreLink."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                base_url = user_input[CONF_URL]

                client = LibreLinkAPI(
                    base_url=base_url, session=async_create_clientsession(self.hass)
                )
                await client.async_login(username, password)

                self.patients = await client.async_get_data()
                self.basic_info = user_input

                return await self.async_step_patient()
            except LibreLinkAPIAuthenticationError as e:
                LOGGER.warning(e)
                _errors["base"] = "auth"
            except LibreLinkAPIConnectionError as e:
                LOGGER.error(e)
                _errors["base"] = "connection"
            except LibreLinkAPIError as e:
                LOGGER.exception(e)
                _errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=(user_input or {}).get(CONF_USERNAME)
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT),
                    ),
                    vol.Required(
                        CONF_PASSWORD, default=(user_input or {}).get(CONF_PASSWORD)
                    ): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD),
                    ),
                    vol.Required(CONF_URL): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(label=k, value=v)
                                for k, v in BASE_URL_LIST.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
            errors=_errors,
            description_placeholders={
                "documentation_url": "https://github.com/dodog/librelink"
            },
        )

    async def async_step_patient(self, user_input=None):
        """Handle a flow to select specific patient."""
        if user_input is not None:
            user_input |= self.basic_info

            patient = {patient.id: patient for patient in self.patients}.get(
                user_input[CONF_PATIENT_ID]
            )

            # Optional nickname: if provided, used for the config entry title
            # instead of the patient's real name. Purely optional - if left
            # blank, behavior is identical to before this field existed.
            display_name = (user_input.get(CONF_DISPLAY_NAME) or "").strip()
            title_name = display_name or patient.name

            return self.async_create_entry(
                title=f"{title_name} (via {user_input[CONF_USERNAME]})",
                data=user_input,
            )

        return self.async_show_form(
            step_id="patient",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PATIENT_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=patient.id, label=patient.name)
                                for patient in self.patients
                            ]
                        )
                    ),
                    vol.Required(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                u.unit_of_measurement for u in UNITS_OF_MEASUREMENT
                            ]
                        )
                    ),
                    vol.Optional(CONF_DISPLAY_NAME): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT),
                    ),
                }
            ),
        )
