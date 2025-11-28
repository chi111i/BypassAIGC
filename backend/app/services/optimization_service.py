import json
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    OptimizationSession, OptimizationSegment, 
    SessionHistory, ChangeLog
)
from app.services.ai_service import (
    AIService, split_text_into_segments,
    count_chinese_characters, count_text_length, get_default_polish_prompt,
    get_default_enhance_prompt, get_emotion_polish_prompt, get_compression_prompt
)
from app.services.concurrency import concurrency_manager
from app.services.stream_manager import stream_manager
from app.config import settings
from starlette.concurrency import run_in_threadpool


class OptimizationService:
    """优化处理服务"""
    
    def __init__(self, db: Session, session_obj: OptimizationSession):
        self.db = db
        self.session_obj = session_obj
        self.polish_service: Optional[AIService] = None
        self.enhance_service: Optional[AIService] = None
        self.emotion_service: Optional[AIService] = None
        self.compression_service: Optional[AIService] = None
    
    def _init_ai_services(self):
        """初始化AI服务"""
        # 润色服务
        self.polish_service = AIService(
            model=self.session_obj.polish_model or settings.POLISH_MODEL,
            api_key=self.session_obj.polish_api_key or settings.POLISH_API_KEY,
            base_url=self.session_obj.polish_base_url or settings.POLISH_BASE_URL
        )
        
        # 增强服务
        self.enhance_service = AIService(
            model=self.session_obj.enhance_model or settings.ENHANCE_MODEL,
            api_key=self.session_obj.enhance_api_key or settings.ENHANCE_API_KEY,
            base_url=self.session_obj.enhance_base_url or settings.ENHANCE_BASE_URL
        )
        
        # 感情文章润色服务
        self.emotion_service = AIService(
            model=self.session_obj.emotion_model or settings.POLISH_MODEL,
            api_key=self.session_obj.emotion_api_key or settings.POLISH_API_KEY,
            base_url=self.session_obj.emotion_base_url or settings.POLISH_BASE_URL
        )
        
        # 压缩服务
        self.compression_service = AIService(
            model=settings.COMPRESSION_MODEL,
            api_key=settings.COMPRESSION_API_KEY or settings.OPENAI_API_KEY,
            base_url=settings.COMPRESSION_BASE_URL or settings.OPENAI_BASE_URL
        )
    
    async def start_optimization(self):
        """开始优化流程"""
        try:
            # 初始化AI服务
            self._init_ai_services()

            # 重置错误状态
            self.session_obj.error_message = None
            self.session_obj.failed_segment_index = None
            await run_in_threadpool(self.db.commit)
            
            # 获取并发权限
            acquired = await concurrency_manager.acquire(self.session_obj.session_id)
            if not acquired:
                self.session_obj.status = "queued"
                await run_in_threadpool(self.db.commit)
                
                # 等待获取权限
                while not concurrency_manager.is_active(self.session_obj.session_id):
                    await asyncio.sleep(2)
            
            # 更新状态为处理中
            self.session_obj.status = "processing"
            await run_in_threadpool(self.db.commit)
            
            # 检查是否已存在段落,避免重复创建
            # 在每次循环前检查会话状态，如果被停止则中断执行
            await run_in_threadpool(self.db.refresh, self.session_obj)
            if self.session_obj.status == "stopped":
                return

            def get_existing_segments():
                return self.db.query(OptimizationSegment).filter(
                    OptimizationSegment.session_id == self.session_obj.id
                ).order_by(OptimizationSegment.segment_index).all()
            
            existing_segments = await run_in_threadpool(get_existing_segments)

            if not existing_segments:
                # 首次运行: 分割文本并创建段落记录
                segments = split_text_into_segments(self.session_obj.original_text)
                self.session_obj.total_segments = len(segments)
                await run_in_threadpool(self.db.commit)

                def create_segments():
                    for idx, segment_text in enumerate(segments):
                        segment = OptimizationSegment(
                            session_id=self.session_obj.id,
                            segment_index=idx,
                            stage="polish",
                            original_text=segment_text,
                            status="pending"
                        )
                        self.db.add(segment)
                    self.db.commit()
                
                await run_in_threadpool(create_segments)
            else:
                # 继续运行: 同步总段落数
                self.session_obj.total_segments = len(existing_segments)
                await run_in_threadpool(self.db.commit)
            
            # 根据处理模式执行不同的阶段
            processing_mode = self.session_obj.processing_mode or 'paper_polish_enhance'
            
            if processing_mode == 'paper_polish':
                # 只进行论文润色
                await self._process_stage("polish")
            elif processing_mode == 'emotion_polish':
                # 只进行感情文章润色
                await self._process_stage("emotion_polish")
            elif processing_mode == 'paper_polish_enhance':
                # 论文润色 + 论文增强
                await self._process_stage("polish")
                await self._process_stage("enhance")
            else:
                raise ValueError(f"不支持的处理模式: {processing_mode}")
            
            # 完成
            self.session_obj.status = "completed"
            self.session_obj.completed_at = datetime.utcnow()
            self.session_obj.progress = 100.0
            self.session_obj.failed_segment_index = None
            await run_in_threadpool(self.db.commit)
            
        except Exception as e:
            self.session_obj.status = "failed"
            self.session_obj.error_message = str(e)
            await run_in_threadpool(self.db.commit)
            raise
        finally:
            # 释放并发权限
            await concurrency_manager.release(self.session_obj.session_id)
    
    async def _process_stage(self, stage: str):
        """处理单个阶段"""
        self.session_obj.current_stage = stage
        await run_in_threadpool(self.db.commit)
        
        # 获取该阶段的提示词
        prompt = self._get_prompt(stage)
        
        # 获取AI服务
        if stage == "emotion_polish":
            ai_service = self.emotion_service
        elif stage == "polish":
            ai_service = self.polish_service
        else:  # enhance
            ai_service = self.enhance_service
        
        # 获取所有段落
        def get_segments():
            return self.db.query(OptimizationSegment).filter(
                OptimizationSegment.session_id == self.session_obj.id
            ).order_by(OptimizationSegment.segment_index).all()
        
        segments = await run_in_threadpool(get_segments)
        
        # 历史会话 - 只包含AI的回复内容
        history: List[Dict[str, str]] = []
        total_chars = 0

        # 先加载已完成段落的AI回复到历史上下文
        for segment in segments:
            if segment.is_title:
                # 标题段落不参与历史上下文
                continue
            if stage == "polish" and segment.polished_text:
                history.append({"role": "assistant", "content": segment.polished_text})
                total_chars += count_chinese_characters(segment.polished_text)
            elif stage == "emotion_polish" and segment.polished_text:
                history.append({"role": "assistant", "content": segment.polished_text})
                total_chars += count_chinese_characters(segment.polished_text)
            elif stage == "enhance" and segment.enhanced_text:
                history.append({"role": "assistant", "content": segment.enhanced_text})
                total_chars += count_chinese_characters(segment.enhanced_text)

        # 如果存在失败段落，跳过已完成的段落
        start_index = 0
        if self.session_obj.failed_segment_index is not None:
            start_index = max(self.session_obj.failed_segment_index, 0)
        
        skip_threshold = max(settings.SEGMENT_SKIP_THRESHOLD, 0)

        for idx, segment in enumerate(segments[start_index:], start=start_index):
            # 每次处理段落前检查会话状态
            await run_in_threadpool(self.db.refresh, self.session_obj)
            if self.session_obj.status == "stopped":
                # 释放并发权限并退出
                return

            # 更新进度（无论是否跳过都更新）
            self.session_obj.current_position = idx
            progress = ((idx + (0.5 if stage == "enhance" else 0)) / len(segments)) * 100
            self.session_obj.progress = progress
            await run_in_threadpool(self.db.commit)

            # 若段落已成功处理，直接跳过
            if stage in ["polish", "emotion_polish"] and segment.polished_text:
                continue
            if stage == "enhance" and (segment.enhanced_text or segment.is_title):
                if segment.is_title and not segment.enhanced_text:
                    segment.enhanced_text = segment.polished_text or segment.original_text
                    segment.status = "completed"
                    segment.completed_at = segment.completed_at or datetime.utcnow()
                    await run_in_threadpool(self.db.commit)
                continue

            try:
                # 标题段落或短段落直接跳过
                if count_text_length(segment.original_text) < skip_threshold:
                    segment.is_title = True
                    segment.status = "completed"
                    segment.polished_text = segment.original_text
                    segment.enhanced_text = segment.original_text
                    segment.completed_at = datetime.utcnow()
                    segment.stage = stage
                    await run_in_threadpool(self.db.commit)
                    continue

                segment.status = "processing"
                segment.stage = stage
                await run_in_threadpool(self.db.commit)
                
                # 准备输入文本
                input_text = segment.polished_text if stage == "enhance" else segment.original_text
                
                # 调用AI
                async def execute_call():
                    # 启用流式
                    use_stream = True
                    
                    if stage == "polish":
                        response = await ai_service.polish_text(input_text, prompt, history, stream=use_stream)
                    elif stage == "emotion_polish":
                        response = await ai_service.polish_emotion_text(input_text, prompt, history, stream=use_stream)
                    else:  # enhance
                        response = await ai_service.enhance_text(input_text, prompt, history, stream=use_stream)
                    
                    if use_stream:
                        full_text = ""
                        async for chunk in response:
                            if chunk:
                                full_text += chunk
                                # 推送流式更新
                                await stream_manager.broadcast(self.session_obj.session_id, {
                                    "type": "content",
                                    "segment_index": idx,
                                    "stage": stage,
                                    "content": chunk,
                                    "full_text": full_text  # 可选:发送全量或增量，这里发送增量chunk，全量用于恢复
                                })
                        return full_text
                    else:
                        return response

                output_text = await self._run_with_retry(idx, stage, execute_call)

                if stage in ["polish", "emotion_polish"]:
                    segment.polished_text = output_text
                else:  # enhance
                    segment.enhanced_text = output_text

                segment.status = "completed"
                segment.completed_at = datetime.utcnow()
                await run_in_threadpool(self.db.commit)
                
                # 记录变更
                await self._record_change(segment, input_text, output_text, stage)
                
                # 更新历史会话 - 只添加AI的回复内容
                history.append({"role": "assistant", "content": output_text})
                total_chars += count_chinese_characters(output_text)
                
                # 检查是否需要压缩历史 - 基于字符数阈值
                if total_chars > settings.HISTORY_COMPRESSION_THRESHOLD:
                    compressed_history = await self._compress_history(history, stage)
                    # 压缩后的历史替换原历史，用于后续处理
                    history = compressed_history
                    # 重新计算字符数
                    total_chars = sum(count_chinese_characters(msg.get("content", "")) for msg in history)
                
                # 保存历史
                await self._save_history(history, stage, total_chars)
                
            except Exception as e:
                segment.status = "failed"
                await run_in_threadpool(self.db.commit)
                self.session_obj.failed_segment_index = idx
                self.session_obj.error_message = str(e)
                await run_in_threadpool(self.db.commit)
                raise Exception(f"处理段落 {idx} 失败: {str(e)}")

    async def _run_with_retry(self, segment_index: int, stage: str, task):
        """执行单次任务，不自动重试"""
        try:
            return await task()
        except Exception as exc:
            raise Exception(
                f"段落 {segment_index + 1} 在 {stage} 阶段失败: {str(exc)}"
            )
    
    def _get_prompt(self, stage: str) -> str:
        """获取提示词"""
        if stage == "polish":
            return get_default_polish_prompt()
        elif stage == "emotion_polish":
            return get_emotion_polish_prompt()
        else:  # enhance
            return get_default_enhance_prompt()
    
    async def _compress_history(
        self, 
        history: List[Dict[str, str]], 
        stage: str
    ) -> List[Dict[str, str]]:
        """压缩历史会话 - 智能提取关键信息
        
        压缩历史会话以减少token使用，但保留处理风格的关键特征。
        压缩后的内容单独保存，不影响已完成的润色和增强文本。
        """
        # 如果历史已经是压缩格式（system消息），直接返回
        if len(history) == 1 and history[0].get("role") == "system":
            return history
        
        # 保留最近的2-3条消息作为风格参考
        recent_messages = history[-3:] if len(history) > 3 else history
        
        # 选择合适的压缩提示词
        if stage == "emotion_polish":
            compression_prompt = """你是一个专业的文本摘要助手。请压缩以下历史处理内容，提取关键风格特征：

1. 总结文本的表达风格和语言特点
2. 提取关键的修改方向和处理模式
3. 保留重要的词汇使用倾向
4. 删除重复的内容和冗余表述

要求：
- 压缩后内容不超过原内容的30%
- 只输出压缩后的摘要，不要添加任何解释和注释

历史处理内容："""
        else:
            compression_prompt = """你是一个专业的学术文本摘要助手。请压缩以下历史处理内容，提取关键信息：

1. 保留论文的主要术语、核心概念和关键数据
2. 总结已处理段落的主题和要点
3. 提取处理风格和改进方向的关键特征
4. 删除重复内容和冗余表述

要求：
- 压缩后内容不超过原内容的30%
- 保持学术性和专业性
- 只输出压缩后的摘要文本，不要添加任何解释和注释


历史处理内容："""

        compressed_summary = await self.compression_service.compress_history(
            recent_messages, 
            compression_prompt
        )
        
        # 返回压缩后的历史作为系统消息，用于后续段落的上下文参考
        return [
            {
                "role": "system",
                "content": f"之前处理的段落摘要：\n{compressed_summary}"
            }
        ]
    
    async def _save_history(self, history: List[Dict[str, str]], stage: str, char_count: int):
        """保存历史会话"""
        def save():
            history_obj = SessionHistory(
                session_id=self.session_obj.id,
                stage=stage,
                history_data=json.dumps(history, ensure_ascii=False),
                is_compressed=len(history) == 1 and history[0]["role"] == "system",
                character_count=char_count
            )
            self.db.add(history_obj)
            self.db.commit()
        await run_in_threadpool(save)
    
    async def _record_change(
        self,
        segment: OptimizationSegment,
        before: str,
        after: str,
        stage: str
    ):
        """记录变更"""
        # 简单的变更检测
        changes = {
            "before_length": len(before),
            "after_length": len(after),
            "changed": before != after
        }
        
        def record():
            existing_log = self.db.query(ChangeLog).filter(
                ChangeLog.session_id == self.session_obj.id,
                ChangeLog.segment_index == segment.segment_index,
                ChangeLog.stage == stage
            ).order_by(ChangeLog.created_at.desc()).first()

            serialized_detail = json.dumps(changes, ensure_ascii=False)

            if existing_log:
                # 如果之前已经生成过同一段落同一阶段的记录，直接更新内容避免重复条目
                existing_log.before_text = before
                existing_log.after_text = after
                existing_log.changes_detail = serialized_detail
            else:
                change_log = ChangeLog(
                    session_id=self.session_obj.id,
                    segment_index=segment.segment_index,
                    stage=stage,
                    before_text=before,
                    after_text=after,
                    changes_detail=serialized_detail
                )
                self.db.add(change_log)
            self.db.commit()
        
        await run_in_threadpool(record)
