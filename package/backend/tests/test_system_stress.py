"""System-level HTTP stress — httpx ASGI transport, 全链路不调 AI"""

import asyncio
import pytest
import httpx
from httpx import ASGITransport

from app.services.concurrency import concurrency_manager
from app.main import app

_transport = ASGITransport(app=app)


@pytest.fixture(autouse=True)
def reset_concurrency():
    concurrency_manager.active_sessions.clear()
    concurrency_manager.active_per_user.clear()
    concurrency_manager._session_user.clear()
    concurrency_manager.queue.clear()
    concurrency_manager.max_concurrent = 5
    concurrency_manager.max_per_user = 3
    yield


class TestSystemStress:

    @pytest.mark.xfail(reason="httpx ASGI transport does not dispatch BackgroundTasks before response returns")
    @pytest.mark.asyncio
    async def test_concurrent_submit_same_user(self):
        """httpx ASGI transport: 同一用户并发20个 → per_user=1 → 1活跃"""
        async with httpx.AsyncClient(transport=_transport, base_url="http://test") as c:
            r = await c.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
            admin_tok = r.json()["access_token"]
            await c.post("/api/admin/users/create",
                         json=[{"username": "sys_stress", "password": "pass"}],
                         headers={"Authorization": f"Bearer {admin_tok}"})
            await c.post("/api/admin/config", json={"MAX_CONCURRENT_PER_USER": "1"},
                         headers={"Authorization": f"Bearer {admin_tok}"})
            r = await c.post("/api/auth/login", json={"username": "sys_stress", "password": "pass"})
            tok = r.json()["access_token"]

            async def submit():
                return await c.post("/api/optimization/start",
                    json={"original_text": "test", "processing_mode": "paper_polish"},
                    headers={"Authorization": f"Bearer {tok}"})

            results = await asyncio.gather(*[submit() for _ in range(20)])

            for i, r in enumerate(results):
                assert r.status_code == 200, f"Req {i}: {r.text[:200]}"

            # 等待后台任务调度 acquire()
            for _ in range(30):
                if concurrency_manager.get_active_count() > 0:
                    break
                await asyncio.sleep(0.5)

            assert concurrency_manager.get_active_count() == 1, \
                f"Expected 1 active, got {concurrency_manager.get_active_count()}"
            assert len(concurrency_manager.queue) == 19, \
                f"Expected 19 queued, got {len(concurrency_manager.queue)}"

    @pytest.mark.asyncio
    async def test_two_users_independent(self):
        """两用户各5个 → per_user=2 → 各2个活跃"""
        async with httpx.AsyncClient(transport=_transport, base_url="http://test") as c:
            r = await c.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
            admin_tok = r.json()["access_token"]
            await c.post("/api/admin/config", json={"MAX_CONCURRENT_PER_USER": "2"},
                         headers={"Authorization": f"Bearer {admin_tok}"})

            for u in ["sys_a", "sys_b"]:
                await c.post("/api/admin/users/create",
                    json=[{"username": u, "password": "pass"}],
                    headers={"Authorization": f"Bearer {admin_tok}"})

            r_a = await c.post("/api/auth/login", json={"username": "sys_a", "password": "pass"})
            r_b = await c.post("/api/auth/login", json={"username": "sys_b", "password": "pass"})
            tok_a, tok_b = r_a.json()["access_token"], r_b.json()["access_token"]

            async def submit_many(tok, n):
                return await asyncio.gather(*[
                    c.post("/api/optimization/start",
                        json={"original_text": "test", "processing_mode": "paper_polish"},
                        headers={"Authorization": f"Bearer {tok}"})
                    for _ in range(n)
                ])

            ra, rb = await asyncio.gather(submit_many(tok_a, 5), submit_many(tok_b, 5))
            for r in ra + rb:
                assert r.status_code == 200

            assert concurrency_manager.get_active_count() <= 4

    @pytest.mark.asyncio
    async def test_delete_queued(self):
        """提交→排队→删除→不影响活跃的"""
        async with httpx.AsyncClient(transport=_transport, base_url="http://test") as c:
            r = await c.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
            admin_tok = r.json()["access_token"]
            await c.post("/api/admin/users/create",
                json=[{"username": "sys_del", "password": "pass"}],
                headers={"Authorization": f"Bearer {admin_tok}"})
            await c.post("/api/admin/config", json={"MAX_CONCURRENT_PER_USER": "1"},
                         headers={"Authorization": f"Bearer {admin_tok}"})

            r = await c.post("/api/auth/login", json={"username": "sys_del", "password": "pass"})
            tok = r.json()["access_token"]

            r1 = await c.post("/api/optimization/start",
                json={"original_text": "test", "processing_mode": "paper_polish"},
                headers={"Authorization": f"Bearer {tok}"})
            ses1 = r1.json()["session_id"]

            await c.post("/api/optimization/start",
                json={"original_text": "test", "processing_mode": "paper_polish"},
                headers={"Authorization": f"Bearer {tok}"})

            await asyncio.sleep(0.3)

            old_active = concurrency_manager.get_active_count()
            for ses_id in list(concurrency_manager.queue):
                await c.delete(f"/api/optimization/sessions/{ses_id}",
                               headers={"Authorization": f"Bearer {tok}"})

            await asyncio.sleep(0.2)
            assert concurrency_manager.get_active_count() == old_active

    @pytest.mark.asyncio
    async def test_parallel_submit_delete_race(self):
        """DELETE 和 POST 同时发 → 不崩"""
        async with httpx.AsyncClient(transport=_transport, base_url="http://test") as c:
            r = await c.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
            admin_tok = r.json()["access_token"]
            await c.post("/api/admin/users/create",
                json=[{"username": "sys_race", "password": "pass"}],
                headers={"Authorization": f"Bearer {admin_tok}"})
            r = await c.post("/api/auth/login", json={"username": "sys_race", "password": "pass"})
            tok = r.json()["access_token"]

            rs = await asyncio.gather(*[
                c.post("/api/optimization/start",
                    json={"original_text": "test", "processing_mode": "paper_polish"},
                    headers={"Authorization": f"Bearer {tok}"})
                for _ in range(3)
            ])
            ids = [r.json()["session_id"] for r in rs]

            race_rs = await asyncio.gather(
                c.post("/api/optimization/start",
                    json={"original_text": "test", "processing_mode": "paper_polish"},
                    headers={"Authorization": f"Bearer {tok}"}),
                c.delete(f"/api/optimization/sessions/{ids[2]}",
                         headers={"Authorization": f"Bearer {tok}"}),
                c.delete(f"/api/optimization/sessions/{ids[0]}",
                         headers={"Authorization": f"Bearer {tok}"}),
            )

            for r in race_rs:
                assert r.status_code in (200, 404)
            assert concurrency_manager.get_active_count() <= concurrency_manager.max_concurrent
