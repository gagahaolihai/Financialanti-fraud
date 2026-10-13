"""
LLM 集成客户端 - 支持 DeepSeek / OpenAI / Qwen 等多种模型
当 LLM 可用时增强对话智能，不可用时优雅降级到规则引擎
"""
import json
import logging
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)


def normalize_api_url(api_url: str) -> str:
    """
    把用户填写的地址统一成完整的 chat/completions 端点。

    历史 bug：.env.example 里给的是「基础地址」（如 https://api.deepseek.com/v1），
    而 chat_with_messages 直接把它当 POST 全地址用 → 请求必然 404。
    这里兼容两种写法，用户填哪种都能跑。
    """
    url = (api_url or "").strip().rstrip("/")
    if not url:
        return url
    # 已经是完整端点
    if url.endswith("/chat/completions"):
        return url
    # 以 /v1 结尾或含 /v1/xxx 的基础地址 → 补全
    if url.endswith("/v1") or "/compatible-mode" in url:
        return url + "/chat/completions"
    # 裸域名（如 https://api.moonshot.cn）→ 补 /v1/chat/completions
    if "://" in url and url.count("/") == 2:
        return url + "/v1/chat/completions"
    return url


class LLMClient:
    """大模型 API 客户端（流式/非流式），支持多厂商，支持运行时热切换"""

    PROVIDER_CONFIGS = {
        "deepseek": {
            "url": "https://api.deepseek.com/v1/chat/completions",
            "model": "deepseek-chat",
        },
        "openai": {
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
        },
        "qwen": {
            "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "model": "qwen-plus",
        },
        # Kimi 官方开放平台
        "moonshot": {
            "url": "https://api.moonshot.cn/v1/chat/completions",
            "model": "moonshot-v1-8k",
        },
        # 阿里云百炼（DashScope）兼容模式：同一入口可调 kimi / qwen / glm 等第三方模型
        "bailian": {
            "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "model": "qwen-plus",
        },
    }

    # 反诈专用的 System Prompt
    SYSTEM_PROMPT = """你是一个专业的反电信网络诈骗AI助手"反诈卫士"。你的职责是：

## 核心能力
1. **风险识别**：分析用户描述的情况，判断是否遇到诈骗
2. **知识普及**：用通俗易懂的语言解释各类诈骗手法
3. **劝阻干预**：对正在遭遇诈骗的用户进行紧急劝阻
4. **法律咨询**：提供反诈相关法律法规的科普

## 回答规范
- 用中文回答，语气亲切专业
- 输出结构清晰，善用分段和要点
- 对紧急情况要明确给出行动步骤
- 不确定时明确表示，不编造信息
- 可以引用知识点但不要编造法条

## 已知诈骗类型
刷单返利诈骗、游戏交易诈骗、冒充公检法诈骗、虚假投资诈骗（含杀猪盘）、校园贷诈骗

## 关键提醒
- 公检法不会通过电话办案
- 不存在"安全账户"
- 所有刷单都是诈骗
- 高收益必然伴随高风险
- 要求先交钱的贷款都是诈骗"""

    def __init__(self, provider: str = "deepseek", api_key: str = "",
                 api_url: str = "", model: str = "",
                 fallback_to_rules: bool = True):
        self.provider = provider
        self.api_key = api_key
        self.fallback_to_rules = fallback_to_rules
        self._enabled = bool(api_key)

        config = self.PROVIDER_CONFIGS.get(provider, {})
        self.api_url = normalize_api_url(api_url or config.get("url", ""))
        self.model = model or config.get("model", "deepseek-chat")

        if self._enabled:
            logger.info(f"🤖 LLM 集成已启用: provider={provider}, model={self.model}")
        else:
            logger.info("🤖 LLM 未配置（无 API Key），将使用规则引擎")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def configure(self, provider: str = None, api_key: str = None,
                  api_url: str = None, model: str = None) -> None:
        """
        运行时热切换配置（供管理后台「外部大模型接入」调用），无需重启进程。

        与 __init__ 的差异：provider 切换时，未显式传入的 api_url / model
        会跟随该 provider 的预设刷新，避免残留上一个厂商的地址。
        """
        if provider is not None:
            self.provider = provider
            preset = self.PROVIDER_CONFIGS.get(provider, {})
            if api_url is None:
                api_url = preset.get("url", self.api_url)
            if model is None:
                model = preset.get("model", self.model)

        if api_key is not None:
            self.api_key = api_key

        if api_url is not None:
            self.api_url = normalize_api_url(api_url)
        if model is not None:
            self.model = model

        self._enabled = bool(self.api_key)
        logger.info(
            f"🤖 LLM 配置已热更新: enabled={self._enabled}, "
            f"provider={self.provider}, model={self.model}, url={self.api_url}"
        )

    def test_connection(self, timeout: int = 30) -> dict:
        """
        轻量连通性测试（供管理后台「测试连通」按钮使用）。

        与 chat() 的区别：不吞异常，把失败原因原样返回给调用方展示。
        """
        if not self._enabled:
            return {"ok": False, "error": "未填写 API Key"}
        if not self.api_url:
            return {"ok": False, "error": "未填写 API 地址"}

        import time
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        started = time.time()
        try:
            req = Request(self.api_url, data=payload, headers=headers, method="POST")
            with urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            elapsed_ms = round((time.time() - started) * 1000)
            model_echo = result.get("model", self.model)
            return {
                "ok": True,
                "latency_ms": elapsed_ms,
                "model_echo": model_echo,
                "message": f"连接成功（{elapsed_ms} ms，模型回显：{model_echo}）",
            }
        except HTTPError as e:
            # 把服务端返回的错误正文读出来，否则只剩一个状态码，没法排查
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="ignore")[:300]
            except Exception:
                pass
            return {"ok": False, "error": f"HTTP {e.code}: {detail or e.reason}"}
        except URLError as e:
            return {"ok": False, "error": f"网络不可达: {e.reason}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def chat(self, user_message: str, system_prompt: str = None,
             temperature: float = 0.7, max_tokens: int = 1024) -> Optional[str]:
        """调用 LLM API 获取回复（单轮对话）"""
        messages = [
            {"role": "system", "content": system_prompt or self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        return self.chat_with_messages(messages, temperature, max_tokens)

    def chat_with_messages(self, messages: list,
                           temperature: float = 0.7, max_tokens: int = 1024) -> Optional[str]:
        """v3.0 多轮对话 — 传入完整消息列表"""
        if not self._enabled:
            return None

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            req = Request(self.api_url, data=payload, headers=headers, method="POST")
            with urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                tokens = result.get('usage', {}).get('total_tokens', 'N/A')
                logger.info(f"LLM 回复成功 (tokens: {tokens})")
                return content
        except URLError as e:
            logger.warning(f"LLM API 调用失败: {e}, 将降级到规则引擎")
            return None
        except Exception as e:
            logger.error(f"LLM 调用异常: {e}")
            return None

    def chat_stream(self, messages: list, temperature: float = 0.7,
                    max_tokens: int = 1024):
        """
        v3.0 流式输出 — 逐 token 返回
        
        Yields:
            str: 文本片段
        """
        if not self._enabled:
            yield None
            return

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            req = Request(self.api_url, data=payload, headers=headers, method="POST")
            with urlopen(req, timeout=120) as resp:
                buffer = b""
                for chunk_data in iter(lambda: resp.read(1024), b""):
                    if not chunk_data:
                        break
                    buffer += chunk_data
                    # 解析 SSE 事件
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line = line.decode("utf-8", errors="ignore").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                return
                            try:
                                data = json.loads(data_str)
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except URLError as e:
            logger.warning(f"LLM 流式调用失败: {e}")
            yield None
        except Exception as e:
            logger.error(f"LLM 流式异常: {e}")
            yield None

    def analyze_risk_with_llm(self, user_input: str, dialog_history: list = None) -> Optional[dict]:
        """使用 LLM 增强风险分析"""
        if not self._enabled:
            return None

        context = "\n".join(dialog_history[-5:]) if dialog_history else ""
        prompt = f"""分析以下用户输入是否存在诈骗风险，返回JSON格式结果：

历史对话：
{context}

用户输入：{user_input}

请分析：
1. 是否存在诈骗风险 (has_risk: true/false)
2. 风险等级 (risk_level: none/low/medium/high/critical)
3. 可能的诈骗类型 (fraud_type: 刷单返利/游戏交易/冒充公检法/虚假投资/校园贷/其他)
4. 分析理由 (reason)
5. 建议行动 (advice)

仅返回JSON对象，不要其他内容。"""

        try:
            result = self.chat(prompt, temperature=0.3, max_tokens=512)
            if result:
                # 尝试从回复中提取 JSON
                result_clean = result.strip()
                if result_clean.startswith("```"):
                    result_clean = result_clean.split("\n", 1)[-1]
                    result_clean = result_clean.rsplit("\n", 1)[0]
                if result_clean.startswith("```json"):
                    result_clean = result_clean[7:]
                    result_clean = result_clean.rsplit("```", 1)[0]
                return json.loads(result_clean)
        except Exception as e:
            logger.warning(f"LLM 风险分析解析失败: {e}")
        return None

    def enhance_response(self, rule_based_response: dict, user_input: str,
                         risk_result: dict) -> dict:
        """用 LLM 增强规则引擎的响应"""
        if not self._enabled or not rule_based_response:
            return rule_based_response

        risk_info = f"风险等级: {risk_result.get('risk_level', 'none')}"
        rules_triggered = risk_result.get("triggered_rules", [])
        if rules_triggered:
            risk_info += f"\n触发规则: {', '.join(r['rule'] for r in rules_triggered[:3])}"

        prompt = f"""用户输入：{user_input}
{risk_info}

已知响应（规则引擎生成）：
{rule_based_response.get('response', '')}

请根据以上信息，生成一个更自然、更有温度的回复。保持核心信息不变，
但使表达更亲切、更有说服力。回复要详细、耐心。"""

        enhanced = self.chat(prompt, temperature=0.7, max_tokens=1024)
        if enhanced:
            rule_based_response["response"] = enhanced
            rule_based_response["llm_enhanced"] = True
        return rule_based_response
