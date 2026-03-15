"""HTTP client for ZeroClaw gateway API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    ENDPOINT_HEALTH,
    ENDPOINT_PAIR,
    ENDPOINT_STATUS,
    ENDPOINT_WEBHOOK,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT_DEFAULT = aiohttp.ClientTimeout(total=30)
TIMEOUT_WEBHOOK = aiohttp.ClientTimeout(total=120)


class ZeroClawConnectionError(Exception):
    """Error connecting to ZeroClaw gateway."""


class ZeroClawAuthError(Exception):
    """Authentication error (invalid or missing token)."""


class ZeroClawApiError(Exception):
    """General API error from gateway."""


class ZeroClawApiClient:
    """Client for ZeroClaw gateway HTTP API."""

    def __init__(
        self,
        host: str,
        port: int,
        token: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._token = token
        self._session = session
        self._base_url = f"http://{host}:{port}"

    def _headers(self, auth: bool = True) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def async_pair(self, pairing_code: str) -> str:
        """Exchange pairing code for Bearer token. Returns the token."""
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self._base_url}{ENDPOINT_PAIR}",
                headers={"X-Pairing-Code": pairing_code},
                timeout=TIMEOUT_DEFAULT,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err

        if resp.status == 403:
            raise ZeroClawAuthError("Invalid pairing code")
        if resp.status == 429:
            raise ZeroClawApiError("Too many pairing attempts, try later")
        resp.raise_for_status()

        data = await resp.json()
        self._token = data["token"]
        return data["token"]

    async def async_get_health(self) -> dict[str, Any]:
        """GET /health — no auth required."""
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self._base_url}{ENDPOINT_HEALTH}",
                timeout=TIMEOUT_DEFAULT,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err
        resp.raise_for_status()
        return await resp.json()

    async def async_get_status(self) -> dict[str, Any]:
        """GET /api/status — requires auth."""
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self._base_url}{ENDPOINT_STATUS}",
                headers=self._headers(),
                timeout=TIMEOUT_DEFAULT,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err
        if resp.status == 401:
            raise ZeroClawAuthError("Invalid or expired token")
        resp.raise_for_status()
        return await resp.json()

    async def async_send_message(self, message: str) -> dict[str, Any]:
        """POST /webhook — send message, get LLM response."""
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self._base_url}{ENDPOINT_WEBHOOK}",
                headers=self._headers(),
                json={"message": message},
                timeout=TIMEOUT_WEBHOOK,
            )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ZeroClawConnectionError(
                f"Cannot connect to ZeroClaw at {self._base_url}"
            ) from err
        if resp.status == 401:
            raise ZeroClawAuthError("Invalid or expired token")
        resp.raise_for_status()
        return await resp.json()

    async def async_close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
