import pytest


class TestUserLogin:
    def test_login_success(self, client, test_user):
        resp = client.post("/api/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == test_user["username"]

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/api/auth/login", json={
            "username": test_user["username"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "detail" in resp.json()

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, admin_token, test_user):
        resp = client.post("/api/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"],
        })
        user_id = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {resp.json()['access_token']}"
        }).json()["id"]

        client.patch(
            f"/api/admin/users/{user_id}/toggle",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        resp = client.post("/api/auth/login", json={
            "username": test_user["username"],
            "password": test_user["password"],
        })
        assert resp.status_code == 401


class TestGetMe:
    def test_get_me_with_valid_token(self, client, user_token):
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["is_active"] is True

    def test_get_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_with_invalid_token(self, client):
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid-token-here",
        })
        assert resp.status_code == 401


class TestAdminUserManagement:
    def test_create_single_user(self, client, admin_token):
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "alice", "password": "pass123", "display_name": "Alice"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_created"] == 1
        assert len(data["created"]) == 1
        assert data["created"][0]["username"] == "alice"

    def test_create_duplicate_user_is_skipped(self, client, admin_token, test_user):
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "testuser", "password": "pass123"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_created"] == 0
        assert "testuser" in data["skipped"]

    def test_create_batch_users(self, client, admin_token):
        users = [
            {"username": f"batch_user_{i}", "password": "pass"}
            for i in range(5)
        ]
        resp = client.post(
            "/api/admin/users/create",
            json=users,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_created"] == 5

    def test_create_users_without_admin_token(self, client):
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "hacker", "password": "pass"}],
        )
        assert resp.status_code == 401

    def test_list_users_includes_username(self, client, admin_token, test_user):
        resp = client.get("/api/admin/users", headers={
            "Authorization": f"Bearer {admin_token}",
        })
        assert resp.status_code == 200
        users = resp.json()
        usernames = [u["username"] for u in users if u.get("username")]
        assert "testuser" in usernames

    def test_admin_login_returns_token(self, client):
        resp = client.post("/api/admin/login", json={
            "username": "admin",
            "password": "admin123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_admin_login_wrong_password(self, client):
        resp = client.post("/api/admin/login", json={
            "username": "admin",
            "password": "wrong",
        })
        assert resp.status_code == 401
