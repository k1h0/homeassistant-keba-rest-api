#!/usr/bin/env python3
"""Sample API Client."""

from __future__ import annotations

import socket
import ssl
from typing import Any

import aiohttp  # type: ignore[import]
import async_timeout  # type: ignore[import]

# Default request timeout in seconds
_DEFAULT_REQUEST_TIMEOUT = 10


class KebaRestIntegrationApiClientError(Exception):
    """Exception to indicate a general API error."""


class KebaRestIntegrationApiClientCommunicationError(
    KebaRestIntegrationApiClientError,
):
    """Exception to indicate a communication error."""


class KebaRestIntegrationApiClientAuthenticationError(
    KebaRestIntegrationApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise KebaRestIntegrationApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class KebaRestIntegrationApiClient:
    """Sample API Client with JWT support for login and refresh."""

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._url = url.removesuffix("/")
        self._username = username
        self._password = password
        self._session = session

        # Tokens obtained via /v2/jwt/login and /v2/jwt/refresh
        self._accessToken: str | None = None
        self._refreshToken: str | None = None

    async def async_get_all_wallboxes(self) -> Any:
        """Get all wallboxes from the API using the access token if available."""
        return await self._api_wrapper(
            method="get",
            url=self._url + "/v2/wallboxes",
        )

    async def async_get_wallbox(self, serial_number: str) -> Any:
        """Get complete wallbox information from the API using the access token."""
        return await self._api_wrapper(
            method="get",
            url=self._url + "/v2/wallboxes/" + serial_number,
        )

    async def async_set_wallbox_start_charging(self, serial_number: str) -> Any:
        """Set data on the API using the access token if available."""
        return await self._api_wrapper(
            method="post",
            url=self._url + "/v2/wallboxes/" + serial_number + "/start-charging",
        )

    async def async_set_wallbox_stop_charging(self, serial_number: str) -> Any:
        """Set data on the API using the access token if available."""
        return await self._api_wrapper(
            method="post",
            url=self._url + "/v2/wallboxes/" + serial_number + "/stop-charging",
        )

    async def async_login_jwt(
        self, username: str | None = None, password: str | None = None
    ) -> dict:
        """
        Login with username/password and store access and refresh tokens.

        If username/password are not provided, falls back to values given at init.
        Raises KebaRestIntegrationApiClientAuthenticationError on auth failure.
        Returns a dict with 'accessToken' and 'refreshToken'.
        """
        body = {
            "username": username or self._username,
            "password": password or self._password,
        }
        resp = await self._api_wrapper(
            method="post",
            url=self._url + "/v2/jwt/login",
            data=body,
            include_auth=False,
        )

        # Expect accessToken and refreshToken in response
        access = resp.get("accessToken") if isinstance(resp, dict) else None
        refresh = resp.get("refreshToken") if isinstance(resp, dict) else None
        if not access or not refresh:
            msg = "Login did not return accessToken and refreshToken"
            raise KebaRestIntegrationApiClientAuthenticationError(msg, resp)

        self._accessToken = access
        self._refreshToken = refresh
        return {"accessToken": access, "refreshToken": refresh}

    def set_refresh_token(self, token: str | None) -> None:
        """Set the refresh token on the client (used when loading persisted token)."""
        self._refreshToken = token

    def get_refresh_token(self) -> str | None:
        """Get currently stored refresh token (may be None)."""
        return self._refreshToken

    async def async_refresh_jwt(self) -> str:
        """
        Refresh the access token using the stored refresh token.

        Returns the new access token. Raises KebaRestIntegrationApiClientError
        if no refresh token is available or the refresh fails.
        """
        if not self._refreshToken:
            msg = "No refresh token available"
            raise KebaRestIntegrationApiClientError(msg)

        headers = {"Authorization": f"Bearer {self._refreshToken}"}
        resp = await self._api_wrapper(
            method="post",
            url=self._url + "/v2/jwt/refresh",
            headers=headers,
            include_auth=False,
        )

        access = resp.get("accessToken") if isinstance(resp, dict) else None
        if not access:
            msg = "Refresh did not return new accessToken"
            raise KebaRestIntegrationApiClientError(msg)

        self._accessToken = access
        return access

    async def _perform_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        """
        Perform a single request.

        Retries once with SSL verification disabled on certificate
        verification failures (equivalent to `curl --insecure`).
        """
        try:
            async with async_timeout.timeout(_DEFAULT_REQUEST_TIMEOUT):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()
        except KebaRestIntegrationApiClientAuthenticationError:
            # Propagate authentication errors to be handled by caller
            raise
        except TimeoutError:
            # Propagate timeout to be handled by caller
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # If this looks like a certificate verification failure, retry insecure once
            exc_name = exc.__class__.__name__
            exc_str = str(exc).lower()
            is_cert_error = (
                isinstance(exc, ssl.SSLCertVerificationError)
                or exc_name == "ClientConnectorCertificateError"
                or "certificate" in exc_str
                or "certificate verify failed" in exc_str
            )

            if is_cert_error:
                try:
                    async with async_timeout.timeout(_DEFAULT_REQUEST_TIMEOUT):
                        response = await self._session.request(
                            method=method,
                            url=url,
                            headers=headers,
                            json=data,
                            ssl=False,
                        )
                        _verify_response_or_raise(response)
                        return await response.json()
                except Exception as exc2:
                    msg2 = (
                        f"Error fetching information using insecure SSL mode - {exc2}"
                    )
                    raise KebaRestIntegrationApiClientCommunicationError(msg2) from exc2

            # Non-SSL-related client errors
            if isinstance(exc, (aiohttp.ClientError, socket.gaierror)):
                msg = f"Error fetching information - {exc}"
                raise KebaRestIntegrationApiClientCommunicationError(msg) from exc

            # Re-raise anything else so outer handler can manage it
            raise

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        *,
        data: dict | None = None,
        headers: dict | None = None,
        include_auth: bool = True,
    ) -> Any:
        """
        Get information from the API.

        Adds Authorization header automatically if an access token is present
        and include_auth is True. For login and refresh calls, callers should
        set include_auth=False so we do not attach an access token.
        """
        try:
            req_headers = dict(headers or {})
            if (
                include_auth
                and self._accessToken
                and "Authorization" not in req_headers
            ):
                req_headers["Authorization"] = f"Bearer {self._accessToken}"

            # Perform the request (includes a single insecure retry on cert failures)
            return await self._perform_request(
                method,
                url,
                headers=req_headers,
                data=data,
            )

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise KebaRestIntegrationApiClientCommunicationError(
                msg,
            ) from exception
        except KebaRestIntegrationApiClientAuthenticationError:
            # If we have a refresh token, attempt to refresh and retry the request once
            if include_auth and self._refreshToken:
                await self.async_refresh_jwt()

                # Retry the original request with refreshed access token
                req_headers = dict(headers or {})
                if self._accessToken and "Authorization" not in req_headers:
                    req_headers["Authorization"] = f"Bearer {self._accessToken}"

                return await self._perform_request(
                    method,
                    url,
                    headers=req_headers,
                    data=data,
                )

            # No refresh available or not applicable; re-raise
            raise
        except TypeError as exception:
            # Handle resolver TypeError (aiodns/pycares mismatch)
            msg = f"Communication error during DNS resolution - {exception}"
            raise KebaRestIntegrationApiClientCommunicationError(msg) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise KebaRestIntegrationApiClientError(
                msg,
            ) from exception
