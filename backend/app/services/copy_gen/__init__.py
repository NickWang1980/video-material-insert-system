"""Copy Gen 服务子包。

Phase-1：
- templates.py         — 10 个文案模板 + 平台 tone + 枚举常量
- voice_config.py      — Qwen3-TTS `内容|情绪|语速` 行解析
- llm_client.py        — OpenAI 兼容客户端封装
- model_config_service — ModelConfig CRUD + Fernet 加密
- agent_service        — Agent / Rule / Knowledge CRUD + system prompt 组装
- generator_service    — quick generate / agent generate 主入口
"""
