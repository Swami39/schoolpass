async def test_live(client) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers.get("x-request-id")
    assert response.json()["status"] == "ok"


async def test_ready(client) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
