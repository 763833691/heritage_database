"""预置模型清单。

来源：`H:\\my_code\\短剧白牌重构\\deploy\\providers.example.yaml` 中的厂商与模型条目，
仅搬运「厂商 / 端点 / 上游模型 id / 模态」，**不含任何真实密钥**。
预置项默认 ``enabled=False``，需在「模型路由」界面填入 Key 并启用后才会被任务路由使用。
"""
from __future__ import annotations

PRESET_MODELS: list[dict] = [
    # ---- 火山方舟（短剧项目实测可用）----
    {
        "alias": "volc-doubao-seed-pro",
        "display_name": "豆包 Seed 2.1 Pro（火山方舟）",
        "provider_type": "volcengine",
        "capability": "multimodal",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-2-1-pro-260628",
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "api_key_env": "VOLCENGINE_API_KEY",
        "note": "文本+图像输入，可同时承担 text.chat 与 vision.describe",
    },
    # ---- 移动云（短剧项目实测可用，OpenAI 兼容）----
    {
        "alias": "mobilecloud-qwen3-max",
        "display_name": "Qwen3.7 Max（移动云）",
        "provider_type": "mobile_cloud",
        "capability": "text",
        "base_url": "https://moma.cmecloud.cn/v1",
        "model": "qwen/qwen3.7-max",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "api_key_env": "MOBILE_CLOUD_API_KEY",
        "note": "移动云 OpenAI 兼容端点",
    },
    {
        "alias": "mobilecloud-qwen3-plus",
        "display_name": "Qwen3.6 Plus（移动云）",
        "provider_type": "mobile_cloud",
        "capability": "text",
        "base_url": "https://moma.cmecloud.cn/v1",
        "model": "qwen/qwen3.6-plus",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "api_key_env": "MOBILE_CLOUD_API_KEY",
    },
    # ---- 梧桐大模型（短剧项目聚合网关）----
    {
        "alias": "koala-wutong",
        "display_name": "梧桐大模型（聚合）",
        "provider_type": "koala",
        "capability": "text",
        "base_url": "https://api.lk888.ai",
        "model": "chat.default",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "api_key_env": "KOALA_API_KEY",
        "note": "模型目录由厂商侧同步，model 字段请按实际可用模型调整",
    },
    # ---- 直连常用端点（便于在 datak 内直接跑通文本/视觉）----
    {
        "alias": "dashscope-qwen-vl-max",
        "display_name": "通义千问 VL Max（DashScope 兼容模式）",
        "provider_type": "openai_compatible",
        "capability": "vision",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-vl-max",
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "api_key_env": "DASHSCOPE_API_KEY",
    },
    {
        "alias": "dashscope-qwen-plus",
        "display_name": "通义千问 Plus（DashScope 兼容模式）",
        "provider_type": "openai_compatible",
        "capability": "text",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "api_key_env": "DASHSCOPE_API_KEY",
    },
    {
        "alias": "deepseek-chat",
        "display_name": "DeepSeek Chat",
        "provider_type": "openai_compatible",
        "capability": "text",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "input_modalities": ["text"],
        "output_modalities": ["text"],
        "api_key_env": "OPENAI_API_KEY",
    },
    {
        "alias": "openai-gpt-4o-mini",
        "display_name": "OpenAI GPT-4o mini",
        "provider_type": "openai_compatible",
        "capability": "multimodal",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "api_key_env": "OPENAI_API_KEY",
    },
]
