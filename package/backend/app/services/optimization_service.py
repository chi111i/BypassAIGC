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

# 错误信息最大长度，避免数据库字段溢出
MAX_ERROR_MESSAGE_LENGTH = 500


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
        """初始化AI服务
        
        改进的初始化逻辑：
        1. 验证必需的配置项
        2. 提供更详细的错误信息
        3. 确保所有服务都正确初始化
        """
        try:
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
            
            print(f"[INFO] 所有 AI 服务初始化成功，会话: {self.session_obj.session_id}")
            
        except Exception as e:
            error_msg = f"AI 服务初始化失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
    
    async def start_optimization(self):
        """开始优化流程"""
        try:
            # 初始化AI服务
            self._init_ai_services()

            # 重置错误状态
            self.session_obj.error_message = None
            self.session_obj.failed_segment_index = None
            self.db.commit()
            
            # 获取并发权限
            acquired = await concurrency_manager.acquire(self.session_obj.session_id)
            if not acquired:
                self.session_obj.status = "queued"
                self.db.commit()
                
                # 等待获取权限 - acquire 方法内部已包含等待逻辑
                acquired = await concurrency_manager.acquire(self.session_obj.session_id)
                if not acquired:
                    raise Exception("等待并发权限超时")
            
            # 更新状态为处理中
            self.session_obj.status = "processing"
            self.db.commit()
            
            # 检查是否已存在段落,避免重复创建
            # 在每次循环前检查会话状态，如果被停止则中断执行
            self.db.refresh(self.session_obj)
            if self.session_obj.status == "stopped":
                raise Exception("会话已被用户停止")

            existing_segments = self.db.query(OptimizationSegment).filter(
                OptimizationSegment.session_id == self.session_obj.id
            ).order_by(OptimizationSegment.segment_index).all()

            if not existing_segments:
                # 首次运行: 分割文本并创建段落记录
                segments = split_text_into_segments(self.session_obj.original_text)
                self.session_obj.total_segments = len(segments)
                self.db.commit()

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
            else:
                # 继续运行: 同步总段落数
                self.session_obj.total_segments = len(existing_segments)
                self.db.commit()
            
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
            self.db.commit()
            
        except Exception as e:
            self.session_obj.status = "failed"
            # 安全地截断错误信息
            error_msg = str(e)
            if len(error_msg) > MAX_ERROR_MESSAGE_LENGTH:
                error_msg = error_msg[:MAX_ERROR_MESSAGE_LENGTH - 50] + "... [错误信息已截断]"
            self.session_obj.error_message = error_msg
            self.db.commit()
            raise
        finally:
            # 释放并发权限
            await concurrency_manager.release(self.session_obj.session_id)
            # 清理 AI 服务资源
            self._cleanup_ai_services()
    
    def _cleanup_ai_services(self):
        """清理 AI 服务资源"""
        # 将服务引用设置为 None，让 Python 的垃圾回收处理
        # AsyncOpenAI 客户端会自动清理连接
        self.polish_service = None
        self.enhance_service = None
        self.emotion_service = None
        self.compression_service = None
    
    async def _process_stage(self, stage: str):
        """处理单个阶段"""
        print(f"\n[STAGE START] Stage: {stage}, Session: {self.session_obj.session_id}", flush=True)
        
        self.session_obj.current_stage = stage
        self.db.commit()
        
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
        segments = self.db.query(OptimizationSegment).filter(
            OptimizationSegment.session_id == self.session_obj.id
        ).order_by(OptimizationSegment.segment_index).all()
        
        # 如果存在失败段落，跳过已完成的段落
        start_index = 0
        if self.session_obj.failed_segment_index is not None:
            start_index = max(self.session_obj.failed_segment_index, 0)
        
        # 历史会话 - 只包含AI的回复内容
        # 只加载 start_index 之前的段落到历史，避免重试时历史与当前处理位置不一致
        history: List[Dict[str, str]] = []
        total_chars = 0

        for segment in segments[:start_index]:
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
        
        print(f"[STAGE] Loaded {len(history)} history messages from segments[:start_index={start_index}]", flush=True)
        
        skip_threshold = max(settings.SEGMENT_SKIP_THRESHOLD, 0)

        # 获取处理模式，用于正确计算进度
        processing_mode = self.session_obj.processing_mode or 'paper_polish_enhance'

        for idx, segment in enumerate(segments[start_index:], start=start_index):
            # 每次处理段落前检查会话状态
            self.db.refresh(self.session_obj)
            if self.session_obj.status == "stopped":
                raise Exception("会话已被用户停止")

            # 更新进度（无论是否跳过都更新）
            self.session_obj.current_position = idx
            # 根据处理模式正确计算进度
            if processing_mode == 'paper_polish_enhance':
                if stage == "polish":
                    # 第一阶段占 0-50%
                    progress = (idx / len(segments)) * 50
                else:  # enhance
                    # 第二阶段占 50-100%
                    progress = 50 + (idx / len(segments)) * 50
            else:
                # 其他模式占 0-100%
                progress = (idx / len(segments)) * 100
            self.session_obj.progress = min(progress, 100.0)
            self.db.commit()

            # 先判断标题和短段落（提前到这里）
            if count_text_length(segment.original_text) < skip_threshold:
                if not segment.is_title:
                    segment.is_title = True
                    segment.status = "completed"
                    segment.polished_text = segment.original_text
                    segment.enhanced_text = segment.original_text
                    segment.completed_at = datetime.utcnow()
                    segment.stage = stage
                    self.db.commit()
                continue

            # 然后检查是否已处理
            if stage in ["polish", "emotion_polish"] and segment.polished_text:
                continue
            if stage == "enhance":
                if segment.enhanced_text:
                    continue
                if segment.is_title and not segment.enhanced_text:
                    segment.enhanced_text = segment.polished_text or segment.original_text
                    segment.status = "completed"
                    segment.completed_at = segment.completed_at or datetime.utcnow()
                    self.db.commit()
                    continue

            try:

                print(f"\n[SEGMENT {idx}] Processing segment {idx+1}/{len(segments)}, Stage: {stage}", flush=True)
                print(f"[SEGMENT {idx}] Input Length: {count_text_length(segment.original_text)}", flush=True)
                
                segment.status = "processing"
                segment.stage = stage
                self.db.commit()
                
                # 准备输入文本
                input_text = segment.polished_text if stage == "enhance" else segment.original_text
                
                # 调用AI
                async def execute_call():
                    # 使用配置中的流式设置，默认非流式（False）以避免API阻止
                    use_stream = settings.USE_STREAMING
                    
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
                self.db.commit()
                
                # 记录变更
                await self._record_change(segment, input_text, output_text, stage)
                
                # 更新历史会话 - 只添加AI的回复内容
                history.append({"role": "assistant", "content": output_text})
                total_chars += count_chinese_characters(output_text)
                
                # 检查是否需要压缩历史 - 基于字符数阈值
                if total_chars > settings.HISTORY_COMPRESSION_THRESHOLD:
                    print(f"\n[HISTORY COMPRESS] Triggering compression, Stage: {stage}", flush=True)
                    print(f"[HISTORY COMPRESS] Before: {total_chars} chars, {len(history)} messages", flush=True)
                    
                    compressed_history = await self._compress_history(history, stage)
                    # 压缩后的历史替换原历史，用于后续处理
                    history = compressed_history
                    # 重新计算字符数
                    total_chars = sum(count_chinese_characters(msg.get("content", "")) for msg in history)
                    
                    print(f"[HISTORY COMPRESS] After: {total_chars} chars, {len(history)} messages", flush=True)
                    
                    # 推送压缩通知给前端
                    await stream_manager.broadcast(self.session_obj.session_id, {
                        "type": "history_compressed",
                        "stage": stage,
                        "message": f"历史会话已压缩（{stage} 阶段），节省上下文空间",
                        "new_char_count": total_chars
                    })
                    
                    # 只在压缩后保存历史，减少数据库写入
                    await self._save_history(history, stage, total_chars)
                
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"[ERROR] Segment {idx} processing failed:", flush=True)
                print(error_trace, flush=True)
                
                segment.status = "failed"
                self.session_obj.failed_segment_index = idx
                
                # 安全地截断错误信息，避免数据库字段溢出
                error_msg = str(e)
                if len(error_msg) > MAX_ERROR_MESSAGE_LENGTH:
                    # 保留前面的主要错误信息和末尾的部分
                    prefix_len = MAX_ERROR_MESSAGE_LENGTH - 50
                    error_msg = error_msg[:prefix_len] + "... [错误信息已截断]"
                
                self.session_obj.error_message = error_msg
                self.db.commit()
                
                # 直接抛出原异常，保留堆栈
                raise

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
        
        如果压缩失败，返回最近的几条消息而不是抛出异常。
        """
        try:
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
            
        except Exception as e:
            # 压缩失败时，不抛出异常，而是返回最近的几条消息
            print(f"[WARNING] 历史压缩失败: {str(e)}, 将使用最近的消息代替", flush=True)
            # 返回最近的2条消息，避免上下文过长
            return history[-2:] if len(history) > 2 else history
    
    async def _save_history(self, history: List[Dict[str, str]], stage: str, char_count: int):
        """保存历史会话 - 只在压缩后保存
        
        只有压缩后的历史才保存到数据库，以避免频繁写入导致数据库膨胀。
        压缩后的内容单独保存，不影响已完成的润色和增强文本。
        
        注意：未压缩的历史不会保存，因为：
        1. 润色/增强后的文本已经保存在 segments 表中
        2. 压缩只在字符数超过阈值时触发
        3. 压缩后的历史用于后续段落的上下文参考
        """
        # 检测是否为压缩后的历史：压缩后只有一条 system 消息，包含之前处理的摘要
        # 这种检测方式与 _compress_history 的返回格式保持一致
        is_compressed = len(history) == 1 and history[0].get("role") == "system"
        
        if not is_compressed:
            return  # 非压缩状态不保存，减少数据库写入
        
        # 检查是否已存在该阶段的压缩记录
        existing = self.db.query(SessionHistory).filter(
            SessionHistory.session_id == self.session_obj.id,
            SessionHistory.stage == stage,
            SessionHistory.is_compressed.is_(True)
        ).first()
        
        if existing:
            # 更新现有记录
            existing.history_data = json.dumps(history, ensure_ascii=False)
            existing.character_count = char_count
            existing.created_at = datetime.utcnow()
        else:
            # 创建新记录
            history_obj = SessionHistory(
                session_id=self.session_obj.id,
                stage=stage,
                history_data=json.dumps(history, ensure_ascii=False),
                is_compressed=True,
                character_count=char_count
            )
            self.db.add(history_obj)
        
        self.db.commit()
    
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
