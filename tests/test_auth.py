async def test_password_login_and_me(client, world) -> None:
    response = await client.post(
        "/api/v1/auth/password/login",
        json={"identifier": world["email_a"], "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == world["email_a"]
    assert me.json()["tenant_id"] == str(world["tenant_a"])


async def test_password_login_rejects_bad_password(client, world) -> None:
    response = await client.post(
        "/api/v1/auth/password/login",
        json={"identifier": world["email_a"], "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_refresh_rotation(client, world) -> None:
    login = await client.post(
        "/api/v1/auth/password/login",
        json={"identifier": world["email_a"], "password": "correct-horse-battery"},
    )
    first = login.json()["refresh_token"]
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401


async def test_staff_list_is_tenant_scoped(client, world) -> None:
    login_a = await client.post(
        "/api/v1/auth/password/login",
        json={"identifier": world["email_a"], "password": "correct-horse-battery"},
    )
    login_b = await client.post(
        "/api/v1/auth/password/login",
        json={"identifier": world["email_b"], "password": "correct-horse-battery"},
    )
    staff_a = await client.get(
        "/api/v1/staff",
        headers={"Authorization": f"Bearer {login_a.json()['access_token']}"},
    )
    staff_b = await client.get(
        "/api/v1/staff",
        headers={"Authorization": f"Bearer {login_b.json()['access_token']}"},
    )
    assert staff_a.status_code == 200
    ids_a = {item["user_id"] for item in staff_a.json()["items"]}
    ids_b = {item["user_id"] for item in staff_b.json()["items"]}
    assert str(world["user_a"]) in ids_a
    assert str(world["user_b"]) not in ids_a
    assert str(world["user_b"]) in ids_b
    assert str(world["user_a"]) not in ids_b


async def test_unauthenticated_staff_forbidden(client) -> None:
    response = await client.get("/api/v1/staff")
    assert response.status_code == 401
