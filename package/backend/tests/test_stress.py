"""
暴力压力测试 — 直接测试 ConcurrencyManager，不依赖超时
"""
import asyncio
import pytest

from app.services.concurrency import ConcurrencyManager


async def _acquire_no_wait(mgr, session_id, user_id=None):
    """acquire 但不等待排队（如果没拿到就算 False）"""
    async with mgr._condition:
        if session_id in mgr.active_sessions:
            return True

        user_count = mgr.active_per_user.get(user_id, 0) if user_id is not None else 0
        can_acquire = (
            len(mgr.active_sessions) < mgr.max_concurrent
            and (user_id is None or user_count < mgr.max_per_user)
        )

        if can_acquire:
            mgr.active_sessions[session_id] = __import__('datetime').datetime.utcnow()
            if user_id is not None:
                mgr.active_per_user[user_id] = mgr.active_per_user.get(user_id, 0) + 1
                mgr._session_user[session_id] = user_id
            return True

        if session_id not in mgr.queue:
            mgr.queue.append(session_id)
            if user_id is not None:
                mgr._session_user[session_id] = user_id
        return False


@pytest.fixture
def mgr():
    m = ConcurrencyManager(max_concurrent=5)
    m.max_per_user = 1
    return m


class TestStressConcurrency:

    def test_first_acquires_second_queues(self, mgr):
        """第1个获取, 第2个排队"""
        async def run():
            r1 = await _acquire_no_wait(mgr, "s1", user_id=42)
            assert r1 == True, "First should acquire immediately"
            r2 = await _acquire_no_wait(mgr, "s2", user_id=42)
            assert r2 == False, "Second should queue"
            assert mgr.get_active_count() == 1
            assert len(mgr.queue) == 1
            assert mgr.active_per_user.get(42) == 1
        asyncio.run(run())

    def test_release_activates_queued_same_user(self, mgr):
        """释放后排队中的同用户任务被激活"""
        async def run():
            await _acquire_no_wait(mgr, "s1", user_id=42)
            await _acquire_no_wait(mgr, "s2", user_id=42)
            assert len(mgr.queue) == 1
            await mgr.release("s1")
            assert mgr.get_active_count() == 1
            assert len(mgr.queue) == 0
            assert mgr.active_per_user.get(42) == 1
        asyncio.run(run())

    def test_two_users_each_get_one_slot(self, mgr):
        """两个用户各自获取一个槽位"""
        async def run():
            r1 = await _acquire_no_wait(mgr, "a1", user_id=1)
            r2 = await _acquire_no_wait(mgr, "b1", user_id=2)
            assert r1 and r2, "Both should acquire"
            assert mgr.get_active_count() == 2
            assert mgr.active_per_user.get(1) == 1
            assert mgr.active_per_user.get(2) == 1
        asyncio.run(run())

    def test_three_different_users(self, mgr):
        """3个不同用户, per_user=1, 各1个槽位"""
        async def run():
            for i in range(3):
                assert await _acquire_no_wait(mgr, f"s{i}", user_id=i)
            assert mgr.get_active_count() == 3
            assert len(mgr.queue) == 0
        asyncio.run(run())

    def test_release_activates_queued_under_per_user_limit(self, mgr):
        """per_user=2时释放, 排队中同用户被激活"""
        async def run():
            mgr.max_per_user = 2
            await _acquire_no_wait(mgr, "s1", user_id=42)
            await _acquire_no_wait(mgr, "s2", user_id=42)
            assert await _acquire_no_wait(mgr, "s3", user_id=42) == False
            assert mgr.get_active_count() == 2
            await mgr.release("s1")
            assert mgr.get_active_count() == 2
            assert mgr.active_per_user.get(42) == 2
            assert len(mgr.queue) == 0
        asyncio.run(run())

    def test_release_blocks_if_same_user_at_limit(self, mgr):
        """per_user=1时释放一个, 排队中同用户不被激活（FIFO）"""
        async def run():
            await _acquire_no_wait(mgr, "a1", user_id=1)
            await _acquire_no_wait(mgr, "b1", user_id=2)
            await _acquire_no_wait(mgr, "a2", user_id=1)
            await _acquire_no_wait(mgr, "b2", user_id=2)
            assert mgr.get_active_count() == 2
            assert len(mgr.queue) == 2
            await mgr.release("b1")
            assert mgr.get_active_count() == 1
            assert len(mgr.queue) == 2
        asyncio.run(run())

    def test_high_frequency_no_leak(self, mgr):
        """高频acquire/release 100x, 无泄漏"""
        async def run():
            for _ in range(100):
                assert await _acquire_no_wait(mgr, "s", user_id=1)
                await mgr.release("s")
            assert mgr.get_active_count() == 0
            assert mgr.active_per_user.get(1, 0) == 0
        asyncio.run(run())

    def test_max_concurrent_global_limit(self, mgr):
        """max_concurrent=5, 10个不同用户, 仅5个能获取"""
        async def run():
            acquired = 0
            for i in range(10):
                if await _acquire_no_wait(mgr, f"s{i}", user_id=i):
                    acquired += 1
            assert acquired == 5
            assert mgr.get_active_count() == 5
            assert len(mgr.queue) == 5
        asyncio.run(run())

    def test_update_per_user_limit_at_runtime(self, mgr):
        """运行时修改 per_user 限制"""
        async def run():
            mgr.max_per_user = 3
            await _acquire_no_wait(mgr, "s1", user_id=1)
            await _acquire_no_wait(mgr, "s2", user_id=1)
            await _acquire_no_wait(mgr, "s3", user_id=1)
            await _acquire_no_wait(mgr, "s4", user_id=1)
            assert mgr.get_active_count() == 3
            mgr.max_per_user = 1
            assert mgr.get_active_count() == 3
            await mgr.release("s1")
            assert mgr.get_active_count() == 2
            assert mgr.active_per_user.get(1) == 2
        asyncio.run(run())

    def test_delete_queued_does_not_activate_other(self, mgr):
        """删除排队中的任务, 不应导致另一个排队任务被激活"""
        async def run():
            await _acquire_no_wait(mgr, "a1", user_id=1)
            await _acquire_no_wait(mgr, "a2", user_id=1)
            await _acquire_no_wait(mgr, "a3", user_id=1)
            assert mgr.get_active_count() == 1
            assert len(mgr.queue) == 2
            assert mgr.active_per_user.get(1) == 1
            await mgr.release("a2")
            assert mgr.get_active_count() == 1
            assert len(mgr.queue) == 1
            assert mgr.queue[0] == "a3"
            assert mgr.active_per_user.get(1) == 1
        asyncio.run(run())

    def test_release_nonexistent_session_is_safe(self, mgr):
        """释放不存在的 session 不报错, 状态不变"""
        async def run():
            await _acquire_no_wait(mgr, "s1", user_id=1)
            await _acquire_no_wait(mgr, "s2", user_id=1)
            await mgr.release("nonexistent")
            assert mgr.get_active_count() == 1
            assert mgr.active_per_user.get(1) == 1
        asyncio.run(run())

    def test_double_release_same_session(self, mgr):
        """对同一个活跃 session release 两次 → 第二次无影响"""
        async def run():
            await _acquire_no_wait(mgr, "s1", user_id=1)
            await mgr.release("s1")
            await mgr.release("s1")
            assert mgr.get_active_count() == 0
            assert mgr.active_per_user.get(1, 0) == 0
        asyncio.run(run())

    def test_boundary_max_concurrent_1(self, mgr):
        """max_concurrent=1 → 即使不同用户也排队"""
        async def run():
            mgr.max_concurrent = 1
            mgr.max_per_user = 1
            await _acquire_no_wait(mgr, "s1", user_id=1)
            r2 = await _acquire_no_wait(mgr, "s2", user_id=2)
            assert r2 == False
            assert mgr.get_active_count() == 1
            assert len(mgr.queue) == 1
        asyncio.run(run())

    def test_large_scale_1000_operations(self, mgr):
        """1000 次 acquire/release 循环, 无泄漏"""
        async def run():
            for i in range(1000):
                assert await _acquire_no_wait(mgr, "s", user_id=i % 10)
                await mgr.release("s")
            assert mgr.get_active_count() == 0
            assert len(mgr._session_user) == 0
        asyncio.run(run())

    def test_large_queue_100_sessions(self, mgr):
        """100 个排队后逐个释放, FIFO 正确"""
        async def run():
            for i in range(5):
                assert await _acquire_no_wait(mgr, f"a{i}", user_id=i)
            for i in range(100):
                await _acquire_no_wait(mgr, f"q{i}", user_id=i + 100)
            assert len(mgr.queue) == 100
            for i in range(5):
                await mgr.release(f"a{i}")
            assert mgr.get_active_count() == 5
            assert len(mgr.queue) == 95
        asyncio.run(run())

    def test_anonymous_session_not_limited_by_per_user(self, mgr):
        """user_id=None 的 session 不受 per_user 限制"""
        async def run():
            for i in range(5):
                assert await _acquire_no_wait(mgr, f"s{i}", user_id=None)
            assert mgr.get_active_count() == 5
        asyncio.run(run())
