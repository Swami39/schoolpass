from uuid import uuid4

import pytest
from sqlalchemy import func, select

from schoolpass.db.session import apply_tenant_context
from schoolpass.notifications.constants import NOTIFICATION_TYPE_SCHOOL_EXIT
from schoolpass.notifications.models import Notification
from schoolpass.notifications.preferences import set_push_preference
from schoolpass.notifications.service import build_idempotency_key, create_notification_with_outbox
from schoolpass.tenancy.context import TenantContext


@pytest.mark.asyncio
async def test_disabled_push_still_creates_notification(db_factory, student_world) -> None:
    tenant_id = student_world["tenant_a"]
    recipient = student_world["user_a"]
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=recipient),
            )
            await set_push_preference(
                session,
                tenant_id=tenant_id,
                user_id=recipient,
                notification_type=NOTIFICATION_TYPE_SCHOOL_EXIT,
                push_enabled=False,
            )
            await create_notification_with_outbox(
                session,
                tenant_id=tenant_id,
                recipient_user_id=recipient,
                notification_type=NOTIFICATION_TYPE_SCHOOL_EXIT,
                title="Exit",
                body="Left",
                payload={"student_id": str(student_world["a_student_id"])},
                idempotency_key=build_idempotency_key(
                    notification_type=NOTIFICATION_TYPE_SCHOOL_EXIT,
                    reference_id=uuid4(),
                    recipient_user_id=recipient,
                ),
            )
            count = (await session.execute(select(func.count()).select_from(Notification))).scalar_one()
    assert count == 1
