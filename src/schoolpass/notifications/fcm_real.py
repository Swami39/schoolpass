"""Real FCM HTTP v1 transport and Google service-account credentials.

Production implementations of the ``FcmCredentials`` and ``FcmTransport``
protocols from :mod:`schoolpass.notifications.fcm`:

- :class:`GoogleServiceAccountCredentials` mints OAuth2 access tokens from a
  Firebase service-account JSON key via ``google-auth``.
- :class:`HttpxFcmTransport` delivers messages through the FCM HTTP v1 REST
  API via ``httpx``.

Pure helpers (:func:`build_fcm_message`, :func:`classify_fcm_response`) are
kept free of I/O so they can be unit-tested without network or database.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from schoolpass.notifications.fcm import FcmSendResult

FCM_MESSAGING_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_FCM_SEND_TEMPLATE = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
_TOKEN_REFRESH_MARGIN = timedelta(minutes=5)


def build_fcm_message(
    *,
    token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> dict[str, Any]:
    """Build the ``message`` object for an FCM HTTP v1 ``messages:send`` call.

    ``data`` values are coerced to ``str`` (FCM requires a string map).
    Title/body ride in ``notification`` so the OS shows a tray notification
    even when the app is killed; ``data`` carries routing info for the app.
    """
    return {
        "token": token,
        "notification": {"title": title, "body": body},
        "data": {str(key): str(value) for key, value in data.items()},
        "android": {"priority": "HIGH"},
        "apns": {"payload": {"aps": {"sound": "default"}}},
    }


def _extract_error_text(status_code: int, payload: dict[str, Any]) -> str:
    """Best-effort upper-cased text from an FCM HTTP v1 error body."""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    parts: list[str] = [str(error.get("status") or ""), str(error.get("message") or "")]
    details = error.get("details")
    if isinstance(details, list):
        for detail in details:
            if isinstance(detail, dict) and isinstance(detail.get("errorCode"), str):
                parts.append(str(detail["errorCode"]))
    return " ".join(parts).upper()


def classify_fcm_error(status_code: int, payload: dict[str, Any]) -> FcmSendResult:
    """Map an FCM HTTP v1 error response onto an :class:`FcmSendResult`.

    ``UNREGISTERED``/``INVALID_ARGUMENT`` mark the token invalid so delivery
    prunes it. 429/5xx are transient; 401/403 are configuration errors.
    """
    text = _extract_error_text(status_code, payload)
    if "UNREGISTERED" in text or "INVALID_ARGUMENT" in text:
        return FcmSendResult(
            ok=False,
            error_code="fcm_invalid_token",
            transient=False,
            invalid_token=True,
        )
    if status_code == 429 or 500 <= status_code < 600:
        return FcmSendResult(ok=False, error_code=f"fcm_http_{status_code}", transient=True)
    return FcmSendResult(ok=False, error_code=f"fcm_http_{status_code}", transient=False)


def classify_fcm_response(status_code: int, payload: dict[str, Any]) -> FcmSendResult:
    """Map any FCM HTTP v1 response (success or error) onto a result."""
    if 200 <= status_code < 300:
        name = payload.get("name")
        return FcmSendResult(ok=True, message_id=str(name) if name is not None else None)
    return classify_fcm_error(status_code, payload)


class GoogleServiceAccountCredentials:
    """Mint FCM access tokens from a service-account JSON key file.

    Tokens are cached until shortly before expiry so the (synchronous)
    ``google-auth`` refresh runs off the event loop only when needed.
    """

    def __init__(self, *, service_account_file: str) -> None:
        self._service_account_file = service_account_file
        self._credentials: Any = None

    def _load(self) -> Any:
        if self._credentials is None:
            from google.oauth2 import service_account

            self._credentials = service_account.Credentials.from_service_account_file(
                self._service_account_file,
                scopes=[FCM_MESSAGING_SCOPE],
            )
        return self._credentials

    def _needs_refresh(self) -> bool:
        creds = self._load()
        if not creds.valid:
            return True
        expiry = creds.expiry
        if expiry is None:
            return False
        now = datetime.now(UTC)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry - now < _TOKEN_REFRESH_MARGIN

    async def access_token(self) -> str:
        if self._needs_refresh():
            from google.auth.transport.requests import Request

            creds = self._load()
            await asyncio.to_thread(creds.refresh, Request())
        token = self._load().token
        if not token:
            raise RuntimeError("FCM service-account refresh did not yield an access token")
        return str(token)


class HttpxFcmTransport:
    """Deliver FCM HTTP v1 messages with ``httpx``."""

    def __init__(self, *, client: httpx.AsyncClient | None = None, timeout_seconds: float = 10.0) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def send(
        self,
        *,
        access_token: str,
        project_id: str,
        token: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> FcmSendResult:
        url = _FCM_SEND_TEMPLATE.format(project_id=project_id)
        message = build_fcm_message(token=token, title=title, body=body, data=data)
        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"message": message},
                )
            except httpx.TimeoutException:
                return FcmSendResult(ok=False, error_code="fcm_timeout", transient=True)
            except httpx.TransportError:
                return FcmSendResult(ok=False, error_code="fcm_transport_error", transient=True)
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            return classify_fcm_response(response.status_code, payload)
        finally:
            if owned:
                await client.aclose()
