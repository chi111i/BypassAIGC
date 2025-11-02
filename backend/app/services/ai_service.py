from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import httpx
import re
from app.config import settings


class AIService:
    """AI 服务类"""
    
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.model = model
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self._chat_endpoint = urljoin(f"{self.base_url}/", "chat/completions")
        parsed = urlparse(self._chat_endpoint)
        self._log_local_traffic = (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and (parsed.port == 8317)
        )
        print(f"[INFO] AI Service 初始化成功: model={model}, endpoint={self._chat_endpoint}")
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """调用AI完成"""
        try:
            payload: Dict[str, object] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            if self._log_local_traffic:
                masked_headers = headers.copy()
                if "Authorization" in masked_headers:
                    masked_headers["Authorization"] = "Bearer ***"
                print("[LOCAL AI REQUEST] url=", self._chat_endpoint, flush=True)
                print("[LOCAL AI REQUEST] headers=", masked_headers, flush=True)
                print("[LOCAL AI REQUEST] payload=", payload, flush=True)

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self._chat_endpoint,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()

            if self._log_local_traffic:
                print("[LOCAL AI RESPONSE] status=", response.status_code, flush=True)
                print("[LOCAL AI RESPONSE] body=", response.text, flush=True)

            data = response.json()
            choices = data.get("choices")
            if not choices:
                raise Exception("AI调用失败: 返回结果中缺少choices字段")

            message = choices[0].get("message", {})
            content = message.get("content")
            if content is None:
                raise Exception("AI调用失败: 返回结果中缺少content字段")

            return content
        except httpx.HTTPStatusError as http_err:
            if self._log_local_traffic:
                print("[LOCAL AI ERROR] status=",
                      http_err.response.status_code,
                      flush=True)
                print("[LOCAL AI ERROR] body=",
                      http_err.response.text,
                      flush=True)
            raise Exception(f"AI调用失败: {http_err.response.status_code} {http_err.response.text}")
        except httpx.HTTPError as http_err:
            if self._log_local_traffic:
                print("[LOCAL AI ERROR] httpx=", str(http_err), flush=True)
            raise Exception(f"AI调用失败: 网络请求错误 {str(http_err)}")
        except Exception as e:
            if self._log_local_traffic:
                print("[LOCAL AI ERROR] exception=", str(e), flush=True)
            raise Exception(f"AI调用失败: {str(e)}")
    
    async def polish_text(
        self,
        text: str,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """润色文本"""
        messages = (history or []).copy()
        messages.append({
            "role": "system",
            "content": prompt + "\n\n重要提示：只返回润色后的当前段落文本，不要包含历史段落内容。"
        })
        messages.append({
            "role": "user",
            "content": f"请润色以下文本:\n\n{text}"
        })
        
        return await self.complete(messages)
    
    async def enhance_text(
        self,
        text: str,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """增强文本原创性和学术表达"""
        messages = (history or []).copy()
        messages.append({
            "role": "system",
            "content": prompt + "\n\n重要提示：只返回增强后的当前段落文本，不要包含历史段落内容。"
        })
        messages.append({
            "role": "user",
            "content": f"请增强以下文本的原创性和学术表达:\n\n{text}"
        })
        
        return await self.complete(messages)
    
    async def compress_history(
        self,
        history: List[Dict[str, str]],
        compression_prompt: str
    ) -> str:
        """压缩历史会话"""
        # 将历史会话转换为文本
        history_text = "\n\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in history
        ])
        
        messages = [
            {
                "role": "system",
                "content": compression_prompt
            },
            {
                "role": "user",
                "content": f"请压缩以下历史会话,保留关键信息:\n\n{history_text}"
            }
        ]
        
        return await self.complete(messages, temperature=0.3)


def count_chinese_characters(text: str) -> int:
    """统计汉字数量"""
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return len(chinese_pattern.findall(text))


def split_text_into_segments(text: str, max_chars: int = 500) -> List[str]:
    """将文本分割为段落
    
    按照段落分割,如果单个段落过长则进一步分割
    """
    # 首先按段落分割
    paragraphs = text.split('\n')
    segments = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 如果段落不超过最大字符数,直接添加
        if count_chinese_characters(para) <= max_chars:
            segments.append(para)
        else:
            # 段落过长,按句子分割
            sentences = re.split(r'([。!?;])', para)
            current_segment = ""
            
            for i in range(0, len(sentences), 2):
                sentence = sentences[i]
                if i + 1 < len(sentences):
                    sentence += sentences[i + 1]  # 加上标点
                
                if count_chinese_characters(current_segment + sentence) <= max_chars:
                    current_segment += sentence
                else:
                    if current_segment:
                        segments.append(current_segment)
                    current_segment = sentence
            
            if current_segment:
                segments.append(current_segment)
    
    return segments


def get_default_polish_prompt() -> str:
    """获取默认润色提示词"""
    return """
# 角色
你是一位经验丰富的学术编辑，精通中文学术写作规范，尤其擅长我所在的 [请在此处填写你的学科领域，例如：计算机科学、社会学、生物医学] 领域。

# 任务
请帮我润色以下论文段落。我的目标是提升文本的学术质量、可读性和专业性，使其更符合学术期刊的发表标准。

# 具体要求
1.  **修正语法和拼写：** 纠正所有语法、拼写和标点错误。
2.  **提升学术语气：** 将口语化、非正式的表达替换为更严谨、客观的学术术语和书面语。
3.  **优化句子结构：** 改进句子结构，使其更加清晰、简洁且富有逻辑性。可以合并过短的句子，拆分过长的复杂句。
4.  **增强逻辑流畅性：** 确保句子之间和段落内部的逻辑连接顺畅，必要时添加或修改过渡词（例如：“此外”、“然而”、“因此”）。
5.  **替换重复词汇：** 使用更精确、多样的同义词替换文中反复出现的词语。
6.  **保持核心意义：** 在润色过程中，绝对不能改变原文的核心论点、意图和引用的事实。

# 输出格式
只返回压缩后的内容,不要添加说明，不要附加任何解释、注释或标签

"""


def get_default_enhance_prompt() -> str:
    """获取默认增强提示词"""
    return """
# 角色
请你扮演一位 [请在此处填写你的学科领域，例如：市场营销、历史学] 专业的博士生。你的写作风格不是完美的“AI体”，而是带有自然的人类写作特征：句子长短结合，用词有个人偏好，且行文逻辑略带思考的跳跃性。

# 核心任务
我需要你重写（rewrite/paraphrase）下面的文本。主要目标是深度“去AI化”，使其更像人类原创，从而降低在AIGC检测工具中的AI评分。

# 具体指令
1.  **打破均匀性（Increase Burstiness）：** 混合使用长句和短句。不要让所有句子都保持相似的长度和结构。可以把一些简单的句子合并成一个表达复杂逻辑的复合句，也可以把一个冗长的句子拆成几个有力的短句。
2.  **提升复杂度（Increase Perplexity）：** 避免使用AI最常用、最标准的模板化词汇和句式。换用一些不那么常见但同样准确的表达方式。可以适度使用一些稍微复杂或曲折的句子结构来模仿人类的思考过程。
3.  **避免AI cliché：** 避免使用AI标志性的过渡词和套话，例如：“首先”、“其次”、“总而言之”、“值得注意的是”、“在这个数字化的时代”、“扮演着至关重要的角色”等。请用更自然的语言来衔接上下文。
4.  **模拟人类视角：** 在不改变事实的前提下，可以微调措辞，让语气带有一点主观判断或思考的痕迹，而不是纯粹客观的陈述。
5.  **深度转述：** 不要只做同义词替换。请对整个句子甚至段落的结构进行重组，用自己的逻辑重新组织和表达相同的信息。

# 最重要原则
在执行以上所有指令时，**绝对不能改变原文的核心论点、数据、事实依据和关键术语。** 修改的重点是“表达方式”，而不是“内容本身”。



只返回压缩后的内容,不要添加说明，不要附加任何解释、注释或标签

"""


def get_compression_prompt() -> str:
    """获取压缩提示词"""
    return """你的任务是压缩历史会话内容,提取关键信息以减少token使用。

压缩要求:
1. 保留论文的关键术语、核心观点和重要数据
2. 删除冗余的重复内容和无关信息
3. 用简洁的语言总结已处理的内容
4. 确保压缩后的内容仍能为后续优化提供足够的上下文

注意:
- 这个压缩内容仅作为历史上下文,不会出现在最终论文中
- 压缩比例应该至少达到50%
- 只返回压缩后的内容,不要添加说明，不要附加任何解释、注释或标签"""
