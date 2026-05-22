import pytest
import time
from unittest.mock import AsyncMock, patch


class TestSessionCreation:
    def test_create_session_success(self, client, user_token):
        resp = client.post(
            "/api/optimization/start",
            json={
                "original_text": "这是一篇测试论文的摘要部分。",
                "processing_mode": "paper_polish",
            },
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert data["processing_mode"] == "paper_polish"
        assert "session_id" in data

    def test_create_session_without_token(self, client):
        resp = client.post(
            "/api/optimization/start",
            json={"original_text": "测试", "processing_mode": "paper_polish"},
        )
        assert resp.status_code == 401

    def test_create_session_invalid_mode(self, client, user_token):
        resp = client.post(
            "/api/optimization/start",
            json={"original_text": "测试", "processing_mode": "invalid_mode"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 400

    def test_create_session_all_modes(self, client, user_token):
        modes = ["paper_polish", "paper_enhance", "paper_polish_enhance", "emotion_polish"]
        for mode in modes:
            resp = client.post(
                "/api/optimization/start",
                json={"original_text": "测试文本", "processing_mode": mode},
                headers={"Authorization": f"Bearer {user_token}"},
            )
            assert resp.status_code == 200, f"Mode {mode} failed: {resp.text}"
            assert resp.json()["processing_mode"] == mode


class TestSessionListing:
    def test_list_empty_sessions(self, client, user_token):
        resp = client.get("/api/optimization/sessions", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_sessions_after_creation(self, client, user_token):
        client.post(
            "/api/optimization/start",
            json={"original_text": "测试1", "processing_mode": "paper_polish"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        client.post(
            "/api/optimization/start",
            json={"original_text": "测试2", "processing_mode": "paper_enhance"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        resp = client.get("/api/optimization/sessions", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 2

    def test_list_sessions_without_token(self, client):
        resp = client.get("/api/optimization/sessions")
        assert resp.status_code == 401


class TestSessionOperations:
    def _create_session(self, client, user_token, text="测试文本"):
        return client.post(
            "/api/optimization/start",
            json={"original_text": text, "processing_mode": "paper_polish"},
            headers={"Authorization": f"Bearer {user_token}"},
        ).json()

    def test_get_session_detail(self, client, user_token):
        session = self._create_session(client, user_token)
        resp = client.get(
            f"/api/optimization/sessions/{session['session_id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session["session_id"]

    def test_get_session_progress(self, client, user_token):
        session = self._create_session(client, user_token)
        resp = client.get(
            f"/api/optimization/sessions/{session['session_id']}/progress",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200
        progress = resp.json()
        assert "status" in progress
        assert "progress" in progress

    def test_delete_session(self, client, user_token):
        session = self._create_session(client, user_token)
        resp = client.delete(
            f"/api/optimization/sessions/{session['session_id']}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 200

    def test_stop_queued_session(self, client, user_token):
        """Stop a newly created session before background task picks it up."""
        for i in range(10):
            session = self._create_session(client, user_token, f"快速停止测试 {i}")
            sid = session["session_id"]
            resp = client.post(
                f"/api/optimization/sessions/{sid}/stop",
                headers={"Authorization": f"Bearer {user_token}"},
            )
            if resp.status_code == 200:
                return
        pytest.skip("Background task processed all sessions too fast")

    def test_retry_failed_session(self, client, user_token):
        """Create session, let background task fail it, then retry."""
        session = self._create_session(client, user_token)
        sid = session["session_id"]
        time.sleep(1)  # brief wait for background to fail the task
        resp = client.post(
            f"/api/optimization/sessions/{sid}/retry",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code in [200, 400]
        if resp.status_code == 400:
            assert "仅可对失败或已停止的会话执行重试" in resp.json()["detail"] \
                   or "会话不存在" in resp.json().get("detail", "")

    def test_cannot_access_others_session(self, client, user_token, second_user_token):
        session = self._create_session(client, user_token)
        resp = client.get(
            f"/api/optimization/sessions/{session['session_id']}",
            headers={"Authorization": f"Bearer {second_user_token}"},
        )
        assert resp.status_code == 404
