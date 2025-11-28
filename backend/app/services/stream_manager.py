import asyncio
from typing import Dict, List, Any
import json
from asyncio import Queue

class StreamManager:
    """流式响应管理器"""
    
    def __init__(self):
        # session_id -> List[Queue]
        self.connections: Dict[str, List[Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, session_id: str) -> Queue:
        """建立连接"""
        async with self._lock:
            if session_id not in self.connections:
                self.connections[session_id] = []
            
            queue = Queue()
            self.connections[session_id].append(queue)
            return queue
    
    async def disconnect(self, session_id: str, queue: Queue):
        """断开连接"""
        async with self._lock:
            if session_id in self.connections:
                if queue in self.connections[session_id]:
                    self.connections[session_id].remove(queue)
                
                if not self.connections[session_id]:
                    del self.connections[session_id]

    async def broadcast(self, session_id: str, data: Dict[str, Any]):
        """广播消息给指定会话的所有连接"""
        # 不加锁以避免阻塞，只在读取连接列表时加锁（如果需要严格一致性，但这里为了性能可以放宽）
        # 使用副本进行迭代
        queues = []
        async with self._lock:
            if session_id in self.connections:
                queues = list(self.connections[session_id])
        
        if not queues:
            return

        message = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        for queue in queues:
            try:
                await queue.put(message)
            except Exception as e:
                print(f"Error pushing to queue: {e}")

# 全局实例
stream_manager = StreamManager()