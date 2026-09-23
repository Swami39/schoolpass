"""Unit tests for the FCM push plumbing (no DB, no network).

Covers the pure FCM HTTP v1 helpers in
:mod:`schoolpass.notifications.fcm_real`: message payload construction,
response classification (including invalid-token pruning signals), and the
provider/transport wiring with in-memory doubles plus ``httpx`` mock
transports.
"""

from __future__ import annotations

import json

import httpx
import pytest

from schoolpass.notifications.fcm import FcmHttpV1Provider, MemoryFcmCredentials, RecordingFcmTransport
from schoolpass.notifications.fcm_real import (
    HttpxFcmTransport,
    build_fcm_message,
    classify_fcm_response,
)

pytestmark = pytest.mark.unit


def test_build_fcm_message_shape() -> None:
    message = build_fcm_message(
        token="device-token",
        title="Bus boarding",
        body="Aarav boarded the bus.",
        data={"notification_id": "abc", "notification_type": "bus_boarding"},
    )
    assert message["token"] == "device-token"
    assert message["notification"] == {"title": "Bus boarding", "body": "Aarav boarded the bus."}
    assert message["data"] == {"notification_id": "abc", "notification_type": "bus_boarding"}
    assert message["android"] == {"priority": "HIGH"}
    assert message["apns"]["payload"]["aps"] == {"sound": "default"}


def test_build_fcm_message_coerces_data_to_strings() -> None:
    message = build_fcm_message(token="t", title="t", body="b", data={"count": 3, "flag": True})  # type: ignore[dict-item]
    assert message["data"] == {"count": "3", "flag": "True"}
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in message["data"].items())


def test_classify_success_extracts_message_name() -> None:
    result = classify_fcm_response(200, {"name": "projects/demo/messages/abc123"})
    assert result.ok is True
    assert result.message_id == "projects/demo/messages/abc123"
    assert result.invalid_token is False


def test_classify_unregistered_token_is_prunable() -> None:
    payload = {
        "error": {
            "code": 404,
            "message": "Requested entity was not found.",
            "status": "NOT_FOUND",
            "details": [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}],
        }
    }
    result = classify_fcm_response(404, payload)
    assert result.ok is False
    assert result.invalid_token is True
    assert result.transient is False
    assert result.error_code == "fcm_invalid_token"


def test_classify_invalid_argument_token_is_prunable() -> None:
    payload = {"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "Invalid registration token"}}
    result = classify_fcm_response(400, payload)
    assert result.invalid_token is True
    assert result.transient is False


def test_classify_server_errors_are_transient() -> None:
    for status in (429, 500, 503):
        result = classify_fcm_response(status, {"error": {"code": status, "status": "UNAVAILABLE"}})
        assert result.ok is False
        assert result.transient is True
        assert result.invalid_token is False


def test_classify_auth_failure_is_not_transient() -> None:
    result = classify_fcm_response(401, {"error": {"code": 401, "status": "UNAUTHENTICATED"}})
    assert result.ok is False
    assert result.transient is False
    assert result.invalid_token is False


def test_classify_malformed_body_does_not_crash() -> None:
    result = classify_fcm_response(500, {"unexpected": [1, 2]})
    assert result.ok is False
    assert result.transient is True


async def test_provider_passes_access_token_to_transport() -> None:
    transport = RecordingFcmTransport()
    provider = FcmHttpV1Provider(
        project_id="demo-project",
        credentials=MemoryFcmCredentials(token="tok-123"),
        transport=transport,
    )
    result = await provider.send_push(
        token="device-token",
        title="Hi",
        body="Hello",
        data={"notification_id": "n1"},
    )
    assert result.ok is True
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["project_id"] == "demo-project"
    assert call["token"] == "device-token"
    assert call["title"] == "Hi"
    assert call["has_auth"] is True


def _mock_client(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_httpx_transport_success_posts_v1_url_and_body() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"name": "projects/demo-project/messages/msg-1"})

    transport = HttpxFcmTransport(client=_mock_client(handler))
    result = await transport.send(
        access_token="tok-123",
        project_id="demo-project",
        token="device-token",
        title="Hi",
        body="Hello",
        data={"notification_id": "n1"},
    )
    assert result.ok is True
    assert result.message_id == "projects/demo-project/messages/msg-1"
    assert seen["url"] == "https://fcm.googleapis.com/v1/projects/demo-project/messages:send"
    assert seen["auth"] == "Bearer tok-123"
    message = seen["body"]["message"]
    assert message["token"] == "device-token"
    assert message["notification"] == {"title": "Hi", "body": "Hello"}


async def test_httpx_transport_maps_unregistered_to_invalid_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": {"code": 404, "status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}},
        )

    transport = HttpxFcmTransport(client=_mock_client(handler))
    result = await transport.send(
        access_token="tok",
        project_id="demo-project",
        token="stale-token",
        title="Hi",
        body="Hello",
        data={},
    )
    assert result.ok is False
    assert result.invalid_token is True


async def test_httpx_transport_timeout_is_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    transport = HttpxFcmTransport(client=_mock_client(handler))
    result = await transport.send(
        access_token="tok",
        project_id="demo-project",
        token="device-token",
        title="Hi",
        body="Hello",
        data={},
    )
    assert result.ok is False
    assert result.transient is True
    assert result.error_code == "fcm_timeout"
