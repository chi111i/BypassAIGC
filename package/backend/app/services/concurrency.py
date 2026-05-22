import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from app.config import settings

# 等待并发权限的最大超时时间（秒）
ACQUIRE_TIMEOUT = 3600  # 1小时


class ConcurrencyManager:
    """并发控制管理器"""
    
    def __init__(self, max_concurrent: int = None):
        self.max_concurrent = max_concurrent or settings.MAX_CONCURRENT_USERS
        self.max_per_user = settings.MAX_CONCURRENT_PER_USER
        self.active_sessions: Dict[str, datetime] = {}
        self.active_per_user: Dict[int, int] = {}
        self._session_user: Dict[str, int] = {}  # session_id -> user_id
        self.queue: List[str] = []
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
    
    async def acquire(self, session_id: str, user_id: int = None, timeout: float = ACQUIRE_TIMEOUT) -> bool:
        """获取执行权限
        
        Args:
            session_id: 会话ID
            user_id: 用户ID（用于每用户并发控制）
            timeout: 等待超时时间（秒），默认1小时
            
        Returns:
            True if acquired, False if timed out or removed from queue
        """
        async with self._condition:
            if session_id in self.active_sessions:
                return True
            
            user_count = self.active_per_user.get(user_id, 0) if user_id is not None else 0
            can_acquire = (
                len(self.active_sessions) < self.max_concurrent
                and (user_id is None or user_count < self.max_per_user)
            )
            
            if can_acquire:
                self.active_sessions[session_id] = datetime.utcnow()
                if user_id is not None:
                    self.active_per_user[user_id] = self.active_per_user.get(user_id, 0) + 1
                    self._session_user[session_id] = user_id
                return True

            if session_id not in self.queue:
                self.queue.append(session_id)
                if user_id is not None:
                    self._session_user[session_id] = user_id
            
            start_time = datetime.utcnow()
            while session_id not in self.active_sessions and session_id in self.queue:
                try:
                    remaining_timeout = timeout - (datetime.utcnow() - start_time).total_seconds()
                    if remaining_timeout <= 0:
                        if session_id in self.queue:
                            self.queue.remove(session_id)
                        return False
                    await asyncio.wait_for(self._condition.wait(), timeout=min(remaining_timeout, 60))
                except asyncio.TimeoutError:
                    continue
            
            return session_id in self.active_sessions
    
    async def release(self, session_id: str):
        """释放执行权限"""
        async with self._condition:
            was_active = session_id in self.active_sessions
            user_id = self._session_user.pop(session_id, None)
            if user_id is not None and was_active:
                count = self.active_per_user.get(user_id, 0) - 1
                if count <= 0:
                    self.active_per_user.pop(user_id, None)
                else:
                    self.active_per_user[user_id] = count
            if was_active:
                del self.active_sessions[session_id]
            if session_id in self.queue:
                self.queue.remove(session_id)
            if was_active:
                self._activate_waiting_locked()
                self._condition.notify_all()
    
    async def get_status(self, session_id: Optional[str] = None) -> Dict:
        """获取队列状态"""
        async with self._lock:
            current_users = len(self.active_sessions)
            queue_list = list(self.queue)
            
            status = {
                "current_users": current_users,
                "max_users": self.max_concurrent,
                "queue_length": len(queue_list),
                "your_position": None,
                "estimated_wait_time": None
            }
            
            if session_id and session_id in queue_list:
                position = queue_list.index(session_id) + 1
                status["your_position"] = position
                # 估算等待时间(假设每个任务平均5分钟)
                status["estimated_wait_time"] = position * 300
            
            return status
    
    def is_active(self, session_id: str) -> bool:
        """检查会话是否活跃"""
        return session_id in self.active_sessions
    
    def get_active_count(self) -> int:
        """获取活跃会话数量"""
        return len(self.active_sessions)

    async def update_limit(self, new_limit: int):
        """更新并发限制"""
        async with self._condition:
            self.max_concurrent = max(1, new_limit)
            self._activate_waiting_locked()
            self._condition.notify_all()  # 唤醒所有等待者以检查新的限制

    async def update_per_user_limit(self, new_limit: int):
        """更新每用户并发限制"""
        async with self._condition:
            self.max_per_user = max(1, new_limit)
            # 检查当前活跃用户是否超过新限制
            for user_id in list(self.active_per_user.keys()):
                if self.active_per_user[user_id] > self.max_per_user:
                    # 用户超过限制，保留 max_per_user 个，多余的标记为可释放
                    pass  # 等待队列中的后续 session 会被 _activate_waiting_locked 的 per_user 检查挡住
            self._activate_waiting_locked()
            self._condition.notify_all()

    def _activate_waiting_locked(self):
        """尝试为等待队列中的会话分配执行权限 (需持有锁)"""
        while self.queue and len(self.active_sessions) < self.max_concurrent:
            next_session = self.queue[0]
            user_id = self._session_user.get(next_session)
            if user_id is not None and self.active_per_user.get(user_id, 0) >= self.max_per_user:
                break  # 此用户已达上限，跳过
            self.queue.pop(0)
            self.active_sessions[next_session] = datetime.utcnow()
            if user_id is not None:
                self._session_user[next_session] = user_id
                self.active_per_user[user_id] = self.active_per_user.get(user_id, 0) + 1


# 全局并发管理器实例
concurrency_manager = ConcurrencyManager()
