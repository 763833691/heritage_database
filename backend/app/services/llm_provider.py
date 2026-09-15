"""
LLM 提供商抽象层
支持 DashScope（通义千问）、OpenAI、Mock（本地模板）
DashScope 流式使用 asyncio.Queue + 线程池，避免同步 SDK 阻塞事件循环
"""
import asyncio
import concurrent.futures
from abc import ABC, abstractmethod
from typing import List, Dict, AsyncGenerator

from ..core.config import settings

# 线程池：用于执行同步 DashScope SDK 调用
_stream_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm")


class BaseLLMProvider(ABC):
    """LLM 提供商基类"""

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """非流式对话"""
        ...

    @abstractmethod
    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """流式对话，逐 token yield"""
        ...


class DashScopeProvider(BaseLLMProvider):
    """阿里云通义千问（DashScope）"""

    def __init__(self, model: str = None, api_key: str = None):
        super().__init__(
            model=model or settings.AI_MODEL or "qwen-plus",
            api_key=api_key or settings.DASHSCOPE_API_KEY,
        )

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        loop = asyncio.get_running_loop()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    _stream_executor,
                    self._sync_chat,
                    messages,
                ),
                timeout=60.0,
            )
            return response
        except asyncio.TimeoutError:
            raise RuntimeError("DashScope 调用超时（60秒），请检查网络或 API key 是否正确")
        except ImportError:
            raise ImportError("请安装 dashscope: pip install dashscope")
        except Exception as e:
            raise RuntimeError(f"DashScope 调用失败: {str(e)}")

    def _sync_chat(self, messages: List[Dict[str, str]]) -> str:
        """同步调用 DashScope（在线程池中执行）"""
        from dashscope.aigc.generation import Generation

        response = Generation.call(
            model=self.model,
            messages=messages,
            result_format='message',
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            api_key=self.api_key,
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise RuntimeError(
                f"DashScope API 错误 [{response.status_code}]: {response.message}"
            )

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        流式对话：在线程池中运行整个同步流式循环，通过 Queue 传递 token。
        这样不会阻塞 asyncio 事件循环。
        """
        print(f"[LLM] 开始 DashScope 流式调用，模型: {self.model}")
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _run_stream():
            """在线程池中执行同步流式调用"""
            try:
                from dashscope.aigc.generation import Generation

                responses = Generation.call(
                    model=self.model,
                    messages=messages,
                    result_format='message',
                    stream=True,
                    incremental_output=True,
                    max_tokens=settings.AI_MAX_TOKENS,
                    temperature=settings.AI_TEMPERATURE,
                    api_key=self.api_key,
                )

                for event in responses:
                    if event.status_code == 200:
                        output = event.output
                        if output and output.choices:
                            content = output.choices[0].message.content
                            if content:
                                # 将 token 放入队列（线程安全）
                                loop.call_soon_threadsafe(
                                    queue.put_nowait, {"type": "token", "data": content}
                                )
                    else:
                        err_msg = f"DashScope 错误 [{event.status_code}]: {event.message}"
                        loop.call_soon_threadsafe(
                            queue.put_nowait, {"type": "error", "data": err_msg}
                        )
                        return

                # 完成信号
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "done", "data": None})

            except Exception as e:
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"type": "error", "data": str(e)}
                )

        # 在线程池中启动流式调用
        future = loop.run_in_executor(_stream_executor, _run_stream)

        # 异步消费队列中的 token
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                future.cancel()
                raise RuntimeError("DashScope 流式调用超时（60秒）")

            if item["type"] == "token":
                yield item["data"]
            elif item["type"] == "error":
                raise RuntimeError(item["data"])
            elif item["type"] == "done":
                break

        # 确保线程完成
        await future


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API（兼容 Azure、本地模型等）"""

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None):
        super().__init__(
            model=model or "gpt-3.5-turbo",
            api_key=api_key or settings.OPENAI_API_KEY,
        )
        self.base_url = base_url

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
            )
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
            )
            return response.choices[0].message.content
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
        except Exception as e:
            raise RuntimeError(f"OpenAI 调用失败: {str(e)}")

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
            )
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                max_tokens=settings.AI_MAX_TOKENS,
                temperature=settings.AI_TEMPERATURE,
            )
            chunk_count = 0
            async for chunk in stream:
                chunk_count += 1
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
            print(f"[LLM] 流式完成，共收到 {chunk_count} 个 chunk")
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
        except Exception as e:
            raise RuntimeError(f"OpenAI 流式调用失败: {str(e)}")


class MockProvider(BaseLLMProvider):
    """Mock 提供商：返回空，由 RAG 引擎的本地模板接管"""

    def __init__(self):
        super().__init__(model="mock", api_key="")

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        return ""  # 空字符串表示走本地模板

    async def chat_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        # Mock 模式下不 yield 任何 token，由 RAG 引擎的模板接管
        # Python 3.6+ 空生成器直接 return
        return
        yield  # 使函数成为生成器（实际上不会执行到这里）


def get_llm_provider() -> BaseLLMProvider:
    """
    工厂函数：根据配置返回合适的 LLM 提供商
    - dashscope + LLM_BASE_URL → 走 OpenAI 兼容接口（推荐，支持新模型）
    - dashscope 无 base_url → 走原生 DashScope SDK
    - openai → 走 OpenAI SDK
    """
    if not settings.ai_available:
        print("[LLM] 未配置 AI API key，使用本地模板模式")
        return MockProvider()

    provider_name = settings.AI_PROVIDER.lower()

    if provider_name == "dashscope" and settings.LLM_BASE_URL:
        print(f"[LLM] 使用 DashScope OpenAI 兼容接口，模型: {settings.AI_MODEL}, 地址: {settings.LLM_BASE_URL}")
        return OpenAIProvider(
            model=settings.AI_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )

    print(f"[LLM] 初始化 {provider_name} 提供商，模型: {settings.AI_MODEL}")

    if provider_name == "dashscope":
        return DashScopeProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    else:
        print(f"[LLM] 未知提供商 '{provider_name}'，回退到本地模板模式")
        return MockProvider()
