import pytest

from schoolpass.notifications.constants import NOTIFICATION_TYPE_SCHOOL_ENTRY
from schoolpass.notifications.fcm import FcmHttpV1Provider, MemoryFcmCredentials, RecordingFcmTransport
from schoolpass.notifications.templates import render_notification, validate_template_placeholders


@pytest.mark.asyncio
async def test_fcm_request_minimal_data() -> None:
    transport = RecordingFcmTransport()
    provider = FcmHttpV1Provider(
        project_id="proj",
        credentials=MemoryFcmCredentials("secret-token"),
        transport=transport,
    )
    result = await provider.send_push(
        token="device-token",
        title="School entry",
        body="Your child has entered school.",
        data={"notification_id": "n1", "notification_type": NOTIFICATION_TYPE_SCHOOL_ENTRY},
    )
    assert result.ok
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["token"] == "device-token"
    assert "latitude" not in str(call["data"]).lower()
    assert call["has_auth"] is True


def test_template_rejects_unknown_placeholders() -> None:
    with pytest.raises(ValueError):
        validate_template_placeholders({"student_display_name", "<script>"})


def test_template_render_no_html() -> None:
    rendered = render_notification(NOTIFICATION_TYPE_SCHOOL_ENTRY, student_display_name="Alex")
    assert "<" not in rendered.body
