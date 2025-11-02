import asyncio
from typing import Optional, Dict, List
from datetime import datetime
from app.config import settings


class ConcurrencyManager:
    """并发控制管理器"""
    
    def __init__(self, max_concurrent: int = None):
        self.max_concurrent = max_concurrent or settings.MAX_CONCURRENT_USERS
        self.active_sessions: Dict[str, datetime] = {}
        self.queue: List[str] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self, session_id: str) -> bool:
        """获取执行权限"""
        async with self._lock:
            # 如果已经在活跃会话中,直接返回
            if session_id in self.active_sessions:
                return True
            
            if len(self.active_sessions) < self.max_concurrent:
                self.active_sessions[session_id] = datetime.utcnow()
                return True

            if session_id not in self.queue:
                self.queue.append(session_id)
            return False
    
    async def release(self, session_id: str):
        """释放执行权限"""
        async with self._lock:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            self._activate_waiting_locked()
    
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
        async with self._lock:
            self.max_concurrent = max(1, new_limit)
            self._activate_waiting_locked()

    def _activate_waiting_locked(self):
        """尝试为等待队列中的会话分配执行权限 (需持有锁)"""
        while self.queue and len(self.active_sessions) < self.max_concurrent:
            next_session = self.queue.pop(0)
            self.active_sessions[next_session] = datetime.utcnow()


# 全局并发管理器实例
concurrency_manager = ConcurrencyManager()
