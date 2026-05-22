import pytest
from unittest.mock import AsyncMock, patch
import asyncio


class TestPerUserConcurrency:
    def _create_session(self, client, token, text="测试文本"):
        return client.post(
            "/api/optimization/start",
            json={"original_text": text, "processing_mode": "paper_polish"},
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_multiple_sessions_same_user_allowed(self, client, user_token):
        r1 = self._create_session(client, user_token, "文本1")
        r2 = self._create_session(client, user_token, "文本2")
        r3 = self._create_session(client, user_token, "文本3")
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

    def test_multiple_users_independent(self, client, user_token, second_user_token):
        r1 = self._create_session(client, user_token, "用户1文本")
        r2 = self._create_session(client, second_user_token, "用户2文本")
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_concurrent_submissions_same_user(self, client, user_token):
        for i in range(5):
            r = self._create_session(client, user_token, f"并行测试 {i}")
            assert r.status_code == 200, f"Submission {i} failed: {r.text}"

    def test_queue_status_endpoint(self, client, user_token):
        resp = client.get("/api/optimization/status", headers={
            "Authorization": f"Bearer {user_token}",
        })
        assert resp.status_code == 200
        status = resp.json()
        assert "current_users" in status
        assert "max_users" in status
        assert "queue_length" in status
        assert status["max_users"] == 5


class TestConcurrencyManagerUnit:
    @pytest.fixture
    def cm(self):
        from app.services.concurrency import ConcurrencyManager
        return ConcurrencyManager(max_concurrent=3)

    @pytest.mark.asyncio
    async def test_acquire_basic(self, cm):
        acquired = await cm.acquire("session_1", user_id=1)
        assert acquired is True
        assert cm.is_active("session_1")
        assert cm.get_active_count() == 1

    @pytest.mark.asyncio
    async def test_acquire_up_to_max(self, cm):
        for i in range(3):
            acquired = await cm.acquire(f"session_{i}", user_id=1)
            assert acquired is True
        assert cm.get_active_count() == 3

    @pytest.mark.asyncio
    async def test_acquire_exceeds_max_queues(self, cm):
        for i in range(3):
            await cm.acquire(f"session_{i}", user_id=1)
        acquired = await cm.acquire("session_4", user_id=1, timeout=0.1)
        assert acquired is False
        assert cm.get_active_count() == 3

    @pytest.mark.asyncio
    async def test_release_allows_next(self, cm):
        for i in range(3):
            await cm.acquire(f"session_{i}", user_id=1)
        await cm.release("session_0")
        assert cm.get_active_count() == 2
        acquired = await cm.acquire("session_4", user_id=1)
        assert acquired is True
        assert cm.get_active_count() == 3

    @pytest.mark.asyncio
    async def test_per_user_limit(self, cm):
        cm.max_per_user = 2
        await cm.acquire("s1", user_id=1)
        await cm.acquire("s2", user_id=1)
        acquired = await cm.acquire("s3", user_id=1, timeout=0.1)
        assert acquired is False

    @pytest.mark.asyncio
    async def test_per_user_limit_independent(self, cm):
        cm.max_per_user = 2
        await cm.acquire("s1", user_id=1)
        await cm.acquire("s2", user_id=1)
        acquired = await cm.acquire("s3", user_id=2)
        assert acquired is True

    @pytest.mark.asyncio
    async def test_release_decrements_per_user(self, cm):
        cm.max_per_user = 2
        await cm.acquire("s1", user_id=1)
        await cm.acquire("s2", user_id=1)
        await cm.release("s1")
        acquired = await cm.acquire("s3", user_id=1)
        assert acquired is True

    @pytest.mark.asyncio
    async def test_update_limit(self, cm):
        await cm.update_limit(10)
        assert cm.max_concurrent == 10

    @pytest.mark.asyncio
    async def test_acquire_same_session_idempotent(self, cm):
        await cm.acquire("session_1", user_id=1)
        acquired = await cm.acquire("session_1", user_id=1)
        assert acquired is True
        assert cm.get_active_count() == 1
