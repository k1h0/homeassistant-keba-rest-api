#!/usr/bin/env python3
"""Adds config flow for Keba."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from .api import (
    KebaRestIntegrationApiClient,
    KebaRestIntegrationApiClientAuthenticationError,
    KebaRestIntegrationApiClientCommunicationError,
    KebaRestIntegrationApiClientError,
)
from .const import DOMAIN, LOGGER


class KebaFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Keba."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                tokens = await self._test_credentials(
                    url=user_input[CONF_URL],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except KebaRestIntegrationApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except KebaRestIntegrationApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except KebaRestIntegrationApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    ## Do NOT use this in production code
                    ## The unique_id should never be something that can change
                    ## https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
                    unique_id=slugify(user_input[CONF_USERNAME])
                )
                self._abort_if_unique_id_configured()

                entry_data = {
                    CONF_URL: user_input[CONF_URL],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    "refreshToken": tokens.get("refreshToken"),
                }

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(CONF_URL, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def async_step_reauth(self, data: dict) -> config_entries.ConfigFlowResult:
        """Handle re-authentication."""
        # Store the data for use in the confirm step
        self._reauth_entry = data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Confirm re-authentication with credentials provided by the user."""
        errors = {}
        if user_input is not None:
            try:
                tokens = await self._test_credentials(
                    url=self._reauth_entry[CONF_URL],
                    username=self._reauth_entry[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except KebaRestIntegrationApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except KebaRestIntegrationApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except KebaRestIntegrationApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                # Update the existing config entry with the new password
                # and refresh token
                for entry in self._async_current_entries():
                    if entry.unique_id == slugify(self._reauth_entry[CONF_USERNAME]):
                        new_data = {
                            **entry.data,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            "refreshToken": tokens.get("refreshToken"),
                        }
                        self.hass.config_entries.async_update_entry(
                            entry, data=new_data
                        )
                        return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, url: str, username: str, password: str) -> dict:
        """Validate credentials by logging in with JWT and return tokens."""
        client = KebaRestIntegrationApiClient(
            url=url,
            username=username,
            password=password,
            session=async_create_clientsession(self.hass),
        )
        # Attempt JWT login to verify credentials and return tokens
        return await client.async_login_jwt(username=username, password=password)
