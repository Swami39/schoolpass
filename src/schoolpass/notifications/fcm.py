from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FcmSendResult:
    ok: bool
    message_id: str | None = None
    error_code: str | None = None
    transient: bool = False
    invalid_token: bool = False


class FcmCredentials(Protocol):
    async def access_token(self) -> str: ...


class FcmTransport(Protocol):
    async def send(
        self,
        *,
        access_token: str,
        project_id: str,
        token: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> FcmSendResult: ...


class MemoryFcmCredentials:
    def __init__(self, token: str = "test-access-token") -> None:
        self._token = token

    async def access_token(self) -> str:
        return self._token


class RecordingFcmTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._results: dict[str, FcmSendResult] = {}

    def set_result_for_token(self, token: str, result: FcmSendResult) -> None:
        self._results[token] = result

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
        self.calls.append(
            {
                "project_id": project_id,
                "token": token,
                "title": title,
                "body": body,
                "data": data,
                "has_auth": bool(access_token),
            }
        )
        return self._results.get(token, FcmSendResult(ok=True, message_id=f"msg-{len(self.calls)}"))


class DisabledFcmTransport:
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
        del access_token, project_id, token, title, body, data
        return FcmSendResult(ok=False, error_code="fcm_not_configured", transient=True)


class FcmHttpV1Provider:
    def __init__(
        self,
        *,
        project_id: str,
        credentials: FcmCredentials,
        transport: FcmTransport,
    ) -> None:
        self._project_id = project_id
        self._credentials = credentials
        self._transport = transport

    async def send_push(
        self,
        *,
        token: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> FcmSendResult:
        access = await self._credentials.access_token()
        return await self._transport.send(
            access_token=access,
            project_id=self._project_id,
            token=token,
            title=title,
            body=body,
            data=data,
        )
