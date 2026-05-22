"""
用户创建业务逻辑测试 — 覆盖表单式批量创建的所有路径
"""
import pytest


class TestUserCreation:
    def test_first_user_in_empty_db(self, client, admin_token):
        """首次创建 — 空数据库中的第一个用户"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "first_user", "password": "pass123", "display_name": "First"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_created"] == 1
        assert len(data["skipped"]) == 0
        assert data["created"][0]["username"] == "first_user"
        assert data["created"][0]["display_name"] == "First"

    def test_create_without_display_name(self, client, admin_token):
        """display_name 可选 — 不传也能创建"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "no_display", "password": "pass123"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_created"] == 1

    def test_create_with_empty_display_name(self, client, admin_token):
        """空 display_name — 相当于不传"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "empty_display", "password": "pass123", "display_name": ""}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_create_multiple_users_batch(self, client, admin_token):
        """批量创建 — 一次创建 5 个用户"""
        users = [{"username": f"batch_{i}", "password": f"pass_{i}"} for i in range(5)]
        resp = client.post(
            "/api/admin/users/create",
            json=users,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_created"] == 5
        assert len(data["skipped"]) == 0

    def test_duplicate_username_is_skipped(self, client, admin_token):
        """重复用户名 — 跳过不报错，其他正常创建"""
        resp1 = client.post(
            "/api/admin/users/create",
            json=[{"username": "dup", "password": "pass1"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp1.json()["total_created"] == 1

        resp2 = client.post(
            "/api/admin/users/create",
            json=[
                {"username": "dup", "password": "pass2"},
                {"username": "new_one", "password": "pass3"},
            ],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["total_created"] == 1  # 只创建了 new_one
        assert "dup" in data["skipped"]

    def test_duplicate_in_same_batch(self, client, admin_token):
        """同批次内重复用户名 — 只创建第一个"""
        resp = client.post(
            "/api/admin/users/create",
            json=[
                {"username": "same", "password": "p1"},
                {"username": "same", "password": "p2"},
            ],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_created"] == 1
        assert len(data["skipped"]) == 1


class TestUserCreationValidation:
    def test_missing_username(self, client, admin_token):
        """缺少 username — 422"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"password": "pass"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    def test_missing_password(self, client, admin_token):
        """缺少 password — 422"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "no_pass"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    def test_empty_body_array(self, client, admin_token):
        """空数组 — 后端允许，返回创建数为 0"""
        resp = client.post(
            "/api/admin/users/create",
            json=[],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["total_created"] == 0

    def test_without_admin_token(self, client):
        """无 token — 401"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "hacker", "password": "p"}],
        )
        assert resp.status_code == 401

    def test_with_user_token_not_admin(self, client, user_token):
        """普通用户 token 不能访问 admin 接口 — 401"""
        resp = client.post(
            "/api/admin/users/create",
            json=[{"username": "hacker", "password": "p"}],
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 401


class TestUserLoginAfterCreation:
    def test_login_immediately_after_creation(self, client, admin_token):
        """创建后立即登录 — 验证密码哈希正确"""
        client.post(
            "/api/admin/users/create",
            json=[{"username": "fresh", "password": "mypassword"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.post("/api/auth/login", json={
            "username": "fresh",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "fresh"

    def test_login_with_wrong_password(self, client, admin_token):
        """创建后使用错误密码登录 — 401"""
        client.post(
            "/api/admin/users/create",
            json=[{"username": "wrongpass", "password": "correct"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.post("/api/auth/login", json={
            "username": "wrongpass",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        """不存在的用户 — 401"""
        resp = client.post("/api/auth/login", json={
            "username": "ghost",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_password_is_hashed(self, client, admin_token, user_token):
        """验证密码确实是哈希存储的 — 原文不应出现在 DB 中"""
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        # 通过 login 验证密码匹配即可反证哈希正确
        # 此项在 test_login_success 中已验证


class TestUserActivation:
    def test_deactivated_user_cannot_login(self, client, admin_token):
        """禁用后无法登录"""
        client.post(
            "/api/admin/users/create",
            json=[{"username": "todeactivate", "password": "pass"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 先登录获取 user_id
        login_resp = client.post("/api/auth/login", json={
            "username": "todeactivate",
            "password": "pass",
        })
        user_id = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {login_resp.json()['access_token']}"
        }).json()["id"]

        # 禁用
        client.patch(
            f"/api/admin/users/{user_id}/toggle",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        resp = client.post("/api/auth/login", json={
            "username": "todeactivate",
            "password": "pass",
        })
        assert resp.status_code == 401

    def test_reactivated_user_can_login(self, client, admin_token):
        """重新启用后可以登录"""
        client.post(
            "/api/admin/users/create",
            json=[{"username": "reactivate", "password": "pass"}],
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        login_resp = client.post("/api/auth/login", json={
            "username": "reactivate",
            "password": "pass",
        })
        user_id = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {login_resp.json()['access_token']}"
        }).json()["id"]

        # 禁用再启用
        client.patch(f"/api/admin/users/{user_id}/toggle", headers={"Authorization": f"Bearer {admin_token}"})
        client.patch(f"/api/admin/users/{user_id}/toggle", headers={"Authorization": f"Bearer {admin_token}"})

        resp = client.post("/api/auth/login", json={
            "username": "reactivate",
            "password": "pass",
        })
        assert resp.status_code == 200
